package main

import (
	"encoding/json"
	"strings"

	"github.com/valyala/fasthttp"
)

type assistReq struct {
	Action      string   `json:"action"`
	Text        string   `json:"text"`
	Instruction string   `json:"instruction"`
	Title       string   `json:"title"`
	Context     []string `json:"context"`
	Audience    string   `json:"audience"`
	Model       string   `json:"model"`
}

var assistPrompts = map[string]string{
	"rewrite":  "Rewrite this page so it flows better and is more vivid, keeping the same events.",
	"simplify": "Rewrite this page with simpler words and shorter sentences for an early reader.",
	"expand":   "Expand this page with a little more sensory detail and feeling (still 2-4 short sentences).",
	"shorten":  "Shorten this page to 1-2 punchy sentences.",
	"rhyme":    "Rewrite this page as gentle rhyming verse.",
	"next":     "Write the next page of the story that follows from the context.",
	"prompt":   "Write one concrete, vivid illustration prompt (max 40 words) for this page, keeping the characters and art style consistent with the story. Output only the prompt.",
}

func (s *Server) handleAssist(ctx *fasthttp.RequestCtx) {
	u := s.user(ctx)
	if u == nil {
		apiError(ctx, fasthttp.StatusUnauthorized, "sign in to use the writing assistant")
		return
	}
	var req assistReq
	if err := json.Unmarshal(ctx.PostBody(), &req); err != nil {
		apiError(ctx, fasthttp.StatusBadRequest, "invalid request")
		return
	}
	task, ok := assistPrompts[req.Action]
	if !ok && strings.TrimSpace(req.Instruction) == "" {
		apiError(ctx, fasthttp.StatusBadRequest, "unknown action")
		return
	}
	if strings.TrimSpace(req.Instruction) != "" {
		task = "Edit this page as instructed: " + strings.TrimSpace(req.Instruction)
	}
	if req.Model == "" || req.Model == "auto" {
		req.Model = unlimitedModel
	}
	if req.Audience == "" {
		req.Audience = "ages 4-8"
	}
	if len(req.Text) > 4000 {
		req.Text = req.Text[:4000]
	}
	ctxText := strings.Join(req.Context, "\n")
	if len(ctxText) > 6000 {
		ctxText = ctxText[len(ctxText)-6000:]
	}
	sys := "You are a children's picture-book editor writing for " + req.Audience +
		". Output ONLY the resulting text — no quotes, labels or commentary."
	user := "Story title: " + req.Title + "\nStory so far:\n" + ctxText + "\n\nCurrent page:\n" + req.Text + "\n\nTask: " + task
	tok, ok := s.aiAuth(ctx, u, req.Model, unlimitedModel, "text", dailyTextCap)
	if !ok {
		return
	}
	out, err := s.gw.chatComplete(tok, req.Model, []chatMessage{
		{Role: "system", Content: sys}, {Role: "user", Content: user},
	}, 800)
	if err != nil {
		s.aiError(ctx, err)
		return
	}
	writeJSON(ctx, 200, map[string]any{"text": strings.Trim(strings.TrimSpace(out), "\"")})
}

func (s *Server) handleGetStory(ctx *fasthttp.RequestCtx) {
	u := s.user(ctx)
	if u == nil {
		apiError(ctx, fasthttp.StatusUnauthorized, "sign in")
		return
	}
	st, err := s.stories.get(string(ctx.QueryArgs().Peek("id")))
	if err != nil || st == nil || st.UserID != u.ID {
		apiError(ctx, fasthttp.StatusNotFound, "story not found")
		return
	}
	pages := make([]map[string]any, 0, len(st.Pages))
	for _, p := range st.Pages {
		pages = append(pages, map[string]any{"text": p.Text, "image_url": p.ImageURL, "image_prompt": p.ImagePrompt})
	}
	writeJSON(ctx, 200, map[string]any{
		"id": st.ID, "title": st.Title, "prompt": st.Prompt, "public": st.Public,
		"text_model": st.TextModel, "image_model": st.ImageModel, "pages": pages,
	})
}

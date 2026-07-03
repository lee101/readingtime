package main

import (
	"encoding/base64"
	"encoding/json"
	"os"
	"path/filepath"
	"strings"

	"github.com/valyala/fasthttp"
)

// ---------- helpers ----------

func (s *Server) user(ctx *fasthttp.RequestCtx) *User {
	if s.auth == nil {
		return nil
	}
	return s.auth.userFromRequest(ctx)
}

func writeJSON(ctx *fasthttp.RequestCtx, status int, v any) {
	ctx.SetStatusCode(status)
	ctx.SetContentType("application/json; charset=utf-8")
	_ = json.NewEncoder(ctx).Encode(v)
}

func apiError(ctx *fasthttp.RequestCtx, status int, msg string) {
	writeJSON(ctx, status, map[string]any{"error": msg})
}

// loginURL returns the app.nz login URL that returns the user back here.
func (s *Server) loginURL(returnTo string) string {
	if returnTo == "" {
		returnTo = s.cfg.SiteBaseURL + "/"
	}
	sep := "?"
	if strings.Contains(s.cfg.LoginURL, "?") {
		sep = "&"
	}
	// app.nz's login page reads `next` to return the user after sign-in.
	return s.cfg.LoginURL + sep + "next=" + url(returnTo)
}

func url(s string) string {
	r := strings.NewReplacer(":", "%3A", "/", "%2F", "?", "%3F", "&", "%26", "=", "%3D", " ", "%20")
	return r.Replace(s)
}

// returnTo resolves a post-auth landing URL on readingtime from an untrusted
// `next` value, refusing to redirect off-site (the value rides through the
// app.nz login round-trip, so we keep it scoped to our own origin).
func (s *Server) returnTo(next string) string {
	next = strings.TrimSpace(next)
	switch {
	case next == "":
		return s.cfg.SiteBaseURL + "/"
	case strings.HasPrefix(next, "/") && !strings.HasPrefix(next, "//"):
		return s.cfg.SiteBaseURL + next
	case strings.HasPrefix(next, s.cfg.SiteBaseURL):
		return next
	default:
		return s.cfg.SiteBaseURL + "/"
	}
}

// handleLogin is readingtime's first-party entry point to app.nz SSO. Visiting
// /login (or /login?next=/author) bounces to the shared app.nz sign-in, which
// sets the `.app.nz` session cookie and returns the user here already signed in.
func (s *Server) handleLogin(ctx *fasthttp.RequestCtx) {
	// Already signed in? Skip the round-trip.
	if s.user(ctx) != nil {
		ctx.Redirect(s.returnTo(string(ctx.QueryArgs().Peek("next"))), fasthttp.StatusFound)
		return
	}
	dest := s.loginURL(s.returnTo(string(ctx.QueryArgs().Peek("next"))))
	ctx.Redirect(dest, fasthttp.StatusFound)
}

// handleLogout signs the user out network-wide: it asks app.nz to delete the
// server-side session, then expires the shared `.app.nz` cookie in the browser
// so readingtime (and every other app.nz subdomain) sees them as signed out.
// GET redirects home (nav link); POST returns JSON (fetch).
func (s *Server) handleLogout(ctx *fasthttp.RequestCtx) {
	if tok := sessionToken(ctx); tok != "" {
		if err := s.gw.logout(tok); err != nil && s.cfg.Debug {
			// Non-fatal: we still clear the cookie below.
			ctx.Logger().Printf("logout proxy failed: %v", err)
		}
	}
	s.expireSharedCookie(ctx)
	if string(ctx.Method()) == "POST" {
		writeJSON(ctx, 200, map[string]any{"ok": true})
		return
	}
	ctx.Redirect(s.returnTo(string(ctx.QueryArgs().Peek("next"))), fasthttp.StatusFound)
}

// expireSharedCookie clears the `.app.nz`-scoped session cookie. readingtime is
// a subdomain of the cookie's domain, so it is allowed to expire it; this is
// what makes the local sign-out take effect immediately.
func (s *Server) expireSharedCookie(ctx *fasthttp.RequestCtx) {
	c := fasthttp.AcquireCookie()
	defer fasthttp.ReleaseCookie(c)
	c.SetKey(sharedSessionCookie)
	c.SetValue("")
	c.SetPath("/")
	c.SetHTTPOnly(true)
	c.SetSecure(true)
	c.SetSameSite(fasthttp.CookieSameSiteLaxMode)
	if s.cfg.CookieDomain != "" {
		c.SetDomain(s.cfg.CookieDomain)
	}
	c.SetMaxAge(-1)
	ctx.Response.Header.SetCookie(c)
}

// ---------- pages ----------

type cardView struct {
	Title, Cover, Href, Author string
}

type homeView struct {
	User          *User
	Cfg           Config
	LoginURL      string
	Samples       []cardView
	MyStories     []cardView
	PublicStories []cardView
}

func (s *Server) handleHome(ctx *fasthttp.RequestCtx) {
	u := s.user(ctx)
	v := homeView{User: u, Cfg: s.cfg, LoginURL: s.loginURL(s.cfg.SiteBaseURL + "/")}
	for _, name := range s.bookOrder {
		b := s.books[name]
		v.Samples = append(v.Samples, cardView{
			Title: b.Title,
			Cover: "/static/kids-book-covers/" + b.CoverImageURL,
			Href:  "/book/" + name,
		})
	}
	if pub, err := s.stories.listPublic(24); err == nil {
		for _, st := range pub {
			v.PublicStories = append(v.PublicStories, storyCard(st))
		}
	}
	if u != nil {
		if mine, err := s.stories.listByUser(u.ID, 48); err == nil {
			for _, st := range mine {
				v.MyStories = append(v.MyStories, storyCard(st))
			}
		}
	}
	s.render(ctx, "home.html", v)
}

func storyCard(st *Story) cardView {
	cover := st.CoverURL
	if cover == "" {
		for _, p := range st.Pages {
			if p.ImageURL != "" {
				cover = p.ImageURL
				break
			}
		}
	}
	return cardView{Title: st.Title, Cover: cover, Href: "/story/" + st.ID, Author: st.AuthorName}
}

func (s *Server) handleAuthor(ctx *fasthttp.RequestCtx) {
	u := s.user(ctx)
	s.render(ctx, "author.html", map[string]any{
		"User":     u,
		"Cfg":      s.cfg,
		"LoginURL": s.loginURL(s.cfg.SiteBaseURL + "/author"),
	})
}

func (s *Server) handleBook(ctx *fasthttp.RequestCtx, name string) {
	name = strings.Trim(name, "/")
	b, ok := s.books[name]
	if !ok {
		s.handleNotFound(ctx)
		return
	}
	view := ReaderView{
		Title: b.Title, AudioLink: b.AudioLink, SubsLink: b.SubsLink,
		User: s.user(ctx), Cfg: s.cfg, LoginURL: s.loginURL(s.cfg.SiteBaseURL + "/"), BackHref: "/",
	}
	counter := 0
	for i, p := range b.Pages {
		var html, next = renderPage(p.Words, i, counter)
		counter = next
		img := p.ImageURL
		if img == "" && p.ImagePath != "" {
			img = "/static/bookdata/" + name + "/" + p.ImagePath
		}
		view.Pages = append(view.Pages, PageView{
			HTML: html, Image: img, Layout: p.Layout, DarkColor: p.DarkColor,
			CSS: cssSafe(p.CSS),
		})
	}
	s.render(ctx, "reader.html", view)
}

func (s *Server) handleStoryReader(ctx *fasthttp.RequestCtx, id string) {
	id = strings.Trim(id, "/")
	st, err := s.stories.get(id)
	if err != nil || st == nil {
		s.handleNotFound(ctx)
		return
	}
	u := s.user(ctx)
	if !st.Public && (u == nil || u.ID != st.UserID) {
		apiError(ctx, fasthttp.StatusForbidden, "this story is private")
		return
	}
	view := ReaderView{Title: st.Title, User: u, Cfg: s.cfg, LoginURL: s.loginURL(s.cfg.SiteBaseURL + "/"), BackHref: "/"}
	counter := 0
	for i, p := range st.Pages {
		words := p.Words
		if len(words) == 0 {
			words = splitWordsKeepSep(p.Text)
		}
		html, next := renderPage(words, i, counter)
		counter = next
		view.Pages = append(view.Pages, PageView{HTML: html, Image: p.ImageURL})
	}
	s.render(ctx, "reader.html", view)
}

func (s *Server) handleNotFound(ctx *fasthttp.RequestCtx) {
	ctx.SetStatusCode(fasthttp.StatusNotFound)
	s.render(ctx, "404.html", map[string]any{"Cfg": s.cfg, "User": s.user(ctx), "LoginURL": s.loginURL(s.cfg.SiteBaseURL + "/")})
}

// ---------- JSON API ----------

func (s *Server) handleMe(ctx *fasthttp.RequestCtx) {
	u := s.user(ctx)
	if u == nil {
		writeJSON(ctx, 200, map[string]any{"signedIn": false, "loginUrl": s.loginURL(s.cfg.SiteBaseURL + "/author")})
		return
	}
	writeJSON(ctx, 200, map[string]any{
		"signedIn":   true,
		"name":       u.DisplayName(),
		"email":      u.Email,
		"credits":    u.Credits(),
		"accountUrl": s.cfg.AccountURL,
	})
}

func (s *Server) handleModels(ctx *fasthttp.RequestCtx) {
	text, image, err := s.gw.listModels(sessionToken(ctx))
	if err != nil {
		// Fall back to curated defaults so the picker still works offline.
		writeJSON(ctx, 200, map[string]any{
			"text": preferredTextModels, "image": preferredImageModels, "degraded": true,
		})
		return
	}
	writeJSON(ctx, 200, map[string]any{"text": text, "image": image})
}

type generateReq struct {
	Prompt   string `json:"prompt"`
	Model    string `json:"model"`
	Pages    int    `json:"pages"`
	Audience string `json:"audience"`
}

type genPage struct {
	Text        string `json:"text"`
	ImagePrompt string `json:"image_prompt"`
}

type genResult struct {
	Title string    `json:"title"`
	Pages []genPage `json:"pages"`
}

func (s *Server) handleGenerate(ctx *fasthttp.RequestCtx) {
	u := s.user(ctx)
	if u == nil {
		apiError(ctx, fasthttp.StatusUnauthorized, "sign in with your app.nz account to generate stories")
		return
	}
	var req generateReq
	if err := json.Unmarshal(ctx.PostBody(), &req); err != nil {
		apiError(ctx, fasthttp.StatusBadRequest, "invalid request")
		return
	}
	req.Prompt = strings.TrimSpace(req.Prompt)
	if req.Prompt == "" {
		apiError(ctx, fasthttp.StatusBadRequest, "please describe the story you want")
		return
	}
	if req.Pages < 3 {
		req.Pages = 6
	}
	if req.Pages > 16 {
		req.Pages = 16
	}
	if req.Model == "" {
		req.Model = "auto"
	}
	if req.Audience == "" {
		req.Audience = "ages 4-8"
	}

	sys := "You are a master children's picture-book author. Write warm, vivid, age-appropriate " +
		"stories with simple, rhythmic sentences a child can follow word-by-word. Respond ONLY with " +
		"minified JSON, no markdown fences, of the exact shape: " +
		`{"title":"string","pages":[{"text":"1-3 short sentences","image_prompt":"a concrete, vivid illustration description in a consistent art style"}]}.`
	user := "Write a " + itoa(req.Pages) + "-page picture book for " + req.Audience + ".\n" +
		"Story idea: " + req.Prompt + "\n" +
		"Keep each page's text short (1-3 sentences). Make image_prompt for every page describe the same " +
		"characters and a consistent, beautiful illustration style so the pictures feel like one book."

	out, err := s.gw.chatComplete(sessionToken(ctx), req.Model, []chatMessage{
		{Role: "system", Content: sys},
		{Role: "user", Content: user},
	}, 4000)
	if err != nil {
		s.aiError(ctx, err)
		return
	}
	result, err := parseStoryJSON(out)
	if err != nil {
		apiError(ctx, fasthttp.StatusBadGateway, "the model returned an unexpected format — try again or pick another model")
		return
	}
	writeJSON(ctx, 200, result)
}

type illustrateReq struct {
	Prompt string `json:"prompt"`
	Model  string `json:"model"`
	Style  string `json:"style"`
	Size   string `json:"size"`
}

func (s *Server) handleIllustrate(ctx *fasthttp.RequestCtx) {
	u := s.user(ctx)
	if u == nil {
		apiError(ctx, fasthttp.StatusUnauthorized, "sign in to illustrate pages")
		return
	}
	var req illustrateReq
	if err := json.Unmarshal(ctx.PostBody(), &req); err != nil {
		apiError(ctx, fasthttp.StatusBadRequest, "invalid request")
		return
	}
	prompt := strings.TrimSpace(req.Prompt)
	if prompt == "" {
		apiError(ctx, fasthttp.StatusBadRequest, "missing image prompt")
		return
	}
	if req.Style != "" {
		prompt = prompt + ", " + req.Style
	}
	if req.Model == "" {
		req.Model = "openpaths/auto-image"
	}
	imgURL, b64, err := s.gw.generateImage(sessionToken(ctx), req.Model, prompt, req.Size)
	if err != nil {
		s.aiError(ctx, err)
		return
	}
	if imgURL == "" && b64 != "" {
		imgURL, err = s.saveGeneratedImage(u.ID, b64)
		if err != nil {
			apiError(ctx, fasthttp.StatusInternalServerError, "could not store generated image")
			return
		}
	}
	writeJSON(ctx, 200, map[string]any{"url": imgURL})
}

type savePageReq struct {
	Text     string `json:"text"`
	ImageURL string `json:"image_url"`
}

type saveStoryReq struct {
	ID         string        `json:"id"`
	Title      string        `json:"title"`
	Prompt     string        `json:"prompt"`
	TextModel  string        `json:"text_model"`
	ImageModel string        `json:"image_model"`
	Public     bool          `json:"public"`
	Pages      []savePageReq `json:"pages"`
}

func (s *Server) handleSaveStory(ctx *fasthttp.RequestCtx) {
	u := s.user(ctx)
	if u == nil {
		apiError(ctx, fasthttp.StatusUnauthorized, "sign in to save stories")
		return
	}
	var req saveStoryReq
	if err := json.Unmarshal(ctx.PostBody(), &req); err != nil {
		apiError(ctx, fasthttp.StatusBadRequest, "invalid request")
		return
	}
	if strings.TrimSpace(req.Title) == "" {
		req.Title = "Untitled Story"
	}
	if len(req.Pages) == 0 {
		apiError(ctx, fasthttp.StatusBadRequest, "a story needs at least one page")
		return
	}
	st := &Story{
		ID: req.ID, UserID: u.ID, AuthorName: u.DisplayName(),
		Title: strings.TrimSpace(req.Title), Prompt: req.Prompt,
		TextModel: req.TextModel, ImageModel: req.ImageModel, Public: req.Public,
	}
	if st.ID == "" {
		st.ID = genID()
	} else {
		// Editing an existing story: ensure ownership.
		if existing, _ := s.stories.get(st.ID); existing != nil && existing.UserID != u.ID {
			apiError(ctx, fasthttp.StatusForbidden, "not your story")
			return
		}
	}
	for _, p := range req.Pages {
		text := strings.TrimSpace(p.Text)
		st.Pages = append(st.Pages, Page{
			Text:     text,
			Words:    splitWordsKeepSep(text),
			ImageURL: p.ImageURL,
		})
		if st.CoverURL == "" && p.ImageURL != "" {
			st.CoverURL = p.ImageURL
		}
	}
	if err := s.stories.save(st); err != nil {
		apiError(ctx, fasthttp.StatusInternalServerError, "could not save story")
		return
	}
	writeJSON(ctx, 200, map[string]any{"id": st.ID, "url": "/story/" + st.ID})
}

func (s *Server) handleListStories(ctx *fasthttp.RequestCtx) {
	u := s.user(ctx)
	if u == nil {
		writeJSON(ctx, 200, map[string]any{"stories": []any{}})
		return
	}
	mine, _ := s.stories.listByUser(u.ID, 100)
	list := make([]map[string]any, 0, len(mine))
	for _, st := range mine {
		list = append(list, map[string]any{
			"id": st.ID, "title": st.Title, "url": "/story/" + st.ID,
			"cover": storyCard(st).Cover, "public": st.Public, "pages": len(st.Pages),
		})
	}
	writeJSON(ctx, 200, map[string]any{"stories": list})
}

func (s *Server) handleDeleteStory(ctx *fasthttp.RequestCtx) {
	u := s.user(ctx)
	if u == nil {
		apiError(ctx, fasthttp.StatusUnauthorized, "sign in")
		return
	}
	var req struct {
		ID string `json:"id"`
	}
	if err := json.Unmarshal(ctx.PostBody(), &req); err != nil || req.ID == "" {
		apiError(ctx, fasthttp.StatusBadRequest, "missing id")
		return
	}
	if err := s.stories.delete(req.ID, u.ID); err != nil {
		apiError(ctx, fasthttp.StatusInternalServerError, "could not delete")
		return
	}
	writeJSON(ctx, 200, map[string]any{"ok": true})
}

// ---------- support ----------

func (s *Server) aiError(ctx *fasthttp.RequestCtx, err error) {
	switch err {
	case errNotSignedIn:
		apiError(ctx, fasthttp.StatusUnauthorized, "your app.nz session expired — please sign in again")
	case errInsufficientCredits:
		apiError(ctx, fasthttp.StatusPaymentRequired, "you're out of app.nz credits — top up to keep creating")
	default:
		apiError(ctx, fasthttp.StatusBadGateway, "generation failed: "+err.Error())
	}
}

// saveGeneratedImage persists a base64 image returned by a provider that doesn't
// host the result, and returns its public /static URL.
func (s *Server) saveGeneratedImage(userID, b64 string) (string, error) {
	data, err := base64.StdEncoding.DecodeString(b64)
	if err != nil {
		return "", err
	}
	dir := filepath.Join("static", "generated")
	if err := os.MkdirAll(dir, 0o755); err != nil {
		return "", err
	}
	name := genID() + ".png"
	if err := os.WriteFile(filepath.Join(dir, name), data, 0o644); err != nil {
		return "", err
	}
	return "/static/generated/" + name, nil
}

// parseStoryJSON extracts the story JSON the model returned, tolerating code
// fences and surrounding prose.
func parseStoryJSON(out string) (*genResult, error) {
	out = strings.TrimSpace(out)
	out = strings.TrimPrefix(out, "```json")
	out = strings.TrimPrefix(out, "```")
	out = strings.TrimSuffix(out, "```")
	if i := strings.IndexByte(out, '{'); i >= 0 {
		if j := strings.LastIndexByte(out, '}'); j >= i {
			out = out[i : j+1]
		}
	}
	var r genResult
	if err := json.Unmarshal([]byte(out), &r); err != nil {
		return nil, err
	}
	if strings.TrimSpace(r.Title) == "" {
		r.Title = "My Story"
	}
	return &r, nil
}

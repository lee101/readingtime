package main

import (
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"strings"
	"time"
)

// gatewayClient talks to the app.nz OpenAI-compatible AI gateway. Every call
// forwards the signed-in user's session cookie so the gateway authenticates
// them and meters the spend against their app.nz credits (see app-site
// gateway.go meterUsage -> deductCredits). readingtime itself never touches the
// credit ledger; the platform is the single billing path.
type gatewayClient struct {
	base string
	http *http.Client
}

func newGatewayClient(base string) *gatewayClient {
	return &gatewayClient{
		base: strings.TrimRight(base, "/"),
		http: &http.Client{Timeout: 180 * time.Second},
	}
}

// gwModel is the slimmed view of a catalogue model the author UI needs.
type gwModel struct {
	ID       string `json:"id"`
	Provider string `json:"provider"`
	Vision   bool   `json:"supports_vision"`
}

type modelsResponse struct {
	Models []gwModel `json:"models"`
}

func (g *gatewayClient) do(method, path, cookieTok string, body []byte) (*http.Response, error) {
	var rdr io.Reader
	if body != nil {
		rdr = bytes.NewReader(body)
	}
	req, err := http.NewRequest(method, g.base+path, rdr)
	if err != nil {
		return nil, err
	}
	if body != nil {
		req.Header.Set("Content-Type", "application/json")
	}
	if strings.HasPrefix(cookieTok, "key:") {
		req.Header.Set("Authorization", "Bearer "+strings.TrimPrefix(cookieTok, "key:"))
	}
	return g.http.Do(req)
}

// listModels fetches the catalogue and splits it into curated text and image
// model lists for the author UI's model pickers.
func (g *gatewayClient) listModels(cookieTok string) (text, image []string, err error) {
	resp, err := g.do("GET", "/api/gateway/models", cookieTok, nil)
	if err != nil {
		return nil, nil, err
	}
	defer resp.Body.Close()
	if resp.StatusCode != 200 {
		return nil, nil, fmt.Errorf("models: status %d", resp.StatusCode)
	}
	var mr modelsResponse
	if err := json.NewDecoder(resp.Body).Decode(&mr); err != nil {
		return nil, nil, err
	}
	for _, m := range mr.Models {
		switch {
		case isImageModel(m.ID):
			image = append(image, m.ID)
		case isTextModel(m.ID):
			text = append(text, m.ID)
		}
	}
	text = withPreferred(text, preferredTextModels)
	image = withPreferred(image, preferredImageModels)
	return text, image, nil
}

type chatMessage struct {
	Role    string `json:"role"`
	Content string `json:"content"`
}

// chatComplete runs a non-streaming completion and returns the assistant text.
func (g *gatewayClient) chatComplete(cookieTok, model string, messages []chatMessage, maxTokens int) (string, error) {
	payload := map[string]any{
		"model":       model,
		"messages":    messages,
		"stream":      false,
		"temperature": 0.9,
	}
	if maxTokens > 0 {
		payload["max_tokens"] = maxTokens
	}
	body, _ := json.Marshal(payload)
	resp, err := g.do("POST", "/v1/chat/completions", cookieTok, body)
	if err != nil {
		return "", err
	}
	defer resp.Body.Close()
	raw, _ := io.ReadAll(resp.Body)
	if resp.StatusCode == 401 {
		return "", errNotSignedIn
	}
	if resp.StatusCode == 402 {
		return "", errInsufficientCredits
	}
	if resp.StatusCode != 200 {
		return "", fmt.Errorf("chat: status %d: %s", resp.StatusCode, snippet(raw))
	}
	var parsed struct {
		Choices []struct {
			Message struct {
				Content string `json:"content"`
			} `json:"message"`
		} `json:"choices"`
	}
	if err := json.Unmarshal(raw, &parsed); err != nil {
		return "", err
	}
	if len(parsed.Choices) == 0 {
		return "", errors.New("chat: empty response")
	}
	return parsed.Choices[0].Message.Content, nil
}

// generateImage returns either a hosted URL or base64 data for one image.
func (g *gatewayClient) generateImage(cookieTok, model, prompt, size string) (url, b64 string, err error) {
	if size == "" {
		size = "1024x1024"
	}
	body, _ := json.Marshal(map[string]any{
		"model":  model,
		"prompt": prompt,
		"n":      1,
		"size":   size,
	})
	resp, err := g.do("POST", "/v1/images/generations", cookieTok, body)
	if err != nil {
		return "", "", err
	}
	defer resp.Body.Close()
	raw, _ := io.ReadAll(resp.Body)
	if resp.StatusCode == 401 {
		return "", "", errNotSignedIn
	}
	if resp.StatusCode == 402 {
		return "", "", errInsufficientCredits
	}
	if resp.StatusCode != 200 {
		return "", "", fmt.Errorf("image: status %d: %s", resp.StatusCode, snippet(raw))
	}
	var parsed struct {
		Data []struct {
			URL     string `json:"url"`
			B64JSON string `json:"b64_json"`
		} `json:"data"`
	}
	if err := json.Unmarshal(raw, &parsed); err != nil {
		return "", "", err
	}
	if len(parsed.Data) == 0 {
		return "", "", errors.New("image: empty response")
	}
	return parsed.Data[0].URL, parsed.Data[0].B64JSON, nil
}

var (
	errNotSignedIn         = errors.New("sign in required")
	errInsufficientCredits = errors.New("insufficient app.nz credits")
)

func snippet(b []byte) string {
	s := strings.TrimSpace(string(b))
	if len(s) > 240 {
		return s[:240] + "…"
	}
	return s
}

// --- model categorisation heuristics (the catalogue carries no modality flag) ---

var imageNeedles = []string{"flux", "dall-e", "dalle", "sdxl", "imagen", "seedream",
	"qwen-image", "zimage", "z-image", "hidream", "nano-banana", "gpt-image", "glm-image",
	"grok-imagine-image", "ideogram", "recraft", "stable-diffusion", "playground", "auto-image", "ra2"}

var nonImageNeedles = []string{"video", "-3d", "to-3d", "image-to-3d", "image-to-video",
	"edit", "outpaint", "inpaint", "extend", "upscale", "controlnet", "rerank", "embed",
	"whisper", "tts", "speech", "audio", "music", "voice"}

func containsAny(s string, needles []string) bool {
	for _, n := range needles {
		if strings.Contains(s, n) {
			return true
		}
	}
	return false
}

func isImageModel(id string) bool {
	l := strings.ToLower(id)
	if l == "ra2" {
		return true
	}
	if containsAny(l, nonImageNeedles) {
		return false
	}
	return containsAny(l, imageNeedles) || strings.Contains(l, "image")
}

func isTextModel(id string) bool {
	l := strings.ToLower(id)
	if isImageModel(id) || l == "ra2" || l == "ra2v" {
		return false
	}
	if containsAny(l, nonImageNeedles) {
		return false
	}
	// Chat models: typical LLM families plus the auto router.
	textNeedles := []string{"auto", "gpt", "claude", "gemini", "deepseek", "grok",
		"llama", "qwen", "mistral", "mixtral", "command", "glm", "kimi", "yi", "phi",
		"sonnet", "opus", "haiku", "o1", "o3", "o4", "nova"}
	return containsAny(l, textNeedles) && !strings.Contains(l, "imagine")
}

var preferredTextModels = []string{"deepseek-v4-flash", "auto", "claude-sonnet-4-6", "claude-opus-5",
	"gpt-5.1", "gpt-4.1", "gemini-2.5-flash", "gemini-2.5-pro", "deepseek-chat"}

// Ordered by what is actually routable on this platform today (auto-image picks
// a configured provider; gpt-image-* are configured). Models that depend on
// unconfigured providers still appear (after these) so they light up if keys are
// added later.
var preferredImageModels = []string{"ra2", "openpaths/auto-image", "gpt-image-1", "gpt-image-1.5",
	"gpt-image-2", "gpt-image-1-mini", "flux-schnell", "flux-dev", "flux-pro"}

// withPreferred returns the available models with the preferred ones (that exist)
// floated to the top in order, de-duplicated.
func withPreferred(available, preferred []string) []string {
	have := make(map[string]bool, len(available))
	for _, a := range available {
		have[a] = true
	}
	seen := make(map[string]bool)
	out := make([]string, 0, len(available))
	for _, p := range preferred {
		if have[p] && !seen[p] {
			out = append(out, p)
			seen[p] = true
		}
	}
	for _, a := range available {
		if !seen[a] {
			out = append(out, a)
			seen[a] = true
		}
	}
	return out
}

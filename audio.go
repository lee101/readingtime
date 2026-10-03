package main

import (
	"bytes"
	"crypto/rsa"
	"crypto/sha256"
	"crypto/x509"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"encoding/pem"
	"fmt"
	"html"
	"io"
	"log"
	"net/http"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"sync"
	"time"

	"crypto"
	"crypto/rand"

	"github.com/valyala/fasthttp"
)

type wordTime struct {
	I int     `json:"i"`
	T float64 `json:"t"`
}

type narration struct {
	Audio    string     `json:"audio"`
	Words    []wordTime `json:"words"`
	Duration float64    `json:"duration"`
	Cached   bool       `json:"cached"`
}

type saKey struct {
	ClientEmail string `json:"client_email"`
	PrivateKey  string `json:"private_key"`
	TokenURI    string `json:"token_uri"`
}

type narrator struct {
	r2        *r2Client
	sa        *saKey
	voice     string
	lang      string
	rate      float64
	http      *http.Client
	mu        sync.Mutex
	token     string
	expiry    time.Time
	flight    map[string]*flightCall
	googleOff time.Time
	limMu     sync.Mutex
	lim       map[string][]time.Time
}

type flightCall struct {
	wg  sync.WaitGroup
	res *narration
	err error
}

var (
	narratorOnce sync.Once
	narratorInst *narrator
)

func getNarrator() *narrator {
	narratorOnce.Do(func() {
		n := &narrator{
			r2:     newR2FromEnv(),
			voice:  envOr("READINGTIME_TTS_VOICE", "en-US-Neural2-H"),
			lang:   envOr("READINGTIME_TTS_LANG", "en-US"),
			rate:   0.92,
			http:   &http.Client{Timeout: 60 * time.Second},
			flight: map[string]*flightCall{},
			lim:    map[string][]time.Time{},
		}
		if v, err := strconv.ParseFloat(os.Getenv("READINGTIME_TTS_RATE"), 64); err == nil && v > 0.25 && v <= 4 {
			n.rate = v
		}
		path := os.Getenv("READINGTIME_GOOGLE_CREDENTIALS")
		if path == "" {
			path = os.Getenv("GOOGLE_APPLICATION_CREDENTIALS")
		}
		if raw, err := os.ReadFile(path); err == nil {
			var k saKey
			if json.Unmarshal(raw, &k) == nil && k.PrivateKey != "" {
				if k.TokenURI == "" {
					k.TokenURI = "https://oauth2.googleapis.com/token"
				}
				n.sa = &k
			}
		}
		if n.r2 == nil {
			log.Printf("narration: R2 unset, caching to static/generated/audio")
		}
		if n.sa == nil && n.geminiKey() == "" {
			log.Printf("narration: no tts credentials, narration disabled")
		}
		narratorInst = n
	})
	return narratorInst
}

func b64url(b []byte) string { return base64.RawURLEncoding.EncodeToString(b) }

func (n *narrator) accessToken() (string, error) {
	n.mu.Lock()
	defer n.mu.Unlock()
	if n.token != "" && time.Now().Before(n.expiry.Add(-time.Minute)) {
		return n.token, nil
	}
	blk, _ := pem.Decode([]byte(n.sa.PrivateKey))
	if blk == nil {
		return "", fmt.Errorf("bad private key")
	}
	pk, err := x509.ParsePKCS8PrivateKey(blk.Bytes)
	if err != nil {
		return "", err
	}
	rk, ok := pk.(*rsa.PrivateKey)
	if !ok {
		return "", fmt.Errorf("not rsa key")
	}
	now := time.Now()
	hdr, _ := json.Marshal(map[string]string{"alg": "RS256", "typ": "JWT"})
	cl, _ := json.Marshal(map[string]any{
		"iss": n.sa.ClientEmail, "scope": "https://www.googleapis.com/auth/cloud-platform",
		"aud": n.sa.TokenURI, "iat": now.Unix(), "exp": now.Add(55 * time.Minute).Unix(),
	})
	in := b64url(hdr) + "." + b64url(cl)
	sum := sha256.Sum256([]byte(in))
	sig, err := rsa.SignPKCS1v15(rand.Reader, rk, crypto.SHA256, sum[:])
	if err != nil {
		return "", err
	}
	form := "grant_type=" + "urn%3Aietf%3Aparams%3Aoauth%3Agrant-type%3Ajwt-bearer" + "&assertion=" + in + "." + b64url(sig)
	resp, err := n.http.Post(n.sa.TokenURI, "application/x-www-form-urlencoded", strings.NewReader(form))
	if err != nil {
		return "", err
	}
	defer resp.Body.Close()
	body, _ := io.ReadAll(resp.Body)
	var out struct {
		AccessToken string `json:"access_token"`
		ExpiresIn   int    `json:"expires_in"`
	}
	if err := json.Unmarshal(body, &out); err != nil || out.AccessToken == "" {
		return "", fmt.Errorf("token exchange: %d %s", resp.StatusCode, truncate(string(body), 200))
	}
	n.token = out.AccessToken
	n.expiry = now.Add(time.Duration(out.ExpiresIn) * time.Second)
	return n.token, nil
}

func truncate(s string, n int) string {
	if len(s) > n {
		return s[:n]
	}
	return s
}

func isWordToken(w string) bool {
	if w == "" {
		return false
	}
	r := []rune(w)
	return !strings.ContainsRune(separatorRunes, r[0])
}

func buildSSML(tokens []string) (string, int) {
	var b strings.Builder
	b.WriteString("<speak>")
	idx := 0
	for _, t := range tokens {
		if t == "" {
			continue
		}
		if isWordToken(t) {
			fmt.Fprintf(&b, `<mark name="%d"/>%s`, idx, html.EscapeString(t))
			idx++
		} else {
			b.WriteString(html.EscapeString(t))
		}
	}
	b.WriteString(`<mark name="end"/></speak>`)
	return b.String(), idx
}

type synthResult struct {
	audio []byte
	words []wordTime
	dur   float64
}

func (n *narrator) synthesize(ssml string, wordCount int) (*synthResult, error) {
	tok, err := n.accessToken()
	if err != nil {
		return nil, err
	}
	req := map[string]any{
		"input":              map[string]string{"ssml": ssml},
		"voice":              map[string]string{"languageCode": n.lang, "name": n.voice},
		"audioConfig":        map[string]any{"audioEncoding": "MP3", "speakingRate": n.rate, "sampleRateHertz": 24000},
		"enableTimePointing": []string{"SSML_MARK"},
	}
	body, _ := json.Marshal(req)
	hr, _ := http.NewRequest("POST", "https://texttospeech.googleapis.com/v1beta1/text:synthesize", bytes.NewReader(body))
	hr.Header.Set("Authorization", "Bearer "+tok)
	hr.Header.Set("Content-Type", "application/json")
	resp, err := n.http.Do(hr)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	raw, _ := io.ReadAll(resp.Body)
	if resp.StatusCode/100 != 2 {
		return nil, fmt.Errorf("tts %d: %s", resp.StatusCode, truncate(string(raw), 300))
	}
	var out struct {
		AudioContent string `json:"audioContent"`
		Timepoints   []struct {
			MarkName    string  `json:"markName"`
			TimeSeconds float64 `json:"timeSeconds"`
		} `json:"timepoints"`
	}
	if err := json.Unmarshal(raw, &out); err != nil {
		return nil, err
	}
	audio, err := base64.StdEncoding.DecodeString(out.AudioContent)
	if err != nil {
		return nil, err
	}
	res := &synthResult{audio: audio}
	for _, tp := range out.Timepoints {
		if tp.MarkName == "end" {
			res.dur = tp.TimeSeconds
			continue
		}
		i, err := strconv.Atoi(tp.MarkName)
		if err != nil {
			continue
		}
		res.words = append(res.words, wordTime{I: i, T: tp.TimeSeconds})
	}
	if len(res.words) != wordCount {
		return nil, fmt.Errorf("tts timepoints %d != words %d (voice %s lacks mark support?)", len(res.words), wordCount, n.voice)
	}
	return res, nil
}

func (n *narrator) localDir() string { return filepath.Join("static", "generated", "audio") }

func (n *narrator) load(hash string) (*narration, bool) {
	if n.r2 != nil {
		raw, ok, err := n.r2.get("audio/" + hash + ".json")
		if err != nil || !ok {
			return nil, false
		}
		var out narration
		if json.Unmarshal(raw, &out) != nil {
			return nil, false
		}
		return &out, true
	}
	raw, err := os.ReadFile(filepath.Join(n.localDir(), hash+".json"))
	if err != nil {
		return nil, false
	}
	var out narration
	if json.Unmarshal(raw, &out) != nil {
		return nil, false
	}
	return &out, true
}

func (n *narrator) store(hash string, res *synthResult) (*narration, error) {
	out := &narration{Words: res.words, Duration: res.dur}
	if n.r2 != nil {
		out.Audio = n.r2.publicURL("audio/" + hash + ".mp3")
		if out.Audio == "" {
			return nil, fmt.Errorf("READINGTIME_R2_PUBLIC_BASE unset")
		}
		meta, _ := json.Marshal(out)
		if err := n.r2.put("audio/"+hash+".mp3", res.audio, "audio/mpeg", "public, max-age=31536000, immutable"); err != nil {
			return nil, err
		}
		if err := n.r2.put("audio/"+hash+".json", meta, "application/json", "public, max-age=31536000, immutable"); err != nil {
			return nil, err
		}
		return out, nil
	}
	if err := os.MkdirAll(n.localDir(), 0o755); err != nil {
		return nil, err
	}
	out.Audio = "/static/generated/audio/" + hash + ".mp3"
	meta, _ := json.Marshal(out)
	if err := os.WriteFile(filepath.Join(n.localDir(), hash+".mp3"), res.audio, 0o644); err != nil {
		return nil, err
	}
	if err := os.WriteFile(filepath.Join(n.localDir(), hash+".json"), meta, 0o644); err != nil {
		return nil, err
	}
	return out, nil
}

func (n *narrator) allow(ip string) bool {
	n.limMu.Lock()
	defer n.limMu.Unlock()
	cut := time.Now().Add(-time.Hour)
	ts := n.lim[ip][:0]
	for _, t := range n.lim[ip] {
		if t.After(cut) {
			ts = append(ts, t)
		}
	}
	if len(ts) >= 40 {
		n.lim[ip] = ts
		return false
	}
	n.lim[ip] = append(ts, time.Now())
	return true
}

func (n *narrator) providers() []string {
	switch strings.ToLower(os.Getenv("READINGTIME_TTS_PROVIDER")) {
	case "google":
		return []string{"google"}
	case "gemini":
		return []string{"gemini"}
	}
	var out []string
	if n.sa != nil && time.Now().After(n.googleOff) {
		out = append(out, "google")
	}
	if n.geminiKey() != "" {
		out = append(out, "gemini")
	}
	return out
}

func (n *narrator) cacheKey(provider, ssml, plain string) string {
	var in string
	if provider == "google" {
		in = "google|" + n.voice + "|" + strconv.FormatFloat(n.rate, 'f', 2, 64) + "|" + ssml
	} else {
		in = "gemini|" + envOr("READINGTIME_GEMINI_VOICE", "Sulafat") + "|" + envOr("READINGTIME_GEMINI_TTS_MODEL", "gemini-2.5-flash-preview-tts") + "|v1|" + plain
	}
	sum := sha256.Sum256([]byte(in))
	return hex.EncodeToString(sum[:16])
}

func (n *narrator) narrate(tokens []string, ip string) (*narration, error) {
	ssml, wc := buildSSML(tokens)
	if wc == 0 {
		return &narration{}, nil
	}
	plain := strings.Join(tokens, "")
	provs := n.providers()
	if len(provs) == 0 {
		return nil, fmt.Errorf("no tts provider")
	}
	for _, p := range provs {
		if out, ok := n.load(n.cacheKey(p, ssml, plain)); ok {
			out.Cached = true
			return out, nil
		}
	}
	first := n.cacheKey(provs[0], ssml, plain)
	n.mu.Lock()
	if fc, ok := n.flight[first]; ok {
		n.mu.Unlock()
		fc.wg.Wait()
		return fc.res, fc.err
	}
	fc := &flightCall{}
	fc.wg.Add(1)
	n.flight[first] = fc
	n.mu.Unlock()
	defer func() {
		n.mu.Lock()
		delete(n.flight, first)
		n.mu.Unlock()
		fc.wg.Done()
	}()
	if !n.allow(ip) {
		fc.err = errNarrateRate
		return nil, fc.err
	}
	var lastErr error
	for _, p := range provs {
		var res *synthResult
		var err error
		if p == "google" {
			res, err = n.synthesize(ssml, wc)
			if err != nil && strings.Contains(err.Error(), "tts 403") {
				n.googleOff = time.Now().Add(10 * time.Minute)
			}
		} else {
			res, err = n.synthesizeGemini(tokens)
			if err == nil && len(res.words) != wc {
				err = fmt.Errorf("gemini alignment %d != %d", len(res.words), wc)
			}
		}
		if err != nil {
			log.Printf("narration provider %s: %v", p, err)
			lastErr = err
			continue
		}
		fc.res, fc.err = n.store(n.cacheKey(p, ssml, plain), res)
		return fc.res, fc.err
	}
	fc.err = lastErr
	return nil, lastErr
}

func narrateIP(ctx *fasthttp.RequestCtx) string {
	if v := string(ctx.Request.Header.Peek("X-Real-IP")); v != "" {
		return v
	}
	if v := string(ctx.Request.Header.Peek("X-Forwarded-For")); v != "" {
		return strings.TrimSpace(strings.Split(v, ",")[0])
	}
	return ctx.RemoteIP().String()
}

var errNarrateRate = fmt.Errorf("narration rate limit")

func pageTokens(p Page) []string {
	if len(p.Words) > 0 {
		return p.Words
	}
	return splitWordsKeepSep(p.Text)
}

func (s *Server) handleAudioPage(ctx *fasthttp.RequestCtx) {
	n := getNarrator()
	if n.sa == nil && n.geminiKey() == "" {
		apiError(ctx, fasthttp.StatusServiceUnavailable, "narration unavailable")
		return
	}
	q := ctx.QueryArgs()
	page, err := strconv.Atoi(string(q.Peek("page")))
	if err != nil || page < 0 {
		apiError(ctx, fasthttp.StatusBadRequest, "bad page")
		return
	}
	var pages []Page
	if name := string(q.Peek("book")); name != "" {
		b, ok := s.books[name]
		if !ok {
			apiError(ctx, fasthttp.StatusNotFound, "no such book")
			return
		}
		pages = b.Pages
	} else if id := string(q.Peek("story")); id != "" {
		st, err := s.stories.get(id)
		if err != nil || st == nil {
			apiError(ctx, fasthttp.StatusNotFound, "no such story")
			return
		}
		if !st.Public {
			u := s.user(ctx)
			if u == nil || u.ID != st.UserID {
				apiError(ctx, fasthttp.StatusForbidden, "this story is private")
				return
			}
		}
		pages = st.Pages
	} else {
		apiError(ctx, fasthttp.StatusBadRequest, "book or story required")
		return
	}
	if page >= len(pages) {
		apiError(ctx, fasthttp.StatusNotFound, "no such page")
		return
	}
	out, err := n.narrate(pageTokens(pages[page]), narrateIP(ctx))
	if err != nil {
		code := fasthttp.StatusBadGateway
		if err == errNarrateRate {
			code = fasthttp.StatusTooManyRequests
		}
		log.Printf("narration: %v", err)
		apiError(ctx, code, "narration failed")
		return
	}
	writeJSON(ctx, 200, out)
}

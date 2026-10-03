package main

import (
	"encoding/json"
	"strings"
	"sync"
	"time"

	"github.com/valyala/fasthttp"
)

type authReq struct {
	Email    string `json:"email"`
	Password string `json:"password"`
	Handle   string `json:"handle"`
	Next     string `json:"next"`
}

var (
	attemptMu sync.Mutex
	attempts  = map[string][]time.Time{}
)

func tooMany(ip string) bool {
	attemptMu.Lock()
	defer attemptMu.Unlock()
	cut := time.Now().Add(-10 * time.Minute)
	var keep []time.Time
	for _, t := range attempts[ip] {
		if t.After(cut) {
			keep = append(keep, t)
		}
	}
	if len(keep) >= 20 {
		attempts[ip] = keep
		return true
	}
	attempts[ip] = append(keep, time.Now())
	// Without a global sweep, entries keyed by spoofed IPs are never reclaimed.
	if len(attempts) > 10000 {
		attempts = map[string][]time.Time{}
	}
	return false
}

// clientIP resolves the caller for rate limiting. CF-Connecting-IP is set by
// Cloudflare and cannot be forged by the client; the XFF fallback is only
// trustworthy because nginx appends $remote_addr after it.
func clientIP(ctx *fasthttp.RequestCtx) string {
	if v := strings.TrimSpace(string(ctx.Request.Header.Peek("CF-Connecting-IP"))); v != "" {
		return v
	}
	if v := string(ctx.Request.Header.Peek("X-Forwarded-For")); v != "" {
		return strings.TrimSpace(strings.Split(v, ",")[0])
	}
	return ctx.RemoteIP().String()
}

func (s *Server) setSession(ctx *fasthttp.RequestCtx, tok string, exp time.Time) {
	c := fasthttp.AcquireCookie()
	defer fasthttp.ReleaseCookie(c)
	c.SetKey(sessionCookie)
	c.SetValue(tok)
	c.SetPath("/")
	c.SetHTTPOnly(true)
	c.SetSecure(!s.cfg.Dev)
	c.SetSameSite(fasthttp.CookieSameSiteLaxMode)
	if tok == "" {
		c.SetMaxAge(-1)
	} else {
		c.SetExpire(exp)
	}
	ctx.Response.Header.SetCookie(c)
}

func (s *Server) handleLogin(ctx *fasthttp.RequestCtx) {
	next := string(ctx.QueryArgs().Peek("next"))
	if s.user(ctx) != nil {
		ctx.Redirect(s.returnTo(next), fasthttp.StatusFound)
		return
	}
	mode := "login"
	if string(ctx.QueryArgs().Peek("mode")) == "signup" {
		mode = "signup"
	}
	s.render(ctx, "login.html", map[string]any{
		"Meta": Meta{Title: "Sign in — Reading Time", Desc: siteDesc, Canonical: s.cfg.SiteBaseURL + "/login"},
		"User": nil, "Cfg": s.cfg, "LoginURL": "/login",
		"Next": s.returnTo(next), "Mode": mode,
	})
}

func (s *Server) authDone(ctx *fasthttp.RequestCtx, u *User, next string) {
	tok, exp, err := s.auth.createSession(u.ID)
	if err != nil {
		apiError(ctx, fasthttp.StatusInternalServerError, "could not start session")
		return
	}
	s.setSession(ctx, tok, exp)
	writeJSON(ctx, 200, map[string]any{"ok": true, "next": strings.TrimPrefix(s.returnTo(next), s.cfg.SiteBaseURL)})
}

func (s *Server) handleSignup(ctx *fasthttp.RequestCtx) {
	var r authReq
	if json.Unmarshal(ctx.PostBody(), &r) != nil || tooMany(clientIP(ctx)) {
		apiError(ctx, fasthttp.StatusTooManyRequests, "too many attempts, try again later")
		return
	}
	u, err := s.auth.signup(r.Email, r.Password, r.Handle)
	if err != nil {
		code := fasthttp.StatusBadRequest
		if err == errEmailTaken {
			code = fasthttp.StatusConflict
		}
		apiError(ctx, code, err.Error())
		return
	}
	s.authDone(ctx, u, r.Next)
}

func (s *Server) handleLoginPost(ctx *fasthttp.RequestCtx) {
	var r authReq
	if json.Unmarshal(ctx.PostBody(), &r) != nil || tooMany(clientIP(ctx)) {
		apiError(ctx, fasthttp.StatusTooManyRequests, "too many attempts, try again later")
		return
	}
	u, err := s.auth.login(r.Email, r.Password)
	if err != nil {
		apiError(ctx, fasthttp.StatusUnauthorized, err.Error())
		return
	}
	s.authDone(ctx, u, r.Next)
}

func (s *Server) handleLogout(ctx *fasthttp.RequestCtx) {
	s.auth.deleteSession(sessionToken(ctx))
	s.setSession(ctx, "", time.Time{})
	if string(ctx.Method()) == "POST" {
		writeJSON(ctx, 200, map[string]any{"ok": true})
		return
	}
	ctx.Redirect(s.returnTo(string(ctx.QueryArgs().Peek("next"))), fasthttp.StatusFound)
}

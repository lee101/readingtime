package main

import (
	"strings"
	"time"

	"github.com/valyala/fasthttp"
)

const freeCookie = "rt_free"

var crawlerUA = []string{"googlebot", "bingbot", "facebookexternalhit", "twitterbot", "slackbot", "linkedinbot", "whatsapp", "duckduckbot", "applebot"}

func isCrawler(ctx *fasthttp.RequestCtx) bool {
	ua := strings.ToLower(string(ctx.UserAgent()))
	for _, c := range crawlerUA {
		if strings.Contains(ua, c) {
			return true
		}
	}
	return false
}

func (b *billing) initFree() error {
	_, err := b.db.Exec(`CREATE TABLE IF NOT EXISTS free_reads (
		user_id TEXT PRIMARY KEY, item_id TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL)`)
	return err
}

// allowRead enforces one free book per visitor (cookie) or account (local db);
// subscribers, owners and link-preview crawlers always pass.
func (s *Server) allowRead(ctx *fasthttp.RequestCtx, u *User, itemID, ownerID string) bool {
	if isCrawler(ctx) || (u != nil && u.ID == ownerID) || s.billing.subscriber(u) {
		return true
	}
	cookie := string(ctx.Request.Header.Cookie(freeCookie))
	setCookie := func(v string) {
		var c fasthttp.Cookie
		c.SetKey(freeCookie)
		c.SetValue(v)
		c.SetPath("/")
		c.SetHTTPOnly(true)
		c.SetExpire(time.Now().AddDate(1, 0, 0))
		ctx.Response.Header.SetCookie(&c)
	}
	if u == nil {
		if cookie == "" {
			setCookie(itemID)
			return true
		}
		return cookie == itemID
	}
	var used string
	_ = s.billing.db.QueryRow(`SELECT item_id FROM free_reads WHERE user_id = ?`, u.ID).Scan(&used)
	if used == "" {
		used = cookie
		if used == "" {
			used = itemID
		}
		_, _ = s.billing.db.Exec(`INSERT INTO free_reads (user_id, item_id, created_at) VALUES (?,?,?) ON CONFLICT DO NOTHING`,
			u.ID, used, time.Now().UTC())
		setCookie(used)
	}
	return used == itemID
}

func (s *Server) renderPaywall(ctx *fasthttp.RequestCtx, u *User, title, back string) {
	ctx.SetStatusCode(fasthttp.StatusPaymentRequired)
	s.render(ctx, "paywall.html", map[string]any{
		"Meta":     Meta{Title: "Keep reading — Reading Time", Desc: siteDesc},
		"User":     u,
		"Cfg":      s.cfg,
		"Title":    title,
		"LoginURL": s.loginURL(s.cfg.SiteBaseURL + string(ctx.RequestURI())),
		"Sub":      false,
		"Enabled":  s.billing.enabled(),
	})
}

// aiAuth authenticates AI calls with the platform key. Subscribers get the
// fair-use cap; free accounts a small daily allowance.
func (s *Server) aiAuth(ctx *fasthttp.RequestCtx, u *User, model, included, kind string, cap int) (tok string, ok bool) {
	if s.cfg.ServiceGatewayKey == "" {
		apiError(ctx, fasthttp.StatusServiceUnavailable, "generation is not configured")
		return "", false
	}
	if !s.billing.subscriber(u) {
		cap = freeDailyCap[kind]
		if model != included && model != "" && model != "auto" && kind == "text" {
			apiError(ctx, fasthttp.StatusPaymentRequired, "that model needs Unlimited")
			return "", false
		}
	}
	if !s.billing.takeUsage(u.ID, kind, cap) {
		msg := "daily limit reached — it resets at midnight UTC"
		if !s.billing.subscriber(u) {
			msg = "free daily limit reached — go Unlimited for more"
		}
		apiError(ctx, fasthttp.StatusTooManyRequests, msg)
		return "", false
	}
	return "key:" + s.cfg.ServiceGatewayKey, true
}

var freeDailyCap = map[string]int{"text": 5, "img": 30}

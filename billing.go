package main

import (
	"crypto/hmac"
	"crypto/sha256"
	"database/sql"
	"encoding/hex"
	"encoding/json"
	"errors"
	"io"
	"log"
	"net/http"
	neturl "net/url"
	"strconv"
	"strings"
	"time"

	"github.com/valyala/fasthttp"
)

const (
	unlimitedModel = "deepseek-v4-flash"
	dailyTextCap   = 80
	dailyImageCap  = 400
	stripeAPI      = "https://api.stripe.com/v1"
)

type billing struct {
	db      *pgDB
	secret  string
	whsec   string
	monthly string
	yearly  string
	http    *http.Client
}

func newBilling(db *pgDB, cfg Config) (*billing, error) {
	if _, err := db.Exec(`
		CREATE TABLE IF NOT EXISTS subscriptions (
			user_id TEXT PRIMARY KEY,
			customer_id TEXT NOT NULL DEFAULT '',
			subscription_id TEXT NOT NULL DEFAULT '',
			status TEXT NOT NULL DEFAULT '',
			period_end TIMESTAMPTZ,
			updated_at TIMESTAMPTZ NOT NULL
		);
		CREATE INDEX IF NOT EXISTS idx_subs_customer ON subscriptions(customer_id);
		CREATE TABLE IF NOT EXISTS usage_daily (
			user_id TEXT NOT NULL,
			day TEXT NOT NULL,
			n INTEGER NOT NULL DEFAULT 0,
			PRIMARY KEY(user_id, day)
		);
	`); err != nil {
		return nil, err
	}
	return &billing{
		db: db, secret: cfg.StripeSecretKey, whsec: cfg.StripeWebhookSecret,
		monthly: cfg.StripePriceMonthly, yearly: cfg.StripePriceYearly, http: &http.Client{Timeout: 30 * time.Second},
	}, nil
}

func (b *billing) enabled() bool { return b != nil && b.secret != "" }

func (b *billing) subscriber(u *User) bool {
	return b != nil && u != nil && b.active(u.ID)
}

func (b *billing) active(userID string) bool {
	if b == nil || userID == "" {
		return false
	}
	var status string
	var end sql.NullTime
	err := b.db.QueryRow(`SELECT status, period_end FROM subscriptions WHERE user_id = ?`, userID).Scan(&status, &end)
	if err != nil {
		return false
	}
	if status != "active" && status != "trialing" && status != "past_due" {
		return false
	}
	return !end.Valid || end.Time.After(time.Now().Add(-3*24*time.Hour))
}

func (b *billing) customer(userID string) string {
	var c string
	_ = b.db.QueryRow(`SELECT customer_id FROM subscriptions WHERE user_id = ?`, userID).Scan(&c)
	return c
}

func (b *billing) upsert(userID, customer, sub, status string, end time.Time) error {
	var endv any
	if !end.IsZero() {
		endv = end.UTC()
	}
	_, err := b.db.Exec(`
		INSERT INTO subscriptions (user_id, customer_id, subscription_id, status, period_end, updated_at)
		VALUES (?,?,?,?,?,?)
		ON CONFLICT(user_id) DO UPDATE SET
			customer_id=CASE WHEN excluded.customer_id!='' THEN excluded.customer_id ELSE customer_id END,
			subscription_id=CASE WHEN excluded.subscription_id!='' THEN excluded.subscription_id ELSE subscription_id END,
			status=excluded.status, period_end=COALESCE(excluded.period_end, period_end),
			updated_at=excluded.updated_at`,
		userID, customer, sub, status, endv, time.Now().UTC())
	return err
}

// takeUsage counts one generation against the daily fair-use cap; false when over.
func (b *billing) takeUsage(userID, kind string, cap int) bool {
	userID += ":" + kind
	day := time.Now().UTC().Format("2006-01-02")
	var n int
	_ = b.db.QueryRow(`SELECT n FROM usage_daily WHERE user_id = ? AND day = ?`, userID, day).Scan(&n)
	if n >= cap {
		return false
	}
	_, _ = b.db.Exec(`INSERT INTO usage_daily (user_id, day, n) VALUES (?,?,1)
		ON CONFLICT(user_id, day) DO UPDATE SET n = n + 1`, userID, day)
	return true
}

func (b *billing) stripe(method, path string, form neturl.Values) (map[string]any, error) {
	var body io.Reader
	if form != nil {
		body = strings.NewReader(form.Encode())
	}
	req, err := http.NewRequest(method, stripeAPI+path, body)
	if err != nil {
		return nil, err
	}
	req.SetBasicAuth(b.secret, "")
	if form != nil {
		req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	}
	resp, err := b.http.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	raw, _ := io.ReadAll(io.LimitReader(resp.Body, 4<<20))
	var out map[string]any
	_ = json.Unmarshal(raw, &out)
	if resp.StatusCode/100 != 2 {
		return nil, errors.New("stripe: " + snippet(raw))
	}
	return out, nil
}

func str(m map[string]any, k string) string {
	s, _ := m[k].(string)
	return s
}

func periodEnd(sub map[string]any) time.Time {
	if f, ok := sub["current_period_end"].(float64); ok && f > 0 {
		return time.Unix(int64(f), 0)
	}
	if items, ok := sub["items"].(map[string]any); ok {
		if data, ok := items["data"].([]any); ok && len(data) > 0 {
			if it, ok := data[0].(map[string]any); ok {
				if f, ok := it["current_period_end"].(float64); ok && f > 0 {
					return time.Unix(int64(f), 0)
				}
			}
		}
	}
	return time.Time{}
}

func (b *billing) verify(payload []byte, header string) bool {
	if b.whsec == "" {
		return false
	}
	var ts string
	var sigs []string
	for _, part := range strings.Split(header, ",") {
		kv := strings.SplitN(strings.TrimSpace(part), "=", 2)
		if len(kv) != 2 {
			continue
		}
		switch kv[0] {
		case "t":
			ts = kv[1]
		case "v1":
			sigs = append(sigs, kv[1])
		}
	}
	t, err := strconv.ParseInt(ts, 10, 64)
	if err != nil || time.Since(time.Unix(t, 0)) > 10*time.Minute {
		return false
	}
	mac := hmac.New(sha256.New, []byte(b.whsec))
	mac.Write([]byte(ts + "."))
	mac.Write(payload)
	want := hex.EncodeToString(mac.Sum(nil))
	for _, s := range sigs {
		if hmac.Equal([]byte(s), []byte(want)) {
			return true
		}
	}
	return false
}

func (b *billing) userByCustomer(customer string) string {
	var id string
	_ = b.db.QueryRow(`SELECT user_id FROM subscriptions WHERE customer_id = ?`, customer).Scan(&id)
	return id
}

func (b *billing) applySub(sub map[string]any, fallbackUser string) {
	customer := str(sub, "customer")
	userID := fallbackUser
	if md, ok := sub["metadata"].(map[string]any); ok && userID == "" {
		userID = str(md, "user_id")
	}
	if userID == "" {
		userID = b.userByCustomer(customer)
	}
	if userID == "" {
		log.Printf("stripe: subscription %s has no user", str(sub, "id"))
		return
	}
	if err := b.upsert(userID, customer, str(sub, "id"), str(sub, "status"), periodEnd(sub)); err != nil {
		log.Printf("stripe: upsert: %v", err)
	}
}

func (s *Server) handleStripeWebhook(ctx *fasthttp.RequestCtx) {
	if !s.billing.enabled() {
		ctx.SetStatusCode(503)
		return
	}
	body := ctx.PostBody()
	if !s.billing.verify(body, string(ctx.Request.Header.Peek("Stripe-Signature"))) {
		ctx.SetStatusCode(400)
		return
	}
	var ev struct {
		Type string `json:"type"`
		Data struct {
			Object map[string]any `json:"object"`
		} `json:"data"`
	}
	if err := json.Unmarshal(body, &ev); err != nil {
		ctx.SetStatusCode(400)
		return
	}
	obj := ev.Data.Object
	switch ev.Type {
	case "checkout.session.completed":
		subID := str(obj, "subscription")
		if subID == "" {
			break
		}
		sub, err := s.billing.stripe("GET", "/subscriptions/"+subID, nil)
		if err != nil {
			log.Printf("stripe: fetch sub: %v", err)
			ctx.SetStatusCode(500)
			return
		}
		s.billing.applySub(sub, str(obj, "client_reference_id"))
		amount, _ := obj["amount_total"].(float64)
		thTrack("purchase", str(obj, "client_reference_id"), str(obj, "id"), map[string]any{
			"revenue": amount / 100, "currency": strings.ToUpper(str(obj, "currency")),
			"subscription_id": str(sub, "id"), "transaction_id": str(obj, "id"), "surface": "stripe_checkout",
		})
	case "customer.subscription.created", "customer.subscription.updated", "customer.subscription.deleted":
		s.billing.applySub(obj, "")
	}
	ctx.SetStatusCode(200)
}

func (s *Server) handleCheckout(ctx *fasthttp.RequestCtx) {
	u := s.user(ctx)
	if u == nil {
		apiError(ctx, fasthttp.StatusUnauthorized, "sign in to subscribe")
		return
	}
	if !s.billing.enabled() {
		apiError(ctx, fasthttp.StatusServiceUnavailable, "subscriptions are not available yet")
		return
	}
	var req struct {
		Plan string `json:"plan"`
	}
	_ = json.Unmarshal(ctx.PostBody(), &req)
	price := s.billing.monthly
	if req.Plan == "year" {
		price = s.billing.yearly
	}
	if s.billing.active(u.ID) {
		apiError(ctx, fasthttp.StatusConflict, "you already have an active plan")
		return
	}
	f := neturl.Values{}
	f.Set("mode", "subscription")
	f.Set("line_items[0][price]", price)
	f.Set("line_items[0][quantity]", "1")
	f.Set("success_url", s.cfg.SiteBaseURL+"/author?subscribed=1")
	f.Set("cancel_url", s.cfg.SiteBaseURL+"/pricing")
	f.Set("client_reference_id", u.ID)
	f.Set("subscription_data[metadata][user_id]", u.ID)
	f.Set("allow_promotion_codes", "true")
	if c := s.billing.customer(u.ID); c != "" {
		f.Set("customer", c)
	} else {
		f.Set("customer_email", u.Email)
	}
	out, err := s.billing.stripe("POST", "/checkout/sessions", f)
	if err != nil {
		log.Printf("checkout: %v", err)
		apiError(ctx, fasthttp.StatusBadGateway, "could not start checkout")
		return
	}
	writeJSON(ctx, 200, map[string]any{"url": str(out, "url")})
}

func (s *Server) handlePortal(ctx *fasthttp.RequestCtx) {
	u := s.user(ctx)
	if u == nil {
		apiError(ctx, fasthttp.StatusUnauthorized, "sign in")
		return
	}
	c := ""
	if s.billing.enabled() {
		c = s.billing.customer(u.ID)
	}
	if c == "" {
		apiError(ctx, fasthttp.StatusNotFound, "no subscription found")
		return
	}
	f := neturl.Values{}
	f.Set("customer", c)
	f.Set("return_url", s.cfg.SiteBaseURL+"/pricing")
	out, err := s.billing.stripe("POST", "/billing_portal/sessions", f)
	if err != nil {
		apiError(ctx, fasthttp.StatusBadGateway, "could not open billing portal")
		return
	}
	writeJSON(ctx, 200, map[string]any{"url": str(out, "url")})
}

type subInfo struct {
	Active    bool   `json:"active"`
	Status    string `json:"status"`
	RenewsAt  string `json:"renews_at,omitempty"`
	HasPortal bool   `json:"has_portal"`
}

func (b *billing) info(userID string) subInfo {
	var si subInfo
	var cust string
	var end sql.NullTime
	_ = b.db.QueryRow(`SELECT status, period_end, customer_id FROM subscriptions WHERE user_id = ?`, userID).Scan(&si.Status, &end, &cust)
	si.Active = b.active(userID)
	si.HasPortal = cust != ""
	if end.Valid {
		si.RenewsAt = end.Time.UTC().Format("2006-01-02")
	}
	return si
}

func (s *Server) handleAccountAPI(ctx *fasthttp.RequestCtx) {
	u := s.user(ctx)
	if u == nil {
		apiError(ctx, fasthttp.StatusUnauthorized, "sign in")
		return
	}
	mine, _ := s.stories.listByUser(u.ID, 200)
	list := make([]map[string]any, 0, len(mine))
	for _, st := range mine {
		list = append(list, map[string]any{"id": st.ID, "title": st.Title, "url": "/story/" + st.ID,
			"edit": "/author?id=" + st.ID, "public": st.Public, "pages": len(st.Pages), "minutes": st.ReadingMinutes})
	}
	writeJSON(ctx, 200, map[string]any{
		"email": u.Email, "name": u.DisplayName(),
		"subscription": s.billing.info(u.ID), "stories": list,
	})
}

func (s *Server) handleAccount(ctx *fasthttp.RequestCtx) {
	u := s.user(ctx)
	if u == nil {
		ctx.Redirect(s.loginURL(s.cfg.SiteBaseURL+"/account"), fasthttp.StatusFound)
		return
	}
	s.render(ctx, "account.html", map[string]any{
		"Meta": Meta{Title: "Your account — Reading Time", Desc: siteDesc}, "User": u, "Cfg": s.cfg,
		"LoginURL": s.loginURL(s.cfg.SiteBaseURL + "/account"),
	})
}

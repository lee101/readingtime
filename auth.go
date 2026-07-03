package main

import (
	"crypto/sha256"
	"database/sql"
	"encoding/base64"
	"strings"
	"time"

	"github.com/valyala/fasthttp"
)

// Cookie names match app.nz (app-site/server/main.go). The shared cookie is set
// on the `.app.nz` domain so it is sent to readingtime.app.nz automatically —
// that is what makes login seamless: if you are signed in on app.nz you are
// signed in here, no extra round-trip.
const (
	sessionCookie       = "__Host-appnz_sso_session"
	sharedSessionCookie = "appnz_session"
)

// User is the subset of the shared app.nz users row we need.
type User struct {
	ID         string `json:"id"`
	Email      string `json:"email"`
	Handle     string `json:"handle"`
	FreeCredit int    `json:"free_credits"`
	PaidCredit int    `json:"paid_credits"`
	IsAdmin    bool   `json:"is_admin"`
}

func (u *User) Credits() int { return u.FreeCredit + u.PaidCredit }

func (u *User) DisplayName() string {
	if u == nil {
		return ""
	}
	if u.Handle != "" {
		return u.Handle
	}
	if i := strings.IndexByte(u.Email, '@'); i > 0 {
		return u.Email[:i]
	}
	return u.Email
}

// authStore reads the shared app.nz SSO/billing DB (read-only path of trust).
type authStore struct {
	db *sql.DB
}

func newAuthStore(path string) (*authStore, error) {
	path = strings.TrimSpace(path)
	if path == "" {
		return nil, nil
	}
	// Read-only-ish: we only SELECT here. Open with WAL + busy timeout to play
	// nicely with the app.nz writer process sharing this file.
	db, err := sql.Open("sqlite3", path+"?_journal_mode=WAL&_busy_timeout=5000&mode=ro")
	if err != nil {
		return nil, err
	}
	db.SetMaxOpenConns(4)
	db.SetMaxIdleConns(4)
	return &authStore{db: db}, nil
}

// hashToken matches app.nz: sha256 -> base64 RawURLEncoding. The cookie carries
// the raw token; the DB stores its hash.
func hashToken(token string) string {
	sum := sha256.Sum256([]byte(token))
	return base64.RawURLEncoding.EncodeToString(sum[:])
}

// sessionToken returns the raw session token from the request cookies (and which
// cookie carried it). The raw token is what we forward to the AI gateway so it
// authenticates the same user and bills their credits.
func sessionToken(ctx *fasthttp.RequestCtx) string {
	for _, name := range []string{sessionCookie, sharedSessionCookie} {
		if tok := strings.TrimSpace(string(ctx.Request.Header.Cookie(name))); tok != "" {
			return tok
		}
	}
	return ""
}

// userFromRequest validates the app.nz session cookie against sso_sessions and
// returns the user (or nil if not signed in / expired).
func (a *authStore) userFromRequest(ctx *fasthttp.RequestCtx) *User {
	if a == nil {
		return nil
	}
	tok := sessionToken(ctx)
	if tok == "" {
		return nil
	}
	var userID string
	var expiresAt time.Time
	err := a.db.QueryRow("SELECT user_id, expires_at FROM sso_sessions WHERE id = ?", hashToken(tok)).
		Scan(&userID, &expiresAt)
	if err != nil {
		return nil
	}
	if time.Now().After(expiresAt) {
		return nil
	}
	return a.userByID(userID)
}

func (a *authStore) userByID(id string) *User {
	var u User
	var handle sql.NullString
	var admin int
	err := a.db.QueryRow(
		`SELECT id, email, COALESCE(handle,''), COALESCE(free_credits,0), COALESCE(paid_credits,0), COALESCE(is_admin,0)
		 FROM users WHERE id = ? AND disabled_at IS NULL`, id).
		Scan(&u.ID, &u.Email, &handle, &u.FreeCredit, &u.PaidCredit, &admin)
	if err != nil {
		return nil
	}
	u.Handle = handle.String
	u.IsAdmin = admin != 0
	return &u
}

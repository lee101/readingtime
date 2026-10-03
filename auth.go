package main

import (
	"crypto/rand"
	"crypto/sha256"
	"database/sql"
	"encoding/base64"
	"errors"
	"net/mail"
	"strings"
	"time"

	"github.com/valyala/fasthttp"
	"golang.org/x/crypto/bcrypt"
)

const sessionCookie = "rt_session"

const sessionTTL = 90 * 24 * time.Hour

type User struct {
	ID      string `json:"id"`
	Email   string `json:"email"`
	Handle  string `json:"handle"`
	IsAdmin bool   `json:"is_admin"`
	Sub     bool   `json:"subscriber"`
}

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

type authStore struct {
	db *pgDB
}

func newAuthStore(db *pgDB) (*authStore, error) {
	if _, err := db.Exec(`
		CREATE TABLE IF NOT EXISTS accounts (
			id            TEXT PRIMARY KEY,
			email         TEXT NOT NULL,
			password_hash TEXT NOT NULL,
			handle        TEXT NOT NULL DEFAULT '',
			is_admin      BOOLEAN NOT NULL DEFAULT FALSE,
			created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
			disabled_at   TIMESTAMPTZ
		);
		CREATE UNIQUE INDEX IF NOT EXISTS accounts_email_idx ON accounts (lower(email));
		CREATE TABLE IF NOT EXISTS sessions (
			id         TEXT PRIMARY KEY,
			user_id    TEXT NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
			expires_at TIMESTAMPTZ NOT NULL,
			created_at TIMESTAMPTZ NOT NULL DEFAULT now()
		);
		CREATE INDEX IF NOT EXISTS sessions_user_idx ON sessions (user_id);
	`); err != nil {
		return nil, err
	}
	return &authStore{db: db}, nil
}

func hashToken(token string) string {
	sum := sha256.Sum256([]byte(token))
	return base64.RawURLEncoding.EncodeToString(sum[:])
}

func newToken() string {
	b := make([]byte, 32)
	_, _ = rand.Read(b)
	return base64.RawURLEncoding.EncodeToString(b)
}

var (
	errEmailTaken = errors.New("an account with that email already exists")
	errBadLogin   = errors.New("wrong email or password")
)

func normEmail(e string) (string, error) {
	e = strings.TrimSpace(e)
	a, err := mail.ParseAddress(e)
	if err != nil || a.Address != e || len(e) > 254 {
		return "", errors.New("enter a valid email address")
	}
	return strings.ToLower(e), nil
}

func (a *authStore) signup(email, password, handle string) (*User, error) {
	email, err := normEmail(email)
	if err != nil {
		return nil, err
	}
	if len(password) < 8 || len(password) > 72 {
		return nil, errors.New("password must be 8 to 72 characters")
	}
	handle = strings.TrimSpace(handle)
	if len(handle) > 40 {
		handle = handle[:40]
	}
	h, err := bcrypt.GenerateFromPassword([]byte(password), bcrypt.DefaultCost)
	if err != nil {
		return nil, err
	}
	u := &User{ID: genID(), Email: email, Handle: handle}
	res, err := a.db.Exec(`INSERT INTO accounts (id, email, password_hash, handle) VALUES (?,?,?,?)
		ON CONFLICT DO NOTHING`, u.ID, u.Email, string(h), u.Handle)
	if err != nil {
		return nil, err
	}
	if n, _ := res.RowsAffected(); n == 0 {
		return nil, errEmailTaken
	}
	return u, nil
}

func (a *authStore) login(email, password string) (*User, error) {
	email = strings.ToLower(strings.TrimSpace(email))
	var u User
	var hash string
	err := a.db.QueryRow(`SELECT id, email, handle, is_admin, password_hash FROM accounts
		WHERE lower(email) = ? AND disabled_at IS NULL`, email).Scan(&u.ID, &u.Email, &u.Handle, &u.IsAdmin, &hash)
	if err != nil {
		bcrypt.CompareHashAndPassword([]byte("$2a$10$7EqJtq98hPqEX7fNZaFWoOhi5BUe1LzW8cD2YbU5Z1m1bZ3Qh7Xqa"), []byte(password))
		return nil, errBadLogin
	}
	if bcrypt.CompareHashAndPassword([]byte(hash), []byte(password)) != nil {
		return nil, errBadLogin
	}
	return &u, nil
}

func (a *authStore) createSession(userID string) (string, time.Time, error) {
	tok := newToken()
	exp := time.Now().Add(sessionTTL)
	_, err := a.db.Exec(`INSERT INTO sessions (id, user_id, expires_at) VALUES (?,?,?)`, hashToken(tok), userID, exp.UTC())
	return tok, exp, err
}

func (a *authStore) deleteSession(tok string) {
	if tok != "" {
		_, _ = a.db.Exec(`DELETE FROM sessions WHERE id = ?`, hashToken(tok))
	}
}

func sessionToken(ctx *fasthttp.RequestCtx) string {
	return strings.TrimSpace(string(ctx.Request.Header.Cookie(sessionCookie)))
}

func (a *authStore) userFromRequest(ctx *fasthttp.RequestCtx) *User {
	if a == nil {
		return nil
	}
	tok := sessionToken(ctx)
	if tok == "" {
		return nil
	}
	var u User
	err := a.db.QueryRow(`SELECT a.id, a.email, a.handle, a.is_admin FROM sessions s
		JOIN accounts a ON a.id = s.user_id
		WHERE s.id = ? AND s.expires_at > now() AND a.disabled_at IS NULL`, hashToken(tok)).
		Scan(&u.ID, &u.Email, &u.Handle, &u.IsAdmin)
	if err != nil {
		if !errors.Is(err, sql.ErrNoRows) {
			return nil
		}
		return nil
	}
	return &u
}

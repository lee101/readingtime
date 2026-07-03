package main

import (
	"crypto/rand"
	"database/sql"
	"encoding/base64"
	"encoding/json"
	"regexp"
	"strings"
	"time"
)

// Story is a user-authored, AI-generated reading book. Pages mirror Book pages
// so the same reveal.js word-highlight reader renders them.
type Story struct {
	ID         string    `json:"id"`
	UserID     string    `json:"user_id"`
	AuthorName string    `json:"author_name"`
	Title      string    `json:"title"`
	Prompt     string    `json:"prompt"`
	CoverURL   string    `json:"cover_url"`
	TextModel  string    `json:"text_model"`
	ImageModel string    `json:"image_model"`
	Public     bool      `json:"public"`
	Pages      []Page    `json:"pages"`
	CreatedAt  time.Time `json:"created_at"`
	UpdatedAt  time.Time `json:"updated_at"`
}

type storyStore struct {
	db *sql.DB
}

func newStoryStore(path string) (*storyStore, error) {
	db, err := sql.Open("sqlite3", path+"?_journal_mode=WAL&_busy_timeout=5000")
	if err != nil {
		return nil, err
	}
	db.SetMaxOpenConns(8)
	db.SetMaxIdleConns(8)
	if _, err := db.Exec(`
		CREATE TABLE IF NOT EXISTS stories (
			id           TEXT PRIMARY KEY,
			user_id      TEXT NOT NULL,
			author_name  TEXT NOT NULL DEFAULT '',
			title        TEXT NOT NULL,
			prompt       TEXT NOT NULL DEFAULT '',
			cover_url    TEXT NOT NULL DEFAULT '',
			text_model   TEXT NOT NULL DEFAULT '',
			image_model  TEXT NOT NULL DEFAULT '',
			public       INTEGER NOT NULL DEFAULT 0,
			pages_json   TEXT NOT NULL,
			created_at   TIMESTAMP NOT NULL,
			updated_at   TIMESTAMP NOT NULL
		);
		CREATE INDEX IF NOT EXISTS idx_stories_user ON stories(user_id, updated_at DESC);
		CREATE INDEX IF NOT EXISTS idx_stories_public ON stories(public, updated_at DESC);
	`); err != nil {
		return nil, err
	}
	return &storyStore{db: db}, nil
}

func (s *storyStore) save(st *Story) error {
	pages, err := json.Marshal(st.Pages)
	if err != nil {
		return err
	}
	now := time.Now().UTC()
	if st.CreatedAt.IsZero() {
		st.CreatedAt = now
	}
	st.UpdatedAt = now
	pub := 0
	if st.Public {
		pub = 1
	}
	_, err = s.db.Exec(`
		INSERT INTO stories (id, user_id, author_name, title, prompt, cover_url, text_model, image_model, public, pages_json, created_at, updated_at)
		VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
		ON CONFLICT(id) DO UPDATE SET
			author_name=excluded.author_name, title=excluded.title, prompt=excluded.prompt,
			cover_url=excluded.cover_url, text_model=excluded.text_model, image_model=excluded.image_model,
			public=excluded.public, pages_json=excluded.pages_json, updated_at=excluded.updated_at`,
		st.ID, st.UserID, st.AuthorName, st.Title, st.Prompt, st.CoverURL, st.TextModel, st.ImageModel,
		pub, string(pages), st.CreatedAt, st.UpdatedAt)
	return err
}

func (s *storyStore) get(id string) (*Story, error) {
	row := s.db.QueryRow(`
		SELECT id, user_id, author_name, title, prompt, cover_url, text_model, image_model, public, pages_json, created_at, updated_at
		FROM stories WHERE id = ?`, id)
	return scanStory(row)
}

func (s *storyStore) listByUser(userID string, limit int) ([]*Story, error) {
	return s.query(`
		SELECT id, user_id, author_name, title, prompt, cover_url, text_model, image_model, public, pages_json, created_at, updated_at
		FROM stories WHERE user_id = ? ORDER BY updated_at DESC LIMIT ?`, userID, limit)
}

func (s *storyStore) listPublic(limit int) ([]*Story, error) {
	return s.query(`
		SELECT id, user_id, author_name, title, prompt, cover_url, text_model, image_model, public, pages_json, created_at, updated_at
		FROM stories WHERE public = 1 ORDER BY updated_at DESC LIMIT ?`, limit)
}

func (s *storyStore) delete(id, userID string) error {
	_, err := s.db.Exec(`DELETE FROM stories WHERE id = ? AND user_id = ?`, id, userID)
	return err
}

func (s *storyStore) query(q string, args ...any) ([]*Story, error) {
	rows, err := s.db.Query(q, args...)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []*Story
	for rows.Next() {
		st, err := scanStory(rows)
		if err != nil {
			return nil, err
		}
		out = append(out, st)
	}
	return out, rows.Err()
}

type scanner interface {
	Scan(dest ...any) error
}

func scanStory(row scanner) (*Story, error) {
	var st Story
	var pub int
	var pagesJSON string
	if err := row.Scan(&st.ID, &st.UserID, &st.AuthorName, &st.Title, &st.Prompt, &st.CoverURL,
		&st.TextModel, &st.ImageModel, &pub, &pagesJSON, &st.CreatedAt, &st.UpdatedAt); err != nil {
		return nil, err
	}
	st.Public = pub != 0
	if pagesJSON != "" {
		_ = json.Unmarshal([]byte(pagesJSON), &st.Pages)
	}
	return &st, nil
}

// --- shared helpers ---

// wordSplit mirrors the original fixtures.py regex: it splits text into
// alternating word / separator tokens (the separator — whitespace plus any
// surrounding punctuation — is kept so the reader can render and skip it). The
// reader treats a token whose first rune is whitespace/punctuation as a
// non-highlightable separator.
var wordSplit = regexp.MustCompile(`([-  ,.;:'!?"…”“]*\s+[- ,.;:'!?"…”“]*)`)

func splitWords(text string) []string {
	return wordSplit.Split(text, -1)
}

// splitWordsKeepSep replicates Python's re.split with a capturing group, which
// keeps the separators interleaved in the result.
func splitWordsKeepSep(text string) []string {
	idx := wordSplit.FindAllStringIndex(text, -1)
	if len(idx) == 0 {
		return []string{text}
	}
	out := make([]string, 0, len(idx)*2+1)
	last := 0
	for _, m := range idx {
		out = append(out, text[last:m[0]]) // word chunk (may be empty)
		out = append(out, text[m[0]:m[1]]) // separator chunk
		last = m[1]
	}
	out = append(out, text[last:])
	return out
}

func genID() string {
	b := make([]byte, 16)
	_, _ = rand.Read(b)
	return base64.RawURLEncoding.EncodeToString(b)
}

func humanizeName(name string) string {
	parts := strings.Split(name, "-")
	for i, p := range parts {
		if p == "" {
			continue
		}
		parts[i] = strings.ToUpper(p[:1]) + p[1:]
	}
	return strings.Join(parts, " ")
}

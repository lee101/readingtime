package main

import (
	"sort"
	"strings"
	"sync"
	"time"
	"unicode"

	"github.com/valyala/fasthttp"
)

type searchDoc struct {
	Title   string `json:"t"`
	Author  string `json:"a,omitempty"`
	Cover   string `json:"c,omitempty"`
	Href    string `json:"h"`
	Minutes int    `json:"m,omitempty"`
	Body    string `json:"b,omitempty"`
}

const searchBodyMax = 600

func tokens(s string) []string {
	return strings.FieldsFunc(strings.ToLower(s), func(r rune) bool {
		return !unicode.IsLetter(r) && !unicode.IsDigit(r)
	})
}

func clip(s string, n int) string {
	if len(s) <= n {
		return s
	}
	return s[:n]
}

func pagesText(pages []Page, n int) string {
	var b strings.Builder
	for i, p := range pages {
		if i >= n {
			break
		}
		b.WriteString(p.Text)
		b.WriteByte(' ')
	}
	return b.String()
}

func (s *Server) buildSearchIndex() []searchDoc {
	docs := make([]searchDoc, 0, len(s.bookOrder)+64)
	for _, name := range s.bookOrder {
		b := s.books[name]
		docs = append(docs, searchDoc{
			Title: b.Title, Cover: "/static/kids-book-covers/" + b.CoverImageURL,
			Href: "/book/" + name, Minutes: readingMinutes(b.Pages),
			Body: clip(strings.ToLower(pagesText(b.Pages, 3)), searchBodyMax),
		})
	}
	if pub, err := s.stories.listPublic(1000); err == nil {
		for _, st := range pub {
			c := storyCard(st)
			docs = append(docs, searchDoc{
				Title: c.Title, Author: c.Author, Cover: c.Cover, Href: c.Href, Minutes: c.Minutes,
				Body: clip(strings.ToLower(st.Prompt+" "+pagesText(st.Pages, 3)), searchBodyMax),
			})
		}
	}
	return docs
}

var searchCache struct {
	sync.Mutex
	at   time.Time
	docs []searchDoc
}

func (s *Server) searchIndex() []searchDoc {
	searchCache.Lock()
	defer searchCache.Unlock()
	if searchCache.docs == nil || time.Since(searchCache.at) > time.Minute {
		searchCache.docs = s.buildSearchIndex()
		searchCache.at = time.Now()
	}
	return searchCache.docs
}

func prefixIn(words []string, q string) bool {
	for _, w := range words {
		if strings.HasPrefix(w, q) {
			return true
		}
	}
	return false
}

// scoreDoc requires every query term to prefix-match some word; title hits
// outweigh author hits, which outweigh body hits. Mirrored in search.js.
func scoreDoc(d *searchDoc, qs []string) int {
	title, author, body := tokens(d.Title), tokens(d.Author), tokens(d.Body)
	total := 0
	for _, q := range qs {
		switch {
		case prefixIn(title, q):
			total += 6
			if len(title) > 0 && strings.HasPrefix(title[0], q) {
				total += 2
			}
		case prefixIn(author, q):
			total += 3
		case prefixIn(body, q):
			total++
		default:
			return 0
		}
	}
	return total
}

func searchDocs(docs []searchDoc, query string, limit int) []searchDoc {
	qs := tokens(query)
	if len(qs) == 0 {
		return nil
	}
	type hit struct {
		d     searchDoc
		score int
	}
	var hits []hit
	for i := range docs {
		if sc := scoreDoc(&docs[i], qs); sc > 0 {
			hits = append(hits, hit{docs[i], sc})
		}
	}
	sort.SliceStable(hits, func(i, j int) bool { return hits[i].score > hits[j].score })
	if limit > 0 && len(hits) > limit {
		hits = hits[:limit]
	}
	out := make([]searchDoc, len(hits))
	for i, h := range hits {
		h.d.Body = ""
		out[i] = h.d
	}
	return out
}

func searchCards(docs []searchDoc) []cardView {
	cards := make([]cardView, len(docs))
	for i, d := range docs {
		cards[i] = cardView{Title: d.Title, Cover: d.Cover, Href: d.Href, Author: d.Author, Minutes: d.Minutes}
	}
	return cards
}

func (s *Server) handleSearch(ctx *fasthttp.RequestCtx) {
	q := string(ctx.QueryArgs().Peek("q"))
	ctx.Response.Header.Set("Cache-Control", "public, max-age=30")
	writeJSON(ctx, 200, map[string]any{"q": q, "results": searchDocs(s.searchIndex(), q, 60)})
}

func (s *Server) handleSearchIndex(ctx *fasthttp.RequestCtx) {
	ctx.Response.Header.Set("Cache-Control", "public, max-age=60")
	writeJSON(ctx, 200, s.searchIndex())
}

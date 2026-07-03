package main

import (
	"bytes"
	"html/template"
	"strings"

	"github.com/valyala/fasthttp"
)

func loadTemplates() (*template.Template, error) {
	return template.New("").Funcs(template.FuncMap{
		"upper": strings.ToUpper,
	}).ParseGlob("templates/*.html")
}

func (s *Server) render(ctx *fasthttp.RequestCtx, name string, data any) {
	var buf bytes.Buffer
	if err := s.tmpl.ExecuteTemplate(&buf, name, data); err != nil {
		ctx.SetStatusCode(fasthttp.StatusInternalServerError)
		ctx.SetContentType("text/plain; charset=utf-8")
		ctx.WriteString("template error: " + err.Error())
		return
	}
	ctx.SetContentType("text/html; charset=utf-8")
	ctx.Write(buf.Bytes())
}

// --- view models ---

type Meta struct {
	Title, Desc, Canonical, Image string
}

// PageView is a fully resolved page ready for the reader template.
type PageView struct {
	HTML      template.HTML // pre-rendered reading-word spans
	Image     string        // resolved image URL ("" if none)
	Layout    string
	DarkColor bool
	CSS       template.CSS
}

// ReaderView drives reader.html for both sample books and AI stories.
type ReaderView struct {
	Meta      Meta
	Title     string
	AudioLink string
	SubsLink  string
	Pages     []PageView
	User      *User
	Cfg       Config
	LoginURL  string
	BackHref  string
}

const separatorRunes = " \n\t-,.;:'!?\"<…”“"

// renderPage builds the highlightable word spans for one page, continuing the
// book-wide word counter (used for span ids + audio sync), mirroring the
// original jinja2 reader exactly.
func renderPage(words []string, pageIdx, counter int) (template.HTML, int) {
	var b strings.Builder
	first := true
	for _, w := range words {
		if w == "" {
			continue
		}
		r := []rune(w)
		if strings.ContainsRune(separatorRunes, r[0]) {
			b.WriteString(template.HTMLEscapeString(w))
			continue
		}
		b.WriteString(`<span id="word-`)
		b.WriteString(itoa(counter))
		b.WriteString(`" class="reading-word" tabindex="0"`)
		if first {
			b.WriteString(` onfocus="readingtime.wordFocus(`)
			b.WriteString(itoa(pageIdx))
			b.WriteString(`, `)
			b.WriteString(itoa(counter))
			b.WriteString(`)"`)
			first = false
		}
		b.WriteString(`>`)
		b.WriteString(template.HTMLEscapeString(w))
		b.WriteString(`</span>`)
		counter++
	}
	return template.HTML(b.String()), counter
}

// cssSafe wraps per-page CSS authored in our own books.json as trusted CSS.
func cssSafe(s string) template.CSS { return template.CSS(s) }

func itoa(n int) string {
	if n == 0 {
		return "0"
	}
	var buf [20]byte
	i := len(buf)
	for n > 0 {
		i--
		buf[i] = byte('0' + n%10)
		n /= 10
	}
	return string(buf[i:])
}

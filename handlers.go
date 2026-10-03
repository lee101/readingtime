package main

import (
	"encoding/base64"
	"encoding/json"
	"math/rand/v2"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"time"

	"github.com/valyala/fasthttp"
)

// ---------- helpers ----------

func (s *Server) user(ctx *fasthttp.RequestCtx) *User {
	if s.auth == nil {
		return nil
	}
	u := s.auth.userFromRequest(ctx)
	if u != nil {
		u.Sub = s.billing.subscriber(u)
	}
	return u
}

func writeJSON(ctx *fasthttp.RequestCtx, status int, v any) {
	ctx.SetStatusCode(status)
	ctx.SetContentType("application/json; charset=utf-8")
	_ = json.NewEncoder(ctx).Encode(v)
}

func apiError(ctx *fasthttp.RequestCtx, status int, msg string) {
	writeJSON(ctx, status, map[string]any{"error": msg})
}

func (s *Server) loginURL(returnTo string) string {
	return "/login?next=" + qesc(strings.TrimPrefix(returnTo, s.cfg.SiteBaseURL))
}

func qesc(s string) string {
	r := strings.NewReplacer(":", "%3A", "/", "%2F", "?", "%3F", "&", "%26", "=", "%3D", " ", "%20")
	return r.Replace(s)
}

// returnTo resolves a post-auth landing URL on readingtime from an untrusted
// `next` value, refusing to redirect off-site (the value rides through the
// app.nz login round-trip, so we keep it scoped to our own origin).
func (s *Server) returnTo(next string) string {
	next = strings.TrimSpace(next)
	switch {
	case next == "":
		return s.cfg.SiteBaseURL + "/"
	case strings.HasPrefix(next, "/") && !strings.HasPrefix(next, "//"):
		return s.cfg.SiteBaseURL + next
	case strings.HasPrefix(next, s.cfg.SiteBaseURL):
		return next
	default:
		return s.cfg.SiteBaseURL + "/"
	}
}

// ---------- pages ----------

type cardView struct {
	Title, Cover, Href, Author string
	Minutes                    int
}

type homeView struct {
	Meta        Meta
	User        *User
	Cfg         Config
	LoginURL    string
	Library     []cardView
	MyStories   []cardView
	Bands       []bandView
	ActiveBand  string
	BandActive  bool
	Orders      []orderView
	ActiveOrder string
	OrderActive bool
	Reshuffle   string
	Q           string
	Results     []cardView
}

func (s *Server) applySearch(ctx *fasthttp.RequestCtx, v *homeView) {
	v.Q = strings.TrimSpace(string(ctx.QueryArgs().Peek("q")))
	if v.Q != "" {
		v.Results = searchCards(searchDocs(s.searchIndex(), v.Q, 60))
	}
}

// bandView is one chip in the reading-time filter.
type bandView struct {
	ID     string
	Label  string
	Count  int
	Active bool
	Href   string
}

// orderView is one chip in the shelf-order control.
type orderView struct {
	ID     string
	Label  string
	Active bool
	Href   string
}

// libraryOrders are the ways a reading shelf can be ordered. "new" is the feed a
// returning reader wants; "mix" is the one that matters at library size, because
// four hundred stories in updated_at order is a wall of the last batch and
// nothing else; the two reading-time orders are for a parent who already knows
// how long tonight's read has to be.
var libraryOrders = []struct{ ID, Label string }{
	{"new", "Newest"},
	{"mix", "Shuffled"},
	{"short", "Shortest"},
	{"long", "Longest"},
}

// orderOf reads `?o=`, falling back to def so an unknown value shows the page's
// own default order rather than an empty parameter.
func orderOf(ctx *fasthttp.RequestCtx, def string) string {
	want := string(ctx.QueryArgs().Peek("o"))
	for _, order := range libraryOrders {
		if order.ID == want {
			return want
		}
	}
	return def
}

// shelfHref builds the link for a chip, keeping the other half of the filter.
// The default order is left out of the query so the plain URL stays canonical.
func shelfHref(path, band, order, def, salt string) string {
	query := "?"
	first := true
	add := func(key, value string) {
		if value == "" || (key == "o" && value == def) {
			return
		}
		if !first {
			query += "&"
		}
		query += key + "=" + qesc(value)
		first = false
	}
	add("t", band)
	add("o", order)
	add("s", salt)
	if first {
		return path
	}
	return path + query
}

// orderCards sorts a shelf in place. The mix is seeded by the day and the `?s=`
// salt, so the order holds still while a reader browses and turns over overnight;
// the reshuffle control only bumps the salt.
func orderCards(cards []cardView, order, salt string) {
	switch order {
	case "short":
		sort.SliceStable(cards, func(i, j int) bool { return cards[i].Minutes < cards[j].Minutes })
	case "long":
		sort.SliceStable(cards, func(i, j int) bool { return cards[i].Minutes > cards[j].Minutes })
	case "mix":
		day := uint64(time.Now().UTC().Unix() / 86400)
		rng := rand.New(rand.NewPCG(day, uint64(len(salt)+7)*0x9e3779b97f4a7c15+hashString(salt)))
		for i := len(cards) - 1; i > 0; i-- {
			j := rng.IntN(i + 1)
			cards[i], cards[j] = cards[j], cards[i]
		}
	}
}

// hashString is FNV-1a, so any salt the reshuffle control invents lands in a
// different permutation without having to be numeric.
func hashString(s string) uint64 {
	const prime = 0x100000001b3
	hash := uint64(0xcbf29ce484222325)
	for i := 0; i < len(s); i++ {
		hash = (hash ^ uint64(s[i])) * prime
	}
	return hash
}

// orderBars is the order chip row for a shelf, each chip carrying the reading-time
// band the reader already chose.
func orderBars(path, band, order, def, salt string) []orderView {
	bars := make([]orderView, 0, len(libraryOrders))
	for _, o := range libraryOrders {
		bars = append(bars, orderView{
			ID: o.ID, Label: o.Label, Active: o.ID == order,
			Href: shelfHref(path, band, o.ID, def, salt),
		})
	}
	return bars
}

// readingBands are the library's reading-time filters. The "all" chip has a
// zero id, which is also what an absent `?t=` selects, so an unknown value
// falls back to showing everything rather than an empty library.
var readingBands = []struct {
	ID, Label string
	Min, Max  int
}{
	{"", "Any length", 0, 0},
	{"1-5", "Under 5 min", 1, 5},
	{"6-10", "5-10 min", 6, 10},
	{"11-20", "10-20 min", 11, 20},
	{"21-30", "20-30 min", 21, 30},
	{"31", "30+ min", 31, 0},
}

func inBand(minutes, min, max int) bool {
	if min <= 1 && max == 0 {
		return true
	}
	if minutes < min {
		return false
	}
	return max == 0 || minutes <= max
}

// applyBands annotates a card list with its band chips and returns the cards
// inside the active band, so the chips can show what each band would yield.
// Each chip links back with the shelf order it was clicked under.
func applyBands(cards []cardView, active, path, order, def, salt string) ([]cardView, []bandView) {
	bands := make([]bandView, 0, len(readingBands))
	kept := make([]cardView, 0, len(cards))
	for _, band := range readingBands {
		count := 0
		for _, card := range cards {
			if !inBand(card.Minutes, band.Min, band.Max) {
				continue
			}
			count++
			if band.ID == active {
				kept = append(kept, card)
			}
		}
		bands = append(bands, bandView{
			ID: band.ID, Label: band.Label, Count: count, Active: band.ID == active,
			Href: shelfHref(path, band.ID, order, def, salt),
		})
	}
	return kept, bands
}

// activeBand reads `?t=`, falling back to the "any length" band.
func activeBand(ctx *fasthttp.RequestCtx) string {
	want := string(ctx.QueryArgs().Peek("t"))
	for _, band := range readingBands {
		if band.ID == want {
			return want
		}
	}
	return ""
}

const siteDesc = "Reading Time is an AI storytelling & reading app for kids. Stories light up word-by-word as they're narrated, making learning to read easier — and you can generate whole illustrated picture books with AI."

func (s *Server) meta(title, desc, path string) Meta {
	return Meta{Title: title, Desc: desc, Canonical: s.cfg.SiteBaseURL + path}
}

// sampleCards are the books shipped in books.json, in their own order.
func (s *Server) sampleCards() []cardView {
	cards := make([]cardView, 0, len(s.bookOrder))
	for _, name := range s.bookOrder {
		b := s.books[name]
		cards = append(cards, cardView{
			Title:   b.Title,
			Cover:   "/static/kids-book-covers/" + b.CoverImageURL,
			Href:    "/book/" + name,
			Minutes: readingMinutes(b.Pages),
		})
	}
	return cards
}

// shelf is the reading-time filter and the order control for one page of the
// library. def is the page's own default order, so the plain URL stays canonical
// and the chips know which one is the fallback.
func shelf(ctx *fasthttp.RequestCtx, path, def string) (band, order, salt string, bars []orderView) {
	band = activeBand(ctx)
	order = orderOf(ctx, def)
	salt = string(ctx.QueryArgs().Peek("s"))
	return band, order, salt, orderBars(path, band, order, def, salt)
}

func (s *Server) handleHome(ctx *fasthttp.RequestCtx) {
	u := s.user(ctx)
	band, order, salt, bars := shelf(ctx, "/", "new")
	// The sample books and the AI stories belong in one grid, so they are one
	// list: filtered and ordered together, not shelf by shelf.
	library := s.sampleCards()
	if pub, err := s.stories.listPublic(400); err == nil {
		for _, st := range pub {
			library = append(library, storyCard(st))
		}
	}
	v := homeView{
		Meta: s.meta("Reading Time — AI storytelling & reading app for kids", siteDesc, "/"),
		User: u, Cfg: s.cfg, LoginURL: s.loginURL(s.cfg.SiteBaseURL + "/"),
		ActiveBand: band, BandActive: band != "",
		Orders: bars, ActiveOrder: order, OrderActive: order != "new",
		Reshuffle: shelfHref("/", band, order, "new", salt),
	}
	if u != nil {
		if mine, err := s.stories.listByUser(u.ID, 48); err == nil {
			for _, st := range mine {
				v.MyStories = append(v.MyStories, storyCard(st))
			}
		}
	}
	// One filter over everything a reader can open, so the counts on the chips
	// describe the whole library rather than one shelf.
	v.Library, v.Bands = applyBands(library, band, "/", order, "new", salt)
	orderCards(v.Library, order, salt)
	s.applySearch(ctx, &v)
	s.render(ctx, "home.html", v)
}

func storyCard(st *Story) cardView {
	cover := st.CoverURL
	if cover == "" {
		for _, p := range st.Pages {
			if p.ImageURL != "" {
				cover = p.ImageURL
				break
			}
		}
	}
	return cardView{
		Title: st.Title, Cover: cover, Href: "/story/" + st.ID,
		Author: st.AuthorName, Minutes: st.ReadingMinutes,
	}
}

func (s *Server) handleAuthor(ctx *fasthttp.RequestCtx) {
	u := s.user(ctx)
	s.render(ctx, "author.html", map[string]any{
		"Meta":     s.meta("Create a story — Reading Time", "Describe an idea and generate a complete illustrated picture book with AI, then read it together with word-by-word highlighting..", "/author"),
		"User":     u,
		"Cfg":      s.cfg,
		"LoginURL": s.loginURL(s.cfg.SiteBaseURL + "/author"),
	})
}

func (s *Server) handleStories(ctx *fasthttp.RequestCtx) {
	band, order, salt, bars := shelf(ctx, "/stories", "mix")
	var stories []cardView
	if pub, err := s.stories.listPublic(400); err == nil {
		for _, st := range pub {
			stories = append(stories, storyCard(st))
		}
	}
	v := homeView{
		Meta: s.meta("Story gallery — Reading Time", "Browse illustrated picture books created with AI by the Reading Time community — read any of them together with word-by-word highlighting.", "/stories"),
		User: s.user(ctx), Cfg: s.cfg, LoginURL: s.loginURL(s.cfg.SiteBaseURL + "/stories"),
		ActiveBand: band, BandActive: band != "",
		Orders: bars, ActiveOrder: order, OrderActive: order != "mix",
		Reshuffle: shelfHref("/stories", band, order, "mix", salt),
	}
	v.Library, v.Bands = applyBands(stories, band, "/stories", order, "mix", salt)
	orderCards(v.Library, order, salt)
	s.applySearch(ctx, &v)
	s.render(ctx, "stories.html", v)
}

func (s *Server) handlePricing(ctx *fasthttp.RequestCtx) {
	s.render(ctx, "pricing.html", map[string]any{
		"Meta":     s.meta("Pricing — Reading Time Unlimited", "Read your first book free, then go Unlimited: every book, unlimited AI story writing and illustration. $9/month or $90/year.", "/pricing"),
		"User":     s.user(ctx),
		"Enabled":  s.billing.enabled(),
		"Cfg":      s.cfg,
		"LoginURL": s.loginURL(s.cfg.SiteBaseURL + "/author"),
	})
}

func (s *Server) handleSitemap(ctx *fasthttp.RequestCtx) {
	var b strings.Builder
	b.WriteString("<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n")
	b.WriteString("<urlset xmlns=\"http://www.sitemaps.org/schemas/sitemap/0.9\">\n")
	add := func(path, lastmod string) {
		b.WriteString("<url><loc>")
		b.WriteString(s.cfg.SiteBaseURL + path)
		b.WriteString("</loc>")
		if lastmod != "" {
			b.WriteString("<lastmod>" + lastmod + "</lastmod>")
		}
		b.WriteString("</url>\n")
	}
	add("/", "")
	add("/author", "")
	add("/stories", "")
	add("/pricing", "")
	for _, name := range s.bookOrder {
		add("/book/"+name, "")
	}
	if pub, err := s.stories.listPublic(500); err == nil {
		for _, st := range pub {
			add("/story/"+st.ID, st.UpdatedAt.UTC().Format("2006-01-02"))
		}
	}
	b.WriteString("</urlset>\n")
	ctx.SetContentType("application/xml; charset=utf-8")
	ctx.WriteString(b.String())
}

func (s *Server) handleBook(ctx *fasthttp.RequestCtx, name string) {
	name = strings.Trim(name, "/")
	b, ok := s.books[name]
	if !ok {
		s.handleNotFound(ctx)
		return
	}
	if u := s.user(ctx); !s.allowRead(ctx, u, "book:"+name, "") {
		s.renderPaywall(ctx, u, b.Title, "/")
		return
	}
	view := ReaderView{
		Meta:  s.meta(b.Title+" — Reading Time", "Read \""+b.Title+"\" together on Reading Time — each word lights up as it's read aloud, helping kids learn to read.", "/book/"+name),
		Title: b.Title, AudioLink: b.AudioLink, SubsLink: b.SubsLink,
		User: s.user(ctx), Cfg: s.cfg, LoginURL: s.loginURL(s.cfg.SiteBaseURL + "/"), BackHref: "/",
		Minutes: readingMinutes(b.Pages),
	}
	view.Meta.Image = s.cfg.SiteBaseURL + "/static/kids-book-covers/" + b.CoverImageURL
	counter := 0
	for i, p := range b.Pages {
		var html, next = renderPage(p.Words, i, counter)
		counter = next
		img := p.ImageURL
		if img == "" && p.ImagePath != "" {
			img = "/static/bookdata/" + name + "/" + p.ImagePath
		}
		view.Pages = append(view.Pages, PageView{
			HTML: html, Image: img, Layout: p.Layout, DarkColor: p.DarkColor,
			CSS: cssSafe(p.CSS),
		})
	}
	s.render(ctx, "reader.html", view)
}

func (s *Server) handleStoryReader(ctx *fasthttp.RequestCtx, id string) {
	id = strings.Trim(id, "/")
	st, err := s.stories.get(id)
	if err != nil || st == nil {
		s.handleNotFound(ctx)
		return
	}
	u := s.user(ctx)
	if !st.Public && (u == nil || u.ID != st.UserID) {
		apiError(ctx, fasthttp.StatusForbidden, "this story is private")
		return
	}
	if !s.allowRead(ctx, u, "story:"+st.ID, st.UserID) {
		s.renderPaywall(ctx, u, st.Title, "/")
		return
	}
	desc := "\"" + st.Title + "\""
	if st.AuthorName != "" {
		desc += " by " + st.AuthorName
	}
	desc += " — an AI-generated picture book on Reading Time. Read along as each word lights up."
	view := ReaderView{
		Meta:  s.meta(st.Title+" — Reading Time", desc, "/story/"+st.ID),
		Title: st.Title, User: u, Cfg: s.cfg, LoginURL: s.loginURL(s.cfg.SiteBaseURL + "/"), BackHref: "/",
		Minutes: st.ReadingMinutes,
	}
	if c := storyCard(st).Cover; strings.HasPrefix(c, "/") {
		view.Meta.Image = s.cfg.SiteBaseURL + c
	} else {
		view.Meta.Image = c
	}
	counter := 0
	for i, p := range st.Pages {
		words := p.Words
		if len(words) == 0 {
			words = splitWordsKeepSep(p.Text)
		}
		html, next := renderPage(words, i, counter)
		counter = next
		view.Pages = append(view.Pages, PageView{HTML: html, Image: p.ImageURL})
	}
	s.render(ctx, "reader.html", view)
}

func (s *Server) handleNotFound(ctx *fasthttp.RequestCtx) {
	ctx.SetStatusCode(fasthttp.StatusNotFound)
	s.render(ctx, "404.html", map[string]any{
		"Meta":     Meta{Title: "Not found — Reading Time", Desc: siteDesc},
		"Cfg":      s.cfg,
		"User":     s.user(ctx),
		"LoginURL": s.loginURL(s.cfg.SiteBaseURL + "/"),
	})
}

// ---------- JSON API ----------

func (s *Server) handleMe(ctx *fasthttp.RequestCtx) {
	u := s.user(ctx)
	if u == nil {
		writeJSON(ctx, 200, map[string]any{"signedIn": false, "loginUrl": s.loginURL(s.cfg.SiteBaseURL + "/author")})
		return
	}
	writeJSON(ctx, 200, map[string]any{
		"signedIn":   true,
		"name":       u.DisplayName(),
		"email":      u.Email,
		"subscriber": u.Sub,
		"accountUrl": "/account",
	})
}

func (s *Server) handleModels(ctx *fasthttp.RequestCtx) {
	text, image, err := s.gw.listModels(sessionToken(ctx))
	if err != nil {
		// Fall back to curated defaults so the picker still works offline.
		writeJSON(ctx, 200, map[string]any{
			"text": preferredTextModels, "image": preferredImageModels, "degraded": true,
		})
		return
	}
	writeJSON(ctx, 200, map[string]any{"text": text, "image": image})
}

type generateReq struct {
	Prompt   string `json:"prompt"`
	Model    string `json:"model"`
	Pages    int    `json:"pages"`
	Audience string `json:"audience"`
}

type genPage struct {
	Text        string `json:"text"`
	ImagePrompt string `json:"image_prompt"`
}

type genResult struct {
	Title string    `json:"title"`
	Pages []genPage `json:"pages"`
}

func (s *Server) handleGenerate(ctx *fasthttp.RequestCtx) {
	u := s.user(ctx)
	if u == nil {
		apiError(ctx, fasthttp.StatusUnauthorized, "sign in to generate stories")
		return
	}
	var req generateReq
	if err := json.Unmarshal(ctx.PostBody(), &req); err != nil {
		apiError(ctx, fasthttp.StatusBadRequest, "invalid request")
		return
	}
	req.Prompt = strings.TrimSpace(req.Prompt)
	if req.Prompt == "" {
		apiError(ctx, fasthttp.StatusBadRequest, "please describe the story you want")
		return
	}
	if req.Pages < 3 {
		req.Pages = 6
	}
	if req.Pages > 16 {
		req.Pages = 16
	}
	if req.Model == "" || req.Model == "auto" {
		req.Model = unlimitedModel
	}
	if req.Audience == "" {
		req.Audience = "ages 4-8"
	}

	sys := "You are a master children's picture-book author. Write warm, vivid, age-appropriate " +
		"stories with simple, rhythmic sentences a child can follow word-by-word. Respond ONLY with " +
		"minified JSON, no markdown fences, of the exact shape: " +
		`{"title":"string","pages":[{"text":"1-3 short sentences","image_prompt":"a concrete, vivid illustration description in a consistent art style"}]}.`
	user := "Write a " + itoa(req.Pages) + "-page picture book for " + req.Audience + ".\n" +
		"Story idea: " + req.Prompt + "\n" +
		"Keep each page's text short (1-3 sentences). Make image_prompt for every page describe the same " +
		"characters and a consistent, beautiful illustration style so the pictures feel like one book."

	tok, ok := s.aiAuth(ctx, u, req.Model, unlimitedModel, "text", dailyTextCap)
	if !ok {
		return
	}
	out, err := s.gw.chatComplete(tok, req.Model, []chatMessage{
		{Role: "system", Content: sys},
		{Role: "user", Content: user},
	}, 4000)
	if err != nil {
		s.aiError(ctx, err)
		return
	}
	result, err := parseStoryJSON(out)
	if err != nil {
		apiError(ctx, fasthttp.StatusBadGateway, "the model returned an unexpected format — try again or pick another model")
		return
	}
	writeJSON(ctx, 200, result)
}

type illustrateReq struct {
	Prompt string `json:"prompt"`
	Model  string `json:"model"`
	Style  string `json:"style"`
	Size   string `json:"size"`
}

func (s *Server) handleIllustrate(ctx *fasthttp.RequestCtx) {
	u := s.user(ctx)
	if u == nil {
		apiError(ctx, fasthttp.StatusUnauthorized, "sign in to illustrate pages")
		return
	}
	var req illustrateReq
	if err := json.Unmarshal(ctx.PostBody(), &req); err != nil {
		apiError(ctx, fasthttp.StatusBadRequest, "invalid request")
		return
	}
	prompt := strings.TrimSpace(req.Prompt)
	if prompt == "" {
		apiError(ctx, fasthttp.StatusBadRequest, "missing image prompt")
		return
	}
	if req.Style != "" {
		prompt = prompt + ", " + req.Style
	}
	if req.Model == "" || req.Model == "openpaths/auto-image" {
		req.Model = "ra2"
	}
	tok, ok := s.aiAuth(ctx, u, req.Model, "ra2", "img", dailyImageCap)
	if !ok {
		return
	}
	imgURL, b64, err := s.gw.generateImage(tok, req.Model, prompt, req.Size)
	if err != nil {
		s.aiError(ctx, err)
		return
	}
	if imgURL == "" && b64 != "" {
		imgURL, err = s.saveGeneratedImage(u.ID, b64)
		if err != nil {
			apiError(ctx, fasthttp.StatusInternalServerError, "could not store generated image")
			return
		}
	}
	writeJSON(ctx, 200, map[string]any{"url": imgURL})
}

type savePageReq struct {
	Text        string `json:"text"`
	ImageURL    string `json:"image_url"`
	ImagePrompt string `json:"image_prompt"`
}

type saveStoryReq struct {
	ID         string        `json:"id"`
	Title      string        `json:"title"`
	Prompt     string        `json:"prompt"`
	TextModel  string        `json:"text_model"`
	ImageModel string        `json:"image_model"`
	Public     bool          `json:"public"`
	Pages      []savePageReq `json:"pages"`
}

func (s *Server) handleSaveStory(ctx *fasthttp.RequestCtx) {
	u := s.user(ctx)
	if u == nil {
		apiError(ctx, fasthttp.StatusUnauthorized, "sign in to save stories")
		return
	}
	var req saveStoryReq
	if err := json.Unmarshal(ctx.PostBody(), &req); err != nil {
		apiError(ctx, fasthttp.StatusBadRequest, "invalid request")
		return
	}
	if strings.TrimSpace(req.Title) == "" {
		req.Title = "Untitled Story"
	}
	if len(req.Pages) == 0 {
		apiError(ctx, fasthttp.StatusBadRequest, "a story needs at least one page")
		return
	}
	st := &Story{
		ID: req.ID, UserID: u.ID, AuthorName: u.DisplayName(),
		Title: strings.TrimSpace(req.Title), Prompt: req.Prompt,
		TextModel: req.TextModel, ImageModel: req.ImageModel, Public: req.Public,
	}
	if st.ID == "" {
		st.ID = genID()
	} else {
		// Editing an existing story: ensure ownership.
		if existing, _ := s.stories.get(st.ID); existing != nil && existing.UserID != u.ID {
			apiError(ctx, fasthttp.StatusForbidden, "not your story")
			return
		}
	}
	for _, p := range req.Pages {
		text := strings.TrimSpace(p.Text)
		st.Pages = append(st.Pages, Page{
			Text:        text,
			Words:       splitWordsKeepSep(text),
			ImageURL:    p.ImageURL,
			ImagePrompt: p.ImagePrompt,
		})
		if st.CoverURL == "" && p.ImageURL != "" {
			st.CoverURL = p.ImageURL
		}
	}
	if err := s.stories.save(st); err != nil {
		apiError(ctx, fasthttp.StatusInternalServerError, "could not save story")
		return
	}
	writeJSON(ctx, 200, map[string]any{"id": st.ID, "url": "/story/" + st.ID})
}

func (s *Server) handleListStories(ctx *fasthttp.RequestCtx) {
	u := s.user(ctx)
	if u == nil {
		writeJSON(ctx, 200, map[string]any{"stories": []any{}})
		return
	}
	mine, _ := s.stories.listByUser(u.ID, 100)
	list := make([]map[string]any, 0, len(mine))
	for _, st := range mine {
		list = append(list, map[string]any{
			"id": st.ID, "title": st.Title, "url": "/story/" + st.ID,
			"cover": storyCard(st).Cover, "public": st.Public, "pages": len(st.Pages),
		})
	}
	writeJSON(ctx, 200, map[string]any{"stories": list})
}

func (s *Server) handleDeleteStory(ctx *fasthttp.RequestCtx) {
	u := s.user(ctx)
	if u == nil {
		apiError(ctx, fasthttp.StatusUnauthorized, "sign in")
		return
	}
	var req struct {
		ID string `json:"id"`
	}
	if err := json.Unmarshal(ctx.PostBody(), &req); err != nil || req.ID == "" {
		apiError(ctx, fasthttp.StatusBadRequest, "missing id")
		return
	}
	if err := s.stories.delete(req.ID, u.ID); err != nil {
		apiError(ctx, fasthttp.StatusInternalServerError, "could not delete")
		return
	}
	writeJSON(ctx, 200, map[string]any{"ok": true})
}

// ---------- support ----------

func (s *Server) aiError(ctx *fasthttp.RequestCtx, err error) {
	switch err {
	case errNotSignedIn:
		apiError(ctx, fasthttp.StatusUnauthorized, "please sign in again")
	case errInsufficientCredits:
		apiError(ctx, fasthttp.StatusPaymentRequired, "out of credits")
	default:
		apiError(ctx, fasthttp.StatusBadGateway, "generation failed: "+err.Error())
	}
}

// saveGeneratedImage persists a base64 image returned by a provider that doesn't
// host the result, and returns its public /static URL.
func (s *Server) saveGeneratedImage(userID, b64 string) (string, error) {
	data, err := base64.StdEncoding.DecodeString(b64)
	if err != nil {
		return "", err
	}
	dir := filepath.Join("static", "generated")
	if err := os.MkdirAll(dir, 0o755); err != nil {
		return "", err
	}
	name := genID() + ".png"
	if err := os.WriteFile(filepath.Join(dir, name), data, 0o644); err != nil {
		return "", err
	}
	return "/static/generated/" + name, nil
}

// parseStoryJSON extracts the story JSON the model returned, tolerating code
// fences and surrounding prose.
func parseStoryJSON(out string) (*genResult, error) {
	out = strings.TrimSpace(out)
	out = strings.TrimPrefix(out, "```json")
	out = strings.TrimPrefix(out, "```")
	out = strings.TrimSuffix(out, "```")
	if i := strings.IndexByte(out, '{'); i >= 0 {
		if j := strings.LastIndexByte(out, '}'); j >= i {
			out = out[i : j+1]
		}
	}
	var r genResult
	if err := json.Unmarshal([]byte(out), &r); err != nil {
		return nil, err
	}
	if strings.TrimSpace(r.Title) == "" {
		r.Title = "My Story"
	}
	return &r, nil
}

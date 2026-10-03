package main

import (
	"fmt"
	"html/template"
	"log"
	"strings"
	"time"

	_ "github.com/mattn/go-sqlite3"
	"github.com/valyala/fasthttp"
)

// staticFS serves /static/* from the on-disk static/ dir (strips the leading
// /static path segment). Scoped to static/ so source files are never exposed.
var staticFS = fasthttp.FSHandler("static", 1)

type Server struct {
	cfg       Config
	books     map[string]*Book
	bookOrder []string
	stories   *storyStore
	auth      *authStore
	billing   *billing
	gw        *gatewayClient
	tmpl      *template.Template
}

func main() {
	cfg := loadConfig()

	books, order, err := loadBooks("books.json")
	if err != nil {
		log.Fatalf("load books: %v", err)
	}
	log.Printf("loaded %d sample books", len(books))

	pg, err := openPG(cfg.DatabaseURL)
	if err != nil {
		log.Fatalf("postgres: %v", err)
	}
	if err := importLegacySQLite(pg, cfg.DBPath); err != nil {
		log.Fatalf("legacy sqlite import: %v", err)
	}
	stories, err := newStoryStore(pg)
	if err != nil {
		log.Fatalf("stories db: %v", err)
	}

	auth, err := newAuthStore(pg)
	if err != nil {
		log.Fatalf("auth store: %v", err)
	}

	bill, err := newBilling(stories.db, cfg)
	if err != nil {
		log.Fatalf("billing: %v", err)
	}
	if err := bill.initFree(); err != nil {
		log.Fatalf("free reads: %v", err)
	}
	if !bill.enabled() {
		log.Printf("STRIPE_SECRET_KEY unset — checkout disabled")
	}

	tmpl, err := loadTemplates()
	if err != nil {
		log.Fatalf("templates: %v", err)
	}

	srv := &Server{
		cfg:       cfg,
		books:     books,
		bookOrder: order,
		stories:   stories,
		auth:      auth,
		billing:   bill,
		gw:        newGatewayClient(cfg.GatewayURL),
		tmpl:      tmpl,
	}

	handler := func(ctx *fasthttp.RequestCtx) {
		path := string(ctx.Path())
		method := string(ctx.Method())
		if cfg.Debug {
			log.Printf("%s %s", method, path)
		}

		if strings.HasPrefix(path, "/api/") {
			ctx.Response.Header.Set("Cache-Control", "no-store")
			if method == "OPTIONS" {
				ctx.SetStatusCode(204)
				return
			}
		}

		switch {
		case path == "/health":
			ctx.SetContentType("text/plain")
			ctx.WriteString("ok")

		case path == "/" && (method == "GET" || method == "HEAD"):
			srv.handleHome(ctx)

		case path == "/author" && method == "GET":
			srv.handleAuthor(ctx)

		case path == "/stories" && method == "GET":
			srv.handleStories(ctx)

		case path == "/api/audio/page" && (method == "GET" || method == "POST"):
			srv.handleAudioPage(ctx)

		case path == "/api/search" && method == "GET":
			srv.handleSearch(ctx)

		case path == "/api/search/index" && method == "GET":
			srv.handleSearchIndex(ctx)

		case path == "/pricing" && method == "GET":
			srv.handlePricing(ctx)

		case path == "/sitemap.xml" && method == "GET":
			srv.handleSitemap(ctx)

		case path == "/login" && method == "GET":
			srv.handleLogin(ctx)

		case path == "/api/auth/signup" && method == "POST":
			srv.handleSignup(ctx)

		case path == "/api/auth/login" && method == "POST":
			srv.handleLoginPost(ctx)

		case path == "/logout" && (method == "GET" || method == "POST"):
			srv.handleLogout(ctx)

		case strings.HasPrefix(path, "/book/") && method == "GET":
			srv.handleBook(ctx, strings.TrimPrefix(path, "/book/"))

		case strings.HasPrefix(path, "/story/") && method == "GET":
			srv.handleStoryReader(ctx, strings.TrimPrefix(path, "/story/"))

		case path == "/api/billing/checkout" && method == "POST":
			srv.handleCheckout(ctx)

		case path == "/api/billing/portal" && method == "POST":
			srv.handlePortal(ctx)

		case path == "/webhook/stripe" && method == "POST":
			srv.handleStripeWebhook(ctx)

		case path == "/api/story/get" && method == "GET":
			srv.handleGetStory(ctx)

		case path == "/api/story/assist" && method == "POST":
			srv.handleAssist(ctx)

		case path == "/account" && method == "GET":
			srv.handleAccount(ctx)

		case path == "/api/account" && method == "GET":
			srv.handleAccountAPI(ctx)

		case path == "/api/me" && method == "GET":
			srv.handleMe(ctx)

		case path == "/api/models" && method == "GET":
			srv.handleModels(ctx)

		case path == "/api/story/generate" && method == "POST":
			srv.handleGenerate(ctx)

		case path == "/api/story/illustrate" && method == "POST":
			srv.handleIllustrate(ctx)

		case path == "/api/story/save" && method == "POST":
			srv.handleSaveStory(ctx)

		case path == "/api/story/list" && method == "GET":
			srv.handleListStories(ctx)

		case path == "/api/story/delete" && method == "POST":
			srv.handleDeleteStory(ctx)

		case path == "/robots.txt":
			ctx.SetContentType("text/plain")
			ctx.WriteString("User-agent: *\nAllow: /\nSitemap: " + cfg.SiteBaseURL + "/sitemap.xml\n")

		case strings.HasPrefix(path, "/static/"):
			staticFS(ctx)
			ctx.Response.Header.Set("Cache-Control", "public, max-age=600, must-revalidate")
			ctx.Response.Header.Set("Access-Control-Allow-Origin", "*")

		default:
			srv.handleNotFound(ctx)
		}
	}

	server := &fasthttp.Server{
		Handler:            handler,
		Name:               "readingtime",
		Concurrency:        4096,
		ReadTimeout:        30 * time.Second,
		WriteTimeout:       200 * time.Second,
		IdleTimeout:        120 * time.Second,
		MaxRequestBodySize: 20 * 1024 * 1024,
		TCPKeepalive:       true,
	}

	addr := fmt.Sprintf(":%d", cfg.Port)
	log.Printf("readingtime listening on %s (gateway=%s, sso=%s)", addr, cfg.GatewayURL, cfg.AppNZDatabasePath)
	if err := server.ListenAndServe(addr); err != nil {
		log.Fatalf("server: %v", err)
	}
}

package main

import (
	"log"
	"os"
	"strconv"
	"strings"

	"github.com/joho/godotenv"
)

// Config holds the readingtime server configuration. Most values integrate the
// app.nz platform: the shared SSO/billing SQLite DB (read for the logged-in
// user) and the local app.nz AI gateway (forwarded the user's session cookie so
// generation is metered against their app.nz credits — exactly like the rest of
// the platform).
type Config struct {
	Port int
	// DBPath is readingtime's own SQLite DB for user-authored stories.
	DBPath string
	// AppNZDatabasePath is the shared app.nz SSO/billing DB. Read-only here: we
	// look up the session cookie -> user. Same file papers.app.nz shares.
	AppNZDatabasePath string
	// GatewayURL is the base URL of the app.nz OpenAI-compatible AI gateway
	// (text + image generation). The user's session cookie is forwarded so the
	// gateway authenticates them and deducts their app.nz credits.
	GatewayURL string
	// LoginURL is where the "Sign in" button bounces to; app.nz sets the
	// shared `.app.nz` session cookie, then returns the user here.
	LoginURL string
	// AccountURL is the app.nz credits/account page (top-up link).
	AccountURL string
	// SiteBaseURL is readingtime's own public origin (for redirect_uri etc.).
	SiteBaseURL string
	// CookieDomain is the parent domain the shared app.nz session cookie is
	// scoped to (".app.nz"). readingtime is a subdomain, so it can expire that
	// cookie on sign-out. Matches app-site's COOKIE_DOMAIN.
	CookieDomain string
	Debug        bool
	Dev          bool
}

func loadConfig() Config {
	if err := godotenv.Load(); err != nil {
		log.Printf("no .env file (using defaults/env)")
	}

	port := 4337
	if p := os.Getenv("PORT"); p != "" {
		if parsed, err := strconv.Atoi(p); err == nil {
			port = parsed
		}
	}

	dbPath := os.Getenv("DB_PATH")
	if dbPath == "" {
		dbPath = "readingtime.db"
	}

	appnzDB := strings.TrimSpace(os.Getenv("APPNZ_DATABASE_PATH"))
	if appnzDB == "" {
		appnzDB = "/nvme0n1-disk/data/appnz-sso.db"
	}

	gateway := strings.TrimSpace(os.Getenv("GATEWAY_URL"))
	if gateway == "" {
		gateway = "http://127.0.0.1:8787"
	}

	login := strings.TrimSpace(os.Getenv("APPNZ_LOGIN_URL"))
	if login == "" {
		login = "https://app.nz/login"
	}
	account := strings.TrimSpace(os.Getenv("APPNZ_ACCOUNT_URL"))
	if account == "" {
		account = "https://app.nz/account"
	}
	site := strings.TrimSpace(os.Getenv("SITE_BASE_URL"))
	if site == "" {
		site = "https://readingtime.app.nz"
	}

	cookieDomain := strings.TrimSpace(os.Getenv("COOKIE_DOMAIN"))
	if cookieDomain == "" {
		cookieDomain = ".app.nz"
	}

	return Config{
		Port:              port,
		DBPath:            dbPath,
		AppNZDatabasePath: appnzDB,
		GatewayURL:        strings.TrimRight(gateway, "/"),
		LoginURL:          login,
		AccountURL:        account,
		SiteBaseURL:       strings.TrimRight(site, "/"),
		CookieDomain:      cookieDomain,
		Debug:             os.Getenv("DEBUG") == "true",
		Dev:               os.Getenv("DEV") == "true",
	}
}

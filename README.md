# readingtime.app.nz

AI storytelling & reading app for kids, on the [app.nz](https://app.nz) network.

- **Read along** — open a book and each word lights up as it's read (reveal.js reader,
  carried over from the original kids' reading app).
- **Author with AI** — describe an idea and generate a complete illustrated picture
  book. Pick your favourite **story model** and **image model**; every generation
  uses your app.nz credits.

## Stack

Go + [fasthttp](https://github.com/valyala/fasthttp), SQLite. Mirrors the
`../papers` integration pattern.

| Concern | How |
| --- | --- |
| **Auth** | Seamless shared-cookie SSO: reads the `.app.nz`-wide `appnz_session` cookie, validates it against `sso_sessions` in the shared `/nvme0n1-disk/data/appnz-sso.db`. Signed in on app.nz ⇒ signed in here. |
| **AI** | Forwards the user's session cookie to the local app.nz OpenAI-compatible gateway (`/v1/chat/completions`, `/v1/images/generations`). The gateway meters the spend against the user's app.nz credits — readingtime never touches the ledger. |
| **Stories** | User-authored books live in `readingtime.db` (`stories` table). Sample books are in `books.json` (converted from the original `fixtures.py`). |

## Run locally

```bash
cp .env.example .env          # adjust if needed
go build -o readingtime .
./readingtime                 # http://127.0.0.1:4337
```

## Deploy (on the server)

```bash
bash deploy.sh
```

Builds the binary, installs `systemd/readingtime.service` + the
`nginx/readingtime.app.nz` vhost (exact server_name beats the `*.app.nz`
wildcard), restarts the service, and health-checks `http://127.0.0.1:4337/health`.

DNS: `readingtime.app.nz` is an `A` record → origin (proxied through Cloudflare),
matching papers/gpubrain. (It previously pointed at the dead App Engine host
`ghs.googlehosted.com`, which is what caused the 503.)

## Endpoints

| Path | What |
| --- | --- |
| `GET /` | Library: sample books, your stories, community stories |
| `GET /book/{name}` | Sample book reader |
| `GET /story/{id}` | AI story reader |
| `GET /author` | AI Story Studio |
| `GET /api/me` | Current user + credits |
| `GET /api/models` | Curated text + image model lists (from the gateway) |
| `POST /api/story/generate` | Generate story text (JSON pages) |
| `POST /api/story/illustrate` | Generate one page image |
| `POST /api/story/save` / `list` / `delete` | Manage saved stories |

## VisualBench

`visualbench.mjs` captures the key pages (desktop + mobile) into `visualbench/`
(gitignored). Run from a dir where `playwright` resolves:

```bash
cd ../app-site && BASE=http://127.0.0.1:4337 node /nvme0n1-disk/code/readingtime/visualbench.mjs
```

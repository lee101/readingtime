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
| **Stories** | User-authored books live in the `stories` table in Postgres (`DATABASE_URL`); a legacy SQLite `readingtime.db` is imported once on first boot. Sample books are in `books.json` (converted from the original Python fixtures). |
| **Reading time** | `stories.word_count` and `stories.reading_minutes`, computed on save and shown on the library card and the reader topbar. 140 words per minute — a slow independent-reader pace, because the app's whole point is helping a child read along. `scripts/backfill_reading_time.py` fills the columns for rows written before they existed. |

## Run locally

Postgres is required: stories, accounts, auth and billing all live there, and the
server exits at startup if `DATABASE_URL` is unset.

```bash
cp .env.example .env          # then set DATABASE_URL
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

## Library order

The library and the gallery each carry an order control next to the reading-time
filter, driven by `?o=`:

| `?o=` | Order |
| --- | --- |
| absent | `new` on `/`, `mix` on `/stories` |
| `new` | newest first, the feed a returning reader wants |
| `mix` | shuffled, re-seeded once a day |
| `short` / `long` | by reading time, either way up |

`mix` is seeded from the UTC day plus an optional `?s=` salt, so the shelf holds
still while a reader browses and turns over overnight; the "Shuffle again" chip
busts the salt with the clock. The default order is left out of the query string,
so `/stories` stays canonical. Both controls carry the other filter's value in
their links, so a band and an order compose.

One combined grid per page: `homeView.Library` is the sample books and the public
stories filtered and ordered together, rather than two shelves each with their
own order.

## Seeding public stories

The author UI needs a signed-in app.nz session, so a batch of gallery stories is
generated server-side instead:

```bash
python3 scripts/seed_stories.py --dry-run                 # show the plan, spend nothing
OPENPATHS_API_KEY=... python3 scripts/seed_stories.py --count 8 --pages 6
OPENPATHS_API_KEY=... python3 scripts/seed_stories.py --no-images   # text only
```

It drives the OpenPaths gateway with a server key using the same prompts as
`/api/story/generate`, defaults to `gpt-5.6-luna` for text and `zimage` for
images (first-party, ~$0.007/image — `--image-model openpaths/auto-image` routes
to gpt-image-2 at ~$0.211/image instead), then inserts `public = 1` rows.

Ideas already present in `stories.prompt` are skipped, so re-running tops the
gallery up rather than duplicating books; when the `IDEAS` list runs dry the
script says so and exits non-zero. Add entries to `IDEAS` for a bigger batch, or
pass `--allow-duplicates` to regenerate an existing idea.

Pages are stored with an empty `words` array on purpose: `handleStoryReader`
recomputes it with `splitWordsKeepSep`, so seeded stories highlight identically
to app-authored ones and the script never duplicates the Go word-split regex.
Rows land straight in SQLite, so no restart is needed — new stories appear on
`/` and `/stories` immediately.

## Manuscript library

`manuscripts/` contains the long-form Markdown collection. The master
`covers.json` currently tracks 210 stories, across the original library, the
12-story science batch, and the 72-story fairy-tale batch. H1 titles are the
story titles; each Markdown file links to its generated cover in
`manuscripts/art/<level>/`.

**The generated artwork is not in this repository.** `manuscripts/art/`,
`static/manuscript-covers/` and `static/manuscript-pages/` are gitignored —
together they are roughly 520MB of images. The Markdown, the world bibles, the
cover manifests (`manuscripts/*-covers.json`) and the page prompts
(`manuscripts/page-prompts/`) *are* committed, so a fresh clone has all the
inputs. Regenerate the images with `scripts/generate_manuscript_covers.py` and
`scripts/generate_manuscript_page_art.py`; both need an AI provider key. Until
you do, a clone renders with missing cover images.

The library is organised as twenty-four shared **story worlds** under
`manuscripts/worlds/`, in three batches of eight. Each world bible names its
setting, the hard rules of its magic, a six-person cast, its places, its visual
style and its nine story slots. Batches one and two use numbers 101-109 and
201-209; batch three, the fairy-tale twists, uses 301-309, 401-409, 501-509,
601-609, 701-709, 801-809, 901-909 and 1001-1009. Within a batch the
accessible stories are the first three of the hundred, intermediate the next
three, advanced the last three, and each level carries a short, medium and
long band. `grand-fantasy-covers.json` holds the first 144 stories and
`fairytale-tales-covers.json` the 72 fairy-tale twists, spanning roughly 6 to
50 minutes of reading time.

The eight fairy-tale-twist worlds each take a familiar tale and give it a hard
magic engine instead of a wish: `the-cinder-ledger` (Cinderella's slipper is a
balance-scale proof), `the-well-bond` (the frog is a water lien),
`the-cloth-of-omission` (the emperor's cloth is woven absence),
`the-three-nights-account` (a true name is the loan), `the-reference-pea` (the
pea is a Bureau standard and the princess an instrument), `the-hearth-ledger`
(Snow White's seven houses are creditors and the apple a delivery),
`the-lamplighter-register` (Aladdin's lamp is leased, not owned) and
`the-house-that-was-promised` (the three pigs are a mortgage dispute with a
licensed wolf).

## The folk-tales batch

`folk-tales-covers.json` is a batch of twelve standalone tales, numbered 110 to
121, in the shape of traditional and tradition-inspired folklore rather than in
one shared invented world. Nothing in the batch shares a setting, a cast or a
canon with anything else; what they share is a register. Each is a self-contained
oral tale with one hard rule of magic, stated once and obeyed to the end, and a
turn that falls out of that rule rather than out of luck. Eight end on a stated
meaning in the village's own voice; four end on an image and leave the meaning
alone. The band 110-121 is reserved for this batch and is free in all three
level directories, so it is not a world range.

The shapes are public-domain ones - the well that answers questions, the tailor
whose seam has to be true, the taboo river-name, the good loaf, the wind that
has to be fed, the tests on the road, the wishing galoshes, the chair nobody will
take, the guest who has to be guessed, the yearly blessing, the talking horse,
the winter in a jar. The tales themselves are newly written and their villages do
not exist.

`manuscripts/worlds/folk-tales.md` carries the batch's shared art direction and
the list of its stories. It is a batch file, not a world bible: its story list is
headed `## Stories`, not `## Titles`, because `check_grand_fantasy_batch.py`
reads every bible in that directory and would reject numbers outside a world
range.

The whole batch, covers and page art, comes from the local OmniServe lane. The
order matters: `publish_manuscripts` has to run before `generate_manuscript_page_art`,
which looks each story row up by its deterministic id and skips the story with
`no story row` when it is not there yet.

```bash
python3 scripts/generate_manuscript_covers.py --manifest manuscripts/folk-tales-covers.json \
    --secret-file /etc/omniserve-qwen.env
python3 scripts/publish_manuscripts.py --manifest manuscripts/folk-tales-covers.json --backup
python3 scripts/generate_manuscript_page_art.py --manifest manuscripts/folk-tales-covers.json \
    --secret-file /etc/omniserve-qwen.env
```

The reverse of that last step is the trap: `publish_manuscripts` rebuilds
`pages_json` from the Markdown on every run, so re-publishing a batch after its
page art exists drops every page `image_url` back to the cover only. Re-run
`generate_manuscript_page_art` afterwards; it skips any page that already has
an image and fills in the rest.

The 168 page prompts live in `manuscripts/page-prompts/folk-*.json`, one fragment
per level, and are keyed to `world: folk-tales` so the page-art generator picks
up the batch's `## Visual Style`.

Cover prompts are 230-270 words, not the one-paragraph form used by the older
manifests. Qwen follows a short cover prompt as a request for a portrait: the
first pass of this batch produced a head-and-shoulders study of a child and two
empty landscapes. The long form works - an establishing sentence naming the place
and the hour, then the figure close in and alone in the frame with a view angle
and a colour lock, then one countable anchor, then a `Style:` block, a "not a
flat cartoon" line, an explicit "Her coat is SCARLET, not pink, not orange" and
a palette. A figure in a big landscape still loses sometimes; when it does, take
the figure out of the deep shot and bring the camera in level with them.

A world bible's `## Visual Style` is appended verbatim to every page prompt, so
its length lands on top of the scene. The first draft of this batch's style
paragraph ran to 214 words, most of it a list of what the picture must not
contain, and the composed page prompts came to 340 words: Qwen returned the
first page of the batch correctly and every page after it as pure noise. The
paragraph is now 58 words of what the picture is, and the same prompts come back
as paintings. Keep a style paragraph under about a hundred words and write it
positively; the other twenty-four bibles are between 113 and 179 words.

## The folk-tales-ii batch, 222 to 233

`folk-tales-ii-covers.json` is a third batch of twelve standalone tales, numbered
222 to 233, in the folk-tales register: one hard rule of magic, stated once by a
villager and obeyed to the end, a turn that falls out of that rule, eight endings
that state a meaning in someone's own voice and four that end on a picture. The
rule is always bookkeeping — a lie, a debt, a name, a word, a measurement — and
never a wish, a monster or a treasure. A hound that will not bark at a liar whose
lie still stands. A cradle that stops when the roof hears something untrue. A
ring that grants one command exactly as worded. Stairs that give one step more
than they take. A water-bride who keeps a slate of truths. A lake that holds the
face of the person you lied to. An orchard that fruits on a settled promise. A
sleeper who wakes only for her true given name. A debt to the river paid in a
year of somebody's life. A common fire that eats only what is said at the
washing line. Reading times run from 6 to 25 minutes.

`manuscripts/worlds/folk-tales-ii.md` carries the batch's art direction and its
story list, headed `## Stories` for the same reason as the other batch files.
The band 222-233 was free in all three level directories and is not a world
range. The run is the standard four steps from a fragment directory:

```bash
python3 scripts/assemble_batch_manifest.py --fragments /tmp/rt-manifest-tales2 \
    --out manuscripts/folk-tales-ii-covers.json
python3 scripts/generate_manuscript_covers.py --manifest manuscripts/folk-tales-ii-covers.json \
    --style painterly --secret-file /etc/omniserve-qwen.env
python3 scripts/publish_manuscripts.py --manifest manuscripts/folk-tales-ii-covers.json --backup
python3 scripts/generate_manuscript_page_art.py --manifest manuscripts/folk-tales-ii-covers.json \
    --style painterly --secret-file /etc/omniserve-qwen.env
```

Cost on this lane: 12 covers at about 45 s and 201 pages at a measured mean of
29.2 s, 2.03 a minute. The batch publishes 213 pages, 12 of which are covers.

### Two failure modes this batch ran into

The page generator counts a render as made whatever came back, and this lane has
a failure the counters do not see: **a blank or near-black frame**, usually a
few kB where a real illustration is 60-130 kB. Twenty of the 201 pages came back
that way and four more as pure noise. File size separates them cleanly, so a
repair driver is worth writing before a long run rather than after one:

```python
defect = page.stat().st_size < 20000 or fine_ratio(page) > 1.6 or page.std() < 15
```

where `fine_ratio` is the mean absolute pixel difference at 128px over the same
at 24px — noise keeps its detail when the image is downsampled, a painting does
not, so the ratio sits near 0.2-0.8 for a painting and above 1.9 for noise. A
low ratio alone will not catch the blank frames, because they are smooth too;
the size and standard-deviation tests are what catch those.

Neither failure is seed-dependent. Re-rolling `--seed-salt` four times over the
same twenty pages moved the count from 20 to 18. What does work is rewriting the
prompt, and two things about the rewrite matter more than the prose:

- **End on a concrete light clause**, the way the working folk-tales fragments
  do: "hard noon light, short shadows on the grass", "fading August, one
  candle". Thirteen of the eighteen pages that would not render at all ended on
  the same abstract line, "One warm light, long soft shadows"; replacing that
  line with a specific one fixed eight of them in a single pass.
- **Lead with the object and put the person in the middle distance**, the
  `Foreground: / Middle: / Background: / Light:` shape the older fragments use.
  It is the form that renders most reliably here.

The residual is prompt-specific rather than index-specific, which is worth
knowing before you rewrite a page by hand: swapping one story's page 1 and
page 12 prompts and re-rendering moved the failure with the text, not with the
position. All 201 pages pass the size and noise checks now, and one page — the
cradle story's opener, which had crowded nine near-identical figures into the
frame and painted the word "Gran" in the corner — was rewritten object-first to
clear both.

## The deep-tales batch, and the anime style

`deep-tales-covers.json` is a second batch of twelve standalone stories,
numbered 122 to 133, and the first one drawn rather than painted. There is no
magic anywhere in it: a small place, a competent person doing a real job, a
problem that costs something to solve, and a last page that does not tidy up.
A boy mends a village radio. A girl keeps a rain tally. A baker breaks his own
rule. A teenager runs the night ferry. A cartographer's son finds a valley that
is on no map. A nurse keeps a second set of notes because the first one is a legal
document. Reading times run from 6 minutes to 25.

The art is a modern Japanese anime film still, and it comes from a second style
preset rather than a different set of prompts. Both generators now take
`--style`, which selects a per-level medium sentence from `MEDIUM_BY_STYLE`:

```bash
python3 scripts/generate_manuscript_covers.py --manifest manuscripts/deep-tales-covers.json \
    --style anime --secret-file /etc/omniserve-qwen.env
python3 scripts/generate_manuscript_page_art.py --manifest manuscripts/deep-tales-covers.json \
    --style anime --secret-file /etc/omniserve-qwen.env
```

`painterly` is the default and is what every batch before this one was generated
with, so old manifests need no flag. The world bible `manuscripts/worlds/deep-tales.md`
adds the batch's palette on top of the preset; the two must not contradict each
other, and the bible's story list is headed `## Stories` for the same reason the
folk-tales one is — `check_grand_fantasy_batch.py` would reject numbers outside a
world range.

Two things the anime register needed that the painterly one did not. First, the
cover prompts put the **figure first**: a header, then the person filling most
of the frame, then the countable object, then the place. Leading with a
location sentence made the model paint the location — a whole fishing village at
night with the boy nowhere in it — so the establishing sentence now comes after
the figure, in the middle-distance line where it belongs. Second, and more
seriously, **never write "empty" or "no people" in a prompt**. Four of the
twelve first-pass covers lost their subject entirely and one came back as a
shirtless portrait, all of it traceable to an establishing sentence that said
the scene was empty. Write the header, then say who is in it.

The 230 page prompts live in `manuscripts/page-prompts/deep-page-*.json`, keyed
to `world: deep-tales`, and follow the one-person rule that keeps this model
usable at 768px: a prompt naming two or more distinct people comes back as noise
about half the time.

## The comic register, and why Halversgate is not published

`halversgate-covers.json` and the twelve manuscripts numbered 134 to 145 are
written, gated and ready. They are **not published**, because the comic style
does not work on this lane and the covers are unusable.

`--style comic` is implemented and the batch has been rendered six ways on a
single cover. What happens, in order: asked for a comic book splash page, the
model draws a page of four inked panels with panel borders. Told explicitly
`no panels, no gutters, no panel borders`, it draws three empty panels of paper
texture — the negative clause reads as a layout brief. Reframed as a cover
illustration painted edge to edge, it drops the subject and paints a
photoreal portrait on white. Given a rendering language with no layout words in
it, it finally returns a single inked scene with no panels and no lettering, but
the figure is small and the scene is generic; run across the twelve stories, all
twelve came back as the same black-and-white inked village panorama with palm
trees, differing only in how many distant figures are walking up the road.

One of those attempts also put real car marques in the picture. Anything from
this register is not shippable until that is fixed, which is one of the reasons
it is not published.

There is no fallback inside the lane: `z-image-turbo` and `flux-schnell` are both
listed by `GET /v1/models` and both return byte-identical output to
`qwen-image` for the same request, so `--model` is not honoured by
`/v1/images/generations` on this deployment. Fixing this means either a model
that follows single-image layout control, or an images endpoint that honours
`--model`.

`painterly` and `anime` both reach twelve out of twelve on this lane. The
stories are level- and audience-tagged exactly like the other batches, so
publishing Halversgate with either of those presets is one command:

```bash
python3 scripts/generate_manuscript_covers.py --manifest manuscripts/halversgate-covers.json \
    --style painterly --force --secret-file /etc/omniserve-qwen.env
python3 scripts/publish_manuscripts.py --manifest manuscripts/halversgate-covers.json --backup
```

Note for whoever picks this up: the `--style comic` medium sentences in both
generators deliberately do **not** contain the words "comic", "page", "panel"
or "splash", and the batch's cover prompts deliberately do not contain "no other
people", "empty" or "no people". Each of those was a measured failure, not a
preference. Put them back and the batch will render panels again.

Each batch has its own fragment directory, passed with `--fragments`, and its
own manifest, passed with `--out`:

```bash
python3 scripts/assemble_grand_fantasy_manifest.py --fragments /tmp/rt-manifest-ft \
    --out manuscripts/fairytale-tales-covers.json --allow-missing
python3 scripts/assemble_grand_fantasy_manifest.py --fragments /tmp/rt-manifest-ft \
    --out manuscripts/fairytale-tales-covers.json
```

`--allow-missing` skips only the cover-link check, so the first pass can build a
manifest for manuscripts whose art does not exist yet. Run the second, strict
pass after `generate_manuscript_covers.py` has inserted the links.

```bash
python3 scripts/generate_manuscript_covers.py --manifest manuscripts/fairytale-tales-covers.json \
    --secret-file /etc/omniserve-qwen.env --dry-run
python3 scripts/generate_manuscript_covers.py --manifest manuscripts/fairytale-tales-covers.json \
    --secret-file /etc/omniserve-qwen.env
python3 scripts/publish_manuscripts.py --manifest manuscripts/fairytale-tales-covers.json --backup
```

```bash
python3 scripts/check_grand_fantasy_batch.py              # gate: presence, level, title, band, pages
python3 scripts/assemble_grand_fantasy_manifest.py         # fragments -> grand-fantasy-covers.json
```

```bash
python3 scripts/generate_manuscript_covers.py --manifest manuscripts/grand-fantasy-covers.json --dry-run
python3 scripts/generate_manuscript_covers.py --manifest manuscripts/grand-fantasy-covers.json
python3 scripts/publish_manuscripts.py --manifest manuscripts/grand-fantasy-covers.json --backup
```


`assemble_grand_fantasy_manifest.py` reads one JSON fragment per world-level
pair from `/tmp/rt-manifest/`, checks each entry against the manuscript on disk
(single H1, cover link, level directory, word band, page cap) and writes the
combined manifest. `check_grand_fantasy_batch.py` reads the bibles' own
`## Titles` lists, so it catches a story written into the wrong level directory
or one clobbered by a concurrent writer.

The first sixteen bibles are also the art direction for the sixteen Ren'Py
novels built from them; `../netwrck/scripts/vn-art-plan-from-world.py` turns
each one into an `art-plan.json` of per-image Qwen prompts.

Qwen Image 2.1 covers are driven by `manuscripts/covers.json` and the local
OmniServe-native lane. Preview without spending, then generate or top up:

```bash
python3 scripts/generate_manuscript_covers.py --secret-file /etc/omniserve-qwen.env --dry-run
python3 scripts/generate_manuscript_covers.py --secret-file /etc/omniserve-qwen.env
```

`--size WxH` overrides the output geometry (default `1024x1536`, portrait, the
shape `.card-cover` crops to). Pass `--manifest` to regenerate a single batch
instead of the whole library; `--only <substring>` narrows further.

The generator preserves prompts, writes WebP assets atomically, and inserts a
cover link only after the image is available. The Go reader continues to use the
`stories` table; these Markdown manuscripts are a separate long-form library.

A cover seed is `sha256(manuscript path)`, so a redraw of an unchanged prompt
reproduces the same image. A handful of seeds on this lane degenerate whatever
the prompt says — measured: six attempts at one story returned an empty
landscape every time — so a broken cover cannot be re-rolled by rewriting its
prompt alone. `--seed-salt N` mixes into the seed, exactly as the page generator
does:

```bash
python3 scripts/generate_manuscript_covers.py --manifest manuscripts/the-body-covers.json \
    --secret-file /etc/omniserve-qwen.env --force --seed-salt 1 --only 219-the
```

`--only` takes one substring per flag, not a list:

```bash
python3 scripts/generate_manuscript_covers.py --manifest manuscripts/deep-water-covers.json \
    --secret-file /etc/omniserve-qwen.env --force --only 161-the --only 164-the
```

### Where a published batch lands

The running app reads **Postgres**; `readingtime.db` is the legacy SQLite file
`migrate.go` imports from, and it stops being written once Postgres is in play.
Both writing scripts therefore target Postgres by default and say so:

```bash
python3 scripts/publish_manuscripts.py --manifest manuscripts/the-body-covers.json --dry-run
# would publish 12 stories, 229 pages to postgres
```

`DATABASE_URL` comes from the environment or from `.env`; `--database-url`
overrides it. `--db path/to.db` is the explicit way back to SQLite, and it also
disables the `.env` lookup, so it cannot be half-honoured. `generate_manuscript_page_art.py`
takes the same two flags and writes each finished page straight back to the row
it came from.

Covers and page images live under `static/manuscript-covers/` and
`static/manuscript-pages/`, which `deploy.sh` syncs to R2. A newly published
batch is therefore invisible in the reader until the next deploy pushes its art;
the reader rewrites `/static/...` to `STATIC_BASE_URL`, so a missing object is a
404 from R2 rather than a fallback to disk.

## Page art

A cover is one image per book. The reader also takes an `image_url` per page, so
`generate_manuscript_page_art.py` gives every page of a batch its own
illustration. It reuses `publish_manuscripts`' page split, so the page indices it
writes are exactly the ones the reader renders; page 0 is the cover and is left
alone. The 72-story fairy-tale-twist batch is 2,060 pages, 1,988 of which need
art.

Page prompts are not in the manifest: a 72-story batch needs ~2,000 of them, one
per page, each grounded in that page's own text. They are authored as one JSON
fragment per world-level in `/tmp/rt-page-prompts/`, against a page plan that
the publisher can generate for itself:

```bash
python3 scripts/generate_manuscript_page_art.py --dry-run     # one plan line per page
python3 scripts/generate_manuscript_page_art.py --secret-file /etc/omniserve-qwen.env
```

Each fragment is `{"world", "level", "stories": [{"path", "pages": [...]}]}`,
with one prompt per page after the first, in the reader's order. The script
appends the world bible's own `## Visual Style` and the same style sentence the
cover generator uses, so page art and cover art sit in one register.

Two failure modes to expect. A page prompt that names two or more distinct
people in one 768px frame comes back as pure noise about half the time, and so
does a prompt that has drifted long; the fix is to cut the page down to one
subject and one countable object and regenerate. When a page is broken for a
prompt you have already simplified, the seed is the next lever:

```bash
python3 scripts/generate_manuscript_page_art.py --only 117-nobody --only-pages 9,10 --seed-salt 3
```

`--seed-salt` mixes into the per-(story, page) seed that the script derives by
default. Passing `--only-pages` at all forces a redo of every page in the range,
so give it the smallest range that covers the page you are replacing. In the
folk-tales batch, 15 of 168 pages came back broken; 12 were fixed by rewriting
the prompt and 3 needed both the rewrite and a re-rolled seed.

The default size is `768x768`, and square for a reason: the reader caps a page
image at the slide height (`.reveal section img { max-height: 100% }` against
`.left { width: 50% }`) and every page image the app already serves is square, so
a portrait page image caps to slide height and leaves half the slide black. At
768px square the art is about 1.4x the width the reader actually lays it out at,
and it runs at roughly 8.5 images a minute — the OmniServe lane gives no gain
from concurrent requests, so size is the only lever on a 2,000-image batch.

The run is resumable. Every page image is written atomically and the story row is
committed as soon as that page lands, so an interrupted run loses at most the
page in flight, and re-running skips every page that already has an `image_url`.
The lane answers 503 "admission timeout; retry" under load, so those are retried
with a backoff instead of counted as failures; anything that is not a transport
failure stops the run instead, so a bug cannot spend four hours being retried.
`--only <substring>` runs one story and `--limit N` stops after N images, both
for topping up a single gap.

The 12 educational science stories use `manuscripts/educational-covers.json`.
Their exact, text-safe diagrams are generated as SVGs under
`manuscripts/infographics/` and copied into the app's
`static/educational-infographics/` directory when published:

```bash
python3 scripts/generate_educational_infographics.py
```

The curated reader-ready batch is published separately, with an optional
database backup:

```bash
python3 scripts/publish_manuscripts.py --manifest manuscripts/ethics-covers.json --dry-run
python3 scripts/publish_manuscripts.py --manifest manuscripts/ethics-covers.json --backup
```

Publish the educational reader batch with:

```bash
python3 scripts/publish_manuscripts.py --manifest manuscripts/educational-covers.json --dry-run
python3 scripts/publish_manuscripts.py --manifest manuscripts/educational-covers.json --backup
```

Publish the 72-story fairy-tale-twist batch with:

```bash
python3 scripts/publish_manuscripts.py --manifest manuscripts/fairytale-tales-covers.json --dry-run
python3 scripts/publish_manuscripts.py --manifest manuscripts/fairytale-tales-covers.json --backup
```

Publish the 72-story fairy-tale batch with:

```bash
python3 scripts/publish_manuscripts.py --manifest manuscripts/fairytale-covers.json --dry-run
python3 scripts/publish_manuscripts.py --manifest manuscripts/fairytale-covers.json --backup
```

## The five craft batches, 146 to 221

Sixty more stories in five batches of twelve, each with its own band, bible and
manifest, all in the `painterly` register and all drawn on the OmniServe-native
Qwen lane:

| Batch | Band | Manifest | Subject |
| --- | --- | --- | --- |
| `how-it-works` | 146-157 | `how-it-works-covers.json` | one real mechanism per story: hive geometry, a canal lock, seed dormancy, a wind vane, a pump's foot valve, echo sounding, grid frequency, a stethoscope, decibels |
| `deep-water` | 158-169 | `deep-water-covers.json` | the sea as a working surface: rock-pool zonation, a shoal counted from a deck, net-mending arithmetic, tide tables, fluke photo-ID, a kelp forest that is one animal, a seabird colony, a chart withdrawn |
| `night-sky` | 170-181 | `night-sky-covers.json` | people who measure the sky: meteor counts, dark adaptation, a gnomon, seeing and transparency, auroral parallax, a comet's period, a pulsar on chart paper, a lunar occultation, photometry, a 2037 eclipse, a parallax argument, a Doppler planet claim |
| `long-ago` | 182-193 | `long-ago-covers.json` | work in the past from inside the job: a quern, a lime kiln, a charcoal pit, withies, a millrace, a composing stick, token working, a ration ledger, a ferry timetable, double entry, a winding-engine wheel, a rain-gauge field book |
| `the-body` | 210-221 | `the-body-covers.json` | a body and its ordinary business: a pulse, a cast, sleep, a reflex arc, an immune memory, oxygen on a hill, digestion, colour vision, an energy ledger, a spirometry report, a sensory map, holding your breath |

The bands run 146-157, 158-169, 170-181, 182-193 and then jump to 210-221:
194-205 is grand-fantasy's second hundred and 206-209 is its third story, so the
body batch was moved rather than left sharing its numbers. Halversgate holds
134-145 and deep-tales 122-133. Each bible is a batch file rather than a world
bible, so its story list is headed `## Stories` and
`check_grand_fantasy_batch.py` skips it: the numbers are in no world range, so a
`## Titles` heading would fail that gate.

A number here is a label, not an identity. `publish_manuscripts.py` derives each
story's id from the sha256 of its manuscript path, so two batches may carry the
same number without colliding — but do not renumber one batch's files with a
loop over a number range without pinning the batch, because the range is shared.

These batches are gated by `scripts/assemble_batch_manifest.py`, not by the
grand-fantasy assembler, because the world assembler reads the number out of the
reserved ranges. It takes one JSON fragment per story and applies the same rules:

```bash
python3 scripts/assemble_batch_manifest.py --fragments /tmp/rt-manifest-the-body \
    --out manuscripts/the-body-covers.json
```

Its `--bands` flag carries the word bands in level order
(`750-850,1700-2100,2600-3200`, the default) and it checks the filename against
the kebab form of the title, the H1, the cover link, the word band and the 3-30
page split.

The full run for one batch, in order, from `/tmp/rt-manifest-<batch>`:

```bash
python3 scripts/assemble_batch_manifest.py --fragments /tmp/rt-manifest-the-body \
    --out manuscripts/the-body-covers.json
python3 scripts/generate_manuscript_covers.py --manifest manuscripts/the-body-covers.json \
    --style painterly --secret-file /etc/omniserve-qwen.env
python3 scripts/publish_manuscripts.py --manifest manuscripts/the-body-covers.json --backup
python3 scripts/generate_manuscript_page_art.py --manifest manuscripts/the-body-covers.json \
    --style painterly --secret-file /etc/omniserve-qwen.env
```

The last step needs one page prompt per reader page after the first, authored
against the publisher's own split. The plan behind them, one entry per story
with the text of every page, is dumped by a throwaway script rather than by
`generate_manuscript_page_art.py`, because `parse_manuscript` insists the cover
file exists and the plan is wanted while the covers are still drawing. Fragments
land in `manuscripts/page-prompts/<batch>-<stem>.json`, one file per story, and
`load_prompts` keys them by manuscript path, so several agents can write the
same directory at once.

Cost, measured on this lane today: a 1024x1536 cover is about 45 s and a 768x768
page about 28 s, one at a time, so the five batches are 60 covers and about
1,070 pages. Page art is the long pole by a wide margin and the run is resumable:
it writes each image atomically, commits the story row as soon as the page
lands, and skips any page that already has an image.

## VisualBench

`visualbench.mjs` captures the key pages (desktop + mobile) into `visualbench/`
(gitignored). Run from a dir where `playwright` resolves:

```bash
cd ../app-site && BASE=http://127.0.0.1:4337 node /nvme0n1-disk/code/readingtime/visualbench.mjs
```

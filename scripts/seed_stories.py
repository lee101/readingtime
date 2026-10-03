#!/usr/bin/env python3
"""Seed public picture books into readingtime's stories table.

Mirrors what /api/story/generate + /api/story/illustrate + /api/story/save do
for a signed-in author, but drives the OpenPaths gateway with a server API key
so a batch can be generated without a browser session. Story text and page
images use the same prompts and the same models the author UI offers.

Pages are stored with an empty `words` array on purpose: handleStoryReader
recomputes it with splitWordsKeepSep when it is empty, so the word-highlight
reader stays byte-identical to app-authored stories and this script never has to
reimplement the Go word-splitting regex.

Usage:
    OPENPATHS_API_KEY=... python3 scripts/seed_stories.py --count 8
    python3 scripts/seed_stories.py --dry-run          # no writes, no spend
    python3 scripts/seed_stories.py --no-images        # text only
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import sqlite3
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GATEWAY = os.environ.get("OPENPATHS_BASE_URL", "https://openpaths.io").rstrip("/")

SYSTEM = (
    "You are a master children's picture-book author. Write warm, vivid, age-appropriate "
    "stories with simple, rhythmic sentences a child can follow word-by-word. Respond ONLY with "
    "minified JSON, no markdown fences, of the exact shape: "
    '{"title":"string","pages":[{"text":"1-3 short sentences",'
    '"image_prompt":"a concrete, vivid illustration description in a consistent art style"}]}.'
)

# (audience, idea). Deliberately spread across settings, tones and reading
# levels so a seeded batch does not read like eight versions of one story.
IDEAS: list[tuple[str, str]] = [
    ("ages 3-5", "A shy little cloud who is scared to rain, until a thirsty sunflower asks for help"),
    ("ages 4-8", "Two kererū cousins racing across a New Zealand valley to deliver one very ripe plum"),
    ("ages 4-8", "A lighthouse keeper's cat who learns to signal ships with her tail on a foggy night"),
    ("ages 5-7", "A girl who discovers her grandmother's paintbrush colours in whatever it is told"),
    ("ages 3-5", "A wombat who cannot sleep because the stars are too loud, and the moon's quiet lesson"),
    ("ages 5-8", "A robot in a seed library who plants the last sunflower on a very dusty planet"),
    ("ages 4-8", "A tuatara and a weta who swap houses for a week and both miss home"),
    ("ages 6-8", "A boy who builds a paper submarine and maps the whole harbour from underneath"),
    ("ages 3-5", "A duckling learning that the biggest puddle is not always the best puddle"),
    ("ages 5-7", "A snowman who wants to see summer, and the friend who keeps his hat safe until autumn"),
    ("ages 4-8", "A kiwi chick who finds a lost torch and returns it to the tramper who dropped it"),
    ("ages 6-8", "A girl who tunes a wonky piano by listening to the birds outside her window"),
    ("ages 3-5", "A very small snail who is late for everything and arrives exactly on time once"),
    ("ages 4-8", "A pūkeko who keeps borrowing the neighbours' washing to decorate her nest"),
    ("ages 5-7", "A boy whose shadow runs off to play, and the afternoon he spends coaxing it back"),
    ("ages 3-5", "A baby octopus counting her arms and finding one extra friend hiding among them"),
    ("ages 5-8", "A girl who trades a jar of fireflies for a map to the quietest place in the forest"),
    ("ages 4-8", "A grumpy old tractor and the lamb who convinces him spring is worth waking for"),
    ("ages 6-8", "A brother and sister who build a library in a hollow tree for the animals of the gully"),
    ("ages 3-5", "A little penguin whose scarf keeps unravelling, one loop per new friend"),
    ("ages 5-7", "A baker in a seaside town who invents a bread that smells like home to everyone"),
    ("ages 4-8", "A morepork who is afraid of the dark and the glow-worms who teach him to see it"),
]


def gw_post(path: str, payload: dict, key: str, timeout: int) -> dict:
    req = urllib.request.Request(
        GATEWAY + path,
        data=json.dumps(payload).encode(),
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer " + key,
            # The edge in front of openpaths.io rejects the default
            # Python-urllib agent with a 403, so identify this seeder instead.
            "User-Agent": "readingtime-seed-stories/1.0",
            "Accept": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def parse_story_json(out: str) -> dict:
    """Tolerate fences and surrounding prose, like parseStoryJSON in handlers.go."""
    out = out.strip()
    for fence in ("```json", "```"):
        if out.startswith(fence):
            out = out[len(fence) :]
    out = out.removesuffix("```").strip()
    start, end = out.find("{"), out.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("no JSON object in model output")
    story = json.loads(out[start : end + 1])
    if not story.get("title"):
        story["title"] = "My Story"
    pages = [p for p in story.get("pages", []) if str(p.get("text", "")).strip()]
    if not pages:
        raise ValueError("story has no pages")
    story["pages"] = pages
    return story


def gen_id() -> str:
    """Same shape as genID() in stories.go: 16 random bytes, raw url-safe base64."""
    return base64.urlsafe_b64encode(os.urandom(16)).decode().rstrip("=")


def generate_story(idea: str, audience: str, pages: int, model: str, key: str) -> dict:
    user = (
        f"Write a {pages}-page picture book for {audience}.\n"
        f"Story idea: {idea}\n"
        "Keep each page's text short (1-3 sentences). Make image_prompt for every page describe the same "
        "characters and a consistent, beautiful illustration style so the pictures feel like one book."
    )
    data = gw_post(
        "/v1/chat/completions",
        {
            "model": model,
            "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}],
            "stream": False,
            "temperature": 0.9,
            # Reasoning models spend part of the budget before any visible
            # content, so leave more headroom than the 4000 the author UI uses.
            "max_tokens": 8000,
        },
        key,
        timeout=300,
    )
    choice = (data.get("choices") or [{}])[0]
    content = (choice.get("message") or {}).get("content") or ""
    if not content.strip():
        raise ValueError(f"model returned no content (finish_reason={choice.get('finish_reason')})")
    return parse_story_json(content)


def illustrate(prompt: str, model: str, key: str, out_dir: Path) -> str:
    """Return a URL for one page image, saving bytes locally only if the
    provider hands back base64 (mirrors handleIllustrate)."""
    data = gw_post(
        "/v1/images/generations",
        {"model": model, "prompt": prompt, "n": 1, "size": "1024x1024"},
        key,
        timeout=600,
    )
    item = (data.get("data") or [{}])[0]
    if item.get("url"):
        return item["url"]
    b64 = item.get("b64_json")
    if not b64:
        raise ValueError("image response had neither url nor b64_json")
    out_dir.mkdir(parents=True, exist_ok=True)
    name = gen_id() + ".png"
    (out_dir / name).write_bytes(base64.b64decode(b64))
    return "/static/generated/" + name


def existing_prompts(db_path: str) -> set[str]:
    """Ideas already seeded, so repeated runs top the gallery up instead of
    generating the same book twice. The idea text is stored in stories.prompt."""
    try:
        con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    except sqlite3.Error:
        return set()
    try:
        rows = con.execute("SELECT prompt FROM stories WHERE prompt != ''").fetchall()
    except sqlite3.Error:
        return set()
    finally:
        con.close()
    return {str(r[0]).strip().casefold() for r in rows}


def insert_story(db: sqlite3.Connection, story: dict) -> None:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f000+00:00")
    db.execute(
        """INSERT INTO stories
           (id, user_id, author_name, title, prompt, cover_url, text_model, image_model,
            public, pages_json, created_at, updated_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            story["id"], story["user_id"], story["author_name"], story["title"], story["prompt"],
            story["cover_url"], story["text_model"], story["image_model"], 1,
            json.dumps(story["pages"], separators=(",", ":")), now, now,
        ),
    )
    db.commit()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", type=int, default=8, help="stories to generate")
    ap.add_argument("--pages", type=int, default=6, help="pages per story (3-16)")
    ap.add_argument("--model", default="gpt-5.6-luna", help="text model id")
    ap.add_argument("--image-model", default="zimage", help="image model id ('' to skip)")
    ap.add_argument("--no-images", action="store_true", help="text only, no illustration spend")
    ap.add_argument("--db", default=str(ROOT / "readingtime.db"))
    ap.add_argument("--user-id", default="8bcad0e1-193d-4584-9d95-ca4a09130d0d")
    ap.add_argument("--author", default="leepenkman")
    ap.add_argument("--start", type=int, default=0, help="offset into the idea list")
    ap.add_argument("--allow-duplicates", action="store_true",
                    help="regenerate ideas already present in the database")
    ap.add_argument("--dry-run", action="store_true", help="print what would run, spend nothing")
    args = ap.parse_args()

    pages = max(3, min(args.pages, 16))
    seen = set() if args.allow_duplicates else existing_prompts(args.db)
    pool = [(a, i) for a, i in IDEAS if i.strip().casefold() not in seen]
    skipped = len(IDEAS) - len(pool)
    if not pool:
        print(f"every idea in the list is already seeded ({skipped}); add more IDEAS "
              f"or pass --allow-duplicates", file=sys.stderr)
        return 1
    picks = [pool[(args.start + i) % len(pool)] for i in range(min(args.count, len(pool)))]

    if args.dry_run:
        print(f"would generate {len(picks)} stories, {pages} pages each")
        if skipped:
            print(f"  ({skipped} idea(s) already in {args.db}, skipped)")
        if len(picks) < args.count:
            print(f"  (asked for {args.count}, only {len(pool)} unused idea(s) available)")
        print(f"  text:  {args.model}")
        print(f"  image: {'(none)' if args.no_images else args.image_model}")
        for audience, idea in picks:
            print(f"  - [{audience}] {idea}")
        return 0

    key = os.environ.get("OPENPATHS_API_KEY", "").strip()
    if not key:
        print("OPENPATHS_API_KEY is required", file=sys.stderr)
        return 2

    if skipped:
        print(f"{skipped} idea(s) already seeded, skipping them")
    if len(picks) < args.count:
        print(f"asked for {args.count} but only {len(pool)} unused idea(s) available")

    image_model = "" if args.no_images else args.image_model
    db = sqlite3.connect(args.db)
    out_dir = ROOT / "static" / "generated"
    made = 0

    for n, (audience, idea) in enumerate(picks, 1):
        label = idea[:58]
        try:
            print(f"[{n}/{len(picks)}] {label} ... text", flush=True)
            story = generate_story(idea, audience, pages, args.model, key)
        except (urllib.error.URLError, urllib.error.HTTPError, ValueError, KeyError) as exc:
            print(f"  skipped ({type(exc).__name__}: {exc})", file=sys.stderr)
            continue

        out_pages, cover = [], ""
        for i, p in enumerate(story["pages"], 1):
            image_url = ""
            if image_model:
                prompt = str(p.get("image_prompt") or p["text"])
                for attempt in (1, 2):
                    try:
                        image_url = illustrate(prompt, image_model, key, out_dir)
                        break
                    except Exception as exc:  # one retry; a missing image is survivable
                        print(f"  page {i} image attempt {attempt} failed: {exc}", file=sys.stderr)
                        time.sleep(2)
            if image_url and not cover:
                cover = image_url
            # words is left empty: the reader recomputes it with the Go splitter.
            out_pages.append({"text": str(p["text"]).strip(), "words": [], "image_url": image_url})
            print(f"  page {i}/{len(story['pages'])}{' (image)' if image_url else ''}", flush=True)

        insert_story(
            db,
            {
                "id": gen_id(), "user_id": args.user_id, "author_name": args.author,
                "title": str(story["title"]).strip(), "prompt": idea, "cover_url": cover,
                "text_model": args.model, "image_model": image_model, "pages": out_pages,
            },
        )
        made += 1
        print(f'  saved "{story["title"]}" ({len(out_pages)} pages)', flush=True)

    print(f"\ndone: {made}/{len(picks)} stories inserted into {args.db}")
    return 0 if made else 1


if __name__ == "__main__":
    raise SystemExit(main())

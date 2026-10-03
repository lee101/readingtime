#!/usr/bin/env python3
"""Generate a Qwen illustration for every page of a manuscript batch.

Modes: generate (default), --list-pages / --dry-run (page split and prompt count
check, no server), --contact-sheet DIR (grid of cover + page art per story),
--no-db (illustrate before publishing; files only), --only-pages 4,8 (redo pages),
--with-covers (also generate the cover, --no-db only). Base URL defaults to the
local OmniServe and the model is autodiscovered from GET /v1/models.

The cover pass (`generate_manuscript_covers.py`) gives a story one image. This
gives every page one, so the reader has art beside the words rather than a
single cover and then a run of text. It reuses `publish_manuscripts`'s page
split, so the page indices here are exactly the page indices the reader renders.

Page prompts come from one JSON fragment per world-level in --fragments:

    {"world": "the-cinder-ledger",
     "level": "accessible",
     "stories": [{"path": "manuscripts/accessible/301-the-last-sack-on-the-board.md",
                  "pages": ["prompt for page 1", "prompt for page 2", ...]}]}

`pages` holds one prompt per page AFTER the first: page 0 is the cover, which
already has art and is never regenerated here.

The run is resumable. Each page image is written atomically and the story row is
committed as soon as that page lands, so an interrupted run loses at most the
page in flight, and re-running skips every page that already has an image_url.
The OmniServe lane answers 503 "admission timeout; retry" under load, so those
are retried with a backoff rather than counted as failures.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import os
import sqlite3
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from PIL import Image, ImageDraw, ImageOps

import generate_manuscript_covers as covers
import publish_manuscripts as pm

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MANIFEST = ROOT / "manuscripts" / "fairytale-tales-covers.json"
DEFAULT_FRAGMENTS = ROOT / "manuscripts" / "page-prompts"
# The reader lays a page image out at up to half the slide width and caps it at
# the slide height (`.reveal section img { max-height: 100% }` against
# `.left { width: 50% }`), and every page image the app already serves is
# square. A portrait page image therefore caps to slide height and leaves half
# the slide black, so page art is square at 768px — about 1.4x the rendered
# width on a laptop — and 768x768 costs less than half of 768x1152.
DEFAULT_SIZE = (768, 768)
DEFAULT_DB = ROOT / "readingtime.db"
DEFAULT_OUTPUT = ROOT / "static" / "manuscript-pages"
DEFAULT_WORLDS = ROOT / "manuscripts" / "worlds"
DEFAULT_COVERS = ROOT / "manuscripts" / "art"
DEFAULT_SHEETS = ROOT / "manuscripts" / "contact-sheets"
MEDIUM_BY_STYLE = {
    "painterly": {
        "accessible": (
            "warm children's storybook illustration, rounded readable forms, luminous color, gentle wonder",
            "character-forward, safe and inviting, with no horror",
        ),
        "intermediate": (
            "painterly fantasy adventure illustration, expressive textures, clear silhouettes, rich environmental detail",
            "youthful protagonists and an emotionally clear heroic moment",
        ),
        "advanced": (
            "sophisticated painterly fantasy illustration, cinematic composition, tactile detail, restrained dramatic light",
            "adult protagonists, nuanced body language, grounded and non-glorifying",
        ),
    },
    "anime": {
        "accessible": (
            "modern Japanese anime key visual, clean confident linework, flat cel shading, soft hand-painted background, expressive face",
            "character-forward, safe and inviting, with no horror",
        ),
        "intermediate": (
            "cinematic anime film still, precise linework, even cel shading, hand-painted background art",
            "youthful protagonists and an emotionally clear heroic moment",
        ),
        "advanced": (
            "moody anime film still, fine linework, cinematic cel shading, hand-painted dusk and night background",
            "adult protagonists, nuanced body language, grounded and non-glorifying",
        ),
    },
    "comic": {
        "accessible": (
            "bold inked illustration, thick black outlines, flat blocks of saturated colour, halftone dot shading in the shadows, expressive cartoon face",
            "character-forward, safe and inviting, with no horror",
        ),
        "intermediate": (
            "bold inked illustration, thick black outlines, flat blocks of colour, hard shadow shapes, halftone dot shading, dramatic foreshortening",
            "youthful protagonists and an emotionally clear heroic moment",
        ),
        "advanced": (
            "adult inked illustration, heavy black outlines, moody blocks of flat colour, screentone shading, noir lighting",
            "adult protagonists, nuanced body language, grounded and non-glorifying",
        ),
    },
}
# Only these are worth a second attempt: a dropped or timed-out connection, or a
# lane that is momentarily out of memory. Anything else is a bug and stops the run.
TRANSIENT = (TimeoutError, ConnectionError, urllib.error.URLError, json.JSONDecodeError)
RETRY_STATUS = (429, 500, 502, 503, 504)


def parse_size(raw: str) -> tuple[int, int]:
    width, separator, height = raw.partition("x")
    if not separator or not width.isdigit() or not height.isdigit():
        raise argparse.ArgumentTypeError("size must look like 768x1152")
    return int(width), int(height)


def read_secret(env_name: str, secret_file: Path | None) -> str:
    value = os.environ.get(env_name, "").strip()
    if value:
        return value
    if secret_file is None or not secret_file.exists():
        return ""
    try:
        contents = secret_file.read_text()
    except PermissionError:
        contents = subprocess.run(
            ["sudo", "-n", "cat", str(secret_file)],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
    for raw in contents.splitlines():
        line = raw.strip()
        if line.startswith("export "):
            line = line[7:].lstrip()
        key, separator, value = line.partition("=")
        if separator and key.strip() == env_name:
            return value.strip().strip("'\"")
    return ""


def request_page(
    base: str,
    model: str,
    prompt: str,
    seed: int,
    size: tuple[int, int],
    secret: str,
    timeout: int,
) -> bytes:
    payload = {
        "model": model,
        "prompt": prompt,
        "width": size[0],
        "height": size[1],
        "steps": 20,
        "seed": seed,
        "output_format": "webp",
        "n": 1,
    }
    headers = {
        "Accept": "application/json, image/*",
        "Content-Type": "application/json",
        "X-Omniserve-Tier": "free",
    }
    if secret:
        headers["X-API-Key"] = secret
    http_request = urllib.request.Request(
        f"{base.rstrip('/')}/v1/images/generations",
        data=json.dumps(payload, separators=(",", ":")).encode(),
        headers=headers,
        method="POST",
    )
    with urllib.request.urlopen(http_request, timeout=timeout) as response:
        body = response.read()
        content_type = response.headers.get_content_type()
    if content_type == "image":
        return body
    document = json.loads(body)
    entries = document.get("data", [])
    if not entries or not entries[0].get("b64_json"):
        raise RuntimeError("Qwen returned no image")
    return base64.b64decode(entries[0]["b64_json"], validate=True)


def normalize(raw: bytes, size: tuple[int, int]) -> bytes:
    with Image.open(io.BytesIO(raw)) as source:
        image = ImageOps.exif_transpose(source)
        image.load()
        if image.size != size:
            raise RuntimeError(f"Qwen returned {image.size}, expected {size}")
        if image.format == "WEBP":
            return raw
        output = io.BytesIO()
        image.convert("RGB").save(output, format="WEBP", quality=88, method=6)
        return output.getvalue()


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_bytes(data)
    temporary.replace(path)


def load_prompts(fragments: Path) -> dict[str, tuple[str, list[str]]]:
    """Map manuscript path -> (world slug, one prompt per page after the first).

    A fragment that is missing, half-written or malformed is reported and
    skipped, not fatal: a long run should still illustrate every story whose
    prompts are already on disk.
    """
    if not fragments.is_dir():
        raise ValueError(f"no prompt fragment directory at {fragments}")
    prompts: dict[str, tuple[str, list[str]]] = {}
    for fragment in sorted(fragments.glob("*.json")):
        try:
            document = json.loads(fragment.read_text(encoding="utf-8"))
            world = str(document["world"])
            stories = [
                (str(story["path"]), [str(text) for text in story["pages"]])
                for story in document["stories"]
            ]
        except (OSError, ValueError, KeyError, TypeError) as error:
            print(f"skip {fragment.name}: {error}", file=sys.stderr)
            continue
        for path, page_prompts in stories:
            if path in prompts:
                print(f"skip {fragment.name}: duplicate story {path}", file=sys.stderr)
                continue
            prompts[path] = (world, page_prompts)
    if not prompts:
        raise ValueError(f"no usable story prompts in {fragments}")
    return prompts

def backoff(attempt: int, title: str, index: int, reason: str) -> None:
    """Wait out a retryable failure, loudly: a silent sleep looks like a hang."""
    delay = min(60, 5 * attempt)
    print(
        f"retry {title} page {index} in {delay}s after {reason}", file=sys.stderr, flush=True
    )
    time.sleep(delay)


def visual_style(worlds: Path) -> dict[str, str]:
    """World slug -> that bible's `## Visual Style` section, as one paragraph."""
    styles: dict[str, str] = {}
    for bible in sorted(worlds.glob("*.md")):
        body = bible.read_text(encoding="utf-8")
        marker = "\n## Visual Style\n"
        if marker not in body:
            continue
        section = body.split(marker, 1)[1].split("\n## ", 1)[0]
        styles[bible.stem] = " ".join(section.split())
    return styles


NO_TEXT_CLAUSE = "no written words, letters, numbers, captions, logos, borders, or watermark"


def compose_prompt(scene: str, style: str, level: str, index: int, total: int,
                   style_preset: str = "painterly") -> str:
    """The scene's own words, then the world's palette, then the no-lettering clause.

    The style and framing sentences are the same ones the cover generator appends,
    so page art and cover art sit in one visual register. A prompt fragment
    already ends with the no-lettering clause, so it is stripped first and added
    once, here.
    """
    medium, framing = MEDIUM_BY_STYLE[style_preset][level]
    position = (
        "the frontispiece"
        if index == 1
        else f"a later moment, plate {index - 1} of {total - 1}"
    )
    body = scene.strip()
    marker = body.lower().rfind(NO_TEXT_CLAUSE)
    if marker != -1:
        body = body[:marker].rstrip(" .,;")
    return (
        f"{body} {style} {medium}; {framing}; {position}; "
        f"vertical composition, one clear scene, {NO_TEXT_CLAUSE}"
    )



CHILD_RE = re.compile(
    r"\b(?:[a-z]+[- ]year[- ]old|young|little|small)?\s*(girl|boy|child)\b", re.I
)
PLURAL_RE = re.compile(
    r"\b(children|kids|girls|boys|siblings|twins|two (?:girls|boys|children)|classmates|friends)\b", re.I
)
SOLO_CLAUSE = (
    "exactly one child in the scene, the same single consistent character in every plate "
    "(same face, hair and clothing), no other person present except those named in this scene"
)


def names_single_child(scene: str) -> bool:
    if PLURAL_RE.search(scene):
        return False
    ages = set(re.findall(r"\b([a-z]+|\d+)[- ]year[- ]old\b", scene, re.I))
    words = {m.lower() for m in re.findall(r"\b(girl|boy|child)\b", scene, re.I)}
    return len(ages) == 1 or (not ages and len(words) == 1)


def check_world(world: str, worlds: Path) -> None:
    if not (worlds / f"{world}.md").is_file():
        known = ", ".join(sorted(p.stem for p in worlds.glob("*.md")))
        raise ValueError(f"unknown world {world!r}: no {worlds / (world + '.md')} (known: {known})")


def parse_pages(raw: str, total: int) -> set[int]:
    """'4,8' or '3-5' -> {4, 8}; indices are 1-based and must exist."""
    selected: set[int] = set()
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        low, dash, high = part.partition("-")
        try:
            values = range(int(low), int(high) + 1) if dash else [int(low)]
        except ValueError as error:
            raise ValueError(f"bad --only-pages entry {part!r}") from error
        selected.update(values)
    bad = sorted(v for v in selected if not 1 <= v < total)
    if bad or not selected:
        raise ValueError(f"--only-pages {sorted(selected)} outside 1..{total - 1}")
    return selected


def cover_seed(key: str) -> int:
    return int.from_bytes(hashlib.sha256(key.encode()).digest()[:8], "big") % (2**63 - 1)


def seed_for(key: str, index: int, salt: int = 0) -> int:
    """Deterministic per (story, page), with an optional salt.

    A handful of seeds degenerate into pure noise or a flat smear on this model
    whatever the prompt says, so a page that came back broken cannot be
    re-rolled by rewriting its prompt. `--seed-salt` is how you re-roll it.
    """
    material = f"{key}:{index}" if not salt else f"{key}:{index}:{salt}"
    return int.from_bytes(hashlib.sha256(material.encode()).digest()[:8], "big") % (2**63 - 1)


@dataclass
class Story:
    key: str
    title: str
    level: str
    stem: str
    pages: list[dict[str, Any]]
    story_id: str | None = None
    item: dict[str, Any] | None = None


def load_stories(args: argparse.Namespace) -> list[Story]:
    if args.no_db or args.list_pages or args.dry_run or args.contact_sheet:
        document = json.loads(args.manifest.read_text(encoding="utf-8"))
        stories = []
        for item in document["covers"]:
            source = ROOT / str(item["path"])
            level = str(item["level"])
            pages = pm.parse_manuscript(source, str(item["title"]), level, "", int(item["target_words"]))
            stories.append(Story(str(item["path"]), str(item["title"]), level, source.stem, pages, None, item))
        return stories
    return [
        Story(f"manuscripts/{r.level}/{r.cover_source.stem}.md", r.title, r.level,
              r.cover_source.stem, r.pages, r.story_id)
        for r in pm.load_records(args.manifest, ROOT / "static")
    ]


def compose_for(story: Story, prompts: dict, styles: dict, worlds: Path, index: int,
                style_preset: str = "painterly") -> str:
    world, scenes = prompts[story.key]
    check_world(world, worlds)
    scene = scenes[index - 1]
    prompt = compose_prompt(scene, styles.get(world, ""), story.level, index, len(story.pages),
                            style_preset)
    if names_single_child(scene):
        prompt = f"{prompt}; {SOLO_CLAUSE}"
    return prompt


def list_pages(story: Story, prompts: dict, worlds: Path, output: Path, plan: bool) -> bool:
    entry = prompts.get(story.key)
    total = len(story.pages) - 1
    if entry is None:
        print(f"{story.stem}: {total} pages, NO PAGE PROMPTS", file=sys.stderr)
        return False
    world, scenes = entry
    ok = len(scenes) == total
    try:
        check_world(world, worlds)
        world_note = world
    except ValueError as error:
        ok = False
        world_note = f"BAD WORLD ({error})"
    print(f"{story.stem} [{story.level}] world={world_note} pages={total} prompts={len(scenes)} "
          f"{'OK' if ok else 'MISMATCH'}")
    for index in range(1, total + 1):
        words = len(story.pages[index]["text"].split())
        scene = scenes[index - 1][:70] if index <= len(scenes) else "(no prompt)"
        solo = " solo" if index <= len(scenes) and names_single_child(scenes[index - 1]) else ""
        target = output / story.level / story.stem / f"{index:02d}.webp"
        state = ("have" if target.exists() else "need") if plan else ""
        print(f"  p{index:02d} {words:4d}w{solo:5s} {state:4s} {scene}")
    return ok


def contact_sheet(story: Story, pages_out: Path, covers_out: Path, dest: Path, columns: int = 4) -> Path | None:
    tiles: list[tuple[str, Path]] = [("cover", covers_out / story.level / f"{story.stem}.webp")]
    tiles += [(f"p{i:02d}", pages_out / story.level / story.stem / f"{i:02d}.webp")
              for i in range(1, len(story.pages))]
    cell = 384
    rows = -(-len(tiles) // columns)
    sheet = Image.new("RGB", (columns * cell, rows * (cell + 18)), (24, 24, 24))
    draw = ImageDraw.Draw(sheet)
    missing = 0
    for n, (label, path) in enumerate(tiles):
        x, y = (n % columns) * cell, (n // columns) * (cell + 18)
        if path.exists():
            with Image.open(path) as source:
                tile = ImageOps.contain(source.convert("RGB"), (cell, cell))
            sheet.paste(tile, (x + (cell - tile.width) // 2, y + 18 + (cell - tile.height) // 2))
        else:
            missing += 1
        draw.text((x + 4, y + 3), f"{label}{'' if path.exists() else ' MISSING'}", fill=(255, 255, 255))
    dest.mkdir(parents=True, exist_ok=True)
    out = dest / f"{story.stem}.jpg"
    sheet.save(out, quality=85)
    print(f"sheet {out} {len(tiles) - missing}/{len(tiles)} tiles")
    return out


def render(call: Callable[[], Any], label: str, retries: int) -> tuple[Any, float] | None:
    """Run one request with retry; returns (result, seconds) or None after reporting."""
    for attempt in range(1, retries + 1):
        began = time.time()
        try:
            return call(), time.time() - began
        except urllib.error.HTTPError as error:
            if error.code not in RETRY_STATUS or attempt == retries:
                detail = error.read(512).decode("utf-8", "replace").strip()
                print(f"failed {label}: HTTP {error.code}: {detail}", file=sys.stderr)
                return None
            backoff(attempt, label, 0, f"HTTP {error.code}")
        except RuntimeError as error:
            if not any(f"HTTP {code}" in str(error) for code in RETRY_STATUS) or attempt == retries:
                print(f"failed {label}: {error}", file=sys.stderr)
                return None
            backoff(attempt, label, 0, str(error)[:20])
        except TRANSIENT as error:
            if attempt == retries:
                print(f"failed {label}: {error}", file=sys.stderr)
                return None
            backoff(attempt, label, 0, type(error).__name__)
    return None


class PlaceholderConnection:
    """psycopg2 spells the placeholder %s where SQLite spells it ?, and exposes
    execute on a cursor rather than on the connection.

    Everything else this script does with the connection - execute, fetchone,
    commit, close - is the same shape on both, so the adapter is the whole of it.
    """

    def __init__(self, connection):
        self._connection = connection
        self._cursor = connection.cursor()

    def execute(self, sql, params=()):
        self._cursor.execute(sql.replace("?", "%s"), params)
        return self._cursor

    def commit(self):
        self._connection.commit()

    def close(self):
        self._cursor.close()
        self._connection.close()

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--fragments", type=Path, default=DEFAULT_FRAGMENTS)
    parser.add_argument("--db", type=Path, default=None,
                        help="write page images back to this SQLite file instead of Postgres")
    parser.add_argument("--database-url", default="",
                        help="write back to Postgres; defaults to DATABASE_URL from the env or .env")
    parser.add_argument("--no-db", action="store_true", help="write image files only")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--covers-output", type=Path, default=DEFAULT_COVERS)
    parser.add_argument("--worlds", type=Path, default=DEFAULT_WORLDS)
    parser.add_argument(
        "--base", default=os.environ.get("OMNISERVE_NATIVE_BASE_URL", covers.DEFAULT_BASE)
    )
    parser.add_argument("--model", default=None, help="default: env, else autodiscover")
    parser.add_argument("--secret-env", default="OMNISERVE_NATIVE_SECRET")
    parser.add_argument("--secret-file", type=Path)
    parser.add_argument("--size", type=parse_size, default=DEFAULT_SIZE)
    parser.add_argument("--cover-size", type=parse_size, default=covers.DEFAULT_SIZE)
    parser.add_argument("--only", action="append", default=[], help="match a story title or file stem")
    parser.add_argument("--only-pages", default="", help="1-based pages to regenerate, e.g. 4,8 or 3-5")
    parser.add_argument("--with-covers", action="store_true", help="also make missing covers (--no-db)")
    parser.add_argument("--list-pages", action="store_true", help="print page split and prompt check")
    parser.add_argument("--contact-sheet", type=Path, nargs="?", const=DEFAULT_SHEETS, default=None,
                        help="write one grid image per story into DIR instead of generating")
    parser.add_argument("--limit", type=int, default=0, help="stop after N images")
    parser.add_argument("--request-timeout", type=int, default=300)
    parser.add_argument("--retries", type=int, default=8)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--seed-salt", type=int, default=0,
                        help="re-roll the deterministic seed; use to replace a page that came back broken")
    parser.add_argument("--style", choices=sorted(MEDIUM_BY_STYLE), default="painterly",
                        help="medium register appended to each page prompt")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    try:
        secret = read_secret(args.secret_env, args.secret_file)
        prompts = load_prompts(args.fragments)
        styles = visual_style(args.worlds)
        stories = load_stories(args)
    except (OSError, ValueError, sqlite3.Error) as exc:
        print(f"generate_manuscript_page_art: {exc}", file=sys.stderr)
        return 1
    stories = [
        s for s in stories
        if not args.only or any(sel in s.title or sel in s.stem for sel in args.only)
    ]
    if not stories:
        print("generate_manuscript_page_art: no story matches --only", file=sys.stderr)
        return 1

    if args.list_pages or args.dry_run:
        good = all([list_pages(s, prompts, args.worlds, args.output, args.dry_run) for s in stories])
        if args.only_pages:
            try:
                for s in stories:
                    print(f"{s.stem}: would redo pages {sorted(parse_pages(args.only_pages, len(s.pages)))}")
            except ValueError as exc:
                print(f"generate_manuscript_page_art: {exc}", file=sys.stderr)
                return 1
        return 0 if good else 1

    if args.contact_sheet is not None:
        for s in stories:
            contact_sheet(s, args.output, args.covers_output, args.contact_sheet)
        return 0

    try:
        model = covers.discover_model(args.base, args.model)
    except RuntimeError as exc:
        print(f"generate_manuscript_page_art: {exc}", file=sys.stderr)
        return 1
    print(f"base {args.base} model {model}", flush=True)

    connection = None
    if not args.no_db:
        dsn = "" if args.db is not None else pm.postgres_url(args.database_url)
        if dsn:
            # The running app reads Postgres, so the page images have to be
            # written back there; readingtime.db is the legacy SQLite file.
            import psycopg2

            connection = PlaceholderConnection(psycopg2.connect(dsn))
        else:
            connection = sqlite3.connect(args.db or DEFAULT_DB, timeout=30)
            connection.execute("PRAGMA busy_timeout = 30000")
    made = skipped = failed = 0
    busy = 0.0
    started = time.time()
    try:
        for story in stories:
            if args.limit and made >= args.limit:
                break
            if story.key not in prompts:
                print(f"skip {story.title}: no page prompts", file=sys.stderr)
                continue
            world, story_prompts = prompts[story.key]
            pages = story.pages
            if len(story_prompts) != len(pages) - 1:
                print(f"skip {story.title}: {len(story_prompts)} prompts for {len(pages) - 1} pages",
                      file=sys.stderr)
                failed += 1
                continue
            try:
                check_world(world, args.worlds)
                selected = parse_pages(args.only_pages, len(pages)) if args.only_pages else None
            except ValueError as exc:
                print(f"generate_manuscript_page_art: {story.title}: {exc}", file=sys.stderr)
                return 1

            if args.with_covers and story.item is not None:
                target = args.covers_output / story.level / f"{story.stem}.webp"
                if args.force or not target.exists():
                    prompt = f"{story.item['prompt']}. {covers.art_direction(story.item, args.style)}"
                    result = render(
                        lambda: covers.request_cover(args.base, model, prompt, cover_seed(story.key),
                                                     args.cover_size, secret, args.request_timeout),
                        f"cover {story.stem}", args.retries)
                    if result is None:
                        failed += 1
                    else:
                        (raw, _), seconds = result
                        atomic_write(target, covers.normalize_cover(raw, args.cover_size))
                        busy += seconds
                        made += 1
                        print(f"made cover {story.stem} {seconds:.1f}s", flush=True)

            live: list[dict[str, Any]] | None = None
            if connection is not None:
                row = connection.execute(
                    "SELECT pages_json FROM stories WHERE id = ?", (story.story_id,)
                ).fetchone()
                if row is None:
                    print(f"skip {story.title}: no story row", file=sys.stderr)
                    continue
                live = json.loads(row[0])

            for index in range(1, len(pages)):
                if args.limit and made >= args.limit:
                    break
                if selected is not None and index not in selected:
                    continue
                target = args.output / story.level / story.stem / f"{index:02d}.webp"
                regenerate = args.force or selected is not None
                if live is not None and live[index].get("image_url") and not regenerate:
                    skipped += 1
                    continue
                if target.exists() and not regenerate:
                    if live is None:
                        skipped += 1
                        continue
                    data: bytes | None = target.read_bytes()
                    seconds = 0.0
                else:
                    prompt = compose_for(story, prompts, styles, args.worlds, index, args.style)
                    result = render(
                        lambda: request_page(args.base, model, prompt, seed_for(story.key, index, args.seed_salt),
                                             args.size, secret, args.request_timeout),
                        f"{story.title} page {index}", args.retries)
                    if result is None:
                        failed += 1
                        continue
                    raw, seconds = result
                    data = normalize(raw, args.size)
                    atomic_write(target, data)
                    busy += seconds
                    made += 1

                if live is not None and connection is not None:
                    live[index]["image_url"] = (
                        f"/static/manuscript-pages/{story.level}/{story.stem}/{index:02d}.webp"
                    )
                    connection.execute(
                        "UPDATE stories SET pages_json = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                        (json.dumps(live, ensure_ascii=False, separators=(",", ":")), story.story_id),
                    )
                    connection.commit()
                wall = time.time() - started
                print(
                    f"made {story.stem} p{index:02d} {len(data) // 1024}kB {seconds:.1f}s "
                    f"[{made} made, {skipped} skipped, {failed} failed, {made / wall * 60:.1f}/min]",
                    flush=True,
                )
    finally:
        if connection is not None:
            connection.close()

    wall = time.time() - started
    mean = busy / made if made else 0.0
    print(f"made {made}, skipped {skipped}, failed {failed}, wall {wall:.0f}s, "
          f"mean {mean:.1f}s/image, {made / wall * 60 if wall else 0:.2f}/min")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

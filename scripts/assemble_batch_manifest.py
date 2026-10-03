#!/usr/bin/env python3
"""Assemble a standalone story batch's cover manifest from per-story fragments.

`assemble_grand_fantasy_manifest.py` checks the nine-hundred world batches, whose
numbers fall in the reserved ranges 101-109, 201-209, ... 1001-1009. The batches
outside those ranges - folk-tales 110-121, deep-tales 122-133, halversgate
134-145 and everything after them - are numbered by hand, so this is the gate for
them: it checks each story against the same rules (one H1 matching the manifest
title, a filename that is the kebab form of that title, a cover link naming the
art file, a word count inside the level's band, a page count under the cap) and
writes the combined manifest.

Fragments are one JSON file per story in --fragments, each a manifest entry or an
array of them:

    {"path": "manuscripts/accessible/146-the-boy-who-counted-the-bees.md",
     "title": "The Boy Who Counted the Bees",
     "level": "accessible", "audience": "Ages 7-10",
     "target_words": 90,
     "prompt": "230-270 words of cover prompt"}

Bands are given as low-high word counts in level order, or read from the
manifest fragment's own batch file:

    python3 scripts/assemble_batch_manifest.py \\
        --fragments /tmp/rt-manifest-hw --out manuscripts/how-it-works-covers.json \\
        --bands 750-850,1700-2100,2600-3200
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_FRAGMENT_DIR = Path("/tmp/rt-manifest-batch")
LEVELS = ("accessible", "intermediate", "advanced")
H1_RE = re.compile(r"^#\s+(.+?)\s*$")
COVER_RE = re.compile(r"^!\[Cover art:\s*([^\]\r\n]+)\]\(([^)\r\n]+)\)\s*$")
WORD_RE = re.compile(r"\b[\w’'-]+\b", re.UNICODE)
NUMBER_RE = re.compile(r"/(\d{3,4})-[^/]+\.md$")
# The bands the standalone batches have actually been written to: halversgate and
# deep-tales both sit inside them, and the publisher's page cap is 30 pages.
DEFAULT_BANDS = "750-850,1700-2100,2600-3200"


def kebab(title: str) -> str:
    cleaned = title.replace("’", "").replace("'", "").replace("&", " and ")
    return re.sub(r"[^a-z0-9]+", "-", cleaned.lower()).strip("-")


def parse_bands(raw: str) -> dict[str, tuple[int, int]]:
    bands: dict[str, tuple[int, int]] = {}
    parts = raw.split(",")
    if len(parts) != len(LEVELS):
        raise ValueError(f"--bands needs {len(LEVELS)} low-high pairs in level order")
    for level, part in zip(LEVELS, parts):
        low, separator, high = part.strip().partition("-")
        if not separator or not low.isdigit() or not high.isdigit():
            raise ValueError(f"bad band {part!r}, want low-high")
        bands[level] = (int(low), int(high))
    return bands


def read_words(path: Path) -> int:
    return len(WORD_RE.findall(path.read_text(encoding="utf-8")))


def check_entry(entry: dict, bands: dict[str, tuple[int, int]], problems: list[str]) -> None:
    label = str(entry.get("path", "<missing path>"))
    for key in ("path", "title", "level", "audience", "target_words", "prompt"):
        if not entry.get(key):
            problems.append(f"{label}: missing or empty {key}")
    level = entry.get("level")
    if level not in LEVELS:
        problems.append(f"{label}: level must be one of {LEVELS}")
    target = entry.get("target_words")
    if not isinstance(target, int) or isinstance(target, bool) or target <= 0:
        problems.append(f"{label}: target_words must be a positive integer")
    manuscript = ROOT / str(entry.get("path", ""))
    if not manuscript.is_file():
        problems.append(f"{label}: manuscript does not exist")
        return
    lines = manuscript.read_text(encoding="utf-8").splitlines()
    h1 = [line for line in lines if H1_RE.fullmatch(line)]
    if len(h1) != 1:
        problems.append(f"{label}: must contain exactly one H1, found {len(h1)}")
    elif H1_RE.fullmatch(h1[0]).group(1) != entry.get("title"):
        problems.append(f"{label}: H1 does not match manifest title")
    if manuscript.stem != f"{manuscript.name.split('-', 1)[0]}-{kebab(str(entry.get('title', '')))}":
        problems.append(f"{label}: filename is not the number and kebab form of its title")
    cover = [line for line in lines if COVER_RE.fullmatch(line.strip())]
    if not cover:
        problems.append(f"{label}: missing cover link line")
    else:
        alt, target_path = COVER_RE.fullmatch(cover[0].strip()).groups()
        if alt != entry.get("title"):
            problems.append(f"{label}: cover alt text does not match title")
        expected = f"../art/{level}/{manuscript.stem}.webp"
        if target_path != expected:
            problems.append(f"{label}: cover link is {target_path}, expected {expected}")
    words = read_words(manuscript)
    band = bands.get(str(level))
    if band is None:
        problems.append(f"{label}: no word band for level {level}")
    elif not band[0] <= words <= band[1]:
        problems.append(f"{label}: {words} words is outside the {band[0]}-{band[1]} band")
    if isinstance(target, int) and not isinstance(target, bool) and target > 0:
        pages = -(-words // target)
        if not 3 <= pages <= 30:
            problems.append(f"{label}: splits into {pages} pages, outside the 3-30 page range")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fragments", type=Path, default=DEFAULT_FRAGMENT_DIR)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--bands", default=DEFAULT_BANDS,
                        help="low-high word bands in accessible,intermediate,advanced order")
    args = parser.parse_args(argv)

    try:
        bands = parse_bands(args.bands)
    except ValueError as exc:
        print(f"assemble_batch_manifest: {exc}", file=sys.stderr)
        return 1

    fragments = sorted(args.fragments.glob("*.json"))
    if not fragments:
        print(f"assemble_batch_manifest: no fragments in {args.fragments}", file=sys.stderr)
        return 1

    entries: list[dict] = []
    seen_paths: set[str] = set()
    problems: list[str] = []
    for fragment in fragments:
        try:
            payload = json.loads(fragment.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            problems.append(f"{fragment.name}: invalid JSON: {exc}")
            continue
        if isinstance(payload, dict):
            payload = payload.get("covers", [payload])
        if not isinstance(payload, list):
            problems.append(f"{fragment.name}: expected a manifest entry or an array of them")
            continue
        for entry in payload:
            check_entry(entry, bands, problems)
            path = str(entry.get("path", ""))
            if path in seen_paths:
                problems.append(f"duplicate manuscript path: {path}")
            seen_paths.add(path)
            entries.append(entry)

    print(f"fragments {len(fragments)}, entries {len(entries)}, "
          f"levels {dict(Counter(e.get('level') for e in entries))}")
    if problems:
        for problem in problems:
            print(f"  {problem}", file=sys.stderr)
        print(f"assemble_batch_manifest: {len(problems)} problem(s)", file=sys.stderr)
        return 1

    entries.sort(key=lambda item: NUMBER_RE.search("/" + str(item["path"])).group(0)[1:])
    args.out.write_text(
        json.dumps({"covers": entries}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    try:
        shown = args.out.relative_to(ROOT)
    except ValueError:
        shown = args.out
    print(f"wrote {shown} with {len(entries)} covers")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
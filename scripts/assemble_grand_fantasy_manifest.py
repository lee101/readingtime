#!/usr/bin/env python3
"""Assemble the grand-fantasy cover manifest from the per-world JSON fragments.

The wave-2 story writers each emit <fragments>/<world>-<level>.json. This
collects them into one manifest in the same shape as the other batches, and
checks each entry against the manuscript that is actually on disk before
writing anything. Every batch has its own fragment directory and output
manifest, so both are arguments rather than constants.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FRAGMENT_DIR = Path("/tmp/rt-manifest")
OUTPUT = ROOT / "manuscripts" / "grand-fantasy-covers.json"
LEVELS = ("accessible", "intermediate", "advanced")
H1_RE = re.compile(r"^#\s+(.+?)\s*$")
COVER_RE = re.compile(r"^!\[Cover art:\s*([^\]\r\n]+)\]\(([^)\r\n]+)\)\s*$")
WORD_RE = re.compile(r"\b[\w’'-]+\b", re.UNICODE)
READING_WPM = 140

# Each batch reserves a hundred numbers: the accessible stories start on 1 and
# the advanced stories on 7 of that hundred, with the levels in blocks of three
# and each level's stories running short, medium, long in order. The first batch
# starts at 101, the second at 201, and so on.
BATCH_STARTS = (101, 201, 301, 401, 501, 601, 701, 801, 901, 1001)
BANDS = (
    ((1_100, 1_500), (1_800, 2_200), (2_500, 2_900)),
    ((2_700, 3_300), (3_700, 4_300), (4_600, 5_100)),
    ((4_200, 4_800), (5_600, 6_200), (6_800, 7_000)),
)
NUMBER_RE = re.compile(r"/(\d{3,4})-[^/]+\.md$")


def band_for(level: str, number: int) -> tuple[int, int] | None:
    """Return the word band for a story number, or None if it is not in a batch."""
    for start in BATCH_STARTS:
        offset = number - start
        if 0 <= offset <= 8:
            placed = LEVELS[offset // 3]
            if placed != level:
                return None
            return BANDS[LEVELS.index(level)][offset % 3]
    return None


def read_words(path: Path) -> int:
    return len(WORD_RE.findall(path.read_text(encoding="utf-8")))


def check_entry(entry: dict, problems: list[str], allow_missing: bool = False) -> None:
    label = entry.get("path", "<missing path>")
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
    cover = [line for line in lines if COVER_RE.fullmatch(line.strip())]
    if not cover and allow_missing:
        pass
    elif not cover:
        problems.append(f"{label}: missing cover link line")
    else:
        alt, target_path = COVER_RE.fullmatch(cover[0].strip()).groups()
        if alt != entry.get("title"):
            problems.append(f"{label}: cover alt text does not match title")
        expected = f"../art/{level}/{manuscript.stem}.webp"
        if target_path != expected:
            problems.append(f"{label}: cover link is {target_path}, expected {expected}")
    words = read_words(manuscript)
    number_match = NUMBER_RE.search("/" + str(entry.get("path", "")))
    number = int(number_match.group(1)) if number_match else 0
    band = band_for(str(level), number) if level in LEVELS else None
    if band is None:
        problems.append(f"{label}: story number {number} is not in a {level} slot of any batch")
    elif not band[0] <= words <= band[1]:
        problems.append(f"{label}: {words} words is outside the {band[0]}-{band[1]} band")
    if isinstance(target, int) and target > 0:
        pages = -(-words // target)
        if pages > 30:
            problems.append(f"{label}: splits into {pages} pages, over the 30-page cap")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fragments", type=Path, default=FRAGMENT_DIR)
    parser.add_argument("--out", type=Path, default=OUTPUT)
    parser.add_argument("--allow-missing", action="store_true")
    args = parser.parse_args(argv)

    fragments = sorted(args.fragments.glob("*.json"))
    if not fragments:
        print(f"assemble_manifest: no fragments in {args.fragments}", file=sys.stderr)
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
        if not isinstance(payload, list):
            problems.append(f"{fragment.name}: expected a JSON array")
            continue
        for entry in payload:
            check_entry(entry, problems, args.allow_missing)
            path = str(entry.get("path", ""))
            if path in seen_paths:
                problems.append(f"duplicate manuscript path: {path}")
            seen_paths.add(path)
            entries.append(entry)

    print(f"fragments {len(fragments)}, entries {len(entries)}, levels {dict(Counter(e.get('level') for e in entries))}")
    if problems:
        for problem in problems:
            print(f"  {problem}", file=sys.stderr)
        print(f"assemble_manifest: {len(problems)} problem(s)", file=sys.stderr)
        return 1

    entries.sort(key=lambda item: (LEVELS.index(item["level"]), item["path"]))
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

#!/usr/bin/env python3
"""Check the grand-fantasy batch against the world bibles.

Every world bible ends with a `## Titles` list of `- <number> <Title>` lines.
For each one this checks that the manuscript exists in the right level
directory, that the filename stem is the kebab form of the bible title, and that
the H1 matches. It catches a story written into the wrong level directory or
clobbered by another agent's file, which is exactly the failure mode when 24
agents write into three shared directories.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORLDS = ROOT / "manuscripts" / "worlds"
TITLES_RE = re.compile(r"^-\s+(\d{3,4})\s+(.+?)\s*$")
H1_RE = re.compile(r"^#\s+(.+?)\s*$")
LEVELS = ("accessible", "intermediate", "advanced")
# Each batch reserves a hundred numbers: its accessible stories start on 1 and
# its advanced stories on 7 of that hundred, with the three levels in blocks of
# three. The second grand-fantasy batch starts at 201 and the counterweight
# batch at 1101, so any number of batches can be checked with the same rules.
BATCH_STARTS = (101, 201, 301, 401, 501, 601, 701, 801, 901, 1001, 1101)
# Indexed by level, then by band (short, medium, long).
BAND_RANGE = (
    ((1_100, 1_500), (1_800, 2_200), (2_500, 2_900)),
    ((2_700, 3_300), (3_700, 4_300), (4_600, 5_100)),
    ((4_200, 4_800), (5_600, 6_200), (6_800, 7_000)),
)
TARGET_WORDS = {"accessible": 100, "intermediate": 170, "advanced": 240}
WORD_RE = re.compile(r"\b[\w’'-]+\b", re.UNICODE)
NUMBERED_HEADING_RE = re.compile(r"^#{1,6}\s+", re.MULTILINE)


def kebab(title: str) -> str:
    cleaned = title.replace("’", "").replace("'", "").replace("&", " and ")
    return re.sub(r"[^a-z0-9]+", "-", cleaned.lower()).strip("-")

def level_for(number: int) -> tuple[str, int] | None:
    """Return (level, index of the first story in that level) for a number."""
    for start in BATCH_STARTS:
        offset = number - start
        if 0 <= offset <= 8:
            level = LEVELS[offset // 3]
            return level, start + (offset // 3) * 3
    return None



def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strict-band", action="store_true", help="fail on out-of-band word counts")
    args = parser.parse_args(argv)

    problems: list[str] = []
    checked = 0
    for bible in sorted(WORLDS.glob("*.md")):
        in_titles = False
        for line in bible.read_text(encoding="utf-8").splitlines():
            if line.strip().lower() == "## titles":
                in_titles = True
                continue
            if in_titles and line.startswith("## "):
                break
            match = TITLES_RE.match(line.strip()) if in_titles else None
            if not match:
                continue
            number, title = int(match.group(1)), match.group(2)
            placement = level_for(number)
            if placement is None:
                problems.append(f"{bible.name}: number {number} is in no level range")
                continue
            level, level_start = placement
            path = ROOT / "manuscripts" / level / f"{number}-{kebab(title)}.md"
            checked += 1
            if not path.is_file():
                problems.append(f"{title}: missing {path.relative_to(ROOT)}")
                continue
            text = path.read_text(encoding="utf-8")
            headings = NUMBERED_HEADING_RE.findall(text)
            if len(headings) != 1:
                problems.append(f"{path.name}: has {len(headings)} headings, expected 1")
                continue
            h1 = H1_RE.match(text.splitlines()[0])
            if h1 is None or h1.group(1) != title:
                problems.append(f"{path.name}: H1 {h1.group(1) if h1 else None!r} != bible title {title!r}")
                continue
            words = len(WORD_RE.findall(text))
            band = (number - level_start) % 3
            low, high = BAND_RANGE[LEVELS.index(level)][band]
            if not low <= words <= high:
                message = f"{path.name}: {words} words outside {low}-{high} band"
                if args.strict_band:
                    problems.append(message)
                else:
                    print(f"  note: {message}")
            pages = -(-words // TARGET_WORDS[level])
            if pages > 30:
                problems.append(f"{path.name}: splits into {pages} pages, over the 30-page cap")

    print(f"checked {checked} stories across {len(list(WORLDS.glob('*.md')))} world bibles")
    for problem in problems:
        print(f"  {problem}", file=sys.stderr)
    if problems:
        print(f"{len(problems)} problem(s)", file=sys.stderr)
        return 1
    print("all stories present, correctly levelled, titled and sized")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

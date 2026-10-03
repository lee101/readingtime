# Batch: Deep Tales

Twelve standalone stories, numbered 122 to 133, in one shared register: a modern
Japanese anime film still, drawn rather than painted. Nothing in the batch shares
a setting, a cast or a canon with anything else. What they share is a kind of
story — a small place, a competent person doing a real job, a problem that costs
something to solve, and a last page that does not tidy up. These are the heavier
cousins of the folk-tales batch: no magic engines, no folklore shapes borrowed
from anywhere, just ordinary people under ordinary pressure, written so that a
reader between eleven and seventeen finds their own life in them.

The anime register is not a costume. It means: clean confident linework, even cel
shading, soft hand-painted background art, and faces drawn simply and close to
the reader's own age. Hands and eyes carry the emotion; the writing in the page
does not tell them what to feel. Clothes are ordinary and worn. The drama is
competence under pressure — a mended radio, a rain tally, a bridge load, a
translated will — and the turns come out of the job itself, never out of a
coincidence or a new rule invented at the end.

The `## Stories` list is deliberately not called `## Titles`.
`scripts/check_grand_fantasy_batch.py` reads every bible in this directory and
assumes a `## Titles` list of `- <number> <Title>` lines whose numbers sit in a
reserved world range (101-109, 201-209, ... 1001-1009). These twelve numbers are
in no world range, so putting them under `## Titles` would make that gate fail.

## Visual Style

Modern Japanese anime film still: clean confident linework, even cel shading, soft hand-painted background art, luminous color, and one warm key light against a cool shade. Faces are simply drawn and close to the reader's own age, and hands and eyes do the work. Clothes are ordinary and worn. One countable object sits in the foreground of every plate: a dial, a tally board, a bread board, a gate latch, a spool, a chart, a fuse, a page, a chart rail.

## Style length

Keep the paragraph above under a hundred words and write it as what the picture
IS. `generate_manuscript_page_art.compose_prompt` appends it verbatim to every
page prompt, so its length lands on top of the scene; the folk-tales batch spent
four days finding that out the hard way. The medium itself comes from
`--style anime` in `generate_manuscript_covers.py` and
`generate_manuscript_page_art.py`, which select the anime sentence from
`MEDIUM_BY_STYLE`; the paragraph here adds the batch's palette on top of that and
must not contradict it.

## Stories

- 122 The Boy Who Mended the Radio (accessible)
- 123 The Girl Who Kept the Rain Tally (accessible)
- 124 The Baker Who Broke His Own Rule (accessible)
- 125 The Dog Who Waited at the Gate (accessible)
- 126 The Girl Who Learned the Wind's Names (intermediate)
- 127 The Summer the River Was Sold (intermediate)
- 128 The Boy Who Ran the Night Ferry (intermediate)
- 129 The House That Moved Up the Hill (intermediate)
- 130 The Cartographer's Son (advanced)
- 131 The Winter the Lights Went Out (advanced)
- 132 The Language Nobody Taught Her (advanced)
- 133 The Second Chart (advanced)

## Numbers

The band 122-133 is reserved for this batch and is free in all three level
directories. It is not a world range: the world ranges are 101-109, 201-209,
301-309, 401-409, 501-509, 601-609, 701-709, 801-809, 901-909 and 1001-1009, one
hundred each, nine stories per world.

## Page and cover geometry

Covers are 1024x1536 portrait, the shape `.card-cover` crops to. Page art is
768x768 square, because the reader caps a page image at the slide height against
a half-width column, so a portrait page image would leave half the slide black.

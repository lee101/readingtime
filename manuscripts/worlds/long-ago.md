# Batch: Ordinary Centuries

Twelve standalone stories, numbered 182 to 193, in one shared register: a
painterly picture-book illustration of work in the past, told from inside a job
nobody would put on a monument. Nothing in the batch shares a setting, a cast or
a canon with anything else; the centuries never meet. What they share is a rule —
the person in each story is competent, and the story is about the competence.

No magic, no gods, no prophecy, and no clever trick. The gruel is ground because
a person has to grind it every morning. A typist composes a forme by hand and the
day comes out crooked and comes out again. A signalman learns that a mistake is
not a matter of shame but a matter of the block behind him. A clerk copies a
ledger twice so that the columns still balance. The subject of each story is a
craft or a system at the moment it is hard: the millrace in a drought, the kiln
that will not reach temperature, the ration book where fair and legal come apart.

The history arrives as a job's own arithmetic — a pound of charcoal out of a
whole wood, a miller's dues in kind, a tide the ferryman had to beat. Nothing is
used to say "life was hard". It is only shown, by somebody losing a day's work to
it. The turn in every story comes out of the craft: a seam that will not hold
water, a lease that binds a mill, a wheel tooth replaced in the wrong order, a
naturalist's specimen that turns out to be a different animal.

The `## Stories` list is deliberately not called `## Titles`.
`scripts/check_grand_fantasy_batch.py` reads every bible in this directory and
assumes a `## Titles` list of `- <number> <Title>` lines whose numbers sit in a
reserved world range (101-109, 201-209, ... 1001-1009). These twelve numbers are
in no world range, so putting them under `## Titles` would make that gate fail.

## Visual Style

Painterly picture-book illustration of the working past, with soft brushwork and
weathered colour. The person fills most of the frame and is alone in it, with one
countable object beside them — a quern stone, a kiln gauge, a composing stick, a
signal token, a ledger, a mill wheel tooth, a pressed plant. Behind the figure
sits the working place with its tools worn shiny: a threshing floor, a print shop,
a signal cabin, a marshalling yard, a boat deck. Light is honest and low, from a
window, a lamp, or an open fire. Colours are the colours of materials and dust:
oat, oak, soot, iron, linen, lamp black, one bright thing per picture.

## Style length

Keep the paragraph above under a hundred words and write it as what the picture
IS. `generate_manuscript_page_art.compose_prompt` appends it verbatim to every
page prompt, so its length lands on top of the scene. The medium itself comes
from `--style painterly`, the default; this paragraph adds the batch's palette on
top of it and must not contradict it.

## Stories

- 182 The Boy Who Ground the Quern (accessible)
- 183 The Girl Who Mended the Kiln (accessible)
- 184 The Boy Who Kept the Fire in the Pit (accessible)
- 185 The Girl Who Unwove the Basket (accessible)
- 186 The Boy Who Worked the Watermill (intermediate)
- 187 The Girl Who Set the Type (intermediate)
- 188 The Boy Who Signalled the Railway (intermediate)
- 189 The Girl Who Kept the Ration Book (intermediate)
- 190 The Woman Who Ran the Ferry Timetable (advanced)
- 191 The Boy Who Copied the Ledger (advanced)
- 192 The Girl Who Mended the Great Wheel (advanced)
- 193 The Girl Who Read the Field Notes (advanced)

## Numbers

The band 182-193 is reserved for this batch and is free in all three level
directories. It is not a world range: the world ranges are 101-109, 201-209,
301-309, 401-409, 501-509, 601-609, 701-709, 801-809, 901-909 and 1001-1009, one
hundred each, nine stories per world.

## Page and cover geometry

Covers are 1024x1536 portrait, the shape `.card-cover` crops to. Page art is
768x768 square, because the reader caps a page image at the slide height against
a half-width column, so a portrait page image would leave half the slide black.
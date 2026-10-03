# Batch: Deep Water

Twelve standalone stories, numbered 158 to 169, in one shared register: a
painterly picture-book illustration of the sea and the people who work it.
Nothing in the batch shares a setting, a cast or a canon with anything else. What
they share is a subject — salt water, and the fact that every single thing in it
is measured, counted or negotiated by somebody who depends on the answer.

The rule of the batch: the sea is never scenery. It is a working surface. Every
story is about a measurement that somebody takes and a decision that falls out of
it — a rock pool surveyed as the tide drops, a shoal counted from a boat deck, a
fluke photographed at four hundred metres and matched to a catalogue, a tide
table read the wrong way round by one hour. The natural history is the plot, not
the decoration: a hermit crab has to trade up a shell or die, a kelp forest is one
animal pretending to be a forest, a seabird colony is a number that a method can
raise or lower by a third.

No magic anywhere in the batch, no luck. The turn comes out of the mechanism: a
spring tide that was not on the chart, an urchin barren that a winter storm
cannot explain, a chart drawn in 1911 that the multibeam finally withdraws. The
sea does what the sea does, and the people are the ones who have to revise.

The `## Stories` list is deliberately not called `## Titles`.
`scripts/check_grand_fantasy_batch.py` reads every bible in this directory and
assumes a `## Titles` list of `- <number> <Title>` lines whose numbers sit in a
reserved world range (101-109, 201-209, ... 1001-1009). These twelve numbers are
in no world range, so putting them under `## Titles` would make that gate fail.

## Visual Style

Painterly picture-book illustration of the sea, with soft brushwork and wet
luminous colour. The person fills most of the frame and is alone in it, with one
countable object beside them — a tide table, a sounding line, a net needle, a
scale pan, a caron glass, a chart tube. Behind the figure the water keeps its own
weather: kelp holdfasts, wet rock, a grey horizon, a boat rail, a wheelhouse
window. Light is honest — low sun on water, a deck lamp, a lighthouse beam
somewhere out of frame. Colours are the colours of a working coast: slate green,
rope tan, rust, wet stone, zinc white, buoy red.

## Style length

Keep the paragraph above under a hundred words and write it as what the picture
IS. `generate_manuscript_page_art.compose_prompt` appends it verbatim to every
page prompt, so its length lands on top of the scene. The medium itself comes
from `--style painterly`, the default; this paragraph adds the batch's palette on
top of it and must not contradict it.

## Stories

- 158 The Girl Who Kept the Rock Pool Book (accessible)
- 159 The Boy Who Watched the Herring (accessible)
- 160 The Girl Who Mended the Net (accessible)
- 161 The Crab That Was Not a Crab (accessible)
- 162 The Woman Who Read the Tide Table (intermediate)
- 163 The Boy Who Tracked the Whale Flukes (intermediate)
- 164 The Girl Who Kept the Fish Ledger (intermediate)
- 165 The Boy Who Watched the Marsh (intermediate)
- 166 The Woman Who Named the Kelp Forest (advanced)
- 167 The Girl Who Counted the Seabirds (advanced)
- 168 The Boy Who Mended the Lighthouse Lamp (advanced)
- 169 The Woman Who Mapped the Seabed (advanced)

## Numbers

The band 158-169 is reserved for this batch and is free in all three level
directories. It is not a world range: the world ranges are 101-109, 201-209,
301-309, 401-409, 501-509, 601-609, 701-709, 801-809, 901-909 and 1001-1009, one
hundred each, nine stories per world.

## Page and cover geometry

Covers are 1024x1536 portrait, the shape `.card-cover` crops to. Page art is
768x768 square, because the reader caps a page image at the slide height against
a half-width column, so a portrait page image would leave half the slide black.
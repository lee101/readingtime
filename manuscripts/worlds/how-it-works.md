# Batch: How It Works

Twelve standalone stories, numbered 146 to 157, in one shared register: a
painterly picture-book illustration of ordinary work. Nothing in the batch shares
a setting, a cast or a canon with anything else. What they share is a shape — one
real mechanism, one person who has to get it right, a problem that costs
something, and a last page where the mechanism has explained itself without
anyone saying so.

The rule of the batch: the science is never announced. It arrives as arithmetic,
as a thing that broke, or as a number somebody would not accept. A canal lock
story is about a leak; the reader who knows that a lock works by letting water in
slowly gets more out of it than they are told, and a reader who does not still
gets a story about a girl who was right. Every one of these is true. None of them
is a textbook. A bee hive is not a lesson in hexagons; it is a boy's arithmetic
over a winter. A heart is not a diagram; it is a person who is surprised by what
their own body does on a hill.

No magic anywhere in the batch, and no coincidence that carries the plot. The
turn comes out of the mechanism: a gauge that has been lying by two millimetres,
a pump that coughs because its foot valve is worn, a grid that will not hold
frequency because one plant is off. Educational in the way a good job teaches you
— by making you pay attention.

The `## Stories` list is deliberately not called `## Titles`.
`scripts/check_grand_fantasy_batch.py` reads every bible in this directory and
assumes a `## Titles` list of `- <number> <Title>` lines whose numbers sit in a
reserved world range (101-109, 201-209, ... 1001-1009). These twelve numbers are
in no world range, so putting them under `## Titles` would make that gate fail.

## Visual Style

Painterly picture-book illustration, warm and textured, with soft brushwork and
luminous colour. The person fills most of the frame and is alone in it, with one
countable object beside them — a gauge, a valve, a jar, a dial, a switch, a ruler.
Behind the figure, one step back and a little soft, sits the place the work
happens in: a lock chamber, a boiler room, a hiveshed, a hillside, a shoreline.
Light is honest daylight or honest lamplight, never studio. Colours are the
colours of the job — brass, slate, wet green, rust, bone, lamp gold.

## Style length

Keep the paragraph above under a hundred words and write it as what the picture
IS. `generate_manuscript_page_art.compose_prompt` appends it verbatim to every
page prompt, so its length lands on top of the scene. The medium itself comes
from `--style painterly`, the default; this paragraph adds the batch's palette on
top of it and must not contradict it.

## Stories

- 146 The Boy Who Counted the Bees (accessible)
- 147 The Girl Who Ran the Canal Lock (accessible)
- 148 The Seed in the Metal Tin (accessible)
- 149 The Thermometer in the Shade (accessible)
- 150 The Boy Who Read the Wind (intermediate)
- 151 The Girl Who Mended the Water Pump (intermediate)
- 152 The Boy Who Mapped the Echo (intermediate)
- 153 The Girl Who Kept the Glass House Warm (intermediate)
- 154 The Woman Who Weighed the River (advanced)
- 155 The Boy Who Ran the Grid (advanced)
- 156 The Girl Who Listened to the Valve (advanced)
- 157 The Man Who Mapped the Noise (advanced)

## Numbers

The band 146-157 is reserved for this batch and is free in all three level
directories. It is not a world range: the world ranges are 101-109, 201-209,
301-309, 401-409, 501-509, 601-609, 701-709, 801-809, 901-909 and 1001-1009, one
hundred each, nine stories per world.

## Page and cover geometry

Covers are 1024x1536 portrait, the shape `.card-cover` crops to. Page art is
768x768 square, because the reader caps a page image at the slide height against
a half-width column, so a portrait page image would leave half the slide black.
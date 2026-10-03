# Batch: Night Sky

Twelve standalone stories, numbered 170 to 181, in one shared register: a
painterly picture-book illustration of people who watch the sky for a living.
Nothing in the batch shares a setting, a cast or a canon with anything else. What
they share is a subject — the sky as something you measure — and a rule: nobody
in this batch is allowed to be impressed by a view.

Every story starts on the ground. A boy counts meteors and has to throw away the
ones he counted wrong. A girl waits twenty minutes in the dark before she can see
the field, because that is how long her eyes take, and the boy who ruins it with
a torch ruins it for everybody. A man listens for a planet around another star and
the evidence is a wobble of a metre per second in a line nobody else believes.
The astronomy is the labour, not the awe: dark adaptation, seeing, transparency,
a magnitude scale that is a formula, an eclipse that only happens somewhere on
Earth on a day in August, a parallax argument fought over parallax in
milliarcseconds.

No magic anywhere in the batch. Every turn comes out of the physics: the wrong
unit, the wrong sky, the wrong night of the year, the season of the stars
themselves. What the reader gets at the end is not awe but a skill — the ability
to look at something enormous and think about the error in the measurement.

The `## Stories` list is deliberately not called `## Titles`.
`scripts/check_grand_fantasy_batch.py` reads every bible in this directory and
assumes a `## Titles` list of `- <number> <Title>` lines whose numbers sit in a
reserved world range (101-109, 201-209, ... 1001-1009). These twelve numbers are
in no world range, so putting them under `## Titles` would make that gate fail.

## Visual Style

Painterly picture-book illustration of the night, with soft brushwork and deep
luminous colour. The person fills most of the frame and is alone in it, with one
countable object beside them — a star chart, a stopwatch, a torch, a notebook, a
pair of binoculars, a gnomon, a dish. Behind the figure the sky does its own
work: a field of stars, a milky band, a low ridge, a dome, the lit rectangle of a
control-room window. Light is honest and scarce — starlight on a face, red lamp
light on hands, moonlight on a board. Colours are the colours of a night
observatory: ink blue, silver, chart-paper cream, red lamp, frost white.

## Style length

Keep the paragraph above under a hundred words and write it as what the picture
IS. `generate_manuscript_page_art.compose_prompt` appends it verbatim to every
page prompt, so its length lands on top of the scene. The medium itself comes
from `--style painterly`, the default; this paragraph adds the batch's palette on
top of it and must not contradict it.

## Stories

- 170 The Boy Who Counted the Meteors (accessible)
- 171 The Girl Who Waited for the Dark (accessible)
- 172 The Boy Who Measured the Shadow (accessible)
- 173 The Girl Who Kept the Observatory Log (accessible)
- 174 The Boy Who Watched the Aurora (intermediate)
- 175 The Girl Who Found the Comet (intermediate)
- 176 The Boy Who Listened for the Pulsar (intermediate)
- 177 The Girl Who Timed the Occultation (intermediate)
- 178 The Woman Who Counted the Photons (advanced)
- 179 The Boy Who Waited for the Eclipse (advanced)
- 180 The Girl Who Argued About the Parallax (advanced)
- 181 The Man Who Listened for a Planet (advanced)

## Numbers

The band 170-181 is reserved for this batch and is free in all three level
directories. It is not a world range: the world ranges are 101-109, 201-209,
301-309, 401-409, 501-509, 601-609, 701-709, 801-809, 901-909 and 1001-1009, one
hundred each, nine stories per world.

## Page and cover geometry

Covers are 1024x1536 portrait, the shape `.card-cover` crops to. Page art is
768x768 square, because the reader caps a page image at the slide height against
a half-width column, so a portrait page image would leave half the slide black.
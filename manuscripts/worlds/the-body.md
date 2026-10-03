# Batch: The Body

Twelve standalone stories, numbered 210 to 221, in one shared register: a
painterly picture-book illustration of a body and the ordinary business of being
one. Nothing in the batch shares a setting, a cast or a canon with anything else.
What they share is a shape — a person whose own body surprises them, and a second
person who knows why.

The rule of the batch: no bodies are creepy and nobody is a case. A heart is a
sound you can hear through a chestpiece and a number that changes when you run up
a hill. A cast is six weeks of not running. An immune response is a system that
remembers, and the second dose is quiet because of the memory, which is why the
injection exists. Sleep is not rest; it is a cycle with a shape. A nerve is a
cable, and the fingertip is a very high-resolution part of it. Every mechanism is
real and every number is checkable, and the story is always about the moment
somebody's own body disagreed with what they expected.

No magic and no miracle cures. A diet is not a moral judgement. The turn comes out
of the physiology: a pulse that will not settle, a reflex that fires without the
brain being asked, a breath held past the point where the reason to breathe
changes. The reader finishes knowing a fact about their own body and knowing one
person who could have told them sooner.

The `## Stories` list is deliberately not called `## Titles`.
`scripts/check_grand_fantasy_batch.py` reads every bible in this directory and
assumes a `## Titles` list of `- <number> <Title>` lines whose numbers sit in a
reserved world range (101-109, 201-209, ... 1001-1009). These twelve numbers are
in no world range, so putting them under `## Titles` would make that gate fail.

## Visual Style

Painterly picture-book illustration of a real place with a real body in it, with
soft brushwork and warm clear colour. The person fills most of the frame and is
alone in it, with one countable object beside them — a chestpiece, a plaster cast,
a stopwatch, a food diary, a blood-pressure cuff, a jar of specimens, a running
shoe. Behind the figure the room keeps its own light: a kitchen table, a school
gym, a hospital corridor, a bedroom at night, a hill path. Light is honest —
window, lamp, or early morning. Colours are the colours of ordinary health and
ordinary care: cotton white, plaster, wood, warm skin, one strong accent per
picture.

## Style length

Keep the paragraph above under a hundred words and write it as what the picture
IS. `generate_manuscript_page_art.compose_prompt` appends it verbatim to every
page prompt, so its length lands on top of the scene. The medium itself comes
from `--style painterly`, the default; this paragraph adds the batch's palette on
top of it and must not contradict it.

## Stories

- 210 The Girl Who Counted Her Heartbeats (accessible)
- 211 The Boy Who Wore the Cast (accessible)
- 212 The Girl Who Slept Eleven Hours (accessible)
- 213 The Boy Who Blinked on Command (accessible)
- 214 The Girl Who Was Ready for the Needle (intermediate)
- 215 The Boy Who Ran Out of Breath on the Hill (intermediate)
- 216 The Girl Who Kept the Food Diary (intermediate)
- 217 The Boy Who Saw the Colours Apart (intermediate)
- 218 The Woman Who Kept the Body's Ledger (advanced)
- 219 The Boy Who Ran the Machine That Measures You (advanced)
- 220 The Woman Who Mapped the Skin (advanced)
- 221 The Boy Who Held His Breath (advanced)

## Numbers

The band 210-221 is reserved for this batch and is free in all three level
directories. It is not a world range: the world ranges are 101-109, 201-209,
301-309, 401-409, 501-509, 601-609, 701-709, 801-809, 901-909 and 1001-1009, one
hundred each, nine stories per world.

## Page and cover geometry

Covers are 1024x1536 portrait, the shape `.card-cover` crops to. Page art is
768x768 square, because the reader caps a page image at the slide height against
a half-width column, so a portrait page image would leave half the slide black.
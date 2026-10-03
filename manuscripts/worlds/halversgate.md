# Batch: Halversgate

Twelve standalone stories, numbered 134 to 145, set in and around one invented
town called **Halversgate**, and drawn as comics rather than as paintings or
anime. This is the batch where a person can do something impossible, and where
the impossible thing has a price attached to it that is stated in the first
three paragraphs and collected at the end.

The register is superhero fiction with the seat taken out. Halversgate has a
cape, a signal lamp in a water tower, a volunteer programme, a committee that
audits hours, and a local paper. It does not have a convention, a press, or a
costume designer. The heroes are tired, they are paid badly or not at all, they
are known by sight rather than by name, and the interesting part is always the
job — the roster, the paperwork, the small print on a mask, the third day of a
thing that was meant to last one.

Two of the stories cross over with earlier batches, deliberately and quietly: a
Halversgate paper runs items about people the reader has already met. The boy
who mended the radio in a fishing village (**122**) and the old man who kept the
rain tally in a town that sets its year by rain (**123**) both appear by name in
**142**, as three lines of local news nobody in Halversgate thinks twice about.
A reader who has finished those books will recognise them and a reader who has
not will not be lost.

The `## Stories` list is deliberately not called `## Titles`.
`scripts/check_grand_fantasy_batch.py` reads every bible in this directory and
assumes a `## Titles` list of `- <number> <Title>` lines whose numbers sit in a
reserved world range (101-109, 201-209, ... 1001-1009). These twelve numbers are
in no world range, so putting them under `## Titles` would make that gate fail.

## Visual Style

Bold black ink linework, flat saturated colour, hard shadow shapes, soft halftone dots, one bright accent per plate, dramatic low angles and foreshortening. Halversgate is a grey harbour town: wet stone, brick, slate, gulls, a lighthouse, a water tower, and a great deal of bad weather. One single image fills the frame: no panels, no gutters, no frames, no borders, no captions, no speech balloons, no lettering and no sound effects.

## Style length

Keep the paragraph above under a hundred words and write it as what the picture
IS. `generate_manuscript_page_art.compose_prompt` appends it verbatim to every
page prompt, so its length lands on top of the scene. The medium itself comes
from `--style comic` in `generate_manuscript_covers.py` and
`generate_manuscript_page_art.py`, which select the comic sentence from
`MEDIUM_BY_STYLE`; the paragraph here adds the town's palette on top of that and
must not contradict it.

The comic register has one failure the other two do not: asked for "comic", the
model wants to draw a page of panels with speech balloons in it. Every prompt in
this batch therefore carries an explicit "one single image, not a panel" clause
and an explicit no-balloons clause, and the generated art is checked for it.

## Stories

- 134 The Boy Who Drew the Bridge (accessible)
- 135 The Girl Who Ran Faster Than the Sirens (accessible)
- 136 The Boy Who Kept the Cape (accessible)
- 137 The Light in the Water Tower (accessible)
- 138 The One Good Mission (intermediate)
- 139 The Sidekick Who Kept the Records (intermediate)
- 140 The Man Who Could Lift the Town's Roof (intermediate)
- 141 The Mask Was a Contract (intermediate)
- 142 The Committee That Audits the Heroes (advanced)
- 143 The League of One (advanced)
- 144 The Girl Who Inherited a God (advanced)
- 145 The Origin Story They Printed Without Asking Him (advanced)

## Numbers

The band 134-145 is reserved for this batch and is free in all three level
directories. It is not a world range: the world ranges are 101-109, 201-209,
301-309, 401-409, 501-509, 601-609, 701-709, 801-809, 901-909 and 1001-1009, one
hundred each, nine stories per world.

## Page and cover geometry

Covers are 1024x1536 portrait, the shape `.card-cover` crops to. Page art is
768x768 square, because the reader caps a page image at the slide height against
a half-width column, so a portrait page image would leave half the slide black.

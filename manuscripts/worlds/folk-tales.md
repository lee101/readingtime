# Batch: Folk Tales

Twelve standalone tales, numbered 110 to 121, in the shape of traditional and tradition-inspired folklore rather than in one shared invented world. Nothing in this batch shares a setting, a cast or a canon with any other story here; what they share is a register. Each is a self-contained oral tale with one hard rule of magic, stated once, obeyed to the end, and a turn that falls out of that rule rather than out of luck. Eight of the twelve end on a stated meaning, said in the village's own voice; four end on an image and leave the meaning alone. The folklore shapes are public-domain ones — the well that answers questions, the tailor whose seam must be true, the taboo river-name, the good loaf, the wind that must be fed, the tests on the road, the wishing galoshes, the chair nobody will take, the guest who must be guessed, the yearly blessing, the talking horse, the winter in a jar. The tales themselves are newly written and their villages do not exist.

The `## Stories` list below is deliberately not called `## Titles`. `scripts/check_grand_fantasy_batch.py` reads every bible in this directory and assumes a `## Titles` list of `- <number> <Title>` lines whose numbers sit in a reserved world range (101-109, 201-209, ... 1001-1009). These twelve numbers are in no world range, so putting them under `## Titles` would make that gate fail. Renaming that heading will break `check_grand_fantasy_batch.py`; fix the gate instead if the batch ever grows a world range of its own.

## Visual Style

Warm painterly oil painting, soft brushwork, canvas texture, honest plain faces, one warm light source in a cold blue shade, oak brown and oat and lichen with one bright accent of colour on a garment or a single object, linen and unglazed clay and blackened iron and birch bark, long soft shadows. One countable object in the foreground.

## Style length

Keep the paragraph above under a hundred words, and write it as what the picture IS rather than what it is not. `generate_manuscript_page_art.compose_prompt` appends it verbatim to every page prompt, so its length is added to the scene. At 214 words the composed prompt ran to 340 words, most of it prohibition, and Qwen answered the first page of this batch correctly and every page after it with pure noise. The other twenty-four bibles sit between 113 and 179 words.

## Stories

- 110 The Well That Only Answered Questions (accessible)
- 111 The Tailor and the Nine Seams (accessible)
- 112 The River That Asked for a Name (accessible)
- 113 The Loaf That Fed Nine (accessible)
- 114 The Boy Who Fed the Wind (accessible)
- 115 The Grandmother Who Kept the Second Story (intermediate)
- 116 The Year Without Feet (intermediate)
- 117 Nobody Would Sit in the Fourth Chair (intermediate)
- 118 The Guest Who Had to Be Guessed (advanced)
- 119 The Blessing That Repeated Itself (advanced)
- 120 The Boy Who Heard the Horse (advanced)
- 121 The Winter in the Jar (advanced)

## Numbers

The band 110-121 is reserved for this batch and is free in all three level directories. It is not a world range: the world ranges are 101-109, 201-209, 301-309, 401-409, 501-509, 601-609, 701-709, 801-809, 901-909 and 1001-1009, one hundred each, nine stories per world.

## Page and cover geometry

Covers are 1024x1536 portrait, the shape `.card-cover` crops to. Page art is 768x768 square, because the reader caps a page image at the slide height against a half-width column, so a portrait page image would leave half the slide black.

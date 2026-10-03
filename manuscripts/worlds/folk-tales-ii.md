# Batch: Folk Tales II

Twelve standalone tales, numbered 222 to 233, in the shape of traditional and tradition-inspired folklore and nowhere else. Nothing in this batch shares a setting, a cast or a canon with any other story here; what they share is a register. Each is a self-contained oral tale with one hard rule of magic, stated once by a villager and obeyed to the end, and a turn that falls out of that rule rather than out of luck. Eight end on a stated meaning, said in the village's own voice; four end on an image and leave the meaning alone.

The batch rule: the magic is bookkeeping. Nothing in these tales is a wish, a monster or a treasure — the rule is a lie, a debt, a name, a word, a measurement, an accounting, and it works the same way on the clever as on the greedy. No luck, no coincidence and no hidden helper carries a plot. The last page is either a thing somebody says in their own words, or a picture, and never a narrator explaining what it all meant.

The shapes are public-domain or tradition-inspired — the dog that knows, the cradle that will not be rocked, the plant in the field of the quarrel, the one command, the bride who keeps the slate, the sleeping sleeper — but the villages do not exist and the tales are newly written. Half of them take something readers think they already know and turn it around: the bark is the alarm and the silence is the danger, the ring grants precision and not power, the water-bride is a clerk and the debt is ended by paying it in full rather than by dying prettily.

The `## Stories` list is deliberately not called `## Titles`. `scripts/check_grand_fantasy_batch.py` reads every bible in this directory and assumes a `## Titles` list of `- <number> <Title>` lines whose numbers sit in a reserved world range (101-109, 201-209, ... 1001-1009). These twelve numbers are in no world range, so putting them under `## Titles` would make that gate fail.

## Visual Style

Painterly storybook oil, warm and plain. Weathered faces, work-worn hands, soft visible brushwork and canvas tooth, one warm light against a cold blue shade, long soft shadows. Oak brown and oat and lichen with one bright accent on a garment or a single object. Linen, unglazed clay, blackened iron, birch bark, wet stone. One countable object in the foreground. The person is close in, alone in the frame, and the place sits one step back behind them.

## Style length

Keep the paragraph above under a hundred words and write it as what the picture IS, not what it is not. `generate_manuscript_page_art.compose_prompt` appends it verbatim to every page prompt, so its length lands on top of the scene. The medium comes from `--style painterly`, the default; this paragraph adds the batch's palette and must not contradict it.

## Stories

- 222 The Hound That Would Not Bark (accessible)
- 223 The Cradle That Would Not Be Rocked (accessible)
- 224 The Boy Who Planted the Argument (accessible)
- 225 The Candle That Burned Downward (accessible)
- 226 The Ring That Understood One Command (intermediate)
- 227 The Stairs That Stood One Step Higher (intermediate)
- 228 The Comb the River Gave Back (intermediate)
- 229 The Lake That Would Not Reflect the Reeve (intermediate)
- 230 The Orchard Where the Promises Were Buried (advanced)
- 231 The Sleeper Who Must Be Named Exactly (advanced)
- 232 The Year the River Was Owed (advanced)
- 233 The Fire That Fed on Words (advanced)

## Numbers

The band 222-233 is reserved for this batch and is free in all three level directories. It is not a world range: the world ranges are 101-109, 201-209, 301-309, 401-409, 501-509, 601-609, 701-709, 801-809, 901-909 and 1001-1009, one hundred each, nine stories per world. Every other standalone batch holds a block of twelve nearby — folk-tales 110-121, deep-tales 122-133, halversgate 134-145, how-it-works 146-157, deep-water 158-169, night-sky 170-181, long-ago 182-193 and the-body 210-221.

## Word bands

This batch is gated by `scripts/assemble_batch_manifest.py`, not by the grand-fantasy assembler, because the grand-fantasy assembler reads the number out of the reserved ranges. Accessible sits inside 750-850 words at 90 words a page, intermediate inside 1700-2100 at 130, advanced inside 2600-3200 at 200.

## Page and cover geometry

Covers are 1024x1536 portrait, the shape `.card-cover` crops to. Page art is 768x768 square, because the reader caps a page image at the slide height against a half-width column, so a portrait page image would leave half the slide black. Page prompts are one JSON fragment per story in `manuscripts/page-prompts/`, keyed to `world: folk-tales-ii`, and one subject per prompt: a page prompt naming two or more distinct people comes back as noise about half the time.

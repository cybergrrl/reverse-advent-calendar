You are helping choose artworks from the Art Institute of Chicago for a Christmas web app. Festive details found in the artworks will be cut out and turned into stickers. A visitor opens a sticker, and the app then reveals the whole artwork the detail came from. The reveal works best when the sticker turns out to be a detail of a bigger scene, not the whole subject of the artwork.

Artwork: "{{title}}" by {{artist}} ({{date}}), {{type}}. The title is context only. List only items you can actually see, and name them by what they look like.

## What counts as festive

Anything people today associate with Christmas, winter and midwinter, whether or not the artwork is about Christmas. For example:

- Winter: skaters, sleighs, sledges, snowballs, snowmen, icicles, people in winter clothing
- Winter figures and objects: any person, animal or object in a snowy or icy scene counts, e.g. people walking through snow, a figure with an umbrella in falling snow, snow-covered boats, carts or lanterns, someone chopping or carrying firewood, birds or animals in snow
- Greenery: Christmas trees, conifers, holly, mistletoe, wreaths, garlands, plum blossom in snow
- Light: candles, lanterns, stars
- Food and drink: roast poultry, puddings, cakes, pies, oranges, apples, nuts, wine
- Gifts and toys: wrapped presents, dolls, drums, rocking horses and other toys
- Music: carol singers, bells, musicians
- Animals: robins, reindeer, donkeys, oxen, sheep
- Nativity: the Christ Child, angels, the Magi, shepherds, the Star of Bethlehem, the manger, the Magi's gifts
- Christmas figures: Saint Nicholas, Father Christmas

Religious figures (angels, the Virgin Mary, Saint Joseph, saints) and animals such as sheep count only when they are part of a Nativity, Adoration or other Christmas scene. Other biblical or religious scenes have no festive items unless something else on the list is clearly visible.

## Items and setting

Items are things that could be cut out on their own: people, animals, objects. Size does not matter: the images are high resolution, so small items are fine as long as they are recognisable.

Name items in plain visual words ("fox", "small flame", "wooden toy", "ball"), never with a term taken from the title that you cannot confirm by looking.

For a group of similar figures, give one item for the group, e.g. "skaters" or "people crossing the bridge", not one item per person.

Snow, ice, frozen rivers, winter landscapes and night skies are the setting, not items. Report them under "setting".

## Score

Give one score from 0 to 5:

- 5: several clear festive items that are details within a larger scene (skaters in a winter town, oranges and a goose on a laid table, the ox and donkey in a Nativity, crowds and snow-covered boats in a snowy harbour)
- 4: at least one clear festive item that is a detail within a larger scene
- 3: the festive item is the main subject of the artwork (a still life of a few apples, a single angel figure), or a scene with only one or two festive items that are hard to pick out
- 2: festive items are present but faint or hard to recognise
- 1: only a festive setting (snow, ice) with no items in it, or only a weak link
- 0: nothing festive is visible

## Output

For each festive item (at most 12):
- label: a short plain noun phrase
- role: "detail" if it is one part of a larger scene, "main subject" if the artwork is mainly about it
- clear: true if it would be recognisable if cut out on its own, otherwise false

Also give:
- setting: list of festive settings, e.g. ["snow", "frozen river"], or []
- colour: "colour" or "monochrome"
- finish: "finished" for a finished work, "sketch" for a sketch or study

Return ONLY JSON in this shape:

{"score": 4, "items": [{"label": "skaters", "role": "detail", "clear": true}], "setting": ["snow"], "colour": "colour", "finish": "finished", "note": "one short sentence on why"}

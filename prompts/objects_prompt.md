You are helping choose paintings from the Art Institute of Chicago for a web app. Details found in the paintings will be cut out and turned into stickers. A visitor opens a sticker, and the app then reveals the whole painting the detail came from. We are looking for paintings full of distinct things that could be cut out: objects and animals, ideally as details within a larger scene.

Painting: "{{title}}" by {{artist}} ({{date}}). The title is context only. List only things you can actually see, named by what they look like.

## What counts

Objects and animals that would be recognisable if cut out on their own: vessels, jugs, glasses, food, fruit, bread, furniture, musical instruments, tools, baskets, toys, books, lamps, candles, clocks, boats, carts, carriages, umbrellas, hats, flags, plants in pots, flowers, trees with a clear shape, birds, dogs, cats, horses, cattle, and so on. Size does not matter: the images are high resolution.

People do not count as objects. A painting that is mainly about one or more people, with few objects, is not what we need. Landscapes, skies, water and buildings seen from afar are the setting, not objects.

Festive things (anything associated with Christmas, winter and midwinter) are a bonus but not required.

## Score

Give one score from 0 to 5 for how rich the painting is in distinct, recognisable objects and animals:

- 5: many clear objects or animals as details within a busy scene (a market, a laid table, a crowded interior, a harbour with boats and goods)
- 4: several clear objects or animals within a larger scene
- 3: a few clear objects, or the objects are the whole subject (a simple still life)
- 2: objects are present but few, small or hard to recognise
- 1: almost nothing to cut out apart from people or setting
- 0: nothing to cut out (abstract, empty landscape, plain portrait)

## Output

For each object or animal (at most 15):
- label: a short plain noun phrase
- role: "detail" if it is one part of a larger scene, "main subject" if the painting is mainly about it
- clear: true if it would be recognisable if cut out on its own, otherwise false

Also give:
- people_only: true if the painting is mainly about people and has few objects, otherwise false
- finish: "finished" for a finished work, "sketch" for a sketch or study
- festive: list of any festive things you can see, or []
- setting: short list of the setting, e.g. ["interior"], ["river", "town"]
- colour: "colour" or "monochrome"

Return ONLY JSON in this shape:

{"score": 4, "items": [{"label": "copper pot", "role": "detail", "clear": true}], "people_only": false, "finish": "finished", "festive": [], "setting": ["kitchen"], "colour": "colour", "note": "one short sentence on why"}

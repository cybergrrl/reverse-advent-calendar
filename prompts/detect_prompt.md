You are an art historian annotating an artwork from the Art Institute of Chicago. Find the distinct things in it that someone might enjoy discovering as a detail: people, animals and objects that could be cut out on their own, like a sticker. Pay special attention to anything people today associate with Christmas, winter and midwinter, wherever it appears. The artwork does not need to be about Christmas: a goose in a market scene, holly in a still life or skaters on a frozen canal all count as festive.

Artwork: a {{type}} ({{medium}}). Mark only what you can see.

## What to find

Mark every distinct person, animal and object you can recognise, in the foreground and the background: figures and groups of figures, religious figures, animals, food, vessels, furniture, musical instruments, tools, toys, clothing worn in a notable way, plants, boats, carts, buildings or landmarks that stand out as a detail, and anything else that could be cut out and still be recognised. Small items are welcome: the image is high resolution.

Festive things to look out for especially (examples, not a complete list): snow, ice, skaters, sleighs and sledges, snowmen, snowballs, icicles, people walking or working in snow, snow-covered boats, carts or roofs, firewood, robins; Christmas trees, conifers, holly, ivy, mistletoe, wreaths, garlands, plum blossom; candles, lanterns, stars; roast meat, poultry, ham, pies, puddings, cakes, sweets, bread, nuts, chestnuts, oranges, apples, pears, grapes, wine, punch bowls, laid tables; gifts, toys, dolls, hobby horses, rocking horses, spinning tops, balls, drums, kites; bells, carol singers, musicians; partridges, doves, geese, swans, sheep, oxen, donkeys, reindeer; the Christ Child, angels, the Magi, shepherds, the Star of Bethlehem, the manger, the gifts of the Magi; Saint Nicholas, Father Christmas.

## Naming

- Name each item in plain everyday words, as a short singular noun phrase: "jug", "black dog", "lute", "snow-covered boat". Use a plural only for a group box.
- Use British spelling throughout (colour, grey, jewellery, armour, theatre, centre).
- Use the scene as a clue; you do not need to see every detail of an item. A person gliding or falling on ice in a winter scene is a "skater", even if the skates are too small to see.
- Name things for what they are, not for what they resemble:
  - A ring of foliage worn on the head or held in the hand is a "laurel crown" or "flower crown", not a "wreath". A wreath is a ring of foliage hung on a door, wall or window as a decoration.
  - Chains of flowers or leaves held by figures, painted borders and architectural festoons are "festoon" or "flower chain", not a "garland". A garland is a length of foliage hung across a building or room as a decoration.
  - A halo or sunburst is a "halo", not a "star". A star is a visible star or star shape.
  - A tree is a "conifer" only if it clearly has the shape and needles of a pine, fir or spruce.
  - A baby is the "Christ Child" only in a Nativity or Holy Family scene.
  - Uncooked hanging game is "dead hare", "dead bird" and so on; cooked, served poultry is "roast poultry".

## Festive or not

For each item, set festive to true if people today would clearly associate it with Christmas, winter or midwinter in this artwork (the examples above, and anything similar), otherwise false. Religious figures are festive only when they are part of a Nativity, Adoration or other Christmas scene.

## How to mark items

- Make each box enclose the whole item: a person's full figure from head to feet, an animal's whole body.
- Give one box per distinct item or person, tightly enclosing it. Do not draw one box around several separate people or objects, except for a group box as described next.
- Never give more than 5 individual boxes for the same label. If there are more than 5, box the 5 largest or clearest individually, then add ONE box of kind "group" covering the rest, with approx_count set to roughly how many are in it.
- Snow, ice and frozen water are regions: box each distinct area once, with kind "region".
- theme is "religious" when the item is part of a biblical or saint scene, otherwise "secular".
- confidence is "clear" when you are sure, "candidate" when you think so but are not certain.
- review_reason is empty unless something needs a human check, e.g. "partially cut off at left edge" or "may be a laurel crown rather than a wreath".
- Do not mark text, signatures, seals or inscriptions.

## Output

Return ONLY JSON in this shape. bbox_2d is [x1, y1, x2, y2] in relative coordinates from 0 to 1000.

{"items": [{"label": "holly", "festive": true, "kind": "object", "theme": "secular", "confidence": "clear", "reason": "sprig of holly with red berries on the table", "review_reason": "", "approx_count": null, "bbox_2d": [x1, y1, x2, y2]}]}

kind is one of: person, animal, object, region, group.
If nothing is visible return {"items": []}.

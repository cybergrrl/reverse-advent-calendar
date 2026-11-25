# Reverse Advent Calendar with artworks from the Art Institute of Chicago

A Christmas calendar of 25 stickers cut from public-domain artworks in the Art Institute of Chicago. Open a door to explore the painting it came from, collect the stickers in an album, and decorate a Christmas card with them.

**Open the calendar:** https://cybergrrl.github.io/reverse-advent-calendar/

## Run it locally

Run it locally with `python3 serve_site.py` and open http://localhost:8766.

## How it was built

This was a vibe coding experiment using Claude to see what I can create with it.

**Claude Code** wrote the code: the selection, detection and cutout scripts, the review tools, the build script and the changes to the app. It also ran the models.
Claude also wrote descriptions for paintings that did not have one. It was instructed to stick to what is visible in each image and to facts in the museum's record. 

**I, the human** had the ideas and set the goals and rules (public domain only, what counts as festive, accuracy over polish). I directed layout and design and selected the final 25 door stickers by hand.
I also acted as the "human in the loop" - reviewing samples of the results at each stage to fine-tune the processes. I manually approved paid model runs too to make sure cost stayed way below £5. 


### Artworks:
Public-domain works with images from the [AIC API](https://api.artic.edu/docs/), filtered by festive words, rated for usable details by Qwen3-VL, then hand-picked (129 works).

### Details:
**Qwen3-VL** found and boxed the people, animals and objects in each work. Labels were grouped, reviewed by hand, and marked festive or not.

### Stickers:
Festive and starred details were cut out locally with **[MultiMatte](https://huggingface.co/feyninc/multimatte)** and given a white border.

### Image descriptions:
The AIC's own descriptions where they exist; for the rest, short descriptions written by Claude from the image and the catalogue record, marked "AI-written" in the app.

I checked only a sample of the descriptions and made Claude remove anything it was not sure about, rather than go through a lengthy manual process. 

### App:
A static site in `docs/` (no build step to view it). 

## Credits

Images: the Art Institute of Chicago, [CC0](https://creativecommons.org/publicdomain/zero/1.0/).

Christmas tree on the postcard: generated with [Leonardo.Ai](https://leonardo.ai).

AIC description texts: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) ([terms](https://www.artic.edu/terms)).

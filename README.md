# Reverse Advent Calendar: Art Institute of Chicago edition

A Christmas calendar of 25 stickers cut from public-domain artworks in the Art Institute of Chicago. Open a door to explore the painting it came from, collect the stickers in an album, and decorate a Christmas card with them.

## How it was built

1. **Artworks:** public-domain works with images from the [AIC API](https://api.artic.edu/docs/), filtered by festive words, rated for usable details by Qwen3-VL, then hand-picked (129 works).
2. **Details:** Qwen3-VL found and boxed the people, animals and objects in each work. Labels were grouped (so "dog" finds dogs in other paintings), reviewed by hand, and marked festive or not.
3. **Stickers:** festive and starred details were cut out locally with [MultiMatte](https://huggingface.co/feyninc/multimatte) and given a white border; weak cutouts were redone or replaced by a plain crop (648 stickers).
4. **Texts:** the AIC's own descriptions where they exist; for the rest, short descriptions written by Claude from the image and the catalogue record, marked "AI-written" in the app.
5. **App:** a static site in `site/` (no build step to view it), adapted from an earlier National Gallery version of the same calendar. `build_site.py` turns the reviewed data into `site/data/calendar.json`.

Run it locally with `python3 serve_site.py` and open http://localhost:8766.

## Credits

Images: the Art Institute of Chicago, [CC0](https://creativecommons.org/publicdomain/zero/1.0/). AIC description texts: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) ([terms](https://www.artic.edu/terms)).

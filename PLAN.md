# Reverse Advent Calendar: Art Institute of Chicago edition

Goal: the same calendar, album and postcard app as the National Gallery (NG) project, filled with festive details found in public-domain artworks from the Art Institute of Chicago (AIC).

The app is reused. The pipeline that feeds it is redesigned for the new source.

```
dump ─> text filter (836) ─> image rating ─> picker (200) ─> detection ─> review ─> cutouts ─> stickers ─> descriptions ─> app
```

**Rule for every step:** only works with `is_public_domain = true` and an `image_id`. Nothing else enters any list, count or download.

---

## 1. Facts about AIC (checked 23 November 2026)

- **Public-domain works with an image:** 59,063 of about 139,750 in the data dump. Of these, 24,696 prints, 7,562 drawings and watercolours, 1,936 paintings.
- **Licences:** images and all data are CC0, except the `description` field, which is CC BY 4.0. The museum requests this caption with every reproduction: "Artist. Title, Date. The Art Institute of Chicago." (https://www.artic.edu/image-licensing).
- **Alt text** (`thumbnail.alt_text`, CC0): present on every record but generic for 33,590 of 34,137 paintings, prints and drawings ("A work made of…"). Only 547 are real descriptions.
- **Subject tags:** 65% of paintings have them, but only about 2% of prints and drawings. For prints, the title is usually the only useful text.
- **API:** 60 requests a minute, and searches stop at 1,000 results. The website search ranks the whole collection rather than filtering it, which explains its odd results.
- **Data dump:** https://artic-api-data.s3.amazonaws.com/artic-api-data.tar.bz2 (130 MB, refreshed monthly). Stored in `source/aic-dump/` (git-ignored).
- **Images (IIIF 2):** masters are large (e.g. 6125×8002), but the server only answers `/full/843,/`, `/full/1686,/`, `/full/3000,/` and `/full/!3000,3000/`. Region crops and other sizes return 403, so all cropping is done locally from downloaded images.

---

## 2. Select the artworks

### 2.1 Text filter (done)

`scripts/build_pool.py` reads the dump and writes:
- `lists/aic_public_domain.jsonl`: all 59,063 public-domain records, with the useful fields only.
- `lists/pool.csv`: **836** candidates (542 prints, 163 paintings, 130 drawings, 1 miniature), with the matched words and fields.

Rules: paintings, prints, drawings and miniatures only. Strong words (Christmas, nativity, winter, snow, skating, sleigh, new year) match in any text field. Weaker words (angels, wreaths, candles, lanterns, feast, still life, toys, carols, robins) match only in the title or tags. Noisy words (gift, present, orange, bell) are left out. Angels count only alongside another festive word: on their own they mostly matched non-Christmas religious scenes (252 works dropped). Angels in nativity scenes are still found by rating and detection.

### 2.2 Image rating (next)

- [ ] Download the 843px image for each candidate into `runs/images_843/` (about 200 MB).
- [ ] Rate each image with a vision model: a 0 to 5 score for clear, sticker-sized festive items, plus a list of those items.
- [ ] **Decision pending:** hosted Qwen3-VL via OpenRouter (about $0.50, minutes, same model as detection) or a local Qwen3-VL around 8B (free, overnight).

### 2.2a Rating prompt: improvements to make

- [ ] **Labels borrowed from the title.** The prompt passes title, artist and date "as context only", but the model copies obscure terms from the title into its item list, e.g. "fox fires" (Hiroshige, "Fox Fires on New Year's Eve…") and a "New Year pull toy". It misses what is actually visible (the foxes themselves). Options: rate without the title, or run with and without the title on the same works and compare the item lists; ask for plain visual labels ("fox", "small flame") instead of named concepts.
- [ ] **Winter figures and objects count** (decided): people, animals and objects in winter scenes are items (Hiroshige's crowds on a snowy bridge, snow-covered boats, Pissarro's woodcutter). A scene with only snow and no items still scores low: it will not work in the app.
- [ ] **Title:** the rating may keep using the title as context; item detection (section 3) runs without it.
- [ ] **Monochrome dropped before download** (done): `build_pool.py` reads the medium text (93% agreement with the model's colour labels on 163 works; AIC's `colorfulness` field proved unreliable). Pool 836 → 545. Side effect: nativity matches 135 → 21, Christmas 16 → 4 (mostly monochrome engravings, e.g. Winslow Homer's magazine prints). Decided: monochrome works whose text explicitly says Christmas stay in (8 works: Homer's three magazine engravings, Harnett's stockings, Palmer, Toulouse-Lautrec's "Christmas Ballad", Weir, Cruikshank). Hand-coloured prints count as colour. Pool now 557.
- [ ] **Balance:** balance types and themes in the final selection only if every work in it is rated highly.
- [ ] **Remove the non-festive works.** 44 of 163 rated works have no items and no festive setting (flowers, Mount Fuji, interiors); drop them from the pool once the prompt is settled.
- [ ] **More title-borrowed labels:** "hand ball", "battledore", "New Year pull toy" (3 works marked "invented items" in the picker).
- [ ] **Selection rules from the first marking round (78 works):** reject monochrome works (all 16 keeps were colour); reject religious scenes with nothing festive (religious figures count only inside a Nativity or Christmas scene); "not festive" paintings can still be kept, so treat that tag as neutral rather than a problem.
- [ ] **What the marks showed:** scores 0–1 were reliably right (all 11 rated 0 got "about right"; 31 of 42 rejects were 0–1), so they can be dropped automatically. Score 4 was "too high" half the time (8 of 16).
- [ ] **Generic labels.** Crowds are listed figure by figure ("person in red coat", "person in yellow coat"…), which inflates the detail count.

### 2.3 Picker app

- [ ] Throwaway local page: grid of the top 300 to 400 by score, filters for type, date and matched word, keep/reject keys, writes `lists/shortlist.csv`.
- [ ] Choose about **200** works.

---

### 2.4 Status (24 November 2026)

- Festive picker (`picker/index.html`, decisions in `lists/decisions.csv`): 95 kept, some maybes still open.
- Object paintings (`picker/paintings.html`, decisions in `lists/paintings_decisions.csv`): 559 non-Asian, non-religious colour paintings rated for objects (`runs/paintings_ratings.csv`, $0.42); 73 kept (including 20 flagged people-only), all decided.
- Selection: about 168 works (116 paintings, 29 Japanese prints, 14 other prints, 9 drawings) plus remaining maybes.
- Screening cost so far: about $1.
- Next: settle maybes, download the selection at 3000px, adapt the NG detection prompt (changes below), pilot on 12, full run.

## 3. Find the festive items

Prompt: `prompts/detect_prompt.md`, adapted from the NG `xmas_prompt.md` (decided 24 November 2026):
- **Open detection:** find every distinct person, animal and object that could be cut out, including religious figures and non-festive things. Discovering what is in the artworks is the point; the festive theme is applied later as a filter.
- Festive things are listed as **examples to look out for**, not as the only allowed labels. Each item gets `festive: true/false`.
- The NG exclusions became **naming rules** (a laurel crown is "laurel crown", not "wreath"; a halo is "halo", not "star").
- No title, artist or date; no minimum size; British spelling for all labels.
- Kept: box rules, max 5 boxes per label plus a group box, JSON format.
- [ ] After the full run: merge synonym labels (jug / pitcher / ewer) so collection pages work.

**Full run (24 November 2026):** 175 works, $0.44 (cap $2.00), 1,768 items (835 festive), 726 distinct labels. **56 works came back empty** (42 of 73 object paintings, 11 festive-pool paintings, 3 prints, 0 drawings), including easy ones (Cézanne apples, Van Gogh "The Bedroom", Heda still life), so the cause is the prompt, not visibility. The objects rating found plenty in the same images. Script: `scripts/detect_items.py` (retries empty answers with other providers, hard budget cap). Viewer: `/detect` in the picker app.
- [x] **Fix for the 56 empty works (24 November 2026):** the Qwen3-VL docs (https://github.com/QwenLM/Qwen3-VL, `cookbooks/2d_grounding.ipynb`) show detection as one short sentence with a category list and a plain `[{"bbox_2d", "label"}]` answer; our long nine-field prompt did not match. Re-run with the official sentence (`prompts/ground_prompt.md`), per-work category lists tidied from the screening items (`lists/ground_categories.csv`, 210 labels, British spelling) and the recommended sampling settings. Script `scripts/ground_items.py`. Result: all 56 now have boxes (1,397), $0.10. `festive` is still blank for these; set it later in a text-only step. Backup of the earlier results in `backup/`.
- [ ] "person" is 468 of the 1,397 new boxes; decide whether to keep people boxes for the app.
- [ ] Generic labels to fix: "person" (133), "group" (20), "metal container" (32).
- [ ] **Label groups (24 November 2026):** the app's "find the dog in other paintings" groups by label, as in the NG app (fixed vocabulary of about 60 labels plus aliases). Open detection gave 711 labels, so `scripts/label_rules.py` maps each to a short group label (colour, material, size, "snow-covered" and clothing dropped; plurals to singular; aliases such as Magus → wise man, cookies → biscuits) . Corrections are stored in `lists/label_overrides.csv`; review page `/labels`. The original wording stays as the item's detail.


- [ ] Download the 200 at `!3000,3000` into `runs/images/`.
- [ ] Detection with Qwen3-VL as in the NG project: the image is embedded in the request (downscaled locally to 1600px), the prompt holds the vocabulary, hints, exclusions and box rules, and answers are cached per artwork.
- [ ] Prompt context: "a work from the Art Institute of Chicago", with type and medium, but **no title** (the model borrows labels from titles).
- [ ] Vocabulary: NG list plus paper lantern, plum blossom, camellia, snowman, snowball, stocking, mittens / scarf, firewood, Christmas card, sleigh bells.
- [ ] Optionally ask for all other notable objects in the same call, for the "show everything the model saw" layer. Pilot against a festive-only prompt first.
- [ ] Pilot on 12 varied works, then the full run.
- [ ] Review in an adapted NG review site (images from `runs/images/`): quarantine, star, merge labels, assign categories.

---

## 4. Cut out the items

**Quarantine before cutting (24 November 2026),** as in the NG project: quarantined items get no sticker and appear in the app as dashed "Also spotted" outlines. Proposals in `lists/quarantine_proposals.csv` from `scripts/propose_quarantine.py` (run with the multimatte Python): **tiny** = shorter side under 94px on the 3000px image (the NG rule of 50px at about 1600px, scaled) and **vague** = label group "person" or "crowd". Starred items are never quarantined. Result: 537 quarantined, 1,339 left for cutting. Reviewed on `/review` (filter "Items: quarantined only", **Q** to quarantine or release); decisions in `lists/review_items.csv` (`quarantine` = yes/no, empty = follow the proposal).
- [ ] Review the quarantine, then decide whether "person" stays out of cutouts entirely.
- **Only festive items become stickers,** as in the NG app (it cut out only its festive list and skipped scenery such as snow). Festive is set by `scripts/festive_rules.py` into `lists/festive_items.csv` (agreed 24 November 2026): a list of festive label groups (nativity, winter, greenery, light, feast incl. all fruit, gifts and toys, plus umbrella, coat, boot, fur blanket/rug, firewood, log, fireplace, all musical instruments, music books and sheet music, kitchen and table things except cups, saucers, cutlery, plain bottles, jars and trays, envelope, postcard, letter, note, stamp), and any item whose original wording is wintry ("snow-covered roof", "frozen river"). Starred items always become stickers. Scenery (snow, river, hill) is festive but not cut out.
- Current split (works kept, items not removed): 615 festive stickers + 29 starred non-festive = 644 to cut; 136 festive quarantined ("Also spotted"); 42 festive scenery; 1,054 not festive ("everything the model saw", no cutouts).
- [ ] Review the quarantined people and release wintry ones.


- [x] Crop each box locally from the 3000px image with a 15% margin (`scripts/cut_stickers.py`, run with `~/venvs/multimatte/bin/python`).
- [x] `feyninc/multimatte` (prompt "the <original wording>", or "the baby/woman/man/king" for nativity figures), with the automatic 40% retry for edge-touching cutouts, the review flags and the white sticker border.
- [x] Pilot of 20 (24 November 2026): 12 clean, 3 odd, 5 weak (loose paint or print styles, boxes tighter than the object).
- [x] Full run: 651 cut out, 0 failed, about 27 minutes; 66 flagged (34 touch a crop edge, 33 fill little of their box). `build_site.py` uses the cutout wherever one exists.
- [ ] Review the flagged cutouts at http://localhost:8770/cutouts: OK, redo, or use the crop (saved in `lists/cutout_review.csv`; `build_site.py` uses the crop for "use crop"). Then redo the "redo" ones with `--keys ... --rerun`.
- [ ] Licence check: multimatte is Apache 2.0 but based on SAM 3 (Meta licence).

---

## 5. Make the stickers

- [ ] `make_stickers.py` (white border, specks removed, pieces joined).
- [ ] WebP stickers at about 600px for the site, plus small door-sized versions; full-size PNGs kept locally.

---

## 6. Descriptions

Decided 24 November 2026, after checking the NG app: it had three texts per painting. `short` and `long` were the Gallery's own curatorial text (confirmed on the NG website); `visual` (about 80 words) was most likely AI-made. "About this painting" showed short/long, item cards quoted up to three sentences from `long` that mention the item ("What the Gallery says", via the `KEYWORDS` list), and `visual` was the alt text and the "Picture description" box.

- [ ] **About this painting:** AIC `description` (CC BY 4.0, needs a credit) where it exists (57 of 129 kept works). Item quotes come from this text, as before.
- [ ] **Missing text:** for now, an obvious placeholder (e.g. "[No description yet]") so the app can be seen; decide later.
- [ ] **AI-written texts for the missing ones** (agreed 24 November 2026): written by Claude in this session from the image and the AIC record only; describe what is visible, add only facts from the record, no assumptions, accuracy over prose; hedge where unsure ("cakes or loaves"). Stored in `lists/written_descriptions.json` (status "draft" until reviewed). The app marks them: a red "AI-written" note under "About this painting", the quote label "What the AI-written description says", and a footer line. AIC texts get "Text from the Art Institute of Chicago." All 63 paintings with stickers now have one (written 24 November 2026, status "draft"); review still to do. The 9 placeholder paintings have no stickers, so they never open in the app.
- [ ] **Alt text:** AIC `thumbnail.alt_text`, even where it is generic ("A work made of…", 111 of 129) or the title only.
- [ ] Stretch goal: our own alt text (about 15 words) for the 111 generic ones.
- [ ] Stretch goal: picture description (visual, about 80 words, batch B style in `descriptions/test_objects.md`, naming the items).
- Test descriptions for 5 works and the comparison page (`/descriptions`) are kept for the stretch goal.

---

## 7. The app

**First version running (24 November 2026):** the NG app copied into `site/` (index, album, postcard), changed only where needed: no theme picker (one calendar, doors dealt from the starred stickers, one per painting), AIC wording and links, the AIC caption under the title, AIC alt text, "What the Art Institute says", plurals for our labels, a footer credit (images CC0, texts CC BY 4.0). `build_site.py` (run with `~/venvs/multimatte/bin/python`) builds `site/data/calendar.json` in the NG shape from the review data, label groups, festive marks and quarantine, saves 2000px WebP paintings and, for now, **plain rectangular crops as stand-in stickers** (to be replaced by cutouts). Preview: `python3 serve_site.py` → http://localhost:8766. First build: 129 paintings (72 with the placeholder text), 651 stickers, 132 "also spotted", 1,051 in "everything the model saw".

- [ ] Rewrite `build_site.py` for the new data: artworks (`id`, `title`, `artist`, `date`, `type`, local WebP image about 2000px, `caption`, `url` = `https://www.artic.edu/artworks/{id}`, our description, alt text) and items (as in NG).
- **One calendar, no theme picker** (decided 24 November 2026). This is the only change to the NG app; everything else stays the same. The 24 doors are either picked by hand from the starred stickers or drawn at random from them. Categories are not needed.
- [ ] **Open question, review once the app is running:** the "See all N …" link appears when a label has 2+ stickers, even if they all come from one painting (e.g. many cherries in one still life). Possibly fine as it is (the old behaviour); possibly limit it to labels found in 2+ paintings, or show it only when it adds more than the "in other paintings" strip. No change for now.
- [ ] Split `calendar.json` into calendar data and per-artwork files if it grows large.
- [x] Credits (24 November 2026): AIC caption under the painting title, under each sticker on collection pages, for the selected sticker and in a "Where your stickers come from" list in the album, in an "Ornaments on this tree" list on the postcard and in its info panel; footer on all three pages: images CC0, painting texts CC BY 4.0, with links to both licences and the AIC terms. Calendar doors show only the sticker (the caption appears once the door is opened).
- [ ] Replace National Gallery wording and links; raise the zoom limit; check the viewer with wide and small print formats.
- [ ] Hosting: Cloudflare Pages, fully public (all images are CC0).

**Door picks connected (25 November 2026):** the 25 stickers picked on http://localhost:8770/doors (saved in `lists/doors.csv`, in pick order) become the calendar doors 1 to 25 in that order. `build_site.py` writes them to `calendar.json` as `doors`; the app uses them and only falls back to dealing random starred stickers if fewer than 25 are picked. Changing picks needs a rebuild.

#!/usr/bin/env python3
import csv
import html
import json
import re
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "picker"))
sys.path.insert(0, str(ROOT / "scripts"))
import label_rules  # noqa: E402
from server import review_data  # noqa: E402

SITE = ROOT / "docs"
DATA_OUT = SITE / "data" / "calendar.json"
PAINTINGS_OUT = SITE / "paintings"
STICKERS_OUT = SITE / "stickers"
IMAGES = ROOT / "runs" / "images_3000"
RECORDS = ROOT / "lists" / "aic_public_domain.jsonl"
ITEMS = ROOT / "runs" / "detect_items.csv"
CUTOUTS = ROOT / "runs" / "cutouts" / "stickers"
CUTOUT_REVIEW = ROOT / "lists" / "cutout_review.csv"
WRITTEN = ROOT / "lists" / "written_descriptions.json"
DOOR_PICKS = ROOT / "lists" / "doors.csv"
PAINTING_PX = 2000
STICKER_PX = 600
CROP_PAD = 0.06
SCENERY = {"snow", "river", "hill"}
PLACEHOLDER = "[No description yet]"


def plain_text(description):
    text = re.sub(r"</p>\s*", "\n\n", description or "")
    text = html.unescape(re.sub(r"<[^>]+>", "", text))
    return re.sub(r"\n{3,}", "\n\n", re.sub(r"[ \t]+", " ", text)).strip()


def caption(artist, title, date):
    return f"{artist or 'Unknown artist'}. {title}, {str(date).rstrip('.')}. The Art Institute of Chicago."


def save_painting(artwork_id):
    out = PAINTINGS_OUT / f"{artwork_id}.webp"
    if not out.exists():
        im = Image.open(IMAGES / f"{artwork_id}.jpg").convert("RGB")
        im.thumbnail((PAINTING_PX, PAINTING_PX))
        im.save(out, "WEBP", quality=85)
    return f"paintings/{out.name}"


def save_crop(im, artwork_id, item_id, box):
    out = STICKERS_OUT / f"{artwork_id}_{item_id}.webp"
    if not out.exists():
        w, h = im.size
        x0, y0, x1, y1 = box[0] * w, box[1] * h, box[2] * w, box[3] * h
        pad = CROP_PAD * max(x1 - x0, y1 - y0)
        crop = im.crop((max(0, x0 - pad), max(0, y0 - pad), min(w, x1 + pad), min(h, y1 + pad)))
        crop.thumbnail((STICKER_PX, STICKER_PX))
        crop.save(out, "WEBP", quality=85)
    return f"stickers/{out.name}"


def crop_verdicts():
    if not CUTOUT_REVIEW.exists():
        return set()
    with open(CUTOUT_REVIEW, newline="", encoding="utf-8") as f:
        return {r["key"] for r in csv.DictReader(f) if r["verdict"] == "crop"}


def save_cutout(artwork_id, item_id, use_crop):
    src = CUTOUTS / f"{artwork_id}_{item_id}.png"
    if use_crop or not src.exists():
        return ""
    out = STICKERS_OUT / f"{artwork_id}_{item_id}_cut.webp"
    if not out.exists() or out.stat().st_mtime < src.stat().st_mtime:
        im = Image.open(src)
        im.thumbnail((STICKER_PX, STICKER_PX))
        im.save(out, "WEBP", quality=90)
    return f"stickers/{out.name}"


def layer(i, group):
    proposed = bool(i["quarantine_reason"]) and not i["starred"]
    quarantined = i["quarantine"] == "yes" or (i["quarantine"] == "" and proposed)
    festive = i["festive"] == "True"
    if i["starred"] or i["quarantine"] == "no" or (festive and not quarantined and group not in SCENERY):
        return "sticker"
    if festive and quarantined:
        return "extra"
    if festive:
        return "main"
    return "more"


def main():
    for d in (DATA_OUT.parent, PAINTINGS_OUT, STICKERS_OUT):
        d.mkdir(parents=True, exist_ok=True)
    records = {}
    with open(RECORDS, encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            records[str(r["id"])] = r
    with open(ITEMS, newline="", encoding="utf-8") as f:
        reasons = {f'{r["id"]}:{r["item_id"]}': r.get("reason", "") for r in csv.DictReader(f)}
    overrides = label_rules.read_overrides()
    use_crop = crop_verdicts()
    written = json.loads(WRITTEN.read_text(encoding="utf-8")) if WRITTEN.exists() else {}

    paintings, items, counts = {}, [], {"sticker": 0, "cutouts": 0, "extra": 0, "main": 0, "more": 0}
    for a in review_data()["artworks"]:
        if a["decision"] != "keep":
            continue
        rec = records.get(a["id"], {})
        text, source = plain_text(rec.get("description")), "aic"
        if not text and a["id"] in written:
            text, source = written[a["id"]]["text"], "ai"
        if not text:
            text, source = PLACEHOLDER, ""
        paintings[a["id"]] = {
            "id": a["id"], "title": a["title"], "artist": a["artist"], "date": a["date"],
            "caption": caption(a["artist"], a["title"], a["date"]), "url": f"https://www.artic.edu/artworks/{a['id']}",
            "image": save_painting(a["id"]), "alt": (rec.get("thumbnail") or {}).get("alt_text") or "",
            "short": text, "long": text, "visual": "", "text_source": source,
        }
        im = None
        for i in a["items"]:
            if i["dropped"]:
                continue
            group = label_rules.resolve(i["label"], overrides)["canonical"]
            kind = layer(i, group)
            counts[kind] += 1
            box = [round(float(i[k]), 4) for k in ("x0", "y0", "x1", "y1")]
            sticker = ""
            if kind == "sticker":
                sticker = save_cutout(a["id"], i["item_id"], f"{a['id']}#{i['item_id']}" in use_crop)
                if sticker:
                    counts["cutouts"] += 1
                else:
                    im = im or Image.open(IMAGES / f"{a['id']}.jpg").convert("RGB")
                    sticker = save_crop(im, a["id"], i["item_id"], box)
            item = {"key": f"{a['id']}#{i['item_id']}", "painting": a["id"], "label": group, "detail": i["label"],
                    "box": box, "sticker": sticker, "star": i["starred"], "flag": False,
                    "reason": reasons.get(f"{a['id']}:{i['item_id']}", "")}
            if kind in ("extra", "more"):
                item["extra"] = True
            if kind == "more":
                item["more"] = True
            items.append(item)
    doors = []
    if DOOR_PICKS.exists():
        with open(DOOR_PICKS, newline="", encoding="utf-8") as f:
            stickers = {i["key"] for i in items if i["sticker"]}
            picks = [r["key"] for r in csv.DictReader(f)]
        doors = [k for k in picks if k in stickers]
        for k in picks:
            if k not in stickers:
                print(f"Door pick {k} is no longer a sticker and was skipped")
    DATA_OUT.write_text(json.dumps({"paintings": paintings, "items": items, "doors": doors}, ensure_ascii=False))
    placeholders = sum(1 for p in paintings.values() if p["long"] == PLACEHOLDER)
    ai = sum(1 for p in paintings.values() if p["text_source"] == "ai")
    print(f"{len(paintings)} paintings ({ai} with AI-written text, {placeholders} with placeholder text), {len(items)} items: "
          f"{counts['sticker']} stickers ({counts['cutouts']} cut out), {counts['main']} festive without sticker, {counts['extra']} also spotted, "
          f"{counts['more']} in 'everything the model saw', {len(doors)} picked doors -> {DATA_OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()

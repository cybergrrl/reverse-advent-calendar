#!/usr/bin/env python3
import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_pool import colour_from_medium  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
PUBLIC_DOMAIN = ROOT / "lists" / "aic_public_domain.jsonl"
RATINGS = ROOT / "runs" / "ratings.csv"
OUTPUT = ROOT / "lists" / "paintings_pool.csv"

PORTRAIT_TITLE = re.compile(r"\b(portrait|self-portrait|head of|bust of|study of a head)\b", re.I)
PORTRAIT_TAG = re.compile(r"portrait", re.I)
RELIGIOUS_TAG = re.compile(r"religio|christian|biblical|saints?\b|jesus|virgin mary|madonna|crucifixion|buddh|bodhisattva|deity|deities", re.I)
ASIAN_FORMAT = re.compile(r"hanging scroll|handscroll|album leaf|screen|fan\b", re.I)
SKETCH = re.compile(r"\b(study|studies|sketch|sketches|esquisse|bozzetto|modello|oil sketch)\b", re.I)
GROUPS = [
    ("still life", r"still life|flowers|fruit|bouquet|vase|tulips|roses|peonies|chrysanthemums"),
    ("myth and history", r"mytholog|classical|venus|cupid|hercules|bacchus|diana|apollo|battle|soldiers|violence|allegor|history"),
    ("everyday scenes and interiors", r"interior|leisure|everyday|genre|domestic|children|woman with children|music|market|cafe|café|dance|fair|festival|party|lunch|dinner|kitchen|tavern|family|games|people|figures|crowd"),
    ("town and buildings", r"building|architect|city|street|boulevard|square|church|bridge|cityscape|town|village|urban"),
    ("water and boats", r"boats?|river|harbou?r|port|beach|sea\b|seascape|coast|ships?|marine|canal"),
    ("animals", r"animals?|horses?|dogs?|cattle|cows?|sheep|birds?|cats?|deer"),
    ("nudes and single figures", r"nudes?|bather|figure\b|woman|man\b|girl|boy"),
    ("landscape", r"landscape|trees|mountain|nature|forest|clouds|fields?|garden|countryside|valley|lake|snow"),
]
GROUPS = [(name, re.compile(rf"\b({rx})", re.I)) for name, rx in GROUPS]
DROPPED_GROUPS = {"nudes and single figures"}


def group_of(r, asian, religious):
    if asian:
        return "Asian"
    if religious:
        return "religious"
    text = " | ".join(tags(r) + [r.get("title") or ""])
    for name, rx in GROUPS:
        if rx.search(text):
            return name
    return "untagged"


def tags(r):
    return (r.get("subject_titles") or []) + (r.get("term_titles") or []) + (r.get("classification_titles") or [])


def main():
    rated = set()
    if RATINGS.exists():
        with open(RATINGS, newline="", encoding="utf-8") as f:
            rated = {row["id"] for row in csv.DictReader(f)}

    counts = Counter()
    rows = []
    with open(PUBLIC_DOMAIN, encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            if r.get("is_public_domain") is not True or not r.get("image_id") or r.get("artwork_type_title") != "Painting":
                continue
            counts["public-domain paintings"] += 1
            if colour_from_medium(r) == "monochrome":
                counts["dropped: monochrome"] += 1
                continue
            if PORTRAIT_TITLE.search(r.get("title") or "") or any(PORTRAIT_TAG.search(t) for t in tags(r)):
                counts["dropped: portrait"] += 1
                continue
            if str(r["id"]) in rated:
                counts["dropped: already rated"] += 1
                continue
            if SKETCH.search(r.get("title") or "") or any(SKETCH.search(t) for t in tags(r)):
                counts["dropped: sketch or study"] += 1
                continue
            asian = r.get("department_title") == "Arts of Asia" or any(ASIAN_FORMAT.search(t) for t in tags(r))
            religious = any(RELIGIOUS_TAG.search(t) for t in tags(r))
            if asian:
                counts["dropped: Asian"] += 1
                continue
            if religious:
                counts["dropped: religious"] += 1
                continue
            group = group_of(r, asian, religious)
            if group in DROPPED_GROUPS:
                counts[f"dropped: {group}"] += 1
                continue
            thumb = r.get("thumbnail") or {}
            rows.append({
                "id": r["id"], "image_id": r["image_id"], "thumb_width": thumb.get("width") or 0,
                "group": group,
                "title": r.get("title") or "", "artist": r.get("artist_title") or "",
                "date": r.get("date_display") or "", "date_end": r.get("date_end") or "",
                "place": r.get("place_of_origin") or "", "department": r.get("department_title") or "",
                "asian": asian, "religious": religious, "boosted": bool(r.get("is_boosted")),
                "subjects": "; ".join(r.get("subject_titles") or []),
            })

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

    for k, v in counts.items():
        print(f"{k:28} {v:5}")
    print(f"{'left':28} {len(rows):5}  -> {OUTPUT.relative_to(ROOT)}\n")
    print("  by group:", Counter(r["group"] for r in rows).most_common(), "\n")
    asian = [r for r in rows if r["asian"]]
    religious = [r for r in rows if r["religious"] and not r["asian"]]
    rest = [r for r in rows if not r["asian"] and not r["religious"]]
    print(f"  Asian (department or scroll/album/screen format): {len(asian)}")
    print(f"  religious subject, not Asian:                     {len(religious)}")
    print(f"  everything else:                                  {len(rest)}")
    print(f"  no subject tags at all:                           {sum(1 for r in rows if not r['subjects'])}")
    print(f"  AIC highlights (is_boosted):                      {sum(1 for r in rows if r['boosted'])}")
    print("\n  'everything else' by place:", Counter(r["place"] for r in rest).most_common(8))
    century = Counter((int(r["date_end"]) // 100 + 1) if str(r["date_end"]).lstrip("-").isdigit() else "?" for r in rest)
    print("  'everything else' by century:", sorted(century.items(), key=lambda kv: str(kv[0])))


if __name__ == "__main__":
    main()

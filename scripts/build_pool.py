#!/usr/bin/env python3
import csv
import json
import re
import sys
from collections import Counter
from html import unescape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DUMP = ROOT / "source" / "aic-dump" / "artic-api-data" / "json" / "artworks"
PD_OUT = ROOT / "lists" / "aic_public_domain.jsonl"
POOL_OUT = ROOT / "lists" / "pool.csv"

KEEP_FIELDS = [
    "id", "is_public_domain", "image_id", "main_reference_number", "title", "alt_titles", "artist_title", "artist_display",
    "date_display", "date_start", "date_end", "artwork_type_title", "classification_titles", "medium_display",
    "place_of_origin", "department_title", "subject_titles", "term_titles", "theme_titles", "category_titles",
    "style_titles", "inscriptions", "short_description", "description", "thumbnail", "is_boosted",
]

TYPES = {"Painting", "Print", "Drawing and Watercolor", "Miniature Painting"}
ALL_FIELDS = ["title", "alt_titles", "subject_titles", "term_titles", "theme_titles",
              "inscriptions", "short_description", "description", "alt_text"]
TAG_FIELDS = ["title", "alt_titles", "subject_titles", "term_titles", "theme_titles"]

STRONG_WORDS = {
    "christmas": r"christmas|xmas|yule(tide)?|santa claus|father christmas|saint nicholas|st\.? nicholas",
    "nativity": r"nativity|cr[eè]che|adoration of the (magi|kings|shepherds)|magi|three kings|epiphany"
                r"|annunciation to the shepherds|star of bethlehem",
    "winter": r"winter|wintry|snow|snowy|snowfall|snowstorm|snowball|snowman|blizzard|icicles?|frozen",
    "winter fun": r"skat(e|es|er|ers|ing)|ice palace|sleighs?|sledg(e|es|ing)|sleds?|toboggan\w*",
    "new year": r"new year'?s?",
}
TAG_ONLY_WORDS = {
    "angels": r"angels?",
    "greenery": r"holly|mistletoe|wreaths?|evergreens?|fir trees?|christmas trees?|poinsettias?",
    "light": r"candles?|candlelight|lanterns?",
    "feast": r"feasts?|banquets?|still life|plum puddings?",
    "toys": r"toys?|dolls?|rocking horse|hobby horse",
    "music": r"carol(s|lers?|ing)?|choir",
    "birds": r"robins?|partridges?",
}
SUPPORTING_ONLY = {"angels"}

COLOUR_MEDIUM = re.compile(
    r"\b(oil|tempera|gouache|watercolou?r|colou?rs?|colored|coloured|polychrom\w*|pastel|chromolithograph\w*"
    r"|hand-?colou?r(ed|ing)?|colou?ring|tinted|gold|silver leaf|opaque|acrylic|enamel|pigments?)\b", re.I)
MONO_MEDIUM = re.compile(
    r"\b(etching|engraving|drypoint|woodcut|wood engraving|mezzotint|aquatint|lithograph|graphite|pencil"
    r"|charcoal|chalk|pen|ink|wash|crayon|bistre|sepia|stipple)\b", re.I)
HIGHLIGHTS = re.compile(r"heightened with[^;,]*", re.I)
EXPLICIT_CHRISTMAS = re.compile(r"christmas|xmas|yule", re.I)


def colour_from_medium(record):
    medium = HIGHLIGHTS.sub("", record.get("medium_display") or "")
    if COLOUR_MEDIUM.search(medium):
        return "colour"
    if MONO_MEDIUM.search(medium):
        return "monochrome"
    return "unknown"
WORDS = {**STRONG_WORDS, **TAG_ONLY_WORDS}
SEARCH_FIELDS = {**{g: ALL_FIELDS for g in STRONG_WORDS}, **{g: TAG_FIELDS for g in TAG_ONLY_WORDS}}
PATTERNS = {group: re.compile(rf"\b({rx})\b", re.I) for group, rx in WORDS.items()}
TAGS = re.compile(r"<[^>]+>")


def text_of(value):
    if value is None:
        return ""
    if isinstance(value, list):
        return " | ".join(str(v) for v in value if v)
    return unescape(TAGS.sub(" ", str(value)))


def load_public_domain():
    records = []
    for path in DUMP.glob("*.json"):
        r = json.loads(path.read_text(encoding="utf-8"))
        if r.get("is_public_domain") is not True or not r.get("image_id"):
            continue
        records.append({k: r.get(k) for k in KEEP_FIELDS})
    return records


def matches(record):
    fields = {f: text_of(record.get(f)) for f in ALL_FIELDS if f != "alt_text"}
    fields["alt_text"] = text_of((record.get("thumbnail") or {}).get("alt_text"))
    found = {}
    for group, pattern in PATTERNS.items():
        for field in SEARCH_FIELDS[group]:
            text = fields[field]
            for m in pattern.finditer(text):
                found.setdefault(group, set()).add((m.group(0).lower(), field))
    return found


def main():
    records = load_public_domain()
    PD_OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(PD_OUT, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    rows, by_type, by_group, by_group_title = [], Counter(), Counter(), Counter()
    dropped_monochrome = 0
    for r in records:
        if r["artwork_type_title"] not in TYPES:
            continue
        found = matches(r)
        if not found or set(found) <= SUPPORTING_ONLY:
            continue
        says_christmas = any(EXPLICIT_CHRISTMAS.search(w) for w, _ in found.get("christmas", ()))
        if colour_from_medium(r) == "monochrome" and not says_christmas:
            dropped_monochrome += 1
            continue
        in_title = {g for g, hits in found.items() if any(field in ("title", "alt_titles") for _, field in hits)}
        by_type[r["artwork_type_title"]] += 1
        by_group.update(found.keys())
        by_group_title.update(in_title)
        rows.append({
            "id": r["id"], "image_id": r["image_id"], "type": r["artwork_type_title"], "title": r["title"],
            "artist": r["artist_title"] or "", "date": r["date_display"] or "", "place": r["place_of_origin"] or "",
            "groups": "; ".join(sorted(found)), "groups_in_title": "; ".join(sorted(in_title)),
            "words": "; ".join(sorted({f"{w} ({field})" for hits in found.values() for w, field in hits})),
            "has_description": bool(r["description"]),
            "medium_colour": colour_from_medium(r),
        })

    with open(POOL_OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(sorted(rows, key=lambda x: (x["type"], x["title"])))

    print(f"public domain with image: {len(records)}")
    print(f"dropped as monochrome (from the medium text): {dropped_monochrome}")
    print(f"pool (any festive word in any field): {len(rows)}")
    print(f"pool with the word in the title: {sum(1 for x in rows if x['groups_in_title'])}\n")
    print("pool by type:")
    for t, n in by_type.most_common(15):
        print(f"  {n:6}  {t}")
    print("\nby word group (any field / title only):")
    for g in WORDS:
        print(f"  {g:15} {by_group[g]:6} / {by_group_title[g]}")


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
import csv
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import label_rules  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
ITEMS = ROOT / "runs" / "detect_items.csv"
OUTPUT = ROOT / "lists" / "festive_items.csv"

FESTIVE_GROUPS = set("""
Christ Child|Mary|Joseph|wise man|angel|shepherd|manger|star|halo|stable|gifts of the Magi|glass orb|censer|ox|donkey|sheep|lamb|camel
snow|icicles|snowball|snowman|skater|sleigh|sleigh bell|horse pulling sleigh|ice|ice block
conifer|christmas tree|holly|wreath|garland|flower wreath|pinecone
candle|candlestick|lantern|stone lantern|paper lantern|street lamp
pie|cake|biscuits|nuts|bread|bread roll|leg of mutton|sausage|goose|chestnuts|sweets|pudding|ham
apple|orange|pear|grapes|plum|fig|lemon|cherry|strawberry|peach|pomegranate|melon|pineapple|banana|coconut|berry|lemon slices|fruit|apricot|quince|raspberry
wine bottle|wine glass|champagne bottle
present|gift box|gift bowl|stocking|toy boat|doll|bell|drum
umbrella|coat|boot|fur blanket|fur rug|firewood|log|fireplace
lute|violin|viola da gamba|recorder|musical instrument|fiddle|hanging violin|flute|guitar|harp|shamisen|koto|trumpet|horn
oyster|cheese|fish|cabbage|carrot|leek|onion|asparagus|aubergine|mushroom|tomato|pea pod|pumpkin slice|pepper|olives|food|sugar cube|egg|bowl of eggs
tablecloth|fringed tablecloth|jug|glass jug|glass|flute glass|plate|china plate|bowl|basket|teapot|goblet|tankard|platter|decanter|salt cellar|dish|pot|container|vessel|mortar and pestle|kettle|terracotta pot
music book|sheet music|music sheet
envelope|postcard|letter|note|postage stamp
""".replace("\n", "|").split("|")) - {""}
WINTRY = re.compile(r"\b(?:snow|snowy|snow-covered|icy|ice-covered|frozen|frosted|frost|winter|icicles?|sleighs?|sleds?|sledges?)\b", re.I)


def judge(label, overrides):
    group = label_rules.resolve(label, overrides)["canonical"]
    if group.lower() in {g.lower() for g in FESTIVE_GROUPS}:
        return True, group, f"group: {group}"
    if WINTRY.search(label):
        return True, group, "wintry wording"
    return False, group, ""


def main():
    overrides = label_rules.read_overrides()
    rows, counts = [], Counter()
    with open(ITEMS, newline="", encoding="utf-8") as f:
        for i in csv.DictReader(f):
            festive, group, reason = judge(i["label"], overrides)
            counts[festive] += 1
            rows.append({"id": i["id"], "item_id": i["item_id"], "label": i["label"], "group": group,
                         "festive": "yes" if festive else "no", "reason": reason})
    with open(OUTPUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["id", "item_id", "label", "group", "festive", "reason"])
        w.writeheader()
        w.writerows(rows)
    print(f"{counts[True]} festive, {counts[False]} not festive -> {OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()

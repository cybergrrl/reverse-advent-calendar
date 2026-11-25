#!/usr/bin/env python3
import csv
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import label_rules  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
ITEMS = ROOT / "runs" / "detect_items.csv"
IMAGES = ROOT / "runs" / "images_3000"
OUTPUT = ROOT / "lists" / "quarantine_proposals.csv"
# Matches the NG rule (shorter side under 50px at about 1600px wide), scaled to the 3000px images.
TINY_PX = 94
VAGUE = {"person", "crowd"}


def main():
    overrides = label_rules.read_overrides()
    sizes, rows = {}, []
    with open(ITEMS, newline="", encoding="utf-8") as f:
        for i in csv.DictReader(f):
            path = IMAGES / f"{i['id']}.jpg"
            if not path.exists():
                continue
            if i["id"] not in sizes:
                sizes[i["id"]] = Image.open(path).size
            w, h = sizes[i["id"]]
            side = min((float(i["x1"]) - float(i["x0"])) * w, (float(i["y1"]) - float(i["y0"])) * h)
            group = label_rules.resolve(i["label"], overrides)["canonical"]
            reasons = (["tiny"] if side < TINY_PX else []) + (["vague"] if group in VAGUE else [])
            if reasons:
                rows.append({"id": i["id"], "item_id": i["item_id"], "label": i["label"], "group": group,
                             "short_side_px": round(side), "reason": " + ".join(reasons)})
    with open(OUTPUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["id", "item_id", "label", "group", "short_side_px", "reason"])
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)} proposals written to {OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()

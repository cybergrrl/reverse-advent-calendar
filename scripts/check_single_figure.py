#!/usr/bin/env python3
import argparse
import csv
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from rate_images import IMAGES, ROOT, call_model, load_api_key, parse  # noqa: E402

RAW_DIR = ROOT / "runs" / "single_figure_raw"
OUTPUT = ROOT / "runs" / "single_figure.csv"
PROMPT = """Look at this artwork and answer two questions about its composition.

1. How many people dominate the picture (the figures that take up most of the attention)? Count 0 if there are no people.
2. Is this essentially a picture of one main person, or one pair, filling much of the image, with little else going on? Typical examples: a portrait, an actor print, a print of a beautiful woman, a single figure standing in the snow. Answer false for crowds, busy scenes, landscapes with small figures, still lifes and scenes with several separate things happening.

Return ONLY JSON: {"main_figures": 1, "single_figure": true, "reason": "one short sentence"}"""


def check(artwork_id, api_key):
    raw = RAW_DIR / f"{artwork_id}.json"
    if raw.exists():
        resp = json.loads(raw.read_text())
    else:
        resp = call_model(api_key, (IMAGES / f"{artwork_id}.jpg").read_bytes(), PROMPT)
        raw.write_text(json.dumps(resp, indent=2))
    answer = parse(resp["choices"][0]["message"]["content"])
    return {"id": artwork_id, "main_figures": answer.get("main_figures", ""),
            "single_figure": answer.get("single_figure", ""), "reason": answer.get("reason", ""),
            "cost_usd": (resp.get("usage") or {}).get("cost", "")}


def main():
    ap = argparse.ArgumentParser(description="Ask whether each artwork is dominated by one main figure.")
    ap.add_argument("ids_file", help="text file with one artwork id per line")
    args = ap.parse_args()
    ids = [line.strip() for line in open(args.ids_file) if line.strip()]
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    api_key = load_api_key()
    with ThreadPoolExecutor(max_workers=4) as pool:
        rows = list(pool.map(lambda i: check(i, api_key), ids))
    with open(OUTPUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    cost = sum(float(r["cost_usd"]) for r in rows if r["cost_usd"] not in ("", None))
    print(f"checked {len(rows)}, single figure: {sum(1 for r in rows if r['single_figure'] is True)}, cost ${cost:.4f}")


if __name__ == "__main__":
    main()

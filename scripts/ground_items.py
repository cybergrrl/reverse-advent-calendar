#!/usr/bin/env python3
import argparse
import base64
import csv
import json
import re
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from rate_images import ENDPOINT, MODEL, load_api_key  # noqa: E402
from detect_items import ITEM_FIELDS, LOG, LOG_FIELDS, OUTPUT, SELECTION, SOURCE, Budget, model_image, read_rows  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CATEGORIES = ROOT / "lists" / "ground_categories.csv"
PROMPT_FILE = ROOT / "prompts" / "ground_prompt.md"
RAW_DIR = ROOT / "runs" / "ground_raw"
BUDGET = Budget(0.5)
# Sampling settings recommended for Qwen3-VL Instruct models in the official README.
SAMPLING = {"temperature": 0.7, "top_p": 0.8, "top_k": 20, "repetition_penalty": 1.0, "presence_penalty": 1.5}


def call_model(api_key, image_bytes, prompt):
    body = {
        "model": MODEL, "max_tokens": 9000, "usage": {"include": True}, **SAMPLING,
        "messages": [{"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + base64.b64encode(image_bytes).decode()}},
            {"type": "text", "text": prompt},
        ]}],
    }
    req = urllib.request.Request(ENDPOINT, data=json.dumps(body).encode(), method="POST", headers={
        "Authorization": f"Bearer {api_key}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as resp:
        data = json.loads(resp.read())
    if "choices" not in data:
        raise RuntimeError(f"provider error: {json.dumps(data.get('error', data))[:300]}")
    return data


def parse_boxes(text):
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
    try:
        data = json.loads(text)
        return data if isinstance(data, list) else data.get("items", []), False
    except json.JSONDecodeError:
        found = []
        for m in re.finditer(r"\{[^{}]*\"bbox_2d\"\s*:\s*\[[^\]]*\][^{}]*\}", text):
            try:
                found.append(json.loads(m.group(0)))
            except json.JSONDecodeError:
                pass
        return found, True


def ground(row, categories, api_key, rerun):
    artwork_id = row["id"]
    log = {"id": artwork_id, "title": row["title"], "note": "grounded with category list", "error": ""}
    raw_path = RAW_DIR / f"{artwork_id}.json"
    try:
        if raw_path.exists() and not rerun:
            resp = json.loads(raw_path.read_text())
        else:
            prompt = PROMPT_FILE.read_text(encoding="utf-8").strip().replace("{{categories}}", categories)
            BUDGET.check()
            resp = call_model(api_key, model_image(artwork_id), prompt)
            BUDGET.add(resp)
            resp["_run_at"], resp["_prompt"] = datetime.now(timezone.utc).isoformat(), prompt
            raw_path.write_text(json.dumps(resp, indent=2))
        boxes, truncated = parse_boxes(resp["choices"][0]["message"]["content"])
        if truncated:
            log["note"] += "; answer cut off, complete items recovered"
        rows = []
        for n, item in enumerate(boxes, 1):
            box = item.get("bbox_2d") or []
            if len(box) != 4:
                continue
            x0, y0, x1, y1 = (max(0.0, min(1.0, float(v) / 1000)) for v in box)
            if x1 <= x0 or y1 <= y0:
                continue
            rows.append({"id": artwork_id, "title": row["title"], "artist": row["artist"], "date": row["date"],
                         "type": row["type"], "item_id": n, "label": (item.get("label") or "").strip(), "festive": "",
                         "kind": "object", "x0": round(x0, 4), "y0": round(y0, 4), "x1": round(x1, 4), "y1": round(y1, 4)})
        usage = resp.get("usage") or {}
        log.update(items=len(rows), festive_items=0, prompt_tokens=usage.get("prompt_tokens", ""),
                   completion_tokens=usage.get("completion_tokens", ""), cost_usd=usage.get("cost", ""))
        return rows, log
    except Exception as e:
        log["error"] = str(e)[:300]
        return [], log


def main():
    ap = argparse.ArgumentParser(description="Box the listed categories in each artwork (official Qwen3-VL grounding prompt).")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--rerun", action="store_true", help="ignore cached answers")
    ap.add_argument("--budget", type=float, default=0.5, help="stop sending requests once this many dollars are spent")
    ap.add_argument("--limit", type=int, help="only the first N works")
    args = ap.parse_args()
    BUDGET.limit = args.budget

    with open(SELECTION, newline="", encoding="utf-8") as f:
        selection = {r["id"]: r for r in csv.DictReader(f)}
    categories = {r["id"]: r["categories"] for r in read_rows(CATEGORIES)}
    todo = [(selection[i], c) for i, c in categories.items() if i in selection and (SOURCE / f"{i}.jpg").exists()]
    todo = todo[:args.limit] if args.limit else todo
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    api_key = load_api_key()
    print(f"grounding {len(todo)} artworks with {MODEL}, cap ${BUDGET.limit:.2f}")

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        results = list(pool.map(lambda t: ground(t[0], t[1], api_key, args.rerun), todo))
    done = {r["id"] for r, _ in todo}
    items = [i for i in read_rows(OUTPUT) if i["id"] not in done] + [i for rows, _ in results for i in rows]
    logs = [l for l in read_rows(LOG) if l["id"] not in done] + [log for _, log in results]
    for path, fields, rows in ((OUTPUT, ITEM_FIELDS, items), (LOG, LOG_FIELDS, logs)):
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
            w.writeheader()
            w.writerows(rows)
    for _, log in results:
        status = f"ERROR {log['error']}" if log["error"] else f"{log['items']} boxes"
        print(f"  {log['title'][:55]:55} {status}")
    empty = sum(1 for _, l in results if not l["error"] and l["items"] == 0)
    errors = sum(1 for _, l in results if l["error"])
    print(f"done: {sum(len(r) for r, _ in results)} boxes, {empty} empty, {errors} errors, spent ${BUDGET.spent:.4f} (cap ${BUDGET.limit:.2f})")


if __name__ == "__main__":
    main()

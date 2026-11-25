#!/usr/bin/env python3
import argparse
import base64
import csv
import json
import re
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from rate_images import ENDPOINT, MODEL, load_api_key  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SELECTION = ROOT / "lists" / "selection.csv"
PROMPT_FILE = ROOT / "prompts" / "detect_prompt.md"
SOURCE = ROOT / "runs" / "images_3000"
MODEL_IMAGES = ROOT / "runs" / "images_1600"
RAW_DIR = ROOT / "runs" / "detect_raw"
OUTPUT = ROOT / "runs" / "detect_items.csv"
LOG = ROOT / "runs" / "detect_artworks.csv"
MODEL_SIZE = 1600
ITEM_FIELDS = ["id", "title", "artist", "date", "type", "item_id", "label", "festive", "kind", "theme", "confidence",
               "reason", "review_reason", "approx_count", "x0", "y0", "x1", "y1"]
LOG_FIELDS = ["id", "title", "items", "festive_items", "prompt_tokens", "completion_tokens", "cost_usd", "note", "error"]


def model_image(artwork_id):
    out = MODEL_IMAGES / f"{artwork_id}.jpg"
    if not out.exists():
        MODEL_IMAGES.mkdir(parents=True, exist_ok=True)
        source = SOURCE / f"{artwork_id}.jpg"
        size = subprocess.run(["sips", "-g", "pixelWidth", "-g", "pixelHeight", str(source)], check=True,
                              capture_output=True, text=True).stdout
        longest = max(int(n) for n in re.findall(r"pixel(?:Width|Height): (\d+)", size))
        if longest <= MODEL_SIZE:
            out.write_bytes(source.read_bytes())
        else:
            subprocess.run(["sips", "-Z", str(MODEL_SIZE), str(source), "--out", str(out)], check=True, capture_output=True)
    return out.read_bytes()


def render_prompt(row):
    kind = (row.get("type") or "artwork").replace("Drawing and Watercolor", "drawing").lower()
    medium = (row.get("medium") or "medium not recorded").rstrip(".")
    return PROMPT_FILE.read_text(encoding="utf-8").replace("{{type}}", kind).replace("{{medium}}", medium)


def call_model(api_key, image_bytes, prompt, retries=3, avoid=()):
    body = {
        "model": MODEL, "temperature": 0.2, "max_tokens": 9000, "usage": {"include": True},
        **({"provider": {"ignore": list(avoid)}} if avoid else {}),
        "messages": [{"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + base64.b64encode(image_bytes).decode()}},
            {"type": "text", "text": prompt},
        ]}],
    }
    req = urllib.request.Request(ENDPOINT, data=json.dumps(body).encode(), method="POST", headers={
        "Authorization": f"Bearer {api_key}", "Content-Type": "application/json"})
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=300) as resp:
                data = json.loads(resp.read())
            if "choices" in data:
                return data
            raise RuntimeError(f"provider error: {json.dumps(data.get('error', data))[:300]}")
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, RuntimeError):
            if attempt == retries - 1:
                raise
            time.sleep(5 * (attempt + 1))


def parse_items(text):
    """Return the item list, recovering complete items when the answer was cut off."""
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
    try:
        return json.loads(text).get("items", []), False
    except json.JSONDecodeError:
        items = []
        for m in re.finditer(r"\{[^{}]*\"bbox_2d\"\s*:\s*\[[^\]]*\][^{}]*\}", text):
            try:
                items.append(json.loads(m.group(0)))
            except json.JSONDecodeError:
                pass
        return items, True


class Budget:
    def __init__(self, limit):
        self.limit, self.spent, self.lock = limit, 0.0, threading.Lock()

    def check(self):
        with self.lock:
            if self.spent >= self.limit:
                raise RuntimeError(f"budget of ${self.limit:.2f} reached; not sent")

    def add(self, resp):
        with self.lock:
            self.spent += float((resp.get("usage") or {}).get("cost") or 0)


BUDGET = Budget(2.0)


def looks_blind(resp):
    """Spot an instant empty answer, which some providers give when they drop the image."""
    content = resp["choices"][0]["message"]["content"]
    return (resp.get("usage") or {}).get("completion_tokens", 99) < 30 and '"items": []' in re.sub(r"\s+", " ", content)


def detect(row, api_key, rerun):
    artwork_id = row["id"]
    log = {"id": artwork_id, "title": row["title"], "note": "", "error": ""}
    raw_path = RAW_DIR / f"{artwork_id}.json"
    try:
        if raw_path.exists() and not rerun:
            resp = json.loads(raw_path.read_text())
        else:
            image, prompt, avoid = model_image(artwork_id), render_prompt(row), []
            BUDGET.check()
            resp = call_model(api_key, image, prompt)
            BUDGET.add(resp)
            while looks_blind(resp) and len(avoid) < 2:
                avoid.append(resp.get("provider") or "")
                BUDGET.check()
                resp = call_model(api_key, image, prompt, avoid=[p for p in avoid if p])
                BUDGET.add(resp)
            if avoid:
                log["note"] = f"retried after empty answer from {', '.join(p for p in avoid if p)}"
            resp["_run_at"] = datetime.now(timezone.utc).isoformat()
            raw_path.write_text(json.dumps(resp, indent=2))
        items, truncated = parse_items(resp["choices"][0]["message"]["content"])
        if truncated:
            log["note"] = "answer cut off; complete items recovered"
        rows = []
        for n, item in enumerate(items, 1):
            box = item.get("bbox_2d") or []
            if len(box) != 4:
                continue
            x0, y0, x1, y1 = (max(0.0, min(1.0, float(v) / 1000)) for v in box)
            if x1 <= x0 or y1 <= y0:
                continue
            rows.append({
                "id": artwork_id, "title": row["title"], "artist": row["artist"], "date": row["date"], "type": row["type"],
                "item_id": n, "label": (item.get("label") or "").strip(), "festive": bool(item.get("festive")),
                "kind": item.get("kind", ""), "theme": item.get("theme", ""), "confidence": item.get("confidence", ""),
                "reason": item.get("reason", ""), "review_reason": item.get("review_reason", ""),
                "approx_count": item.get("approx_count") or "",
                "x0": round(x0, 4), "y0": round(y0, 4), "x1": round(x1, 4), "y1": round(y1, 4),
            })
        usage = resp.get("usage") or {}
        log.update(items=len(rows), festive_items=sum(r["festive"] for r in rows), prompt_tokens=usage.get("prompt_tokens", ""),
                   completion_tokens=usage.get("completion_tokens", ""), cost_usd=usage.get("cost", ""))
        return rows, log
    except Exception as e:
        log["error"] = str(e)[:300]
        return [], log


def read_rows(path):
    if not path.exists():
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def main():
    ap = argparse.ArgumentParser(description="Detect people, animals and objects (with boxes) in the selected artworks.")
    ap.add_argument("--ids", help="text file with artwork ids, one per line (default: whole selection)")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--rerun", action="store_true", help="ignore cached answers")
    ap.add_argument("--budget", type=float, default=2.0, help="stop sending requests once this many dollars are spent")
    args = ap.parse_args()
    BUDGET.limit = args.budget

    with open(SELECTION, newline="", encoding="utf-8") as f:
        selection = {r["id"]: r for r in csv.DictReader(f)}
    ids = [line.strip() for line in open(args.ids)] if args.ids else list(selection)
    todo = [selection[i] for i in ids if i in selection and (SOURCE / f"{i}.jpg").exists()]
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    api_key = load_api_key()
    print(f"detecting in {len(todo)} artworks with {MODEL}")

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        results = list(pool.map(lambda r: detect(r, api_key, args.rerun), todo))
    done_ids = {r["id"] for r in todo}
    items = [i for i in read_rows(OUTPUT) if i["id"] not in done_ids] + [i for rows, _ in results for i in rows]
    logs = [l for l in read_rows(LOG) if l["id"] not in done_ids] + [log for _, log in results]
    for path, fields, rows in ((OUTPUT, ITEM_FIELDS, items), (LOG, LOG_FIELDS, logs)):
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
            w.writeheader()
            w.writerows(rows)
    for log in logs:
        status = f"ERROR {log['error']}" if log["error"] else f"{log['items']} items ({log['festive_items']} festive) {log['note']}"
        print(f"  {log['title'][:50]:50} {status}")
    cost = sum(float(l["cost_usd"]) for l in logs if l.get("cost_usd") not in ("", None))
    empty = [l for l in logs if not l["error"] and str(l.get("items")) == "0"]
    print(f"done: {len(items)} items, {sum(1 for l in logs if l['error'])} errors, {len(empty)} empty, "
          f"spent this run ${BUDGET.spent:.4f} (cap ${BUDGET.limit:.2f}), all answers ${cost:.4f} -> {OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()

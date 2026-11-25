#!/usr/bin/env python3
import argparse
import base64
import csv
import json
import re
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PUBLIC_DOMAIN = ROOT / "lists" / "aic_public_domain.jsonl"
PROMPT_FILE = ROOT / "prompts" / "rating_prompt.md"
IMAGES = ROOT / "runs" / "images_843"
RAW_DIR = ROOT / "runs" / "rating_raw"
OUTPUT = ROOT / "runs" / "ratings.csv"
ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"
MODEL = "qwen/qwen3-vl-235b-a22b-instruct"
FIELDS = ["id", "type", "title", "artist", "date", "score", "detail_items", "clear_items", "items", "setting",
          "colour", "finish", "people_only", "festive", "note", "cost_usd", "error"]


def load_api_key():
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            if line.strip().startswith("OPENROUTER_API_KEY="):
                return line.split("=", 1)[1].strip().strip("'\"")
    raise SystemExit("OPENROUTER_API_KEY missing from .env in the project folder")


def public_domain_records():
    records = {}
    with open(PUBLIC_DOMAIN, encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            if r.get("is_public_domain") is True and r.get("image_id"):
                records[str(r["id"])] = r
    return records


def render_prompt(r):
    return (PROMPT_FILE.read_text(encoding="utf-8")
            .replace("{{title}}", r.get("title") or "untitled")
            .replace("{{artist}}", r.get("artist_title") or "unknown artist")
            .replace("{{date}}", r.get("date_display") or "date unknown")
            .replace("{{type}}", (r.get("artwork_type_title") or "artwork").lower()))


def call_model(api_key, image_bytes, prompt, retries=3):
    body = {
        "model": MODEL,
        "temperature": 0.2,
        "max_tokens": 1500,
        "usage": {"include": True},
        "messages": [{"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + base64.b64encode(image_bytes).decode()}},
            {"type": "text", "text": prompt},
        ]}],
    }
    req = urllib.request.Request(ENDPOINT, data=json.dumps(body).encode(), method="POST", headers={
        "Authorization": f"Bearer {api_key}", "Content-Type": "application/json"})
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=180) as resp:
                data = json.loads(resp.read())
            if "choices" in data:
                return data
            raise RuntimeError(f"provider error: {json.dumps(data.get('error', data))[:300]}")
        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors="replace")[:300]
            if e.code in (429, 502, 503, 504) and attempt < retries - 1:
                time.sleep(5 * (attempt + 1))
                continue
            raise RuntimeError(f"HTTP {e.code}: {detail}")
        except (urllib.error.URLError, TimeoutError, RuntimeError):
            if attempt < retries - 1:
                time.sleep(5 * (attempt + 1))
                continue
            raise


def parse(text):
    match = re.search(r"\{.*\}", text, re.S)
    if not match:
        raise ValueError(f"no JSON in answer: {text[:200]!r}")
    return json.loads(match.group(0))


def rate(artwork_id, record, api_key, rerun):
    row = {"id": artwork_id, "type": record.get("artwork_type_title", ""), "title": record.get("title", ""),
           "artist": record.get("artist_title") or "", "date": record.get("date_display") or "", "error": ""}
    raw_path = RAW_DIR / f"{artwork_id}.json"
    try:
        if raw_path.exists() and not rerun:
            resp = json.loads(raw_path.read_text())
        else:
            image = (IMAGES / f"{artwork_id}.jpg").read_bytes()
            resp = call_model(api_key, image, render_prompt(record))
            resp["_run_at"] = datetime.now(timezone.utc).isoformat()
            raw_path.write_text(json.dumps(resp, indent=2))
        answer = parse(resp["choices"][0]["message"]["content"])
        items = answer.get("items") or []
        clear = [i for i in items if i.get("clear")]
        row.update(
            score=answer.get("score", ""),
            detail_items=sum(1 for i in clear if i.get("role") == "detail"),
            clear_items=len(clear),
            items="; ".join(f"{i.get('label')} ({i.get('role')}{'' if i.get('clear') else ', unclear'})" for i in items),
            setting="; ".join(answer.get("setting") or []),
            colour=answer.get("colour", ""),
            finish=answer.get("finish", ""),
            people_only=answer.get("people_only", ""),
            festive="; ".join(answer.get("festive") or []),
            note=answer.get("note", ""),
            cost_usd=(resp.get("usage") or {}).get("cost", ""),
        )
    except Exception as e:
        row["error"] = str(e)[:300]
    return row


def main():
    global PROMPT_FILE, RAW_DIR, OUTPUT
    ap = argparse.ArgumentParser(description="Rate downloaded candidate images for festive, sticker-sized items.")
    ap.add_argument("--list", default=str(ROOT / "lists" / "pool.csv"), help="CSV with an id column")
    ap.add_argument("--limit", type=int, help="only the first N downloaded images")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--rerun", action="store_true", help="ignore cached answers")
    ap.add_argument("--prompt", default=str(PROMPT_FILE), help="prompt file")
    ap.add_argument("--output", default=str(OUTPUT), help="output CSV")
    ap.add_argument("--raw-dir", default=str(RAW_DIR), help="folder for cached model answers")
    args = ap.parse_args()
    PROMPT_FILE, RAW_DIR, OUTPUT = (Path(p).resolve() for p in (args.prompt, args.raw_dir, args.output))

    api_key = load_api_key()
    records = public_domain_records()
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    with open(args.list, newline="", encoding="utf-8") as f:
        ids = [r["id"] for r in csv.DictReader(f)]
    todo = [i for i in ids if i in records and (IMAGES / f"{i}.jpg").exists()]
    if args.limit:
        todo = todo[:args.limit]
    print(f"rating {len(todo)} images with {MODEL}")

    rows = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(rate, i, records[i], api_key, args.rerun): i for i in todo}
        for n, fut in enumerate(as_completed(futures), 1):
            row = fut.result()
            rows.append(row)
            status = f"ERROR {row['error']}" if row["error"] else f"score {row['score']} | {row['items'][:70]}"
            print(f"[{n}/{len(todo)}] {row['id']} {row['title'][:40]!r}: {status}", flush=True)

    rows.sort(key=lambda r: (-(r["score"] if isinstance(r.get("score"), int) else -1), -(r.get("detail_items") or 0)))
    with open(OUTPUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    cost = sum(float(r["cost_usd"]) for r in rows if r.get("cost_usd") not in ("", None))
    errors = sum(1 for r in rows if r["error"])
    print(f"done: {len(rows)} rated, {errors} errors, cost ${cost:.4f} -> {OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()

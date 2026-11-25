#!/usr/bin/env python3
import argparse
import csv
import json
import random
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PUBLIC_DOMAIN = ROOT / "lists" / "aic_public_domain.jsonl"
IIIF = "https://www.artic.edu/iiif/2/{image_id}/full/{size}/0/default.jpg"
SIZES = ("843", "1686", "3000")
HEADERS = {
    "User-Agent": "xmas-sticker-research/0.1 (image download, one request at a time)",
    "AIC-User-Agent": "xmas-sticker-research",
}


def public_domain_ids():
    ids = {}
    with open(PUBLIC_DOMAIN, encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            if r.get("is_public_domain") is True and r.get("image_id"):
                thumb = r.get("thumbnail") or {}
                ids[str(r["id"])] = (r["image_id"], thumb.get("width") or 0, thumb.get("height") or 0)
    return ids


def size_param(size, width, height):
    """Return an IIIF size the server accepts: it refuses any upscaling beyond the master image."""
    target = int(size)
    if size == "3000" and max(width, height) >= 3000:
        return "!3000,3000"
    if width and width < target:
        return f"{width},"
    return f"{target},"


def fetch(url, retries=3):
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = resp.read()
                kind = resp.headers.get("Content-Type", "")
            if not data.startswith(b"\xff\xd8") or "image" not in kind:
                raise RuntimeError(f"not a JPEG (Content-Type {kind!r}, starts {data[:40]!r})")
            return data
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and attempt < retries - 1:
                wait = int(e.headers.get("Retry-After") or 30 * (attempt + 1))
                print(f"    HTTP {e.code}, waiting {wait}s", flush=True)
                time.sleep(wait)
                continue
            body = e.read()[:200]
            raise RuntimeError(f"HTTP {e.code} {e.reason}; server: {e.headers.get('Server')}; body: {body!r}")
        except (urllib.error.URLError, TimeoutError) as e:
            if attempt < retries - 1:
                time.sleep(10 * (attempt + 1))
                continue
            raise RuntimeError(f"network error: {e}")


def main():
    ap = argparse.ArgumentParser(description="Download AIC public-domain images one at a time.")
    ap.add_argument("--list", default=str(ROOT / "lists" / "pool.csv"), help="CSV with an id column")
    ap.add_argument("--size", choices=SIZES, default="843")
    ap.add_argument("--limit", type=int, help="only N new downloads")
    ap.add_argument("--type", help="only this artwork type, e.g. Painting or 'Drawing and Watercolor'")
    ap.add_argument("--random", type=int, metavar="SEED", help="pick in random order with this seed")
    ap.add_argument("--pause", type=float, default=1.0, help="seconds between requests")
    ap.add_argument("--max-failures", type=int, default=5, help="stop after this many failures in a row")
    args = ap.parse_args()

    out_dir = ROOT / "runs" / f"images_{args.size}"
    out_dir.mkdir(parents=True, exist_ok=True)
    log = open(ROOT / "runs" / f"images_{args.size}.log", "a", encoding="utf-8")

    allowed = public_domain_ids()
    with open(args.list, newline="", encoding="utf-8") as f:
        wanted = [r["id"] for r in csv.DictReader(f) if not args.type or r.get("type") == args.type]
    skipped = [i for i in wanted if i not in allowed]
    todo = [i for i in wanted if i in allowed and not (out_dir / f"{i}.jpg").exists()]
    if skipped:
        print(f"{len(skipped)} ids are not public domain with an image and are skipped")
    if args.random is not None:
        random.Random(args.random).shuffle(todo)
    if args.limit:
        todo = todo[:args.limit]

    done = failed = in_a_row = 0
    for n, artwork_id in enumerate(todo, 1):
        image_id, width, height = allowed[artwork_id]
        path = out_dir / f"{artwork_id}.jpg"
        if path.exists():
            continue
        url = IIIF.format(image_id=image_id, size=size_param(args.size, width, height))
        start = time.time()
        try:
            data = fetch(url)
            path.write_bytes(data)
            done += 1
            in_a_row = 0
            msg = f"[{n}/{len(todo)}] {artwork_id} ok {len(data) // 1024} KB in {time.time() - start:.1f}s"
        except Exception as e:
            failed += 1
            in_a_row += 1
            msg = f"[{n}/{len(todo)}] {artwork_id} FAILED {e}"
        print(msg, flush=True)
        log.write(f"{datetime.now().isoformat(timespec='seconds')} {msg}\n")
        if in_a_row >= args.max_failures:
            print(f"stopping after {in_a_row} failures in a row")
            break
        time.sleep(args.pause)
    print(f"downloaded {done}, failed {failed}, folder {out_dir.relative_to(ROOT)}")


if __name__ == "__main__":
    main()

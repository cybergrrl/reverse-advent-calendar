#!/usr/bin/env python3
import argparse
import csv
import sys
import time
from collections import Counter
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter
from scipy import ndimage

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "picker"))
sys.path.insert(0, str(ROOT / "scripts"))
import label_rules  # noqa: E402
from build_site import layer  # noqa: E402
from server import review_data  # noqa: E402

IMAGES = ROOT / "runs" / "images_3000"
OUT_DIR = ROOT / "runs" / "cutouts"
PNG_DIR = OUT_DIR / "png"
STICKER_DIR = OUT_DIR / "stickers"
RESULTS_CSV = OUT_DIR / "cutouts.csv"
OVERRIDES_CSV = ROOT / "lists" / "cutout_overrides.csv"
MODEL_ID = "feyninc/multimatte"

MARGIN = 0.15
RETRY_MARGIN = 0.4
LOW_BOX_COVER = 0.3
CROP_PX = 2400
BORDER_FRAC = 0.045
MIN_BORDER = 5
PILOT_SIZE = 20
PILOT_GROUPS = ["Christ Child", "Mary", "wise man", "angel", "ox", "sleigh", "skater", "candle", "wreath",
                "violin", "apple", "grapes", "glass", "jug", "basket", "dog", "conifer", "coat", "umbrella", "letter"]
PROMPTS = {"Christ Child": "the baby", "Mary": "the woman", "Joseph": "the man", "wise man": "the king",
           "gifts of the Magi": "the gift", "conifer": "the fir tree", "censer": "the censer"}

RESULT_FIELDS = ["key", "id", "item_id", "title", "group", "detail", "prompt", "file", "sticker", "crop_w", "crop_h",
                 "cut_w", "cut_h", "box_cover", "outside_box", "edge_touch", "margin", "flag", "seconds", "error"]


def sticker_items():
    overrides = label_rules.read_overrides()
    rows = []
    for a in review_data()["artworks"]:
        if a["decision"] != "keep":
            continue
        for i in a["items"]:
            if i["dropped"]:
                continue
            group = label_rules.resolve(i["label"], overrides)["canonical"]
            if layer(i, group) == "sticker":
                rows.append({"key": f"{a['id']}#{i['item_id']}", "id": a["id"], "item_id": i["item_id"],
                             "title": a["title"], "group": group, "detail": i["label"],
                             "box": [float(i[k]) for k in ("x0", "y0", "x1", "y1")]})
    return rows


def short_side(row, sizes):
    w, h = sizes.setdefault(row["id"], Image.open(IMAGES / f"{row['id']}.jpg").size)
    b = row["box"]
    return min((b[2] - b[0]) * w, (b[3] - b[1]) * h)


def pick_pilot(rows):
    sizes, chosen = {}, []
    by_group = {}
    for r in rows:
        by_group.setdefault(r["group"], []).append(r)
    common = [g for g, _ in Counter(r["group"] for r in rows).most_common()]
    for group in PILOT_GROUPS + common:
        if len(chosen) >= PILOT_SIZE:
            break
        if group not in by_group or any(c["group"] == group for c in chosen):
            continue
        candidates = sorted(by_group[group], key=lambda r: short_side(r, sizes))
        medium = [r for r in candidates if 150 <= short_side(r, sizes) <= 700]
        chosen.append((medium or candidates)[len(medium or candidates) // 2])
    return chosen


def load_overrides():
    if not OVERRIDES_CSV.exists():
        return {}
    with open(OVERRIDES_CSV, newline="", encoding="utf-8") as f:
        return {r["key"]: r for r in csv.DictReader(f)}


def apply_overrides(rows):
    overrides = load_overrides()
    for r in rows:
        o = overrides.get(r["key"], {})
        r["prompt"] = o.get("prompt", "")
        r["box"] = [float(v) for v in o["box"].split()] if o.get("box") else r["box"]
        r["clip"] = [float(v) for v in o["clip"].split()] if o.get("clip") else None
        r["shape"] = o.get("shape", "")
    return rows


def refine(alpha, row, region):
    import torch
    h, w = alpha.shape
    keep = None
    if row.get("clip"):
        x0, y0, x1, y1 = box_in_crop(region, row["clip"], w, h)
        keep = torch.zeros_like(alpha)
        keep[max(0, int(y0)):max(0, int(y1)), max(0, int(x0)):max(0, int(x1))] = 1
        alpha = alpha * keep
    shapes = set(row.get("shape", "").split())
    solid = (alpha > 0.5).numpy()
    if "below" in shapes:
        cols = solid.any(axis=0)
        tops = np.where(cols, solid.argmax(axis=0), h)
        solid = np.arange(h)[:, None] >= tops[None, :]
        alpha = torch.maximum(alpha, torch.from_numpy(solid.astype(np.float32)))
    if "fill" in shapes:
        solid = ndimage.binary_fill_holes(solid)
        alpha = torch.maximum(alpha, torch.from_numpy(solid.astype(np.float32)))
    if "largest" in shapes:
        labels, count = ndimage.label(solid)
        if count > 1:
            biggest = 1 + int(np.argmax(ndimage.sum(solid, labels, range(1, count + 1))))
            near = ndimage.binary_dilation(labels == biggest, iterations=3)
            alpha = alpha * torch.from_numpy(near.astype(np.float32))
    if row.get("clip") and shapes & {"below", "fill", "hull"}:
        alpha = alpha * keep
    if "hull" in shapes:
        from scipy.spatial import ConvexHull
        from PIL import ImageDraw
        pts = np.argwhere(solid)[:, ::-1]
        if len(pts) >= 3:
            hull = Image.new("L", (w, h), 0)
            ImageDraw.Draw(hull).polygon([tuple(pts[v]) for v in ConvexHull(pts).vertices], fill=255)
            alpha = torch.maximum(alpha, torch.from_numpy(np.array(hull, np.float32) / 255))
    return alpha


def prompt_for(row):
    if row.get("prompt"):
        return row["prompt"]
    return PROMPTS.get(row["group"]) or f"the {row['detail'].strip().lower()}"


def padded_region(box, margin):
    x0, y0, x1, y1 = box
    dx, dy = (x1 - x0) * margin, (y1 - y0) * margin
    return (max(0.0, x0 - dx), max(0.0, y0 - dy), min(1.0, x1 + dx), min(1.0, y1 + dy))


def crop_image(full, region):
    rx0, ry0, rx1, ry1 = region
    image = full.crop((round(rx0 * full.width), round(ry0 * full.height),
                       round(rx1 * full.width), round(ry1 * full.height)))
    image.thumbnail((CROP_PX, CROP_PX))
    return image


def box_in_crop(region, box, w, h):
    rx0, ry0, rx1, ry1 = region
    sx, sy = w / (rx1 - rx0), h / (ry1 - ry0)
    return [(box[0] - rx0) * sx, (box[1] - ry0) * sy, (box[2] - rx0) * sx, (box[3] - ry0) * sy]


def matte_stats(alpha, box_px, region):
    import torch
    h, w = alpha.shape
    x0, y0, x1, y1 = (int(round(v)) for v in box_px)
    x0, y0, x1, y1 = max(0, x0), max(0, y0), min(w, x1), min(h, y1)
    solid = alpha > 0.5
    total = float(solid.sum())
    inside = float(solid[y0:y1, x0:x1].sum())
    box_area = max(1, (x1 - x0) * (y1 - y0))
    rx0, ry0, rx1, ry1 = region
    edges = [name for name, strip, at_image_edge in (
        ("left", solid[:, 0], rx0 <= 0), ("right", solid[:, -1], rx1 >= 1),
        ("top", solid[0, :], ry0 <= 0), ("bottom", solid[-1, :], ry1 >= 1))
        if not at_image_edge and float(strip.float().mean()) > 0.02]
    return {"box_cover": round(inside / box_area, 3),
            "outside_box": round((total - inside) / total, 3) if total else "",
            "edge_touch": " ".join(edges)}, torch.nonzero(alpha > 0.02)


def trim(cutout, points, pad=4):
    if len(points) == 0:
        return cutout
    ys, xs = points[:, 0], points[:, 1]
    left, top = max(0, int(xs.min()) - pad), max(0, int(ys.min()) - pad)
    right, bottom = min(cutout.width, int(xs.max()) + pad + 1), min(cutout.height, int(ys.max()) + pad + 1)
    return cutout.crop((left, top, right, bottom))


def clean_mask(alpha):
    solid = alpha > 0.5
    labels, count = ndimage.label(solid)
    if count > 1:
        sizes = ndimage.sum(solid, labels, range(1, count + 1))
        keep = np.nonzero(sizes >= max(sizes.max() * 0.03, 20))[0] + 1
        solid = np.isin(labels, keep)
    return solid


def add_border(cut):
    rgba = np.array(cut.convert("RGBA"))
    alpha = rgba[:, :, 3] / 255.0
    border = max(MIN_BORDER, round(max(cut.size) * BORDER_FRAC))
    pad = border * 2 + 4
    h, w = alpha.shape
    solid = np.zeros((h + 2 * pad, w + 2 * pad), bool)
    solid[pad:pad + h, pad:pad + w] = clean_mask(alpha)
    shape = ndimage.distance_transform_edt(~solid) <= border
    shape = ndimage.binary_closing(shape, structure=np.ones((3, 3)), iterations=border)
    shape = ndimage.binary_fill_holes(shape)
    edge = Image.fromarray((shape * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.0))
    inner = ndimage.distance_transform_edt(~solid) <= max(2, border // 3)
    placed = np.zeros((h + 2 * pad, w + 2 * pad, 4), np.uint8)
    placed[pad:pad + h, pad:pad + w] = rgba
    placed[:, :, 3] = (placed[:, :, 3] * inner).astype(np.uint8)
    out = Image.new("RGBA", edge.size, (255, 255, 255, 0))
    out.putalpha(edge)
    out.alpha_composite(Image.fromarray(placed, "RGBA"))
    return out


def cut_out(row, full, model, processor, margin):
    region = padded_region(row["box"], margin)
    image = crop_image(full, region)
    box_px = box_in_crop(region, row["box"], image.width, image.height)
    alpha = model.predict(processor, image, prompt_for(row), [box_px], return_type="alpha").detach().float().cpu()
    alpha = refine(alpha, row, region)
    stats, points = matte_stats(alpha, box_px, region)
    cut = trim(processor.cutout(image, alpha), points)
    name = f"{row['id']}_{row['item_id']}.png"
    cut.save(PNG_DIR / name)
    add_border(cut).save(STICKER_DIR / name)
    return {"prompt": prompt_for(row), "file": f"runs/cutouts/png/{name}", "sticker": f"runs/cutouts/stickers/{name}",
            "crop_w": image.width, "crop_h": image.height, "cut_w": cut.width, "cut_h": cut.height,
            **stats, "margin": margin, "error": ""}


def process(row, full, model, processor):
    started = time.time()
    outcome = cut_out(row, full, model, processor, MARGIN)
    if outcome["edge_touch"]:
        outcome = cut_out(row, full, model, processor, RETRY_MARGIN)
    flags = ([f"touches {outcome['edge_touch']} edge"] if outcome["edge_touch"] else []) + \
            (["fills little of its box"] if outcome["box_cover"] < LOW_BOX_COVER else [])
    return outcome | {"flag": ", ".join(flags), "seconds": round(time.time() - started, 1)}


def load_results():
    if not RESULTS_CSV.exists():
        return {}
    with open(RESULTS_CSV, newline="", encoding="utf-8") as f:
        return {r["key"]: r for r in csv.DictReader(f)}


def save_results(results):
    tmp = RESULTS_CSV.with_suffix(".tmp")
    with open(tmp, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=RESULT_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(sorted(results.values(), key=lambda r: (r["id"], int(r["item_id"]))))
    tmp.replace(RESULTS_CSV)


def load_model():
    import torch
    from nobg import AutoModel, AutoProcessor
    device = "mps" if torch.backends.mps.is_available() else "cpu"
    print(f"Loading {MODEL_ID} on {device}...", flush=True)
    return AutoModel.from_pretrained(MODEL_ID).to(device).eval(), AutoProcessor.from_pretrained(MODEL_ID)


def main():
    ap = argparse.ArgumentParser(description="Cut out sticker items with MultiMatte and add a white border.")
    ap.add_argument("--pilot", action="store_true", help=f"run {PILOT_SIZE} varied items")
    ap.add_argument("--keys", nargs="*", help="id#item_id keys to run")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--rerun", action="store_true", help="redo items that already have a cutout")
    ap.add_argument("--dry-run", action="store_true", help="list what would run, without loading the model")
    args = ap.parse_args()

    rows = apply_overrides(sticker_items())
    if args.pilot:
        rows = pick_pilot(rows)
    if args.keys:
        rows = [r for r in rows if r["key"] in set(args.keys)]
    results = load_results()
    if not args.rerun:
        rows = [r for r in rows if not results.get(r["key"], {}).get("file")]
    if args.limit:
        rows = rows[:args.limit]
    print(f"{len(rows)} items to cut out", flush=True)
    if args.dry_run:
        for r in rows:
            print(f"  {r['key']:12} {r['group']:16} prompt: {prompt_for(r):34} {r['title'][:45]}")
        return
    if not rows:
        return

    PNG_DIR.mkdir(parents=True, exist_ok=True)
    STICKER_DIR.mkdir(parents=True, exist_ok=True)
    model, processor = load_model()
    failures, full, full_id = 0, None, None
    for n, row in enumerate(rows, 1):
        base = {k: row[k] for k in ("key", "id", "item_id", "title", "group", "detail")}
        try:
            if full_id != row["id"]:
                full, full_id = Image.open(IMAGES / f"{row['id']}.jpg").convert("RGB"), row["id"]
            outcome = process(row, full, model, processor)
            note = f"{outcome['seconds']}s, box cover {outcome['box_cover']}"
            if outcome["margin"] == RETRY_MARGIN:
                note += ", retried with a wider margin"
            if outcome["flag"]:
                note += f", FLAG: {outcome['flag']}"
        except Exception as e:
            failures += 1
            outcome = {"error": f"{type(e).__name__}: {e}"[:300], "prompt": prompt_for(row)}
            note = f"FAILED: {outcome['error']}"
        results[row["key"]] = base | outcome
        save_results(results)
        print(f"[{n}/{len(rows)}] {row['group']} | {row['title'][:45]} | {note}", flush=True)
    print(f"Done. {len(rows) - failures} cut out, {failures} failed. Results in {RESULTS_CSV.relative_to(ROOT)}")


if __name__ == "__main__":
    main()

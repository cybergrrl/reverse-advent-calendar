#!/usr/bin/env python3
import csv
import json
import re
import sys
import webbrowser
from datetime import datetime
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HERE = Path(__file__).resolve().parent
IMAGES = ROOT / "runs" / "images_843"
RATINGS = ROOT / "runs" / "ratings.csv"
POOL = ROOT / "lists" / "pool.csv"
PUBLIC_DOMAIN = ROOT / "lists" / "aic_public_domain.jsonl"
DECISIONS = ROOT / "lists" / "decisions.csv"
PAINTINGS_POOL = ROOT / "lists" / "paintings_pool.csv"
PAINTINGS_DECISIONS = ROOT / "lists" / "paintings_decisions.csv"
PORT = 8770
DECISION_FIELDS = ["id", "decision", "reasons", "score_feedback", "item_feedback", "note", "updated"]
ALLOWED = {
    "decision": {"", "keep", "maybe", "reject"},
    "reasons": {"not festive", "wrong mood", "too faint or sketchy", "dull or monochrome",
                "item is the whole picture", "near-duplicate",
                "great hidden detail", "strong colour", "unusual subject", "many good items"},
    "score_feedback": {"", "too low", "about right", "too high"},
    "item_feedback": {"invented items", "missed items"},
}


def read_csv(path):
    if not path.exists():
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_decisions():
    return {r["id"]: {k: r.get(k, "") for k in DECISION_FIELDS} for r in read_csv(DECISIONS)}


def valid(update):
    for key in ("decision", "score_feedback"):
        if key in update and update[key] not in ALLOWED[key]:
            return False
    for key in ("reasons", "item_feedback"):
        if key in update and not (isinstance(update[key], list) and set(update[key]) <= ALLOWED[key]):
            return False
    return "note" not in update or (isinstance(update["note"], str) and len(update["note"]) <= 2000)


def save_decision(artwork_id, update):
    decisions = load_decisions()
    row = decisions.get(artwork_id, {k: "" for k in DECISION_FIELDS})
    row["id"] = artwork_id
    for key in ("decision", "score_feedback", "note"):
        if key in update:
            row[key] = update[key].strip() if key == "note" else update[key]
    for key in ("reasons", "item_feedback"):
        if key in update:
            row[key] = "; ".join(update[key])
    row["updated"] = datetime.now().isoformat(timespec="seconds")
    if any(row[k] for k in DECISION_FIELDS if k not in ("id", "updated")):
        decisions[artwork_id] = row
    else:
        decisions.pop(artwork_id, None)
    with open(DECISIONS, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=DECISION_FIELDS)
        w.writeheader()
        w.writerows(decisions.values())


_records = {}


def public_domain_records():
    if not _records:
        with open(PUBLIC_DOMAIN, encoding="utf-8") as f:
            for line in f:
                r = json.loads(line)
                if r.get("is_public_domain") is True and r.get("image_id"):
                    _records[str(r["id"])] = r
    return _records


def build_data():
    pool = {r["id"]: r for r in read_csv(POOL)}
    ratings = {r["id"]: r for r in read_csv(RATINGS)}
    decisions = load_decisions()
    records = public_domain_records()
    artworks = []
    for artwork_id, p in pool.items():
        rec = records.get(artwork_id)
        if not rec or not (IMAGES / f"{artwork_id}.jpg").exists():
            continue
        rating = ratings.get(artwork_id, {})
        thumb = rec.get("thumbnail") or {}
        artworks.append({
            "id": artwork_id,
            "title": rec.get("title") or "",
            "artist": rec.get("artist_title") or "",
            "artist_display": rec.get("artist_display") or "",
            "date": rec.get("date_display") or "",
            "year": rec.get("date_end") or rec.get("date_start"),
            "type": rec.get("artwork_type_title") or "",
            "medium": rec.get("medium_display") or "",
            "place": rec.get("place_of_origin") or "",
            "max_side": max(thumb.get("width") or 0, thumb.get("height") or 0),
            "groups": p.get("groups", ""),
            "medium_colour": p.get("medium_colour", ""),
            "words": p.get("words", ""),
            "rated": bool(rating) and not rating.get("error"),
            "score": int(rating["score"]) if rating.get("score", "").isdigit() else None,
            "detail_items": int(rating.get("detail_items") or 0),
            "clear_items": int(rating.get("clear_items") or 0),
            "items": rating.get("items", ""),
            "setting": rating.get("setting", ""),
            "colour": rating.get("colour", ""),
            "finish": rating.get("finish", ""),
            "note": rating.get("note", ""),
            "decision": decisions.get(artwork_id, {}).get("decision", ""),
            "reasons": [x for x in decisions.get(artwork_id, {}).get("reasons", "").split("; ") if x],
            "score_feedback": decisions.get(artwork_id, {}).get("score_feedback", ""),
            "item_feedback": [x for x in decisions.get(artwork_id, {}).get("item_feedback", "").split("; ") if x],
            "mark_note": decisions.get(artwork_id, {}).get("note", ""),
        })
    return {"artworks": artworks, "pool_size": len(pool)}


def detect_data():
    logs = read_csv(ROOT / "runs" / "detect_artworks.csv")
    items = read_csv(ROOT / "runs" / "detect_items.csv")
    selection = {r["id"]: r for r in read_csv(ROOT / "lists" / "selection.csv")}
    artworks = []
    for log in logs:
        sel = selection.get(log["id"], {})
        artworks.append({**log, "artist": sel.get("artist", ""), "date": sel.get("date", ""), "type": sel.get("type", ""),
                         "items": [i for i in items if i["id"] == log["id"]]})
    return {"artworks": artworks}


REVIEW_ARTWORKS = ROOT / "lists" / "review_artworks.csv"
REVIEW_ITEMS = ROOT / "lists" / "review_items.csv"
REVIEW_ITEM_FIELDS = ["id", "item_id", "label", "new_label", "dropped", "starred", "quarantine", "updated"]
QUARANTINE_PROPOSALS = ROOT / "lists" / "quarantine_proposals.csv"
FESTIVE_ITEMS = ROOT / "lists" / "festive_items.csv"


def review_data():
    selection = read_csv(ROOT / "lists" / "selection.csv")
    logs = {r["id"]: r for r in read_csv(ROOT / "runs" / "detect_artworks.csv")}
    items = {}
    for i in read_csv(ROOT / "runs" / "detect_items.csv"):
        items.setdefault(i["id"], []).append(i)
    decisions = {r["id"]: r["decision"] for r in read_csv(REVIEW_ARTWORKS)}
    marks = {f'{r["id"]}:{r["item_id"]}': r for r in read_csv(REVIEW_ITEMS)}
    festive = {f'{r["id"]}:{r["item_id"]}': r["festive"] for r in read_csv(FESTIVE_ITEMS)} if FESTIVE_ITEMS.exists() else {}
    proposals = {f'{r["id"]}:{r["item_id"]}': r["reason"] for r in read_csv(QUARANTINE_PROPOSALS)} if QUARANTINE_PROPOSALS.exists() else {}
    artworks = []
    for s in selection:
        art_items = []
        for i in items.get(s["id"], []):
            mark = marks.get(f'{s["id"]}:{i["item_id"]}', {})
            art_items.append({k: i[k] for k in ("item_id", "label", "festive", "kind", "approx_count", "x0", "y0", "x1", "y1")}
                             | {"dropped": mark.get("dropped") == "yes", "starred": mark.get("starred") == "yes",
                                "original_label": i["label"], "label": mark.get("new_label") or i["label"],
                                "quarantine_reason": proposals.get(f'{s["id"]}:{i["item_id"]}', ""),
                                "quarantine": mark.get("quarantine", ""), "model_festive": i["festive"],
                                "festive": {"yes": "True", "no": "False"}.get(festive.get(f'{s["id"]}:{i["item_id"]}', ""), i["festive"])})
        artworks.append({**{k: s.get(k, "") for k in ("id", "source", "type", "title", "artist", "date")},
                         "note": logs.get(s["id"], {}).get("note", ""),
                         "decision": decisions.get(s["id"], ""), "items": art_items})
    return {"artworks": artworks}


def save_review_artworks(ids, decision):
    rows = {r["id"]: r for r in read_csv(REVIEW_ARTWORKS)}
    now = datetime.now().isoformat(timespec="seconds")
    for artwork_id in ids:
        if decision:
            rows[artwork_id] = {"id": artwork_id, "decision": decision, "updated": now}
        else:
            rows.pop(artwork_id, None)
    with open(REVIEW_ARTWORKS, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["id", "decision", "updated"])
        w.writeheader()
        w.writerows(rows.values())


def save_review_items(keys, field, value):
    rows = {f'{r["id"]}:{r["item_id"]}': r for r in read_csv(REVIEW_ITEMS)}
    labels = {f'{i["id"]}:{i["item_id"]}': i["label"] for i in read_csv(ROOT / "runs" / "detect_items.csv")}
    now = datetime.now().isoformat(timespec="seconds")
    for key in keys:
        artwork_id, item_id = key.split(":")
        row = rows.get(key, {"id": artwork_id, "item_id": item_id, "label": labels.get(key, ""), "new_label": "", "dropped": "", "starred": ""})
        row.setdefault("new_label", "")
        row.setdefault("quarantine", "")
        if field == "new_label":
            row["new_label"] = "" if value.strip() == row["label"] else value.strip()
        elif field == "quarantine":
            row["quarantine"] = value
        else:
            row[field] = "yes" if value else ""
        row["updated"] = now
        if row["dropped"] or row["starred"] or row["new_label"] or row["quarantine"]:
            rows[key] = row
        else:
            rows.pop(key, None)
    with open(REVIEW_ITEMS, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=REVIEW_ITEM_FIELDS)
        w.writeheader()
        w.writerows(rows.values())


sys.path.insert(0, str(ROOT / "scripts"))
import label_rules  # noqa: E402


def labels_data():
    overrides = label_rules.read_overrides()
    labels = {i["label"] for a in review_data()["artworks"] for i in a["items"]}
    return {"labels": {l.strip().lower(): label_rules.resolve(l, overrides) for l in labels},
            "categories": sorted(label_rules.CATEGORIES)}


def save_label_overrides(labels, field, value):
    rows = label_rules.read_overrides()
    now = datetime.now().isoformat(timespec="seconds")
    for label in labels:
        key = label.strip().lower()
        row = rows.get(key, {"label": key, "canonical": "", "category": ""})
        rule = label_rules.canonical(key) if field == "canonical" else ""
        row[field] = "" if value == rule else value
        row["updated"] = now
        if row["canonical"] or row["category"]:
            rows[key] = row
        else:
            rows.pop(key, None)
    with open(label_rules.OVERRIDES, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=label_rules.OVERRIDE_FIELDS)
        w.writeheader()
        w.writerows(rows.values())


CUTOUT_RESULTS = ROOT / "runs" / "cutouts" / "cutouts.csv"
CUTOUT_STICKERS = ROOT / "runs" / "cutouts" / "stickers"
CUTOUT_REVIEW = ROOT / "lists" / "cutout_review.csv"
CUTOUT_VERDICTS = ("", "ok", "redo", "crop")


def cutouts_data():
    reviews = {r["key"]: r for r in read_csv(CUTOUT_REVIEW)} if CUTOUT_REVIEW.exists() else {}
    boxes = {f'{i["id"]}#{i["item_id"]}': [float(i[k]) for k in ("x0", "y0", "x1", "y1")]
             for i in read_csv(ROOT / "runs" / "detect_items.csv")}
    starred = {f'{a["id"]}#{i["item_id"]}' for a in review_data()["artworks"] for i in a["items"] if i["starred"]}
    rows = []
    for r in read_csv(CUTOUT_RESULTS):
        if r.get("file"):
            rows.append({k: r[k] for k in ("key", "id", "item_id", "title", "group", "detail", "prompt", "flag",
                                           "box_cover", "edge_touch", "margin")}
                        | {"box": boxes.get(r["key"]), "verdict": reviews.get(r["key"], {}).get("verdict", ""),
                           "note": reviews.get(r["key"], {}).get("note", ""), "starred": r["key"] in starred})
    return {"cutouts": rows}


def save_cutout_review(keys, field, value):
    reviews = {r["key"]: r for r in read_csv(CUTOUT_REVIEW)} if CUTOUT_REVIEW.exists() else {}
    now = datetime.now().isoformat(timespec="seconds")
    for key in keys:
        row = reviews.get(key, {"key": key, "verdict": "", "note": ""}) | {field: value, "updated": now}
        if row["verdict"] or row.get("note"):
            reviews[key] = row
        else:
            reviews.pop(key, None)
    with open(CUTOUT_REVIEW, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["key", "verdict", "note", "updated"], extrasaction="ignore", restval="")
        w.writeheader()
        w.writerows(sorted(reviews.values(), key=lambda r: r["key"]))


CALENDAR_JSON = ROOT / "site" / "data" / "calendar.json"
DOORS = ROOT / "lists" / "doors.csv"


def read_doors():
    return read_csv(DOORS) if DOORS.exists() else []


def doors_data():
    data = json.loads(CALENDAR_JSON.read_text(encoding="utf-8"))
    paintings = {k: {f: p[f] for f in ("id", "title", "caption", "long", "url", "text_source")} for k, p in data["paintings"].items()}
    items = [{f: i[f] for f in ("key", "painting", "label", "detail", "sticker", "star")} for i in data["items"] if i["sticker"]]
    return {"paintings": paintings, "items": items, "doors": [r["key"] for r in read_doors()]}


def save_door(key, picked):
    rows = [r for r in read_doors() if r["key"] != key]
    if picked:
        rows.append({"key": key, "updated": datetime.now().isoformat(timespec="seconds")})
    with open(DOORS, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["key", "updated"])
        w.writeheader()
        w.writerows(rows)


def paintings_data():
    decisions = {r["id"]: r["decision"] for r in read_csv(PAINTINGS_DECISIONS)}
    ratings = {r["id"]: r for r in read_csv(ROOT / "runs" / "paintings_ratings.csv")}
    rows = read_csv(PAINTINGS_POOL)
    for r in rows:
        r["decision"] = decisions.get(r["id"], "")
        r["downloaded"] = (IMAGES / f"{r['id']}.jpg").exists()
        rating = ratings.get(r["id"], {})
        r["score"] = int(rating["score"]) if rating.get("score", "").isdigit() else None
        for key in ("items", "people_only", "finish", "festive", "note", "detail_items"):
            r[key] = rating.get(key, "")
    return {"paintings": rows}


def save_paintings_decisions(ids, decision):
    decisions = {r["id"]: r for r in read_csv(PAINTINGS_DECISIONS)}
    now = datetime.now().isoformat(timespec="seconds")
    for artwork_id in ids:
        if decision:
            decisions[artwork_id] = {"id": artwork_id, "decision": decision, "updated": now}
        else:
            decisions.pop(artwork_id, None)
    with open(PAINTINGS_DECISIONS, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["id", "decision", "updated"])
        w.writeheader()
        w.writerows(decisions.values())


class Handler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_file(self, path, kind):
        data = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "max-age=3600" if kind in ("image/jpeg", "image/webp") else "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        path = self.path.split("?")[0]
        if path in ("/", "/index.html"):
            return self.send_file(HERE / "index.html", "text/html; charset=utf-8")
        if path == "/api/data":
            return self.send_json(build_data())
        if path == "/detect":
            return self.send_file(HERE / "detect.html", "text/html; charset=utf-8")
        if path == "/api/detect":
            return self.send_json(detect_data())
        if path == "/review":
            return self.send_file(HERE / "review.html", "text/html; charset=utf-8")
        if path == "/labels":
            return self.send_file(HERE / "labels.html", "text/html; charset=utf-8")
        if path == "/api/labels":
            return self.send_json(labels_data())
        if path == "/descriptions":
            return self.send_file(HERE / "descriptions.html", "text/html; charset=utf-8")
        m = re.fullmatch(r"/descriptions/([\w-]+)\.md", path)
        if m and (ROOT / "descriptions" / f"{m.group(1)}.md").exists():
            return self.send_file(ROOT / "descriptions" / f"{m.group(1)}.md", "text/plain; charset=utf-8")
        if path == "/cutouts":
            return self.send_file(HERE / "cutouts.html", "text/html; charset=utf-8")
        if path == "/api/cutouts":
            return self.send_json(cutouts_data())
        m = re.fullmatch(r"/cutout/(\d+_\d+)\.png", path)
        if m and (CUTOUT_STICKERS / f"{m.group(1)}.png").exists():
            return self.send_file(CUTOUT_STICKERS / f"{m.group(1)}.png", "image/png")
        if path == "/doors":
            return self.send_file(HERE / "doors.html", "text/html; charset=utf-8")
        if path == "/api/doors":
            return self.send_json(doors_data())
        m = re.fullmatch(r"/stickers/(\d+_\d+(?:_cut)?\.webp)", path)
        if m and (ROOT / "site" / "stickers" / m.group(1)).exists():
            return self.send_file(ROOT / "site" / "stickers" / m.group(1), "image/webp")
        if path == "/starred":
            return self.send_file(HERE / "starred.html", "text/html; charset=utf-8")
        if path == "/api/review":
            return self.send_json(review_data())
        m = re.fullmatch(r"/images1600/(\d+)\.jpg", path)
        if m and (ROOT / "runs" / "images_1600" / f"{m.group(1)}.jpg").exists():
            return self.send_file(ROOT / "runs" / "images_1600" / f"{m.group(1)}.jpg", "image/jpeg")
        if path == "/paintings":
            return self.send_file(HERE / "paintings.html", "text/html; charset=utf-8")
        if path == "/api/paintings":
            return self.send_json(paintings_data())
        m = re.fullmatch(r"/images/(\d+)\.jpg", path)
        if m and (IMAGES / f"{m.group(1)}.jpg").exists():
            return self.send_file(IMAGES / f"{m.group(1)}.jpg", "image/jpeg")
        self.send_error(404)

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        if self.path == "/api/paintings/decision":
            ids = [str(i) for i in body.get("ids", [])]
            decision = body.get("decision", "")
            if not ids or not all(i.isdigit() for i in ids) or decision not in ("", "keep", "reject"):
                return self.send_json({"error": "bad request"}, 400)
            save_paintings_decisions(ids, decision)
            return self.send_json({"ok": True})
        if self.path == "/api/review/artwork":
            ids = [str(i) for i in body.get("ids", [])]
            decision = body.get("decision", "")
            if not ids or not all(i.isdigit() for i in ids) or decision not in ("", "keep", "reject"):
                return self.send_json({"error": "bad request"}, 400)
            save_review_artworks(ids, decision)
            return self.send_json({"ok": True})
        if self.path == "/api/review/item":
            keys = [str(k) for k in body.get("keys", [])]
            field, value = body.get("field"), body.get("value")
            if not keys or not all(re.fullmatch(r"\d+:\d+", k) for k in keys) or field not in ("dropped", "starred", "new_label", "quarantine") \
                    or not (value in ("", "yes", "no") if field == "quarantine" else isinstance(value, bool) if field != "new_label"
                            else isinstance(value, str) and len(value) <= 80):
                return self.send_json({"error": "bad request"}, 400)
            save_review_items(keys, field, value)
            return self.send_json({"ok": True})
        if self.path == "/api/doors":
            key, picked = str(body.get("key", "")), body.get("picked")
            if not re.fullmatch(r"\d+#\d+", key) or not isinstance(picked, bool):
                return self.send_json({"error": "bad request"}, 400)
            save_door(key, picked)
            return self.send_json({"ok": True, "doors": [r["key"] for r in read_doors()]})
        if self.path == "/api/cutouts":
            keys, field, value = [str(k) for k in body.get("keys", [])], body.get("field", "verdict"), body.get("value")
            if not keys or not all(re.fullmatch(r"\d+#\d+", k) for k in keys) or field not in ("verdict", "note") \
                    or not (value in CUTOUT_VERDICTS if field == "verdict" else isinstance(value, str) and len(value) <= 1000):
                return self.send_json({"error": "bad request"}, 400)
            save_cutout_review(keys, field, value.strip())
            return self.send_json({"ok": True})
        if self.path == "/api/labels":
            labels, field, value = body.get("labels", []), body.get("field"), body.get("value", "")
            if not labels or not all(isinstance(l, str) and 0 < len(l) <= 120 for l in labels) or field not in ("canonical", "category") \
                    or not isinstance(value, str) or len(value) > 60:
                return self.send_json({"error": "bad request"}, 400)
            save_label_overrides(labels, field, value.strip())
            return self.send_json({"ok": True})
        if self.path != "/api/decision":
            return self.send_error(404)
        artwork_id = str(body.pop("id", ""))
        update = {k: v for k, v in body.items() if k in DECISION_FIELDS}
        if not artwork_id.isdigit() or not valid(update):
            return self.send_json({"error": "bad request"}, 400)
        save_decision(artwork_id, update)
        self.send_json({"ok": True})


class Server(ThreadingHTTPServer):
    request_queue_size = 128


def main():
    public_domain_records()
    server = Server(("127.0.0.1", PORT), Handler)
    url = f"http://localhost:{PORT}"
    print(f"Candidate browser at {url} (Ctrl+C to stop)")
    if "--no-open" not in sys.argv:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()

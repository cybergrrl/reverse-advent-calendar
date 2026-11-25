const ALBUM_KEY = "album:v1";
const MIN_SCALE = 0.4;
const MAX_SCALE = 3.5;
const NUDGE = 1;
const $ = id => document.getElementById(id);
const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

const store = {
  get(key) { try { return localStorage.getItem(key); } catch { return null; } },
  set(key, value) { try { localStorage.setItem(key, value); } catch {} },
  keys() { try { return Object.keys(localStorage); } catch { return []; } },
};

let data, items = new Map(), placed = {}, selected = null, topZ = 1;

function loadPlaced() {
  try { placed = JSON.parse(store.get(ALBUM_KEY) || "{}").placed || {}; } catch { placed = {}; }
  topZ = Math.max(1, ...Object.values(placed).map(p => p.z || 1));
}

const save = () => store.set(ALBUM_KEY, JSON.stringify({ placed }));
const announce = text => { $("announce").textContent = ""; setTimeout(() => $("announce").textContent = text, 50); };
const captionOf = key => data.paintings[items.get(key).painting].caption;
const nameOf = key => { const i = items.get(key); return `${i.label}, from ${data.paintings[i.painting].title}`; };

function collected() {
  return store.keys().filter(k => k.startsWith("opened:")).map(k => k.slice(7)).filter(k => items.get(k)?.sticker);
}

function renderTray() {
  const keys = collected();
  const loose = keys.filter(k => !placed[k]);
  $("count").textContent = keys.length ? `(${keys.length})` : "";
  $("tray").innerHTML = loose.map(k => `<button class="tray-item" data-key="${esc(k)}" title="${esc(captionOf(k))}" aria-label="${esc(nameOf(k))}. Click or press Enter to hang it on the tree, or drag it to a spot.">
      <img src="${esc(items.get(k).sticker)}" alt=""></button>`).join("");
  $("emptyTray").hidden = keys.length > 0;
  const captions = [...new Set(keys.filter(k => items.get(k)).map(captionOf))].sort();
  $("credits").innerHTML = captions.map(c => `<li>${esc(c)}</li>`).join("");
  $("creditsBox").hidden = !captions.length;
}

function renderBoard() {
  document.querySelectorAll(".ornament").forEach(el => el.remove());
  Object.entries(placed).forEach(([key, p]) => { if (items.get(key)?.sticker) $("board").appendChild(makeOrnament(key, p)); });
}

function makeOrnament(key, p) {
  const el = document.createElement("button");
  el.className = "ornament";
  el.dataset.key = key;
  el.setAttribute("aria-label", `${nameOf(key)}, on the tree`);
  el.innerHTML = `<img src="${esc(items.get(key).sticker)}" alt=""><span class="handle" aria-hidden="true"></span>`;
  position(el, p);
  return el;
}

function position(el, p) {
  el.style.left = `${p.x}%`;
  el.style.top = `${p.y}%`;
  el.style.zIndex = p.z;
  el.style.setProperty("--s", p.s);
  el.style.setProperty("--r", `${p.r}deg`);
}

const ornamentEl = key => document.querySelector(`.ornament[data-key="${CSS.escape(key)}"]`);

function update(key, change) {
  const p = Object.assign(placed[key], change);
  p.s = Math.min(MAX_SCALE, Math.max(MIN_SCALE, p.s));
  p.x = Math.min(100, Math.max(0, p.x));
  p.y = Math.min(100, Math.max(0, p.y));
  position(ornamentEl(key), p);
  save();
}

function select(key) {
  selected = key;
  document.querySelectorAll(".ornament").forEach(el => el.classList.toggle("selected", el.dataset.key === key));
  $("tools").hidden = !key;
  if (key) { $("selName").textContent = nameOf(key); $("selCaption").textContent = captionOf(key); }
}

function hang(key, x, y) {
  placed[key] = { x, y, s: 1, r: Math.round(Math.random() * 16 - 8), z: ++topZ };
  save();
  $("board").appendChild(makeOrnament(key, placed[key]));
  renderTray();
  select(key);
  announce(`${items.get(key).label} hung on the tree`);
  return ornamentEl(key);
}

function unhang(key) {
  delete placed[key];
  save();
  ornamentEl(key)?.remove();
  if (selected === key) select(null);
  renderTray();
  announce(`${items.get(key).label} returned to the tray`);
}

function boardPoint(e) {
  const r = $("board").getBoundingClientRect();
  return { x: ((e.clientX - r.left) / r.width) * 100, y: ((e.clientY - r.top) / r.height) * 100, inside:
    e.clientX >= r.left && e.clientX <= r.right && e.clientY >= r.top && e.clientY <= r.bottom };
}

function dragOrnament(el, e, fromTray) {
  const key = el.dataset.key;
  const start = boardPoint(e), origin = { ...placed[key] };
  try { el.setPointerCapture(e.pointerId); } catch {}
  el.classList.add("dragging");
  const move = ev => {
    const pt = boardPoint(ev);
    update(key, fromTray ? { x: pt.x, y: pt.y } : { x: origin.x + pt.x - start.x, y: origin.y + pt.y - start.y });
    $("board").classList.toggle("drop-target", fromTray);
  };
  const up = ev => {
    el.removeEventListener("pointermove", move);
    el.removeEventListener("pointerup", up);
    el.removeEventListener("pointercancel", up);
    el.classList.remove("dragging");
    $("board").classList.remove("drop-target");
    if (fromTray && !boardPoint(ev).inside) unhang(key);
  };
  el.addEventListener("pointermove", move);
  el.addEventListener("pointerup", up);
  el.addEventListener("pointercancel", up);
}

function dragHandle(el, e) {
  const key = el.dataset.key, p = placed[key];
  const r = el.getBoundingClientRect();
  const cx = r.left + r.width / 2, cy = r.top + r.height / 2;
  const startDist = Math.hypot(e.clientX - cx, e.clientY - cy) || 1;
  const startAngle = Math.atan2(e.clientY - cy, e.clientX - cx);
  const origin = { s: p.s, r: p.r };
  const target = e.target;
  try { target.setPointerCapture(e.pointerId); } catch {}
  const move = ev => {
    const dist = Math.hypot(ev.clientX - cx, ev.clientY - cy);
    const angle = Math.atan2(ev.clientY - cy, ev.clientX - cx);
    update(key, { s: origin.s * dist / startDist, r: Math.round(origin.r + (angle - startAngle) * 180 / Math.PI) });
  };
  const up = () => {
    target.removeEventListener("pointermove", move);
    target.removeEventListener("pointerup", up);
    target.removeEventListener("pointercancel", up);
  };
  target.addEventListener("pointermove", move);
  target.addEventListener("pointerup", up);
  target.addEventListener("pointercancel", up);
}

function act(action, key = selected) {
  if (!key || !placed[key]) return;
  const p = placed[key];
  const actions = {
    smaller: () => update(key, { s: p.s / 1.15 }), bigger: () => update(key, { s: p.s * 1.15 }),
    left: () => update(key, { r: p.r - 10 }), right: () => update(key, { r: p.r + 10 }),
    up: () => update(key, { y: p.y - 2 }), down: () => update(key, { y: p.y + 2 }),
    moveLeft: () => update(key, { x: p.x - 2 }), moveRight: () => update(key, { x: p.x + 2 }),
    tray: () => unhang(key),
  };
  actions[action]?.();
}

function setup() {
  $("tray").addEventListener("pointerdown", e => {
    const item = e.target.closest(".tray-item");
    if (!item || e.button > 0) return;
    e.preventDefault();
    const key = item.dataset.key, start = { x: e.clientX, y: e.clientY };
    let dragging = false;
    const move = ev => {
      if (!dragging && Math.hypot(ev.clientX - start.x, ev.clientY - start.y) < 6) return;
      const pt = boardPoint(ev);
      if (!dragging) { dragging = true; hang(key, pt.x, pt.y); ornamentEl(key).classList.add("dragging"); }
      update(key, { x: pt.x, y: pt.y });
      $("board").classList.add("drop-target");
    };
    const up = ev => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
      window.removeEventListener("pointercancel", up);
      $("board").classList.remove("drop-target");
      if (!dragging) {
        hang(key, 30 + Math.random() * 40, 25 + Math.random() * 50);
        if (window.matchMedia("(max-width: 860px)").matches) $("board").scrollIntoView({ behavior: "smooth", block: "start" });
        return;
      }
      ornamentEl(key)?.classList.remove("dragging");
      if (!boardPoint(ev).inside) unhang(key);
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
    window.addEventListener("pointercancel", up);
  });
  $("tray").addEventListener("keydown", e => {
    const item = e.target.closest(".tray-item");
    if (!item || (e.key !== "Enter" && e.key !== " ")) return;
    e.preventDefault();
    const el = hang(item.dataset.key, 35 + Math.random() * 30, 30 + Math.random() * 45);
    el.focus();
  });
  $("board").addEventListener("pointerdown", e => {
    const el = e.target.closest(".ornament");
    if (!el) return select(null);
    e.preventDefault();
    select(el.dataset.key);
    update(el.dataset.key, { z: ++topZ });
    if (e.target.classList.contains("handle")) dragHandle(el, e);
    else dragOrnament(el, e, false);
  });
  $("board").addEventListener("focusin", e => { const el = e.target.closest(".ornament"); if (el) select(el.dataset.key); });
  $("board").addEventListener("wheel", e => {
    const el = e.target.closest(".ornament");
    if (!el) return;
    e.preventDefault();
    const p = placed[el.dataset.key];
    if (e.shiftKey) update(el.dataset.key, { r: p.r + Math.sign(e.deltaY) * 5 });
    else update(el.dataset.key, { s: p.s * Math.exp(-e.deltaY * 0.0015) });
  }, { passive: false });
  $("board").addEventListener("keydown", e => {
    const el = e.target.closest(".ornament");
    if (!el) return;
    const key = el.dataset.key, p = placed[key];
    const moves = { ArrowLeft: [-NUDGE, 0], ArrowRight: [NUDGE, 0], ArrowUp: [0, -NUDGE], ArrowDown: [0, NUDGE] };
    if (moves[e.key]) { e.preventDefault(); update(key, { x: p.x + moves[e.key][0], y: p.y + moves[e.key][1] }); }
    else if (e.key === "+" || e.key === "=") act("bigger", key);
    else if (e.key === "-") act("smaller", key);
    else if (e.key === "[") act("left", key);
    else if (e.key === "]") act("right", key);
    else if (e.key === "Delete" || e.key === "Backspace") { e.preventDefault(); act("tray", key); }
  });
  $("tools").addEventListener("click", e => { const b = e.target.closest("[data-act]"); if (b) act(b.dataset.act); });
  $("clear").addEventListener("click", () => {
    if (!Object.keys(placed).length || !confirm("Take all stickers off the tree and put them back in the tray?")) return;
    placed = {};
    save();
    renderBoard();
    renderTray();
    select(null);
  });
}

function fitBoardToTree() {
  const tree = $("tree");
  const apply = () => { if (tree.naturalWidth) $("board").style.setProperty("--ratio", tree.naturalWidth / tree.naturalHeight); };
  if (tree.complete) apply();
  tree.addEventListener("load", apply);
}

async function start() {
  fitBoardToTree();
  data = await (await fetch("data/calendar.json")).json();
  data.items.forEach(i => items.set(i.key, i));
  loadPlaced();
  renderBoard();
  renderTray();
  setup();
}

start();

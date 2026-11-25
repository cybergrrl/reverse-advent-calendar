const DOORS = 25;
const MAX_ZOOM = 6;
const PAN_STEP = 80;
const $ = id => document.getElementById(id);
const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");

const SOURCE_NOTES = {
  aic: "Text from the Art Institute of Chicago.",
  ai: "AI-written: this description was written by Claude (Anthropic) from the image and the museum's catalogue record, not by the Art Institute of Chicago.",
};

const KEYWORDS = {
  "Christ Child": ["Christ", "Jesus", "infant", "baby", "child", "Christ Child"],
  "Virgin Mary": ["Virgin", "Mary", "Madonna"],
  "Mary": ["Virgin", "Mary", "Madonna"],
  "Joseph": ["Joseph"],
  "wise man": ["Magi", "king", "kings", "Magus", "wise men", "wise man"],
  "gifts of the Magi": ["gift", "gifts", "gold", "frankincense", "myrrh"],
  "Saint Joseph": ["Joseph"],
  "Saint Nicholas": ["Nicholas", "bishop"],
  "Magi": ["Magi", "king", "kings", "Magus", "wise men"],
  "gift of the Magi": ["gift", "gifts", "gold", "frankincense", "myrrh", "vessel"],
  "God the Father": ["God the Father", "God"],
  "Holy Ghost": ["Holy Ghost", "Holy Spirit", "dove"],
  "Madonna and Child": ["Virgin", "Madonna", "Child"],
  "angel": ["angel", "angels", "cherub", "cherubs", "putti", "putto"],
  "shepherd": ["shepherd", "shepherds"],
  "ox": ["ox", "oxen", "cattle"],
  "sheep": ["sheep", "lamb", "lambs", "flock"],
  "donkey": ["donkey", "ass"],
  "manger": ["manger", "crib", "straw"],
  "stable": ["stable", "shed", "barn", "ruin"],
  "star": ["star", "light"],
  "skater": ["skater", "skaters", "skating", "ice"],
  "sledge": ["sledge", "sledges", "sled", "sleigh"],
  "sleigh": ["sleigh", "sledge", "sled"],
  "snow": ["snow", "snowy", "winter"],
  "frozen river or lake": ["frozen", "ice", "river", "canal", "lake"],
  "glass": ["glass", "glasses", "roemer", "wine"],
  "wine": ["wine", "glass", "jug"],
  "goblet": ["goblet", "cup"],
  "other fruit": ["fruit", "fruits"],
  "fruit basket": ["basket", "fruit"],
  "red clothing": ["red", "cloak", "coat", "robe"],
  "fur": ["fur", "furs", "ermine"],
  "music": ["music", "musician", "instrument", "instruments"],
  "sheet music": ["music", "score", "song"],
  "singers": ["sing", "singer", "singers", "singing"],
  "conifer": ["fir", "pine", "tree", "trees"],
  "tree": ["tree", "trees"],
  "candle": ["candle", "candles", "candlelight"],
  "lantern": ["lantern", "lamp"],
  "garland": ["garland", "garlands", "festoon"],
  "wreath": ["wreath", "wreaths", "laurel"],
};

const store = {
  get(key) { try { return localStorage.getItem(key); } catch { return null; } },
  set(key, value) { try { localStorage.setItem(key, value); } catch {} },
  keys() { try { return Object.keys(localStorage); } catch { return []; } },
};

let data, byPainting = new Map(), current = null, opener = null, pending = false, moved = false;
const preloaded = new Map();
let focused = null;

function preload(item) {
  const src = item && data.paintings[item.painting].image;
  if (!src || preloaded.has(src)) return;
  const img = new Image();
  img.decoding = "async";
  img.src = src;
  preloaded.set(src, img);
}

function preloadDoors() {
  const queue = [...document.querySelectorAll(".door")].map(d => data.items.find(i => i.key === d.dataset.key));
  const idle = window.requestIdleCallback || (fn => setTimeout(fn, 200));
  const next = () => { if (queue.length) { preload(queue.shift()); idle(next); } };
  idle(next);
}
const view = { scale: 1, x: 0, y: 0, w: 0, h: 0 };

function shuffle(list, rand) {
  const a = [...list];
  for (let i = a.length - 1; i > 0; i--) { const j = Math.floor(rand() * (i + 1)); [a[i], a[j]] = [a[j], a[i]]; }
  return a;
}

function retryImage(img) {
  if (img.dataset.retried) return;
  img.dataset.retried = "1";
  setTimeout(() => { img.src = img.src.split("?")[0] + "?retry=1"; }, 400);
}

const titleOf = item => data.paintings[item.painting].title;
const announce = text => { $("announce").textContent = ""; setTimeout(() => $("announce").textContent = text, 50); };

const CALENDAR = "";

function dealDoors(theme, keep = []) {
  const pool = data.items.filter(i => i.sticker && !keep.includes(i));
  const ranked = shuffle(pool, Math.random).sort((a, b) => (b.star - a.star) || (a.flag - b.flag));
  const chosen = [...keep], usedPaintings = new Set(keep.map(i => i.painting));
  for (const i of ranked) if (chosen.length < DOORS && !usedPaintings.has(i.painting)) { chosen.push(i); usedPaintings.add(i.painting); }
  for (const i of ranked) if (chosen.length < DOORS && !chosen.includes(i)) chosen.push(i);
  return keep.length ? chosen : shuffle(chosen, Math.random);
}

function pickDoors(theme, fresh = false) {
  const byKey = new Map(data.items.map(i => [i.key, i]));
  const picked = (data.doors || []).map(k => byKey.get(k)).filter(i => i?.sticker);
  if (picked.length) return picked.length < DOORS ? dealDoors(theme, picked) : picked.slice(0, DOORS);
  let saved = [];
  try { saved = JSON.parse(store.get(`calendar:${theme}`) || "[]").map(k => byKey.get(k)).filter(i => i?.sticker); } catch {}
  const started = store.get(`started:${theme}`);
  const doors = started && saved.length ? (saved.length < DOORS ? dealDoors(theme, saved) : saved)
    : !fresh && saved.length === DOORS ? saved : dealDoors(theme);
  store.set(`calendar:${theme}`, JSON.stringify(doors.map(i => i.key)));
  return doors;
}

function updateAlbumLink() {
  const count = store.keys ? store.keys().filter(k => k.startsWith("opened:")).length : 0;
  $("albumLink").textContent = count ? `My sticker album (${count})` : "My sticker album";
}

const collection = new URLSearchParams(location.search).get("label");
const IRREGULAR = { "wise man": "wise men", man: "men", woman: "women", child: "children", goose: "geese", ox: "oxen", leaf: "leaves", knife: "knives", mouse: "mice", fish: "fish" };
const SAME_PLURAL = new Set(["biscuits", "icicles", "olives", "clothes", "Mary", "Joseph", "lemon slices", "gifts of the Magi", "laundry", "sheep", "Magi", "fur", "gloves", "glass", "wine", "music", "sheet music", "snow", "bread", "cheese", "ham", "red clothing", "other fruit", "apples", "oranges", "grapes", "nuts", "pears", "berries", "plums", "quinces", "oysters", "cards", "singers", "poultry", "frozen river or lake", "Christ Child", "Virgin Mary", "Saint Joseph", "Saint Nicholas", "God the Father", "Holy Ghost", "Madonna and Child"]);
const plural = label => SAME_PLURAL.has(label) ? label : IRREGULAR[label] ? IRREGULAR[label]
  : /(s|sh|ch|x)$/.test(label) ? `${label}es` : /[^aeiou]y$/.test(label) ? `${label.slice(0, -1)}ies` : `${label}s`;
const collectionLink = label => `index.html?label=${encodeURIComponent(label)}`;

function renderCollection() {
  const items = data.items.filter(i => i.sticker && i.label === collection)
    .sort((a, b) => titleOf(a).localeCompare(titleOf(b)));
  const paintings = new Set(items.map(i => i.painting)).size;
  document.title = `All the ${plural(collection)} – Reverse Advent Calendar`;
  document.querySelector(".top h1").innerHTML = `All the <em>${esc(plural(collection))}</em>`;
  document.querySelector(".top .sub").textContent = items.length
    ? `${items.length} sticker${items.length > 1 ? "s" : ""} from ${paintings} painting${paintings > 1 ? "s" : ""}. Open one to explore the painting it came from.`
    : "There are no stickers with this label yet.";
  $("albumLink").insertAdjacentHTML("beforebegin", `<a class="nav-link" href="index.html">&larr; Back to the calendar</a>`);
  $("calendar").setAttribute("aria-label", `All the ${plural(collection)}`);
  $("calendar").innerHTML = items.map(item => `<button class="door collection-door" data-key="${esc(item.key)}"
      aria-label="${esc(item.label)}, from ${esc(titleOf(item))}">
      <img src="${esc(item.sticker)}" alt="" loading="lazy" onerror="retryImage(this)">
      <span class="door-title" aria-hidden="true">${esc(data.paintings[item.painting].caption)}</span>
    </button>`).join("");
}

function renderCalendar(fresh = false) {
  const doors = pickDoors(CALENDAR, fresh);
  $("calendar").innerHTML = doors.map((item, n) => {
    const opened = store.get(`opened:${item.key}`);
    return `<button class="door${opened ? " opened" : ""}" data-key="${esc(item.key)}" data-day="${n + 1}"
      aria-label="Day ${n + 1}: ${esc(item.label)}, from ${esc(titleOf(item))}${opened ? ", opened" : ""}">
      <span class="num" aria-hidden="true">${n + 1}</span>
      <img src="${esc(item.sticker)}" alt="" loading="lazy" onerror="retryImage(this)">
    </button>`;
  }).join("") || `<p class="empty">No stickers yet.</p>`;
}

let introTimers = [];
const later = (fn, ms) => introTimers.push(setTimeout(fn, ms));

function endIntro() {
  introTimers.forEach(clearTimeout);
  introTimers = [];
  $("flyer").classList.remove("show", "fade");
  $("viewer").classList.add("panel-in");
}

function flyCanvas() {
  const c = $("canvas");
  c.classList.remove("animate");
  c.classList.add("fly");
  c.style.transform = `translate(${view.x}px, ${view.y}px) scale(${view.scale})`;
  c.style.setProperty("--inv", 1 / view.scale);
  later(() => c.classList.remove("fly"), 1300);
}

function alignToRect([x0, y0, x1, y1], rect) {
  const s = $("stage").getBoundingClientRect();
  const bw = (x1 - x0) * view.w, bh = (y1 - y0) * view.h;
  view.scale = Math.max(rect.width, rect.height) * 0.86 / Math.max(bw, bh);
  view.x = rect.left + rect.width / 2 - s.left - (x0 + x1) / 2 * view.w * view.scale;
  view.y = rect.top + rect.height / 2 - s.top - (y0 + y1) / 2 * view.h * view.scale;
  apply(false);
}

function openPainting(item, heading, fromDoor = false, fromRect = null) {
  focused = null;
  $("spotLink").hidden = true;
  const wasOpen = $("viewer").classList.contains("open");
  introTimers.forEach(clearTimeout);
  introTimers = [];
  const flying = fromRect && item.sticker && !reducedMotion.matches;
  if (!$("viewer").classList.contains("open")) opener = document.activeElement;
  current = item;
  const p = data.paintings[item.painting];
  const isNew = fromDoor && !store.get(`opened:${item.key}`);
  if (fromDoor) {
    store.set(`opened:${item.key}`, "1");
    store.set(`started:${CALENDAR}`, "1");
    updateAlbumLink();
    document.querySelector(`.door[data-key="${CSS.escape(item.key)}"]`)?.classList.add("opened");
  }
  $("day").innerHTML = `${esc(heading)}${isNew && item.sticker ? ` &middot; <span class="added">Added to your sticker album</span>` : ""}`;
  $("title").textContent = p.title;
  $("meta").textContent = p.caption;
  $("ngLink").hidden = !p.url;
  if (p.url) $("ngLink").href = p.url;
  renderAbout(p);
  $("viewer").classList.add("open");
  $("viewer").setAttribute("aria-hidden", "false");
  if (!wasOpen) $("viewer").classList.remove("panel-in");
  if (reducedMotion.matches) $("viewer").classList.add("panel-in");
  requestAnimationFrame(() => $("viewer").classList.add("dim"));
  $("stage").classList.toggle("flying", flying);
  if (flying) {
    Object.assign($("flyer").style, { left: `${fromRect.left}px`, top: `${fromRect.top}px`, width: `${fromRect.width}px`, height: `${fromRect.height}px` });
    $("flyer").src = item.sticker;
    $("flyer").classList.remove("fade");
    $("flyer").classList.add("show");
  }
  document.body.classList.add("viewing");
  document.querySelector(".top").inert = true;
  $("calendar").inert = true;
  const img = $("painting");
  img.alt = p.alt || p.title;
  $("placeholder").src = item.sticker || "";
  $("stage").classList.add("loading");
  img.removeAttribute("src");
  $("boxes").innerHTML = "";
  img.onload = () => {
    if (!current) return;
    $("stage").classList.remove("loading");
    view.w = img.naturalWidth; view.h = img.naturalHeight;
    $("canvas").style.width = `${view.w}px`; $("canvas").style.height = `${view.h}px`;
    drawBoxes();
    select(current, false);
    if (flying) {
      alignToRect(current.box, fromRect);
      shade = spotFor(current.box, OPENING_ALPHA);
      drawShade(shade);
      requestAnimationFrame(() => $("flyer").classList.add("fade"));
      later(() => { $("flyer").classList.remove("show", "fade"); fit(false); flyCanvas(); }, 450);
      cancelAnimationFrame(shadeFrame);
      const lit = 450 + 1200 + REVEAL_MS;
      later(() => reveal(current.box, 0), 450 + 1200);
      later(() => $("viewer").classList.add("panel-in"), lit);
    } else {
      fit(false);
      const lit = reveal(current.box);
      if (!$("viewer").classList.contains("panel-in")) later(() => $("viewer").classList.add("panel-in"), lit);
    }
  };
  img.src = p.image;
  renderFound();
  $("more").innerHTML = "";
  $("focus").innerHTML = "";
  $("title").focus();
  document.querySelector(".panel").scrollTop = 0;
}

function renderAbout(p) {
  const paragraphs = text => text.split(/\n\s*\n/).map(t => `<p>${esc(t.trim())}</p>`).join("");
  $("aboutSection").hidden = !p.short && !p.long && !p.visual;
  $("about").innerHTML = paragraphs(p.short || p.long);
  $("about").dataset.expanded = "false";
  $("aboutSource").textContent = SOURCE_NOTES[p.text_source] || "";
  $("aboutSource").className = `source ${p.text_source || ""}`;
  $("readMore").hidden = !p.long || p.long === p.short;
  $("readMore").textContent = "Read more";
  $("readMore").setAttribute("aria-expanded", "false");
  $("describedBox").hidden = !p.visual;
  $("describedBox").open = false;
  $("described").textContent = p.visual;
}

function toggleReadMore() {
  const p = data.paintings[current.painting];
  const expand = $("about").dataset.expanded !== "true";
  const paragraphs = text => text.split(/\n\s*\n/).map(t => `<p>${esc(t.trim())}</p>`).join("");
  $("about").innerHTML = paragraphs(expand ? p.long : (p.short || p.long));
  $("about").dataset.expanded = String(expand);
  $("readMore").textContent = expand ? "Show less" : "Read more";
  $("readMore").setAttribute("aria-expanded", String(expand));
}

function drawBoxes() {
  $("boxes").innerHTML = byPainting.get(current.painting).map(i => {
    const [x0, y0, x1, y1] = i.box;
    return `<button class="hit${i.extra ? " extra" : ""}${i.more ? " more" : ""}" data-key="${esc(i.key)}" aria-label="${esc(i.label)}${i.extra ? ", small detail" : ""}"
      style="left:${x0 * 100}%;top:${y0 * 100}%;width:${(x1 - x0) * 100}%;height:${(y1 - y0) * 100}%">
      <span aria-hidden="true">${esc(i.label)}</span></button>`;
  }).join("");
}

function renderFound() {
  const items = byPainting.get(current.painting);
  const chip = i => `<button class="chip${i.sticker ? "" : " no-pic"}${i.extra ? " extra" : ""}" data-key="${esc(i.key)}">
      ${i.sticker ? `<img src="${esc(i.sticker)}" alt="">` : ""}${esc(i.label)}</button>`;
  const main = items.filter(i => !i.extra), extra = items.filter(i => i.extra && !i.more), more = items.filter(i => i.more);
  const showAll = store.get("showAll") === "1";
  $("stage").classList.toggle("show-all", showAll);
  $("found").innerHTML = main.map(chip).join("")
    + (extra.length ? `<p class="also">Also spotted</p>${extra.map(chip).join("")}` : "")
    + (more.length ? `<button class="all-toggle" id="allToggle" aria-pressed="${showAll}">
        ${showAll ? "Hide" : "Show"} everything the model saw (${more.length})</button>${showAll ? groupedChips(more) : ""}` : "");
}

function groupedChips(items) {
  const groups = new Map();
  items.forEach(i => { if (!groups.has(i.label)) groups.set(i.label, []); groups.get(i.label).push(i.key); });
  return [...groups.entries()].sort((a, b) => b[1].length - a[1].length || a[0].localeCompare(b[0]))
    .map(([label, keys]) => `<button class="chip no-pic extra" data-key="${esc(keys[0])}" data-group="${esc(keys.join("|"))}"
      aria-label="${esc(label)}${keys.length > 1 ? `, ${keys.length} found, press again for the next one` : ""}">
      ${esc(label)}${keys.length > 1 ? ` <span class="times">&times;${keys.length}</span>` : ""}</button>`).join("");
}

function sentencesAbout(item) {
  const p = data.paintings[item.painting];
  const text = p.long || p.short;
  if (!text) return [];
  const words = KEYWORDS[item.label] || [item.label, `${item.label}s`];
  const pattern = new RegExp(`\\b(${words.map(w => w.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("|")})\\b`, "gi");
  const sentences = text.replace(/\s+/g, " ").split(/(?<=[.!?])\s+(?=[A-Z‘“"(])/);
  return sentences.filter(s => { pattern.lastIndex = 0; return pattern.test(s); }).slice(0, 3)
    .map(s => esc(s).replace(pattern, "<mark>$1</mark>"));
}

function renderFocus(item) {
  const quotes = sentencesAbout(item);
  $("focus").innerHTML = `<h3>${esc(item.label)}</h3>
    ${item.reason ? `<p class="note">${esc(item.reason[0].toUpperCase() + item.reason.slice(1))}.</p>` : ""}
    ${quotes.length ? `<div class="says"><p class="says-label">${data.paintings[item.painting].text_source === "ai" ? "What the AI-written description says" : "What the Art Institute says"}</p>
      ${quotes.map(q => `<blockquote>${q}</blockquote>`).join("")}</div>` : ""}`;
}

function select(item, zoom, fromGroup = false) {
  if (zoom && introTimers.length) endIntro();
  if (zoom && !fromGroup && focused === item.key) return showWhole();
  if (zoom) focused = item.key;
  current = item;
  document.querySelectorAll(".hit, .chip").forEach(el => {
    const on = el.dataset.key === item.key;
    el.classList.toggle("current", on);
    el.setAttribute("aria-pressed", String(on));
  });
  if (zoom) { spotlight(item.box); zoomTo(item.box); showSpotLinkSoon(); }
  renderFocus(item);
  renderMore(item);
  announce(`Showing the ${item.label}`);
}

function renderMore(item) {
  const others = [], seen = new Set([item.painting]);
  for (const i of data.items) {
    if (i.label === item.label && i.sticker && !seen.has(i.painting)) { others.push(i); seen.add(i.painting); }
  }
  const total = data.items.filter(i => i.label === item.label && i.sticker).length;
  const picks = others.slice(0, 6);
  $("more").innerHTML = `<h3>Find the ${esc(item.label)} in other paintings</h3>` + (picks.length
    ? `<div class="strip">${picks.map(i => `<button data-more="${esc(i.key)}" aria-label="${esc(i.label)} in ${esc(titleOf(i))}">
        <img src="${esc(i.sticker)}" alt=""><br>${esc(titleOf(i))}</button>`).join("")}</div>`
    : `<p class="none">This is the only one so far.</p>`)
    + (total > 1 ? `<a class="see-all" href="${collectionLink(item.label)}">See all ${total} ${esc(plural(item.label))} &rarr;</a>` : "");
}

const REVEAL_HOLD = 700;
const REVEAL_MS = 2400;
const SPOT_MS = 1000;
const LIFT_MS = 800;
const SHADE_ALPHA = 0.84;
const OPENING_ALPHA = 0.97;
const ease = t => t < .5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
let shadeFrame = 0, shade = null;

function drawShade(s) {
  $("shade").style.background = s
    ? `radial-gradient(circle at ${s.cx}px ${s.cy}px, transparent ${s.r}px, rgba(4, 7, 15, ${s.a}) ${s.r + s.f}px)` : "none";
}

function spotFor([x0, y0, x1, y1], a = SHADE_ALPHA) {
  const diag = Math.hypot((x1 - x0) * view.w, (y1 - y0) * view.h);
  return { cx: (x0 + x1) / 2 * view.w, cy: (y0 + y1) / 2 * view.h, r: diag * 0.52,
    f: Math.max(diag * 0.18, Math.hypot(view.w, view.h) * 0.02), a };
}

function openFor(s) {
  const f = Math.hypot(view.w, view.h) * 0.12;
  const far = Math.max(...[[0, 0], [view.w, 0], [0, view.h], [view.w, view.h]].map(([x, y]) => Math.hypot(x - s.cx, y - s.cy)));
  return { cx: s.cx, cy: s.cy, r: far + f, f, a: s.a };
}

function animateShade(target, ms, hold = 0, clearAtEnd = false) {
  cancelAnimationFrame(shadeFrame);
  if (reducedMotion.matches || !ms) { shade = clearAtEnd ? null : target; drawShade(shade); return; }
  const from = shade || openFor(target);
  const began = performance.now() + hold;
  const step = now => {
    const k = ease(Math.min(1, Math.max(0, (now - began) / ms)));
    shade = Object.fromEntries(Object.keys(target).map(key => [key, from[key] + (target[key] - from[key]) * k]));
    drawShade(shade);
    if (k < 1) shadeFrame = requestAnimationFrame(step);
    else if (clearAtEnd) { shade = null; drawShade(null); }
  };
  shadeFrame = requestAnimationFrame(step);
}

function reveal(box, hold = REVEAL_HOLD) {
  const spot = spotFor(box, OPENING_ALPHA);
  shade = spot;
  drawShade(shade);
  animateShade(openFor(spot), REVEAL_MS, hold, true);
  return hold + REVEAL_MS;
}

function spotlight(box) { animateShade(spotFor(box), SPOT_MS); }

function liftShade() { if (shade) animateShade(openFor(shade), LIFT_MS, 0, true); }

function clearShade() { cancelAnimationFrame(shadeFrame); shade = null; drawShade(null); }

function showWhole() {
  liftShade();
  fit();
  if (!focused) return;
  focused = null;
  $("spotLink").hidden = true;
  document.querySelectorAll(".hit.current, .chip.current").forEach(el => { el.classList.remove("current"); el.setAttribute("aria-pressed", "false"); });
  announce("Showing the whole painting");
}

let spotTimer = 0;

function placeSpotLink() {
  const link = $("spotLink");
  const item = focused && data.items.find(i => i.key === focused);
  const total = item ? data.items.filter(i => i.label === item.label && i.sticker).length : 0;
  if (!item || total < 2) { link.hidden = true; return; }
  const [x0, , x1, y1] = item.box;
  const a = area();
  const x = Math.min(Math.max(view.x + (x0 + x1) / 2 * view.w * view.scale, 120), a.width - 120);
  const y = Math.min(view.y + y1 * view.h * view.scale + 18, a.height - 56);
  link.style.left = `${x}px`;
  link.style.top = `${y}px`;
  link.href = collectionLink(item.label);
  link.innerHTML = `See all ${total} ${esc(plural(item.label))} &rarr;`;
  link.hidden = false;
}

function showSpotLinkSoon() {
  clearTimeout(spotTimer);
  $("spotLink").classList.remove("visible");
  placeSpotLink();
  spotTimer = setTimeout(() => $("spotLink").classList.add("visible"), reducedMotion.matches ? 0 : 950);
}

function apply(animate) {
  const c = $("canvas");
  c.classList.toggle("animate", !!animate && !reducedMotion.matches);
  c.style.transform = `translate(${view.x}px, ${view.y}px) scale(${view.scale})`;
  c.style.setProperty("--inv", 1 / view.scale);
  if (focused) placeSpotLink();
}

function applySoon() {
  if (pending) return;
  pending = true;
  requestAnimationFrame(() => { pending = false; apply(false); });
}

function area() {
  const s = $("stage").getBoundingClientRect(), panel = document.querySelector(".panel");
  const mobile = window.matchMedia("(max-width: 760px)").matches;
  return { width: s.width - (mobile ? 0 : panel.offsetWidth), height: s.height - (mobile ? panel.offsetHeight : 0) };
}

function fitScale() {
  const s = area();
  return Math.min(s.width / view.w, s.height / view.h) * 0.94;
}

function fit(animate = true) {
  const s = area();
  view.scale = fitScale();
  view.x = (s.width - view.w * view.scale) / 2;
  view.y = (s.height - view.h * view.scale) / 2;
  apply(animate);
}

function zoomTo([x0, y0, x1, y1]) {
  const s = area();
  const bw = (x1 - x0) * view.w, bh = (y1 - y0) * view.h;
  view.scale = Math.min(s.width / (bw * 2.3), s.height / (bh * 2.3), fitScale() * MAX_ZOOM);
  view.scale = Math.max(view.scale, fitScale());
  view.x = s.width / 2 - ((x0 + x1) / 2) * view.w * view.scale;
  view.y = s.height / 2 - ((y0 + y1) / 2) * view.h * view.scale;
  keepInView(s);
  apply(true);
}

function keepInView(s) {
  const pw = view.w * view.scale, ph = view.h * view.scale;
  view.x = pw <= s.width ? (s.width - pw) / 2 : Math.min(0, Math.max(s.width - pw, view.x));
  view.y = ph <= s.height ? (s.height - ph) / 2 : Math.min(0, Math.max(s.height - ph, view.y));
}

function zoomAt(factor, cx, cy) {
  const next = Math.min(Math.max(view.scale * factor, fitScale() * 0.6), fitScale() * MAX_ZOOM);
  view.x = cx - (cx - view.x) * (next / view.scale);
  view.y = cy - (cy - view.y) * (next / view.scale);
  view.scale = next;
  applySoon();
}

function zoomCentre(factor) {
  const r = area();
  zoomAt(factor, r.width / 2, r.height / 2);
}

function setupStage() {
  const stage = $("stage"), pointers = new Map();
  let last = null, pinch = 0;
  stage.addEventListener("wheel", e => {
    e.preventDefault();
    const r = stage.getBoundingClientRect();
    zoomAt(Math.exp(-e.deltaY * 0.0015), e.clientX - r.left, e.clientY - r.top);
  }, { passive: false });
  stage.addEventListener("pointerdown", e => {
    if (e.target.closest(".zoom-controls")) return;
    pointers.set(e.pointerId, e); moved = false;
    last = { x: e.clientX, y: e.clientY }; stage.classList.add("dragging");
  });
  stage.addEventListener("pointermove", e => {
    if (!pointers.has(e.pointerId)) return;
    pointers.set(e.pointerId, e);
    if (pointers.size === 2) {
      const [a, b] = [...pointers.values()];
      const dist = Math.hypot(a.clientX - b.clientX, a.clientY - b.clientY);
      const r = stage.getBoundingClientRect();
      if (pinch) zoomAt(dist / pinch, (a.clientX + b.clientX) / 2 - r.left, (a.clientY + b.clientY) / 2 - r.top);
      pinch = dist; moved = true;
      return;
    }
    const dx = e.clientX - last.x, dy = e.clientY - last.y;
    if (Math.abs(dx) + Math.abs(dy) > 3) moved = true;
    view.x += dx; view.y += dy; last = { x: e.clientX, y: e.clientY };
    applySoon();
  });
  const end = e => {
    pointers.delete(e.pointerId);
    if (pointers.size < 2) pinch = 0;
    if (!pointers.size) stage.classList.remove("dragging");
    if (pointers.size === 1) { const p = [...pointers.values()][0]; last = { x: p.clientX, y: p.clientY }; }
  };
  ["pointerup", "pointercancel", "pointerleave"].forEach(t => stage.addEventListener(t, end));
  stage.addEventListener("click", e => {
    const hit = e.target.closest(".hit");
    if (hit && !moved) select(data.items.find(i => i.key === hit.dataset.key), true);
  });
  stage.addEventListener("dblclick", e => { if (!e.target.closest(".zoom-controls")) showWhole(); });
  $("zoomIn").addEventListener("click", e => { e.stopPropagation(); zoomCentre(1.5); });
  $("zoomOut").addEventListener("click", e => { e.stopPropagation(); zoomCentre(1 / 1.5); });
  $("zoomReset").addEventListener("click", e => { e.stopPropagation(); showWhole(); });
}

function viewerKeys(e) {
  if (e.key === "Escape") { e.preventDefault(); return close(); }
  if (e.key === "Tab") return trapFocus(e);
  if (e.target.matches("input, select, textarea, summary")) return;
  if (e.key === "Enter" || e.key === " ") moved = false;
  const keys = { "+": () => zoomCentre(1.4), "=": () => zoomCentre(1.4), "-": () => zoomCentre(1 / 1.4), "0": () => showWhole(),
    ArrowLeft: () => { view.x += PAN_STEP; applySoon(); }, ArrowRight: () => { view.x -= PAN_STEP; applySoon(); },
    ArrowUp: () => { view.y += PAN_STEP; applySoon(); }, ArrowDown: () => { view.y -= PAN_STEP; applySoon(); } };
  if (keys[e.key] && (!e.key.startsWith("Arrow") || e.target.closest(".stage"))) { e.preventDefault(); keys[e.key](); }
}

function trapFocus(e) {
  const focusable = [...$("viewer").querySelectorAll("button, [href], summary, [tabindex]:not([tabindex='-1'])")]
    .filter(el => !el.hidden && !el.closest("[hidden]") && el.offsetParent !== null);
  if (!focusable.length) return;
  const first = focusable[0], last = focusable[focusable.length - 1];
  if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
  else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
}

function close() {
  clearShade();
  introTimers.forEach(clearTimeout);
  introTimers = [];
  $("flyer").classList.remove("show", "fade");
  $("viewer").classList.remove("dim", "panel-in");
  $("viewer").classList.remove("open");
  $("viewer").setAttribute("aria-hidden", "true");
  document.body.classList.remove("viewing");
  document.querySelector(".top").inert = false;
  $("calendar").inert = false;
  current = null;
  const door = opener?.classList?.contains("door") && document.contains(opener) ? opener : null;
  if (door) {
    const label = door.getAttribute("aria-label") || "";
    if (!label.endsWith(", opened")) door.setAttribute("aria-label", `${label}, opened`);
    door.focus();
  }
}

async function start() {
  data = await (await fetch("data/calendar.json")).json();
  data.items.forEach(i => { if (!byPainting.has(i.painting)) byPainting.set(i.painting, []); byPainting.get(i.painting).push(i); });
  if (collection) renderCollection(); else renderCalendar();
  updateAlbumLink();
  preloadDoors();
  setupStage();
  const warm = e => { const door = e.target.closest(".door"); if (door) preload(data.items.find(i => i.key === door.dataset.key)); };
  $("calendar").addEventListener("pointerover", warm);
  $("calendar").addEventListener("focusin", warm);
  $("more").addEventListener("pointerover", e => { const b = e.target.closest("[data-more]"); if (b) preload(data.items.find(i => i.key === b.dataset.more)); });
  $("calendar").addEventListener("click", e => {
    const door = e.target.closest(".door");
    if (!door) return;
    const item = data.items.find(i => i.key === door.dataset.key);
    const rect = door.querySelector("img")?.getBoundingClientRect();
    if (collection) openPainting(item, `All the ${plural(item.label)}`, false, rect);
    else openPainting(item, `Day ${door.dataset.day}`, true, rect);
  });
  $("found").addEventListener("click", e => {
    if (e.target.closest("#allToggle")) {
      store.set("showAll", store.get("showAll") === "1" ? "0" : "1");
      renderFound();
      if (current) document.querySelectorAll(".chip").forEach(el => el.classList.toggle("current", el.dataset.key === current.key));
      return;
    }
    const chip = e.target.closest(".chip");
    if (!chip) return;
    if (chip.dataset.group) {
      const keys = chip.dataset.group.split("|");
      const at = chip.classList.contains("current") ? keys.indexOf(focused) : -1;
      if (at === keys.length - 1) return showWhole();
      const next = keys[at + 1];
      select(data.items.find(i => i.key === next), true, true);
      chip.classList.add("current");
      return;
    }
    select(data.items.find(i => i.key === chip.dataset.key), true);
  });
  $("more").addEventListener("click", e => {
    const b = e.target.closest("[data-more]");
    if (b) { const item = data.items.find(i => i.key === b.dataset.more); openPainting(item, `Another ${item.label}`); }
  });
  $("readMore").addEventListener("click", toggleReadMore);
  $("close").addEventListener("click", close);
  $("viewer").addEventListener("keydown", viewerKeys);
  window.addEventListener("resize", () => { if (current) fit(false); });
  const linked = decodeURIComponent((location.hash.match(/item=([^&]+)/) || [])[1] || "");
  const linkedItem = linked && data.items.find(i => i.key === linked);
  if (linkedItem) openPainting(linkedItem, "From a postcard");
}

start();

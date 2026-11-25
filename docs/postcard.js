const TREE = "tree.jpg";
const ALBUM_KEY = "album:v1";
const DRAFT_KEY = "postcard:draft";
const DEFAULT_MESSAGE = "I decorated this Christmas tree for you with items from the Art Institute of Chicago. Check them out to find cool paintings!";
const $ = id => document.getElementById(id);
const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

const store = {
  get(key) { try { return localStorage.getItem(key); } catch { return null; } },
  set(key, value) { try { localStorage.setItem(key, value); } catch {} },
};

let data, items = new Map(), card = null, activeKey = null;

function encodeCard(state) {
  const bytes = new TextEncoder().encode(JSON.stringify(state));
  let binary = "";
  bytes.forEach(b => binary += String.fromCharCode(b));
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

function decodeCard(text) {
  const binary = atob(text.replace(/-/g, "+").replace(/_/g, "/"));
  return JSON.parse(new TextDecoder().decode(Uint8Array.from(binary, c => c.charCodeAt(0))));
}

function cardFromAlbum() {
  let placed = {};
  try { placed = JSON.parse(store.get(ALBUM_KEY) || "{}").placed || {}; } catch {}
  const ornaments = Object.entries(placed).filter(([key]) => items.get(key)?.sticker)
    .sort((a, b) => (a[1].z || 0) - (b[1].z || 0))
    .map(([key, p]) => [key, +p.x.toFixed(1), +p.y.toFixed(1), +p.s.toFixed(2), Math.round(p.r)]);
  let draft = {};
  try { draft = JSON.parse(store.get(DRAFT_KEY) || "{}"); } catch {}
  const msg = typeof draft.msg === "string" ? draft.msg : DEFAULT_MESSAGE;
  return { v: 1, t: TREE, o: ornaments, to: draft.to || "", msg, from: draft.from || "" };
}

function renderFront() {
  document.querySelectorAll("#board .ornament").forEach(el => el.remove());
  card.o.forEach(([key, x, y, s, r], n) => {
    const item = items.get(key);
    if (!item?.sticker) return;
    const el = document.createElement("button");
    el.className = "ornament";
    el.dataset.key = key;
    el.tabIndex = document.body.classList.contains("reading") ? 0 : -1;
    el.setAttribute("aria-label", `${item.label}, from ${data.paintings[item.painting].title}`);
    el.innerHTML = `<img src="${esc(item.sticker)}" alt="">`;
    Object.assign(el.style, { left: `${x}%`, top: `${y}%`, zIndex: n + 1 });
    el.style.setProperty("--s", s);
    el.style.setProperty("--r", `${r}deg`);
    $("board").appendChild(el);
  });
  const captions = [...new Set(card.o.map(([key]) => items.get(key)).filter(i => i?.sticker).map(i => data.paintings[i.painting].caption))].sort();
  $("credits").innerHTML = captions.map(c => `<li>${esc(c)}</li>`).join("");
  $("creditsBox").hidden = !captions.length;
  const stampKey = [...card.o].sort((a, b) => b[3] - a[3])[0]?.[0];
  $("stamp").src = stampKey ? items.get(stampKey).sticker : "";
}

function setTree() {
  const tree = $("tree");
  tree.addEventListener("load", () => $("postcard").style.setProperty("--ratio", tree.naturalWidth / tree.naturalHeight));
  tree.src = card.t || TREE;
}

const canShare = () => typeof navigator.share === "function" && matchMedia("(pointer: coarse)").matches;

function shareDetails(url) {
  const subject = "A Christmas postcard for you";
  const text = `I made you a Christmas postcard, decorated with details from artworks in the Art Institute of Chicago. Open it here:`;
  return { subject, text, url };
}

function emailHref(url) {
  const { subject, text } = shareDetails(url);
  const body = `${card.to ? `${card.to}\n\n` : ""}${text}\n\n${url}${card.from ? `\n\n${card.from}` : ""}`;
  return `mailto:?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;
}

async function sendCard(url) {
  if (canShare()) {
    const { subject, text } = shareDetails(url);
    try { await navigator.share({ title: subject, text, url }); } catch {}
  } else {
    location.href = emailHref(url);
  }
}

function showEditor() {
  document.body.classList.remove("reading");
  $("editor").hidden = false;
  $("reading").hidden = true;
  $("to").value = card.to; $("msg").value = card.msg; $("from").value = card.from;
  const saveDraft = () => store.set(DRAFT_KEY, JSON.stringify({ to: $("to").value, msg: $("msg").value, from: $("from").value }));
  ["to", "msg", "from"].forEach(id => $(id).addEventListener("input", saveDraft));
  $("editor").addEventListener("submit", e => {
    e.preventDefault();
    card = { ...card, to: $("to").value.trim(), msg: $("msg").value.trim(), from: $("from").value.trim() };
    history.pushState(null, "", `#card=${encodeCard(card)}`);
    showReading(true);
    sendCard(location.href);
  });
}

function showReading(justSent) {
  document.body.classList.add("reading");
  $("editor").hidden = true;
  $("reading").hidden = false;
  $("toText").textContent = card.to;
  $("msgText").textContent = card.msg;
  $("fromText").textContent = card.from;
  $("cardHint").hidden = false;
  $("heading").textContent = card.to ? `A postcard for you` : "A Christmas postcard";
  $("subheading").textContent = "Every ornament on this tree is a detail from a work in the Art Institute of Chicago. Click one to find out more.";
  $("sentBanner").hidden = !justSent;
  $("backLink").textContent = justSent ? "← Edit the postcard" : "Make your own calendar →";
  $("backLink").href = justSent ? "postcard.html" : "index.html";
  if (justSent) {
    $("cardLink").value = location.href;
    $("emailLink").href = emailHref(location.href);
    $("shareLink").hidden = !canShare();
    window.scrollTo(0, 0);
  }
  renderFront();
}

function showInfo(key) {
  const item = items.get(key), p = data.paintings[item.painting];
  activeKey = key;
  document.querySelectorAll("#board .ornament").forEach(el => el.classList.toggle("active", el.dataset.key === key));
  $("infoSticker").src = item.sticker;
  $("infoLabel").textContent = item.label;
  $("infoTitle").textContent = p.title;
  $("infoMeta").textContent = p.caption;
  $("infoPainting").src = p.image;
  $("infoPainting").alt = p.alt || p.title;
  $("infoNote").textContent = item.reason ? `${item.reason[0].toUpperCase()}${item.reason.slice(1)}.` : "";
  $("infoNote").hidden = !item.reason;
  $("infoAbout").innerHTML = (p.short || "").split(/\n\s*\n/).filter(Boolean).slice(0, 2).map(t => `<p>${esc(t)}</p>`).join("");
  $("infoExplore").href = `index.html#item=${encodeURIComponent(key)}`;
  $("info").hidden = false;
  $("page").classList.add("with-info");
  $("infoTitle").focus();
}

function hideInfo() {
  $("info").hidden = true;
  $("page").classList.remove("with-info");
  document.querySelectorAll("#board .ornament.active").forEach(el => el.classList.remove("active"));
  const back = activeKey && document.querySelector(`#board .ornament[data-key="${CSS.escape(activeKey)}"]`);
  activeKey = null;
  back?.focus();
}

async function start() {
  data = await (await fetch("data/calendar.json")).json();
  data.items.forEach(i => items.set(i.key, i));
  const shared = location.hash.match(/card=([\w-]+)/);
  if (shared) {
    try { card = decodeCard(shared[1]); } catch { card = null; }
    if (!card) { $("page").hidden = true; $("emptyCard").hidden = false; $("emptyCard").textContent = "Sorry, this postcard link is incomplete or damaged."; return; }
  } else {
    card = cardFromAlbum();
  }
  setTree();
  if (!card.o.length) { $("page").hidden = true; $("emptyCard").hidden = false; return; }
  if (shared) showReading(false); else { showEditor(); renderFront(); }

  $("board").addEventListener("click", e => {
    const el = e.target.closest(".ornament");
    if (el && document.body.classList.contains("reading")) showInfo(el.dataset.key);
  });
  $("infoClose").addEventListener("click", hideInfo);
  document.addEventListener("keydown", e => { if (e.key === "Escape" && !$("info").hidden) hideInfo(); });
  $("shareLink").addEventListener("click", () => sendCard($("cardLink").value));
  $("copyLink").addEventListener("click", async () => {
    try { await navigator.clipboard.writeText($("cardLink").value); $("copyLink").textContent = "Copied"; }
    catch { $("cardLink").select(); }
  });
  window.addEventListener("popstate", () => location.reload());
}

start();

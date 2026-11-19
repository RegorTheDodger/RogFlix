/*
 * Everything personal lives in localStorage:
 *
 *   iml:watchlist  [{id, title, cover, url, year}]
 *   iml:progress   {id: {seconds, duration, at, meta}}   resume position
 *   iml:watched    {id: {title, cover, url, year, lang, seconds, finished, at}}
 *   iml:catalog    {id: {title, cover, url, year}}
 *
 * When signed in, this state is merged with the account copy so it follows
 * the person between the modern and Lumia sites.
 *
 * The server renders the catalogue shelves and the billboard. This file only
 * fills the personal shelves and keeps the add buttons in sync.
 */

const LS_LIST = "iml:watchlist";
const LS_PROGRESS = "iml:progress";
const LS_WATCHED = "iml:watched";
const LS_CATALOG = "iml:catalog";
const LS_REMOVED = "iml:removed";
const LS_DROPPED = "iml:dropped";
const PREFS_AT = "iml:prefs-at";

/* A film is finished when the player reports the last couple of minutes,
 * not when it passes a fraction of the duration. These streams often claim a
 * shorter runtime than the film itself, and 95% of that short number can be
 * the middle of the film — which used to delete a live continue-watching card
 * the moment somebody seeked forward. */
const FINISH_LEFT = 90;
/* a title earns a card in continue watching only after this much playback */
const MIN_WATCH = 10;
/* under this many seconds it is not worth remembering */
const MIN_SECONDS = 10;
/* a jump longer than this is a seek, not watching */
const SEEK_LIMIT = 6;
/* a resume stamp this far ahead is a broken clock, not a fresh entry */
const FUTURE_SLACK = 5 * 60 * 1000;

/* ------------------------------------------------------------------ icons */

const SVG_PLAY =
  '<svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor" aria-hidden="true">' +
  '<path d="M8 5v14l11-7z"/></svg>';
const SVG_PLUS =
  '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor"' +
  ' stroke-width="2.2" stroke-linecap="round" aria-hidden="true"><path d="M12 5v14M5 12h14"/></svg>';
const SVG_CHECK =
  '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor"' +
  ' stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
  '<path d="m5 13 4 4L19 7"/></svg>';

/* ------------------------------------------------------------------ store */

function read(key, fallback) {
  try {
    const raw = localStorage.getItem(key);
    return raw ? JSON.parse(raw) : fallback;
  } catch (e) {
    return fallback;
  }
}

function write(key, value) {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch (e) {
    /* private mode or quota */
  }
}

const getList = () => (Array.isArray(read(LS_LIST, [])) ? read(LS_LIST, []) : []);
const getProgress = () => read(LS_PROGRESS, {}) || {};

/* A sync answer, with anything this device wrote while the request was in
 * flight put back on top. The reply describes the state the server was sent,
 * so without this a second saved mid-request is silently dropped and the card
 * vanishes on the next page. */
function keepWrittenDuring(server, local, since) {
  const out = Object.assign({}, server || {});
  Object.keys(local || {}).forEach((id) => {
    const entry = local[id];
    if (!entry || !entry.at || entry.at < since) return;
    const known = out[id];
    if (known && (known.at || 0) >= entry.at) return;
    out[id] = known
      ? Object.assign({}, entry, {
          seconds: Math.max(entry.seconds || 0, known.seconds || 0)
        })
      : entry;
  });
  return out;
}
const getWatched = () => read(LS_WATCHED, {}) || {};
const getCatalog = () => read(LS_CATALOG, {}) || {};
const getRemoved = () => read(LS_REMOVED, {}) || {};
/* removed from continue watching: {id: at}, so a sync cannot bring it back */
const getDropped = () => read(LS_DROPPED, {}) || {};

/* An older build saved whichever episode was open. Fold those entries into the
 * show once, so an existing list reads the same as one built now. */
function normaliseList() {
  const list = getList();
  const out = [];
  const seen = new Set();
  let changed = false;
  list.forEach((m) => {
    if (!m || !m.id) return;
    const ep = episodeParts(m);
    const id = ep ? "ext:series:" + ep.series : m.id;
    if (seen.has(id)) {
      changed = true;
      return;
    }
    seen.add(id);
    if (ep) {
      changed = true;
      const href = "/title/series/" + ep.series;
      out.push(Object.assign({}, m, { id: id, url: href, href: href }));
    } else {
      out.push(m);
    }
  });
  if (changed) write(LS_LIST, out);
}

function setList(list) {
  write(LS_LIST, list);
  paint();
}

function remember(item) {
  if (!item || !item.id || !item.title) return;
  const cat = getCatalog();
  const prev = cat[item.id] || {};
  cat[item.id] = {
    id: item.id,
    title: item.title || prev.title || item.id,
    cover: item.cover || prev.cover || "",
    url: item.url || prev.url || "/watch/" + item.id,
    href: item.href || prev.href || "",
    year: item.year || prev.year || "",
    lang: item.lang || prev.lang || ""
  };
  write(LS_CATALOG, cat);
}

function toggleList(item) {
  const list = getList();
  const removed = getRemoved();
  const at = list.findIndex((m) => m.id === item.id);
  if (at >= 0) {
    list.splice(at, 1);
    removed[item.id] = Date.now();
  } else {
    delete removed[item.id];
    list.unshift({
      id: item.id,
      title: item.title,
      cover: item.cover || "",
      url: item.url,
      href: item.href || "",
      year: item.year || "",
      lang: item.lang || "",
      at: Date.now()
    });
  }
  write(LS_REMOVED, removed);
  setList(list);
}

/* ------------------------------------------------------------- progress */

function setResume(id, seconds, duration, meta) {
  const p = getProgress();
  if (!duration || duration < 1) {
    return;
  }
  const left = duration - seconds;
  if (seconds < MIN_SECONDS || (left >= 0 && left <= FINISH_LEFT)) {
    delete p[id];
  } else {
    if (meta) remember(meta);
    p[id] = {
      seconds: Math.floor(seconds),
      duration: Math.floor(duration),
      at: Date.now(),
      meta: meta || (p[id] && p[id].meta) || null
    };
    /* Watching it again: a finish from an earlier session no longer stands.
     * It has to be cleared here, not just on screen — the account merge drops
     * any resume point whose watched record still says finished. */
    const seen = getWatched();
    if (seen[id] && seen[id].finished) {
      seen[id] = Object.assign({}, seen[id], { finished: false, at: Date.now() });
      write(LS_WATCHED, seen);
    }
  }
  write(LS_PROGRESS, p);
}

function addWatchTime(id, delta, meta) {
  if (!delta || delta <= 0 || delta > SEEK_LIMIT) return; // ignore seeks
  const w = getWatched();
  const prev = w[id] || {};
  if (meta) remember(meta);
  w[id] = Object.assign(
    { seconds: 0, finished: false },
    prev,
    meta || {},
    { seconds: (prev.seconds || 0) + delta, at: Date.now() }
  );
  write(LS_WATCHED, w);
}

/* Dropping a show is a tombstone, not just a delete: the account copy would
 * otherwise hand the entry straight back on the next sync. */
function dropFromContinue(id) {
  if (!id) return;
  const progress = getProgress();
  delete progress[id];
  write(LS_PROGRESS, progress);
  const dropped = getDropped();
  dropped[id] = Date.now();
  write(LS_DROPPED, dropped);
  paint();
}

/* Emptying the whole shelf drops every card the same way the single × does:
 * a tombstone per id, so a device that still has them cannot hand them back
 * on the next sync. */
function clearContinueWatching() {
  const progress = getProgress();
  const dropped = getDropped();
  const rail = document.querySelector('[data-shelf="continue"]');
  const ids = rail
    ? Array.from(rail.querySelectorAll("article[data-id]")).map((el) => el.dataset.id)
    : Object.keys(progress);
  const at = Date.now();
  ids.forEach((id) => {
    delete progress[id];
    dropped[id] = at;
  });
  write(LS_PROGRESS, progress);
  write(LS_DROPPED, dropped);
  setContinueConfirm(false);
  paint();
}

/* "Clear all" turns into "Are you sure? Yes / No" in place, so the question
 * sits where the button was and nothing jumps around. */
function setContinueConfirm(open) {
  const ask = document.querySelector('[data-confirm="continue"]');
  const button = document.querySelector('[data-action="clear-continue"]');
  const rail = document.querySelector('[data-shelf="continue"]');
  const any = !!(rail && rail.querySelector("article"));
  if (ask) ask.hidden = !open;
  if (button) button.hidden = open || !any;
}

function markFinished(id, meta) {
  const w = getWatched();
  const prev = w[id] || {};
  if (meta) remember(meta);
  w[id] = Object.assign({ seconds: 0, finished: false }, prev, meta || {},
                        { finished: true, at: Date.now() });
  write(LS_WATCHED, w);
  const p = getProgress();
  delete p[id];
  write(LS_PROGRESS, p);
}

function continueWatching() {
  const p = getProgress();
  const cat = getCatalog();
  const dropped = getDropped();
  const saved = new Set(getList().map((m) => m.id));

  return Object.keys(p)
    .map((id) => {
      const entry = p[id];
      /* A stamp from the future would out-rank every removal tombstone for as
       * long as it stays ahead of the clock, so it counts as no stamp at all. */
      const at =
        entry.at > 0 && entry.at <= Date.now() + FUTURE_SLACK ? entry.at : 0;
      if (dropped[id] && dropped[id] >= at) return null;
      const meta = Object.assign({}, cat[id] || {}, entry.meta || {});
      if (!meta.id) meta.id = id;
      if (!meta.title) return null;
      if (!meta.url) meta.url = "/watch/" + id;
      meta.frac = entry.duration ? entry.seconds / entry.duration : 0;
      meta.left = entry.duration ? entry.duration - entry.seconds : null;
      meta.seconds = entry.seconds || 0;
      meta.at = at;
      /* a saved show covers every episode of it, so the + on an episode of a
       * show already in the list reads as saved */
      const part = episodeParts(meta);
      meta.saved = saved.has(id) ||
        !!(part && saved.has("ext:series:" + part.series));
      meta.removable = true;
      return meta;
    })
    /* ten seconds of playback is what earns a card: a page that was opened
     * and left is not watching, and an entry still sitting at zero stays off
     * the shelf even if an older build saved one */
    .filter((m) => m && m.seconds >= MIN_WATCH &&
                   (m.left == null || m.left > FINISH_LEFT))
    .sort((a, b) => b.at - a.at)
    .slice(0, 24);
}

/* --------------------------------------------------------------- markup */

function esc(value) {
  return String(value == null ? "" : value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

/* What a card adds to the list, which is not always what it opens: an episode
 * page saves the show itself, so My List does not fill up with single
 * episodes of the same series. */
function listIdOf(card) {
  return (card && card.dataset.listId) || (card && card.dataset.id) || "";
}

/* ext:series:<imdb>:<season>:<episode> */
function episodeParts(m) {
  const parts = String((m && m.id) || "").split(":");
  if (parts.length === 5 && parts[0] === "ext" && parts[1] === "series") {
    return { series: parts[2], season: parts[3], episode: parts[4] };
  }
  return null;
}

function pad2(value) {
  return String(value).length < 2 ? "0" + value : String(value);
}

function episodeHref(m) {
  // A resume entry for one episode has to reopen that episode; the show page
  // would otherwise start at S01E01.
  const ep = episodeParts(m);
  return ep
    ? "/title/series/" + ep.series + "?s=" + ep.season + "&e=" + ep.episode
    : "";
}

function watchHref(m) {
  // Library titles carry their own page (a show needs an episode first);
  // an einthusan film still has only its watch route.
  const episode = episodeHref(m);
  if (episode) return episode;
  if (m.href && m.href.charAt(0) === "/") return m.href;
  if (m.url && m.url.charAt(0) === "/") return m.url;
  const q = new URLSearchParams({
    t: m.title || "",
    c: m.cover || "",
    y: m.year || "",
    l: m.lang || ""
  });
  return "/watch/" + m.id + "?" + q.toString();
}

function cardHtml(m) {
  const href = esc(watchHref(m));
  const title = esc(m.title);
  const bits = [m.year, m.lang].filter(Boolean).map(esc);
  const ep = episodeParts(m);
  if (ep) bits.push("S" + pad2(ep.season) + " E" + pad2(ep.episode));
  const meta = bits.join(" &middot; ");
  const cover = m.cover
    ? '<img loading="lazy" src="' + esc(m.cover) + '" alt="">'
    : '<span class="card-none">No artwork</span>';

  const progress =
    typeof m.frac === "number" && m.frac > 0
      ? '<span class="card-progress"><i style="width:' +
        Math.round(m.frac * 100) + '%"></i></span>'
      : "";

  return (
    '<article class="card" data-id="' + esc(m.id) +
    '" data-title="' + title +
    '" data-cover="' + esc(m.cover || "") +
    '" data-url="' + esc(m.url || "") +
    '" data-href="' + esc(m.href || m.url || "") +
    '" data-year="' + esc(m.year || "") +
    '" data-lang="' + esc(m.lang || "") + '">' +
    (m.removable
      ? '<button class="card-drop" type="button" data-action="drop"'
        + ' aria-label="Remove from continue watching"'
        + ' title="Remove from continue watching">&times;</button>'
      : "") +
    '<a class="card-link" href="' + href + '" aria-label="' + title + '">' +
    '<span class="card-poster">' +
    cover +
    '<span class="card-shade"></span>' +
    '<span class="card-play">' + SVG_PLAY + "</span>" +
    progress +
    "</span>" +
    '<span class="card-text"><b>' + title + "</b>" +
    (meta ? "<em>" + meta + "</em>" : "") +
    "</span></a>" +
    '<button class="card-add' + (m.saved ? " on" : "") +
    '" type="button" data-action="toggle" aria-label="Add to my list">' +
    '<span class="add-off">' + SVG_PLUS + "</span>" +
    '<span class="add-on">' + SVG_CHECK + "</span></button>" +
    "</article>"
  );
}

/* ext:movie:* is a film, ext:series:* is a show, and an episode id (four
 * parts after the prefix) belongs to the show it came from. */
function isShow(m) {
  return /^ext:series:/.test(String((m && m.id) || ""));
}

function paintCollection(name, items, emptyText) {
  fill(name, items, emptyText);
  const count = document.querySelector('[data-count="' + name + '"]');
  if (count) {
    count.textContent = items.length ? items.length + " saved" : "";
  }
}

function fill(name, items, emptyText) {
  const list = document.querySelector('[data-shelf="' + name + '"]');
  const note = document.querySelector('[data-empty="' + name + '"]');
  if (list) list.innerHTML = items.map(cardHtml).join("");
  if (note) {
    note.hidden = items.length > 0;
    if (!items.length && emptyText) note.textContent = emptyText;
  }
}

/* -------------------------------------------------------------- billboard */

/* The hero is a carousel of films taken from the service rows underneath it,
 * and only the rows still switched on in settings: hiding a catalogue takes
 * its films off the top of the page too. When that leaves nothing, the banner
 * takes over. Each film holds for five seconds with a countdown along the
 * bottom edge, and the dots are built here so their number matches the reel. */
const BILLBOARD_LIMIT = 10;

/* How long each film holds. Ten seconds unless somebody picks another number
 * on /settings; the countdown bar is drawn from the same value. */
const DWELL_KEY = "iml:dwell";
const DWELL_DEFAULT = 10;
const DWELL_MIN = 1;
const DWELL_MAX = 600;

function dwellValue(seconds) {
  const n = Math.round(Number(seconds));
  if (!isFinite(n)) return DWELL_DEFAULT;
  if (n < DWELL_MIN) return DWELL_MIN;
  return n > DWELL_MAX ? DWELL_MAX : n;
}

function savedDwell() {
  try {
    const raw = localStorage.getItem(DWELL_KEY);
    return raw === null || raw === "" ? DWELL_DEFAULT : dwellValue(raw);
  } catch (e) {
    return DWELL_DEFAULT;
  }
}

function storeDwell(seconds) {
  try {
    localStorage.setItem(DWELL_KEY, String(dwellValue(seconds)));
  } catch (e) {
    /* private mode: the choice lasts this page only */
  }
}

function wireBillboard() {
  const host = document.querySelector("[data-billboard]");
  if (!host) return;

  const carousel = host.querySelector("[data-bb-carousel]");
  const fallback = host.querySelector("[data-bb-fallback]");
  const hiddenRows = new Set(
    savedRows().filter((row) => row.on === false).map((row) => row.id)
  );

  /* the server sends extra films so ten are still left after filtering */
  const kept = Array.from(host.querySelectorAll("[data-slide]"))
    .filter((slide) => !hiddenRows.has(slide.dataset.row || ""))
    .slice(0, BILLBOARD_LIMIT);
  host.querySelectorAll("[data-slide]").forEach((slide) => {
    if (kept.indexOf(slide) === -1) slide.remove();
  });

  if (!carousel || !kept.length) {
    if (carousel) carousel.hidden = true;
    if (fallback) fallback.hidden = false;
    return;
  }

  const dotsBox = carousel.querySelector("[data-bb-dots]");
  const bar = carousel.querySelector("[data-bb-progress] i");
  const pauseBtn = carousel.querySelector("[data-bb-pause]");
  /* someone who asked the system for less motion should not be handed a
   * carousel that moves by itself: it starts stopped, and Play starts it */
  let paused = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  let at = 0;
  let timer = 0;

  function load(slide) {
    slide.querySelectorAll("img[data-src]").forEach((img) => {
      if (!img.getAttribute("src")) img.setAttribute("src", img.dataset.src);
    });
  }

  /* the hold, read each time so a change on /settings is picked up */
  function hold() {
    return savedDwell() * 1000;
  }

  /* restart the countdown from empty every time the film changes */
  function countdown() {
    if (!bar || kept.length < 2) return;
    bar.style.transition = "none";
    bar.style.width = "0%";
    if (paused) return;
    void bar.offsetWidth;
    bar.style.transition = "width " + hold() + "ms linear";
    bar.style.width = "100%";
  }

  function syncPause() {
    if (!pauseBtn) return;
    pauseBtn.setAttribute("aria-pressed", paused ? "true" : "false");
    pauseBtn.setAttribute("aria-label",
      paused ? "Play the carousel" : "Pause the carousel");
    const showing = pauseBtn.querySelector(
      paused ? '[data-bb-icon="play"]' : '[data-bb-icon="pause"]'
    );
    pauseBtn.querySelectorAll("[data-bb-icon]").forEach((icon) => {
      icon.hidden = icon !== showing;
    });
  }

  function show(next, byHand) {
    at = (next + kept.length) % kept.length;
    kept.forEach((slide, n) => slide.classList.toggle("is-live", n === at));
    dots.forEach((dot, n) => {
      dot.classList.toggle("is-live", n === at);
      dot.setAttribute("aria-current", n === at ? "true" : "false");
    });
    load(kept[at]);
    countdown();
    if (byHand) start();
  }

  function stop() {
    window.clearInterval(timer);
  }

  function start() {
    stop();
    if (!paused && kept.length > 1) {
      timer = window.setInterval(() => show(at + 1), hold());
    }
  }

  if (pauseBtn) {
    pauseBtn.addEventListener("click", () => {
      paused = !paused;
      syncPause();
      if (paused) {
        stop();
        if (bar) bar.style.width = "0%";
      } else {
        start();
        countdown();
      }
    });
  }

  const dots = kept.map((slide, n) => {
    const dot = document.createElement("button");
    const title = slide.querySelector(".bb-title");
    dot.type = "button";
    dot.className = "bb-dot";
    dot.dataset.bbDot = String(n);
    dot.setAttribute("aria-current", "false");
    dot.setAttribute("aria-label",
      "Show " + ((title && title.textContent) || "film " + (n + 1)));
    dot.addEventListener("click", () => show(n, true));
    if (dotsBox) dotsBox.appendChild(dot);
    return dot;
  });

  if (kept.length < 2 && dotsBox) dotsBox.hidden = true;
  if (kept.length < 2 && pauseBtn) pauseBtn.hidden = true;
  load(kept[0]);
  show(0);
  syncPause();
  start();
}

function paint() {
  const list = getList();
  const saved = new Set(list.map((m) => m.id));

  list.forEach(remember);
  document.querySelectorAll("[data-id][data-title]").forEach((el) =>
    remember({
      id: el.dataset.id,
      title: el.dataset.title,
      cover: el.dataset.cover,
      url: el.dataset.url,
      href: el.dataset.href,
      year: el.dataset.year,
      lang: el.dataset.lang
    })
  );

  const savedItems = list.map((m) => Object.assign({ saved: true }, m));
  fill("watchlist", savedItems);
  /* the list page keeps films and shows apart */
  paintCollection("films", savedItems.filter((m) => !isShow(m)), "Nothing saved yet.");
  paintCollection("shows", savedItems.filter(isShow), "Nothing saved yet.");
  const clearList = document.querySelector('[data-action="clear-watchlist"]');
  if (clearList) clearList.hidden = list.length === 0;
  const leaving = continueWatching();
  fill("continue", leaving);
  /* nothing to clear means no button; a question left open closes with the
   * last card it was about */
  const clearButton = document.querySelector('[data-action="clear-continue"]');
  if (clearButton) clearButton.hidden = leaving.length === 0;
  if (!leaving.length) setContinueConfirm(false);
  document.querySelectorAll(".card-add, .watch-add").forEach((btn) => {
    const card = btn.closest("[data-id]");
    if (card) btn.classList.toggle("on", saved.has(listIdOf(card)));
  });
}

/* ---------------------------------------------------------------- player */

function wirePlayer() {
  const video = document.getElementById("player");
  const wrap = document.querySelector(".watch");
  if (!video || !wrap) return;

  const id = wrap.dataset.id;
  const meta = {
    id: id,
    title: wrap.dataset.title,
    cover: wrap.dataset.cover,
    url: wrap.dataset.url,
    href: wrap.dataset.href || wrap.dataset.url || "",
    year: wrap.dataset.year
  };
  remember(meta);

  const resume = getProgress()[id];
  const note = wrap.querySelector('[data-role="resume"]');
  /* a converted stream has no index yet, so seeking is not possible */
  const live = wrap.dataset.live === "1";

  if (!live && resume && resume.duration && resume.seconds > MIN_SECONDS) {
    const at = Math.min(resume.seconds, resume.duration - 5);
    video.addEventListener(
      "loadedmetadata",
      function () {
        if (video.seekable && video.seekable.length === 0) {
          if (note) note.textContent =
            "This stream cannot seek, so it starts from the beginning.";
          return;
        }
        video.currentTime = at;
        if (note) {
          note.textContent =
            "Resumed at " + Math.floor(at / 60) + "m " +
            Math.floor(at % 60) + "s.";
        }
      },
      { once: true }
    );
  }

  let last = 0;
  let lastTick = 0;

  const tick = function () {
    const now = video.currentTime;
    const delta = now - lastTick;
    if (delta > 0 && delta <= SEEK_LIMIT) addWatchTime(id, delta, meta);
    lastTick = now;
    setResume(id, now, video.duration, meta);
  };

  video.addEventListener("timeupdate", function () {
    const now = Date.now();
    if (now - last < 4000) return;
    last = now;
    tick();
  });

  video.addEventListener("seeking", function () {
    lastTick = video.currentTime;
  });

  video.addEventListener("play", function () {
    lastTick = video.currentTime;
  });

  video.addEventListener("pause", tick);

  video.addEventListener("ended", function () {
    markFinished(id, meta);
    paint();
    syncAccount();
  });

  window.addEventListener("pagehide", tick);
  window.addEventListener("beforeunload", tick);
}

/* ------------------------------------------------------------- player frame */

/* A title page offers a player per source, because any one of them can be
 * missing a title or fall over mid-film. They are all just a URL in a frame,
 * so this file knows only which one is on and which of them talk back: VidLink,
 * VidSrc.sh and Einthusan post `PLAYER_EVENT` messages carrying a position and
 * a duration. Listening to those keeps our resume position, watch time and
 * "finished" state working, and the account sync carries them to the other
 * devices. CineSrc and VidSrc.mov are silent, so watching through either does
 * not move continue watching.
 *
 * Some players take a start second in the URL — CineSrc and Einthusan as `t`,
 * VidLink and VidSrc.sh as `startAt` — and the server tags each button with the
 * parameter it wants, so the frame opens where the film was left. VidSrc.mov
 * has none, so it starts at the top. */
const VIDLINK_ORIGIN = "https://vidlink.pro";
const VIDSRC_ORIGIN = "https://vidsrc.sh";
/* Einthusan has no embed of its own: that frame is a page here, same origin. */
const SITE_ORIGIN = location.origin;
/* the source picked last time, so the same one comes back next visit */
const SOURCE_KEY = "iml:player-source";

/* The players take their accent from a query parameter — VidLink as
 * ?primaryColor= (hex without the "#"), CineSrc as ?color=. The server writes
 * the default saffron into each URL, and the accent picked on /settings
 * replaces it here before the frame is allowed to load, so a blue or green
 * theme no longer plays with an orange scrubber. Nothing is picked for the
 * default theme, so those URLs come back unchanged. */
function playerAccent() {
  const hex = getComputedStyle(document.documentElement)
    .getPropertyValue("--saffron")
    .trim()
    .replace(/^#/, "");
  return /^[0-9a-f]{6}$/i.test(hex) ? hex : "";
}

function tintPlayer(url, key) {
  const hex = playerAccent();
  if (!url || !hex) return url;
  if (key === "vidlink") {
    return url.replace(/([?&]primaryColor=)[^&]*/i, "$1" + hex);
  }
  if (key === "cinesrc") {
    return url.replace(/([?&]color=)[^&]*/i, "$1%23" + hex);
  }
  return url;
}

/* Where a player documents one, the saved second goes on the end. */
function withResume(url, param, at) {
  if (!url || !param || !(at > 0)) return url;
  return url + (url.indexOf("?") === -1 ? "?" : "&") + param + "=" + at;
}

function savedSource() {
  try {
    return localStorage.getItem(SOURCE_KEY) || "";
  } catch (e) {
    return "";
  }
}

function storeSource(key) {
  try {
    localStorage.setItem(SOURCE_KEY, key);
  } catch (e) {
    /* private mode: the choice lasts this page only */
  }
}

function wirePlayer() {
  const frame = document.querySelector("iframe[data-player]");
  const article = frame && frame.closest("[data-id]");
  if (!frame || !article) return;

  const id = article.dataset.id;
  const buttons = Array.from(document.querySelectorAll("[data-source]"));
  const openTab = document.querySelector("[data-embed-link]");
  const note = document.querySelector('[data-role="resume"]');
  const label = document.querySelector('[data-role="source-name"]');
  const stuck = document.querySelector('[data-role="stuck"]');
  const panel = document.querySelector('[data-role="resume-panel"]');
  const jumpField = document.querySelector('[data-role="jump"]');
  const shareBtn = document.querySelector('[data-role="share"]');
  const upNext = document.querySelector('[data-role="up-next"]');
  const upNextRow = document.querySelector('[data-role="up-next-row"]');
  const upNextNote = document.querySelector('[data-role="up-next-note"]');
  const mediaId = article.dataset.media || "";
  const mediaKind = article.dataset.kind === "series" ? "series" : "movie";
  let stuckTimer = 0;

  /* A third-party player can be blank and say nothing at all. Fifteen seconds
   * after a frame is asked for, with no PLAYER_EVENT from it, the page admits
   * it and points at the picker instead of leaving a black rectangle. */
  function clearStuck() {
    window.clearTimeout(stuckTimer);
    stuckTimer = 0;
    if (stuck) stuck.hidden = true;
  }

  function watchStuck() {
    clearStuck();
    if (!stuck) return;
    stuckTimer = window.setTimeout(() => {
      if (stuck) stuck.hidden = false;
    }, 15000);
  }

  const saved = getProgress()[id];
  /* a link somebody shared carries the second it was made at */
  const fromLink = Math.max(
    0,
    Math.floor(Number(new URLSearchParams(location.search).get("t")) || 0)
  );
  const resumeAt =
    fromLink > MIN_SECONDS
      ? fromLink
      : saved && saved.seconds && saved.seconds > MIN_SECONDS
      ? Math.floor(saved.seconds)
      : 0;

  /* every button carries its own player's URL; this visitor's accent and the
   * saved second are written into it before anything is loaded */
  buttons.forEach((button) => {
    const tuned = tintPlayer(button.dataset.src, button.dataset.source);
    button.dataset.src = tuned;
    button.dataset.played = withResume(tuned, button.dataset.resume, resumeAt);
  });

  const meta = {
    id: id,
    title: article.dataset.title,
    cover: article.dataset.cover,
    url: "",
    href: article.dataset.href || location.pathname,
    year: article.dataset.year
  };

  let active = "";

  /* Putting a source on is one place: the frame, the highlighted button, the
   * note underneath and the "new tab" link all follow it. */
  function select(key, reveal) {
    const chosen =
      buttons.find((button) => button.dataset.source === key) || buttons[0];
    if (!chosen) return;
    active = chosen.dataset.source;
    meta.url = chosen.dataset.played;
    buttons.forEach((button) => {
      const on = button === chosen;
      button.classList.toggle("on", on);
      button.setAttribute("aria-pressed", on ? "true" : "false");
    });
    if (frame.getAttribute("src") !== chosen.dataset.played) {
      frame.src = chosen.dataset.played;
    }
    if (openTab) openTab.href = chosen.dataset.played;
    if (label) label.textContent = chosen.textContent.trim();
    if (reveal) {
      const player = frame.closest(".player");
      if (player) player.classList.add("playing");
      watchStuck();
      hideUpNext();
    }
  }

  buttons.forEach((button) => {
    button.addEventListener("click", () => {
      select(button.dataset.source, true);
      storeSource(button.dataset.source);
    });
  });

  paint();

  /* the server already loaded the first player; this applies the saved second
   * (or the source used last time) on top of it */
  select(savedSource(), false);

  if (resumeAt && note) {
    note.textContent =
      "Resumed at " + Math.floor(resumeAt / 60) + "m " +
      Math.floor(resumeAt % 60) + "s" +
      (fromLink ? " from the link you opened." : ".");
    if (panel) panel.hidden = false;
  }

  let lastTick = 0;
  let lastSave = 0;
  let lastKnown = null;
  /* how much of this visit has actually played, so a page that is merely open
   * never becomes a card; picking up an existing episode counts as playing */
  let played = saved && saved.seconds >= MIN_WATCH ? MIN_WATCH : 0;

  function clockish(seconds) {
    const total = Math.max(0, Math.floor(seconds));
    const minutes = Math.floor(total / 60);
    const rest = total % 60;
    return minutes + ":" + (rest < 10 ? "0" : "") + rest;
  }

  function hereSecond() {
    if (lastKnown && lastKnown.now > 0) return Math.floor(lastKnown.now);
    return Math.floor(resumeAt || 0);
  }

  function updateShareLabel() {
    if (!shareBtn) return;
    const at = hereSecond();
    shareBtn.textContent = at > MIN_SECONDS ? "Share at " + clockish(at) : "Copy link";
  }

  function parseClock(text) {
    const raw = String(text || "").trim();
    if (!raw) return -1;
    if (/^\d+$/.test(raw)) return Number(raw);
    const found = raw.match(/^(\d{1,3}):([0-5]?\d)$/);
    return found ? Number(found[1]) * 60 + Number(found[2]) : -1;
  }

  /* The einthusan frame keeps its language in its own address; reading it is
     same-origin, and only ever used to build a share link. */
  function frameLanguage() {
    if (active !== "einthusan") return "";
    try {
      return new URLSearchParams(frame.contentWindow.location.search)
        .get("lang") || "";
    } catch (e) {
      return "";
    }
  }

  /* The chosen source's URL without a start second, so a new one can go on. */
  function playFrom(seconds) {
    const chosen =
      buttons.find((button) => button.dataset.source === active) || buttons[0];
    if (!chosen) return;
    if (!chosen.dataset.resume) {
      if (note) note.textContent = "This source cannot start at a chosen second.";
      return;
    }
    chosen.dataset.played =
      withResume(chosen.dataset.src, chosen.dataset.resume, seconds);
    lastKnown = null;
    lastTick = seconds > 0 ? seconds : 0;
    played = 0;
    select(active, true);
    if (note && seconds > 0) {
      note.textContent = "Playing from " + clockish(seconds) + ".";
    }
  }

  if (panel) {
    const startOver = panel.querySelector('[data-action="start-over"]');
    if (startOver) {
      startOver.addEventListener("click", () => {
        /* a tombstone as well as the delete, so an older copy on another
           device cannot hand the position back */
        dropFromContinue(id);
        panel.hidden = true;
        if (note) note.textContent = "";
        playFrom(0);
      });
    }

    const go = panel.querySelector('[data-action="jump"]');
    if (go && jumpField) {
      go.addEventListener("click", () => {
        const seconds = parseClock(jumpField.value);
        if (seconds < 0) {
          jumpField.setCustomValidity("Try 42:10, or a number of seconds.");
          jumpField.reportValidity();
          return;
        }
        jumpField.setCustomValidity("");
        playFrom(seconds);
      });
      jumpField.addEventListener("keydown", (event) => {
        if (event.key === "Enter") {
          event.preventDefault();
          go.click();
        }
      });
    }
  }

  if (shareBtn) {
    shareBtn.addEventListener("click", () => {
      const at = hereSecond();
      const query = [];
      if (at > MIN_SECONDS) query.push("t=" + at);
      const lang = frameLanguage();
      if (lang) query.push("lang=" + encodeURIComponent(lang));
      const url = location.origin + location.pathname +
        (query.length ? "?" + query.join("&") : "");
      const copied = () => {
        shareBtn.textContent = "Link copied";
        window.setTimeout(updateShareLabel, 1800);
      };
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(url).then(copied, () => {
          if (note) note.textContent = url;
        });
      } else if (note) {
        note.textContent = url;
      }
    });
    updateShareLabel();
  }

  /* ------------------------------------------------------------- up next */

  let upNextRun = 0;

  function hideUpNext() {
    if (upNext) upNext.hidden = true;
  }

  function nextEpisode() {
    const on = document.querySelector(".episode.on");
    if (!on) return null;
    const all = Array.from(
      document.querySelectorAll(".episode[data-season][data-episode]")
    );
    const index = all.indexOf(on);
    if (index < 0 || index + 1 >= all.length) return null;
    const next = all[index + 1];
    const name = next.querySelector(".ep-name");
    return {
      href: next.getAttribute("href") || "",
      label: (name && name.textContent.trim()) || "Next episode"
    };
  }

  function upNextEpisode(next) {
    if (!next || !next.href) return null;
    const link = document.createElement("a");
    link.className = "up-next-episode";
    link.href = next.href;
    link.textContent = "Next: " + next.label;
    return link;
  }

  /* Two players can report the end of the same viewing, so only the newest
     call owns the row: a finished fetch that lost the race is dropped. */
  function showUpNext() {
    if (!upNext) return;
    const run = ++upNextRun;
    const next = nextEpisode();
    if (upNextNote) {
      upNextNote.textContent = next
        ? "That was the end of this episode. The next one is ready."
        : "That was the end. Something else from the same shelf:";
    }
    if (upNextRow) {
      upNextRow.innerHTML = "";
      const episode = upNextEpisode(next);
      if (episode) upNextRow.appendChild(episode);
    }
    upNext.hidden = false;
    if (!mediaId) return;
    fetch("/api/up-next/" + mediaKind + "/" + encodeURIComponent(mediaId))
      .then((response) => response.json())
      .then((data) => {
        const items = (data && data.items) || [];
        if (run !== upNextRun || !upNextRow) return;
        upNextRow.innerHTML = "";
        const episode = upNextEpisode(next);
        if (episode) upNextRow.appendChild(episode);
        if (!items.length) return;
        items.slice(0, 12).forEach((one) => {
          if (!one || !one.id) return;
          const card = document.createElement("a");
          card.className = "up-next-card";
          card.href = "/title/" + (one.type === "series" ? "series" : "movie") +
            "/" + one.id;
          if (one.poster) {
            const img = document.createElement("img");
            img.loading = "lazy";
            img.src = one.poster;
            img.alt = "";
            card.appendChild(img);
          }
          const label = document.createElement("span");
          label.textContent = one.name + (one.year ? " · " + one.year : "");
          card.appendChild(label);
          upNextRow.appendChild(card);
        });
      })
      .catch(() => {});
  }

  function logTime(now, duration) {
    lastKnown = { now: now, duration: duration };
    /* the last stretch only, so an episode the player never formally
     * "ended" still stops haunting continue watching — and a seek into a film
     * whose duration is reported short is not mistaken for finishing it */
    const left = duration - now;
    if (duration > 0 && left >= 0 && left <= FINISH_LEFT) {
      markFinished(id, meta);
      paint();
      syncAccount();
      showUpNext();
      return;
    }
    if (played < MIN_WATCH) return;
    const stamp = Date.now();
    if (stamp - lastSave < 4000) return;
    lastSave = stamp;
    setResume(id, now, duration, meta);
  }

  /* One report. The position moving is the only reliable sign of playback: a
   * paused player does not advance, whichever event carried the number. */
  function tick(now, duration) {
    const delta = now - lastTick;
    if (delta > 0 && delta <= SEEK_LIMIT) {
      played += delta;
      addWatchTime(id, delta, meta);
    }
    lastTick = now;
    updateShareLabel();
    logTime(now, duration);
  }

  window.addEventListener("message", function (event) {
    /* only VidLink reports, and only when its frame is the one showing */
    if (active !== "vidlink") return;
    if (event.origin !== VIDLINK_ORIGIN) return;
    if (event.source !== frame.contentWindow) return;
    const data = event.data;
    if (!data || data.type !== "PLAYER_EVENT" || !data.data) return;
    clearStuck();

    const now = Number(data.data.currentTime) || 0;
    const duration = Number(data.data.duration) || 0;

    switch (data.data.event) {
      case "ended":
        markFinished(id, meta);
        paint();
        syncAccount();
        showUpNext();
        return;
      case "play":
        lastTick = now;
        lastSave = 0;
        logTime(now, duration);
        return;
      case "seeked":
        /* the jump itself is not watching; the next report starts from here */
        lastTick = now;
        lastKnown = { now: now, duration: duration };
        logTime(now, duration);
        return;
      case "pause":
        lastSave = 0;
        tick(now, duration);
        return;
      case "timeupdate":
        tick(now, duration);
        return;
      default:
        return;
    }
  });

  /* VidSrc.sh sends the same `PLAYER_EVENT` type with different field names
   * (`player_status`, `player_progress`, `player_duration`) and its own
   * statuses, so its reports land on the same two functions above. Einthusan's
   * frame is a page of ours and sends exactly the same shape, so both are read
   * here — each with its own origin, and only while it is the source showing. */
  window.addEventListener("message", function (event) {
    if (active !== "vidsrc" && active !== "einthusan") return;
    if (event.origin !== VIDSRC_ORIGIN && event.origin !== SITE_ORIGIN) return;
    if (event.source !== frame.contentWindow) return;
    const data = event.data;
    if (!data || data.type !== "PLAYER_EVENT" || !data.data) return;
    clearStuck();

    const now = Number(data.data.player_progress) || 0;
    const duration = Number(data.data.player_duration) || 0;

    switch (data.data.player_status) {
      case "completed":
        markFinished(id, meta);
        paint();
        syncAccount();
        showUpNext();
        return;
      case "seeked":
        lastTick = now;
        lastKnown = { now: now, duration: duration };
        logTime(now, duration);
        return;
      case "paused":
        lastSave = 0;
        tick(now, duration);
        return;
      case "playing":
        /* fires on start, on resume and then roughly every five seconds */
        tick(now, duration);
        return;
      default:
        return;
    }
  });

  /* Most sessions end by closing the tab, not by pressing pause, so the last
   * position the player told us about is written on the way out. */
  window.addEventListener("pagehide", function () {
    if (!lastKnown || played < MIN_WATCH) return;
    setResume(id, lastKnown.now, lastKnown.duration, meta);
    syncAccount();
  });
}

/* ------------------------------------------------------------------- rails */

const rails = new WeakMap();

function edgeState(rail) {
  const ctl = rails.get(rail);
  const shelf = rail.closest(".shelf");
  if (!ctl || !shelf) return;
  const b = ctl.bounds();
  const prev = shelf.querySelector(".rail-btn.prev");
  const next = shelf.querySelector(".rail-btn.next");
  if (prev) prev.classList.toggle("at-edge", rail.scrollLeft > 4);
  if (next) next.classList.toggle("at-edge", rail.scrollLeft < b.max - 4);
}

function wireRails() {
  document.querySelectorAll(".rail").forEach((rail) => {
    if (rails.has(rail)) return;
    if (!rail.querySelector("article")) return;
    rails.set(rail, window.Motion.attachDrag(rail));
    rail.addEventListener("scroll", () => edgeState(rail), { passive: true });
    edgeState(rail);
  });
}

/* the nav only becomes solid once something is actually under it */
function wireBar() {
  const bar = document.getElementById("bar");
  if (!bar) return;
  const sync = () => bar.classList.toggle("solid", window.scrollY > 12);
  sync();
  window.addEventListener("scroll", sync, { passive: true });
}

/* Account state is merged on the server, so the same login works on both
 * the modern and Lumia clients without exposing the password to JavaScript. */
/* Theme and row order travel with the account. Both are choices rather than
 * history, and neither is a list the server can merge item by item, so a
 * stamp decides which side is newer. */
function prefsAt() {
  try {
    return Number(localStorage.getItem(PREFS_AT)) || 0;
  } catch (e) {
    return 0;
  }
}

function touchPrefs() {
  try {
    localStorage.setItem(PREFS_AT, String(Date.now()));
  } catch (e) {
    /* private mode: the choice lasts this tab only */
  }
}

function localPrefs() {
  return {
    theme: savedTheme(),
    rows: savedRows(),
    dwell: savedDwell(),
    at: prefsAt()
  };
}

function applyPrefs(prefs) {
  if (!prefs || !prefs.at || prefs.at <= prefsAt()) return;
  try {
    localStorage.setItem(THEME_KEY, prefs.theme || "saffron");
    if (Array.isArray(prefs.rows) && prefs.rows.length) storeRows(prefs.rows);
    if (Number(prefs.dwell) >= DWELL_MIN) storeDwell(prefs.dwell);
    localStorage.setItem(PREFS_AT, String(prefs.at));
  } catch (e) {
    return;
  }
  applyTheme(savedTheme());
  markTheme(savedTheme());
  applyHomeRows();
  document.dispatchEvent(new Event("prefs:applied"));
}

function syncAccount() {
  const askedAt = Date.now();
  fetch("/auth/me", { credentials: "same-origin" })
    .then((response) => response.json())
    .then((account) => {
      if (!account.authenticated) return;
      const state = {
        watchlist: getList(),
        progress: getProgress(),
        watched: getWatched(),
        catalog: getCatalog(),
        removed: getRemoved(),
        dropped: getDropped(),
        prefs: localPrefs()
      };
      return fetch("/api/sync", {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(state)
      });
    })
    .then((response) => response && response.ok ? response.json() : null)
    .then((result) => {
      if (!result || !result.state) return;
      const state = result.state;
      write(LS_LIST, state.watchlist || []);
      write(LS_PROGRESS, keepWrittenDuring(state.progress, getProgress(), askedAt));
      write(LS_WATCHED, keepWrittenDuring(state.watched, getWatched(), askedAt));
      write(LS_CATALOG, state.catalog || {});
      write(LS_REMOVED, state.removed || {});
      /* Removing something is this device's decision. Keep the tombstones it
       * holds even if the reply does not carry them back, so a failed or
       * half-merged sync cannot quietly re-add the film. */
      const synced = Object.assign({}, state.dropped || {});
      const local = getDropped();
      Object.keys(local).forEach((id) => {
        if ((local[id] || 0) > (synced[id] || 0)) synced[id] = local[id];
      });
      write(LS_DROPPED, synced);
      applyPrefs(state.prefs);
      paint();
    })
    .catch(() => {
      /* Offline browsing remains available when the account server is down. */
    });
}

function updateAuthUi(account, message) {
  const guest = document.querySelector("[data-auth-guest]");
  const signedIn = document.querySelector("[data-auth-user]");
  const name = document.querySelector("[data-auth-name]");
  const status = document.querySelector("[data-auth-status]");
  const loggedIn = !!(account && account.authenticated);
  if (guest) {
    guest.hidden = loggedIn;
    if (loggedIn) guest.setAttribute("hidden", "hidden");
    else guest.removeAttribute("hidden");
  }
  if (signedIn) {
    signedIn.hidden = !loggedIn;
    if (loggedIn) signedIn.removeAttribute("hidden");
    else signedIn.setAttribute("hidden", "hidden");
  }
  if (name) name.textContent = loggedIn ? account.user.display : "";
  if (status) {
    status.textContent = message || "";
    status.className = "auth-status" + (message ? " good" : "");
  }
}

function wireAuth() {
  fetch("/auth/me", { credentials: "same-origin" })
    .then((response) => response.json())
    .then((account) => updateAuthUi(account))
    .catch(() => updateAuthUi({ authenticated: false }));

  document.addEventListener("submit", (event) => {
    const form = event.target.closest("[data-auth-form]");
    if (!form) return;
    event.preventDefault();
    const data = Object.fromEntries(new FormData(form).entries());
    fetch(form.action, {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data)
    })
      .then(async (response) => {
        const result = await response.json();
        if (!response.ok) throw new Error(result.error || "Could not sign in.");
        return result;
      })
      .then((account) => {
        form.reset();
        updateAuthUi(account, "Signed in. Your library is syncing.");
        syncAccount();
      })
      .catch((error) => updateAuthUi({ authenticated: false }, error.message));
  });

  document.addEventListener("click", (event) => {
    const button = event.target.closest("[data-auth-logout]");
    if (!button) return;
    fetch("/auth/logout", { method: "POST", credentials: "same-origin" })
      .then(() => {
        updateAuthUi({ authenticated: false }, "You are signed out.");
        paint();
      });
  });
}

/* ----------------------------------------------------------------- wiring */

document.addEventListener("click", function (event) {
  const btn = event.target.closest("[data-action]");
  if (btn) {
    const action = btn.dataset.action;
    if (action === "toggle") {
      const card = btn.closest("[data-id]");
      if (card) {
        const listHref = card.dataset.listHref || "";
        toggleList({
          id: listIdOf(card),
          title: card.dataset.title,
          cover: card.dataset.cover,
          url: listHref || card.dataset.url,
          href: listHref || card.dataset.href,
          year: card.dataset.year,
          lang: card.dataset.lang
        });
      }
    } else if (action === "drop") {
      const card = btn.closest("[data-id]");
      if (card) dropFromContinue(card.dataset.id);
    } else if (action === "clear-continue") {
      setContinueConfirm(true);
    } else if (action === "confirm-clear-continue") {
      clearContinueWatching();
    } else if (action === "cancel-clear-continue") {
      setContinueConfirm(false);
    } else if (action === "clear-watchlist") {
      const removed = getRemoved();
      getList().forEach((item) => {
        if (item && item.id) removed[item.id] = Date.now();
      });
      write(LS_REMOVED, removed);
      setList([]);
    } else if (action === "copy") {
      const text = btn.dataset.copy || "";
      if (navigator.clipboard && text) {
        navigator.clipboard.writeText(text).catch(function () {});
      }
      const label = btn.textContent;
      btn.textContent = "Copied";
      window.setTimeout(function () {
        btn.textContent = label;
      }, 1600);
    } else if (action === "clear-search") {
      const form = btn.closest("form");
      const field = form && form.querySelector('input[name="q"]');
      if (field) {
        field.value = "";
        field.dispatchEvent(new Event("input"));
        field.focus();
      }
    } else if (action === "clear-all") {
      [LS_LIST, LS_PROGRESS, LS_WATCHED, LS_CATALOG, LS_REMOVED, LS_DROPPED].forEach((k) =>
        localStorage.removeItem(k));
      paint();
    }
    syncAccount();
    return;
  }

  const arrow = event.target.closest("[data-scroll]");
  if (arrow) {
    const shelf = arrow.closest(".shelf");
    const rail = shelf && shelf.querySelector(".rail");
    const ctl = rail && rails.get(rail);
    if (ctl) {
      ctl.glide(rail.scrollLeft +
        Number(arrow.dataset.scroll) * rail.clientWidth * 0.85);
    }
  }
});

document.addEventListener("input", function (event) {
  const input = event.target;
  if (!input.matches || !input.matches('.search-field input[name="q"]')) return;
  const btn = input.parentElement.querySelector('[data-action="clear-search"]');
  if (btn) btn.hidden = !input.value;
});

document.querySelectorAll('.search-field input[name="q"]').forEach((input) => {
  const btn = input.parentElement.querySelector('[data-action="clear-search"]');
  if (btn) btn.hidden = !input.value;
});

/* The player frame is covered by a poster until it is asked for, so a
 * half-painted player never lands on the page. */
document.addEventListener("click", function (event) {
  const gate = event.target.closest('[data-action="reveal-embed"]');
  if (!gate) return;
  const player = gate.closest(".player");
  if (player) player.classList.add("playing");
});

/* ------------------------------------------------------------ home rows */

/* The rows of the home page in the order somebody chose on /settings. Kept in
 * this browser beside the list: which shelf you want first is a preference,
 * not something to carry to another device. */
const HOME_ROWS_KEY = "iml:home-rows";

function savedRows() {
  try {
    const raw = JSON.parse(localStorage.getItem(HOME_ROWS_KEY) || "[]");
    return Array.isArray(raw)
      ? raw.filter((row) => row && typeof row.id === "string")
      : [];
  } catch (e) {
    return [];
  }
}

function storeRows(rows) {
  try {
    localStorage.setItem(HOME_ROWS_KEY, JSON.stringify(rows));
  } catch (e) {
    /* private mode: the choice lasts this page only */
  }
}

/* Hide and reorder the server-rendered shelves. A row the saved order has
 * never seen keeps its shipped place, after the ones it knows. */
function applyHomeRows() {
  const host = document.querySelector("[data-rows]");
  if (!host) return;
  const rows = savedRows();
  if (!rows.length) return;

  const sections = new Map();
  host.querySelectorAll("[data-row]").forEach((node) => {
    sections.set(node.dataset.row, node);
  });

  const placed = new Set();
  rows.forEach((row) => {
    const node = sections.get(row.id);
    if (!node) return;
    node.hidden = row.on === false;
    host.appendChild(node);
    placed.add(row.id);
  });
  sections.forEach((node, id) => {
    if (!placed.has(id)) host.appendChild(node);
  });
}

function wireRowSettings() {
  const list = document.querySelector("[data-row-list]");
  if (!list) return;

  const items = [...list.querySelectorAll("[data-row-id]")];
  const defaults = items.map((li) => ({
    id: li.dataset.rowId,
    title: li.dataset.rowTitle,
    on: true
  }));
  const shipped = new Map(defaults.map((row) => [row.id, row]));

  let rows = [];

  /* Rebuilt from storage when another device's order arrives mid-visit. */
  function reload() {
    rows = [];
    savedRows().forEach((row) => {
      if (!shipped.has(row.id) || rows.some((one) => one.id === row.id)) return;
      rows.push({
        id: row.id,
        title: shipped.get(row.id).title,
        on: row.on !== false
      });
    });
    defaults.forEach((row) => {
      if (!rows.some((one) => one.id === row.id)) rows.push(row);
    });
    paintRows();
  }

  reload();

  function paintRows() {
    rows.forEach((row) => {
      const li = list.querySelector('[data-row-id="' + row.id + '"]');
      if (!li) return;
      const box = li.querySelector("input");
      if (box) box.checked = row.on !== false;
      list.appendChild(li);
    });
  }

  function save() {
    storeRows(rows);
    touchPrefs();
    syncAccount();
    paintRows();
  }

  list.addEventListener("change", (event) => {
    const box = event.target;
    if (box.type !== "checkbox") return;
    const li = box.closest("[data-row-id]");
    if (!li) return;
    const row = rows.find((one) => one.id === li.dataset.rowId);
    if (!row) return;
    row.on = box.checked;
    save();
  });

  list.addEventListener("click", (event) => {
    const button = event.target.closest("[data-move]");
    if (!button) return;
    const li = button.closest("[data-row-id]");
    const index = rows.findIndex((one) => one.id === li.dataset.rowId);
    const next = index + Number(button.dataset.move);
    if (index < 0 || next < 0 || next >= rows.length) return;
    const moved = rows.splice(index, 1)[0];
    rows.splice(next, 0, moved);
    save();
    const box = list.querySelector('[data-row-id="' + moved.id + '"] input');
    if (box) box.focus();
  });

  const reset = document.querySelector("[data-rows-reset]");
  if (reset) {
    reset.addEventListener("click", () => {
      rows = defaults.map((row) => Object.assign({}, row));
      save();
    });
  }

  paintRows();
  document.addEventListener("prefs:applied", reload);
}

/* --------------------------------------------------------------- themes */

/* The accent chosen on /settings. The attribute is set by a one-line script in
 * <head> before the first paint, so a reload never flashes the default. */
const THEME_KEY = "iml:theme";

function savedTheme() {
  try {
    return localStorage.getItem(THEME_KEY) || "saffron";
  } catch (e) {
    return "saffron";
  }
}

function applyTheme(name) {
  document.documentElement.setAttribute("data-theme", name || "saffron");
}

function markTheme(name) {
  const list = document.querySelector("[data-theme-list]");
  if (!list) return;
  list.querySelectorAll("[data-theme-option]").forEach((button) => {
    button.setAttribute(
      "aria-pressed",
      button.dataset.themeOption === name ? "true" : "false"
    );
  });
}

function wireTheme() {
  const list = document.querySelector("[data-theme-list]");
  if (!list) return;

  markTheme(savedTheme());
  list.addEventListener("click", (event) => {
    const button = event.target.closest("[data-theme-option]");
    if (!button) return;
    const name = button.dataset.themeOption;
    applyTheme(name);
    try {
      localStorage.setItem(THEME_KEY, name);
    } catch (e) {
      /* private mode: the choice lasts this page only */
    }
    touchPrefs();
    syncAccount();
    markTheme(name);
  });
}

/* ---------------------------------------------- carousel speed setting */

function wireDwell() {
  const input = document.querySelector("[data-dwell-input]");
  if (!input) return;

  const show = () => {
    input.value = String(savedDwell());
  };

  const save = () => {
    const seconds = dwellValue(input.value);
    input.value = String(seconds);
    storeDwell(seconds);
    touchPrefs();
    syncAccount();
  };

  show();
  input.addEventListener("change", save);
  /* number fields do not always commit on blur, so save as they type too */
  let pending = 0;
  input.addEventListener("input", () => {
    window.clearTimeout(pending);
    pending = window.setTimeout(save, 500);
  });
  input.addEventListener("keydown", (event) => {
    if (event.key !== "Enter") return;
    event.preventDefault();
    window.clearTimeout(pending);
    save();
  });
  const reset = document.querySelector("[data-dwell-reset]");
  if (reset) {
    reset.addEventListener("click", () => {
      input.value = String(DWELL_DEFAULT);
      save();
    });
  }
  document.addEventListener("prefs:applied", show);
}

normaliseList();
paint();
wireAuth();
syncAccount();
applyTheme(savedTheme());
wirePlayer();
wirePlayer();
wireRails();
wireBar();
wireBillboard();
applyHomeRows();
wireRowSettings();
wireTheme();
wireDwell();
window.addEventListener("pageshow", () => {
  paint();
  wireRails();
});

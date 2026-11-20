/*
 * RogFlix on a television: four arrows, OK, and Back.
 *
 * The site is built for a pointer, so this adds what a remote needs — a focus
 * ring that moves by where things are on screen rather than by document order,
 * OK to press whatever holds the ring, and Back to leave a film or a page. It is
 * only loaded when the /tv cookie is set.
 *
 * Kept to syntax every Tizen browser has had since Chromium 56, because a 2018
 * television is still a television.
 */
(function () {
  "use strict";

  var SELECTOR = [
    "a[href]",
    "button:not([disabled])",
    "input:not([type=hidden])",
    "select",
    "textarea",
    /* Iframes are not stops of their own: a film is entered from the player box
     * that holds it, and only for the counted hand-over below. */
    "video",
    "[tabindex]:not([tabindex='-1'])"
  ].join(",");

  var KEYCODE = {
    13: "ok",
    37: "left",
    38: "up",
    39: "right",
    40: "down",
    8: "back",
    27: "back",
    10009: "back",
    415: "play",
    19: "pause",
    10252: "play"
  };

  var KEYNAME = {
    Enter: "ok",
    ArrowLeft: "left",
    ArrowUp: "up",
    ArrowRight: "right",
    ArrowDown: "down",
    Backspace: "back",
    Escape: "back",
    MediaPlay: "play",
    MediaPlayPause: "play",
    MediaPause: "pause"
  };

  var playerMode = false;
  var playerEl = null;
  var hint = null;
  /* How long somebody else's player may keep the keyboard. See handOver(). */
  var HANDOFF_MS = 15000;
  var frameMode = false;
  var handoffClock = null;

  /* ---------------------------------------------------------------- geometry */

  function rect(el) {
    return el.getBoundingClientRect();
  }

  function centre(el) {
    var r = rect(el);
    return { x: r.left + r.width / 2, y: r.top + r.height / 2 };
  }

  /* Things a remote presses. A container is a way of moving a row with a
   * keyboard, not a stop of its own. */
  var TARGET = /^(A|BUTTON|INPUT|SELECT|TEXTAREA|VIDEO|IFRAME)$/;

  function usable(el) {
    if (!el || el.disabled) return false;
    if (el.getAttribute && el.getAttribute("aria-hidden") === "true") return false;
    if (el.closest && el.closest("[hidden]")) return false;
    /* The row is never a stop, a poster is. An empty row ("Nothing saved yet")
     * otherwise collected the ring as one long bar with nothing to press. */
    if (el.classList && el.classList.contains("rail")) return false;
    /* The rails carry tabindex=0 so a keyboard can scroll them; landing the ring
     * on the row itself hid every poster behind an invisible outline. */
    if (el.getAttribute && el.getAttribute("tabindex") !== null &&
        !TARGET.test(el.tagName) &&
        el.querySelector("a[href], button, input, iframe, video")) return false;
    var style = window.getComputedStyle(el);
    if (style.display === "none" || style.visibility === "hidden") return false;
    if (parseFloat(style.opacity) === 0) return false;
    var r = rect(el);
    return r.width > 8 && r.height > 8;
  }

  function candidates() {
    var found = document.querySelectorAll(SELECTOR);
    var out = [];
    for (var i = 0; i < found.length; i++) {
      if (usable(found[i])) out.push(found[i]);
    }
    return out;
  }

  function overlap(a1, a2, b1, b2) {
    return Math.min(a2, b2) - Math.max(a1, b1);
  }

  /*
   * Nearest thing in a direction, but only among what shares a band with the
   * current one: a row is an unbroken line of posters, and stepping Right into
   * the row above or below it reads as a misfire. Up and Down prefer what is
   * stacked over the current element and fall back to the nearest target so the
   * nav bar above the page stays reachable.
   */
  function best(from, direction) {
    var a = rect(from);
    var origin = centre(from);
    var list = candidates();
    var sideways = direction === "left" || direction === "right";
    var aligned = null;
    var alignedScore = Infinity;
    var any = null;
    var anyScore = Infinity;

    for (var i = 0; i < list.length; i++) {
      var el = list[i];
      if (el === from) continue;
      var r = rect(el);
      var c = { x: r.left + r.width / 2, y: r.top + r.height / 2 };
      var dx = c.x - origin.x;
      var dy = c.y - origin.y;
      var forward;
      var across;
      var band;

      /* The "+" sits on the poster and would keep Up/Down bouncing inside the
       * same card instead of climbing to the row above. It stays reachable
       * sideways. */
      if (!sideways && from.closest && el.closest) {
        var here = from.closest(".card");
        if (here && here === el.closest(".card")) continue;
      }

      if (sideways) {
        forward = direction === "left" ? -dx : dx;
        across = Math.abs(dy);
        band = overlap(a.top, a.bottom, r.top, r.bottom);
      } else {
        forward = direction === "up" ? -dy : dy;
        across = Math.abs(dx);
        band = overlap(a.left, a.right, r.left, r.right);
      }

      if (forward < 8) continue;
      var score = forward + across * 2.5;
      if (band > 0 && score < alignedScore) { alignedScore = score; aligned = el; }
      if (score < anyScore) { anyScore = score; any = el; }
    }

    if (aligned) return aligned;
    /* Right at the end of a row: stay put rather than jump to another shelf. */
    if (sideways) return null;
    return any;
  }

  /*
   * Bring a stop into view without asking scrollIntoView to guess. It also
   * scrolls ancestor scrollers sideways, and with a page this wide the whole
   * document drifted left until the ring sat off the screen at x=-931 while the
   * remote was pressing Right. Vertically the page moves, horizontally only the
   * row under the ring does.
   */
  function reveal(el) {
    var r = rect(el);
    var vh = window.innerHeight || 1080;
    /* The nav is fixed to the top of the screen, so the usual clearance for it
     * would scroll the page every time the ring reached it, lifting the row back
     * above the header for the next Up. */
    var guard = (el.closest && el.closest(".nav")) ? 0 : 96;
    if (r.top < guard || r.bottom > vh - 48) {
      var top = (window.pageYOffset || window.scrollY || 0) + r.top -
        Math.max(24, (vh - r.height) / 2);
      window.scrollTo(0, Math.max(0, top));
    }
    var box = el.parentElement;
    while (box && box !== document.body) {
      var style = window.getComputedStyle(box);
      if (box.scrollWidth > box.clientWidth + 4 &&
          (style.overflowX === "auto" || style.overflowX === "scroll")) break;
      box = box.parentElement;
    }
    if (box && box !== document.body) {
      var br = rect(box);
      if (r.left < br.left + 8 || r.right > br.right - 8) {
        box.scrollLeft = box.scrollLeft + (r.left - br.left) -
          (br.width - r.width) / 2;
      }
    }
  }

  function focus(el, keepStill) {
    if (!el) return false;
    // The ring is drawn from an attribute as well as :focus, because :focus only
    // matches while the document itself has focus — which is not something to
    // rely on when a television hands the window to something else.
    var previous = document.querySelector("[data-tv-focus]");
    if (previous && previous !== el) previous.removeAttribute("data-tv-focus");
    el.setAttribute("data-tv-focus", "");
    try {
      el.focus({ preventScroll: true });
    } catch (error) {
      el.focus();
    }
    if (!keepStill) reveal(el);
    return true;
  }

  function firstStop() {
    var main = document.querySelector("main") || document.body;
    var list = candidates();
    var i;
    for (i = 0; i < list.length; i++) {
      if (main.contains(list[i])) return list[i];
    }
    return list.length ? list[0] : null;
  }

  /* ------------------------------------------------------------------- hint */

  function showHint(text) {
    if (!hint) {
      hint = document.createElement("div");
      hint.className = "tv-hint";
      hint.setAttribute("role", "status");
      document.body.appendChild(hint);
    }
    hint.textContent = text;
    hint.hidden = false;
  }

  function hideHint() {
    if (hint) hint.hidden = true;
  }

  /* ----------------------------------------------------------------- player */

  function playerBox() {
    return document.querySelector(".player");
  }

  function filmFrame() {
    var box = playerBox();
    return (box && box.querySelector("iframe")) || document.querySelector("#player");
  }

  /* Our own film page is on this origin, so the video inside it is a thing this
   * page can read and drive. Somebody else's player is not: asking for its
   * document throws. */
  function ownFilm() {
    var frame = filmFrame();
    if (!frame) return null;
    try {
      var doc = frame.contentDocument;
      return doc ? doc.querySelector("video") : null;
    } catch (error) {
      return null;
    }
  }

  function frameIsOurs(frame) {
    if (!frame) return false;
    try {
      return new URL(frame.src, location.href).origin === location.origin;
    } catch (error) {
      return false;
    }
  }

  function stamp(seconds) {
    seconds = Math.max(0, Math.round(seconds || 0));
    var minutes = Math.floor(seconds / 60);
    var rest = seconds % 60;
    return minutes + ":" + (rest < 10 ? "0" : "") + rest;
  }

  function toggleFilm(video) {
    if (video.paused) {
      var started = video.play();
      if (started && started.catch) started.catch(function () { /* refused */ });
      showHint("Playing · BACK leaves the film");
    } else {
      video.pause();
      showHint("Paused · OK resumes · BACK leaves");
    }
  }

  /* Arrows scrub our own film and Up/Down move its volume, rather than stepping
   * the ring off a film that is already on the screen. */
  function filmKeys(video, action) {
    if (action === "left" || action === "right") {
      var step = action === "left" ? -10 : 10;
      var length = isFinite(video.duration) ? video.duration : Infinity;
      var at = Math.min(Math.max(0, (video.currentTime || 0) + step), length);
      try {
        video.currentTime = at;
      } catch (error) {
        showHint("The film will not jump yet");
        return;
      }
      showHint((step < 0 ? "10 seconds back · " : "10 seconds on · ") + stamp(at));
      return;
    }
    var up = action === "up";
    var volume = Math.min(1, Math.max(0, (video.volume || 0) + (up ? 0.1 : -0.1)));
    video.volume = volume;
    video.muted = false;
    showHint("Volume " + Math.round(volume * 100) + "%");
  }

  /*
   * The film itself lives in someone else's iframe. Focus goes to the frame
   * around it, which this page owns, because a focus inside the frame is a
   * focus the remote can never leave: the keys are delivered there, so Back
   * stops working and the viewer is stuck in a black rectangle.
   */
  function enterPlayer() {
    var box = playerBox();
    if (!box) return false;
    if (!box.hasAttribute("tabindex")) box.setAttribute("tabindex", "-1");
    playerEl = box;
    playerMode = true;
    focus(box, true);
    showHint(ownFilm()
      ? "Arrows seek · Up/Down volume · OK pauses · BACK leaves"
      : "OK hands the remote to the film · BACK leaves");
    return true;
  }

  /*
   * Somebody else's player takes the keyboard and never gives it back: with the
   * frame focused, neither Escape nor Tab reaches this page again, so a plain
   * hand-over would leave the remote dead inside a black rectangle. The hand-over
   * is counted instead — the film gets the keys, the page counts them down, and
   * the ring comes back on its own.
   */
  function handOver() {
    var frame = filmFrame();
    if (!frame || frameMode) return false;
    if (!frame.hasAttribute("tabindex")) frame.setAttribute("tabindex", "0");
    frameMode = true;
    var until = Date.now() + HANDOFF_MS;
    try {
      frame.focus();
    } catch (error) {
      /* the countdown still runs, and still hands the remote back */
    }
    var tick = function () {
      var left = Math.max(0, Math.ceil((until - Date.now()) / 1000));
      if (left <= 0) {
        takeBack();
        return;
      }
      showHint("The film has the remote · back in " + left + "s");
    };
    tick();
    handoffClock = setInterval(tick, 500);
    return true;
  }

  function takeBack() {
    if (!frameMode) return;
    frameMode = false;
    if (handoffClock) {
      clearInterval(handoffClock);
      handoffClock = null;
    }
    var frame = filmFrame();
    if (frame) {
      try {
        frame.blur();
      } catch (error) {
        /* nothing to take back */
      }
    }
    var box = playerBox();
    if (box) {
      playerEl = box;
      playerMode = true;
      focus(box, true);
    }
    showHint("OK takes the remote into the film again · BACK leaves");
  }

  function leavePlayer() {
    playerMode = false;
    hideHint();
    var box = playerEl;
    playerEl = null;
    if (box) {
      var stop = box.querySelector("button:not(.gate), a[href]") || firstStop();
      focus(stop);
      return;
    }
    focus(firstStop());
  }

  /* ------------------------------------------------------------------- keys */

  function activate() {
    var el = document.activeElement;
    if (!el || el === document.body) {
      focus(firstStop());
      return;
    }
    if (playerMode && el === playerEl) {
      var film = ownFilm();
      if (film) {
        toggleFilm(film);
        return;
      }
      var frame = filmFrame();
      if (frame && frameIsOurs(frame)) {
        showHint("The film is still loading");
        return;
      }
      handOver();
      return;
    }
    if (typeof el.click === "function") {
      el.click();
      /* The poster gate is what starts a film: press it, then take the remote
       * into the player so Back is the way out rather than the frame's own. */
      if (el.classList && el.classList.contains("gate")) enterPlayer();
    }
  }

  function goBack() {
    if (frameMode) {
      takeBack();
      return;
    }
    if (playerMode) {
      leavePlayer();
      return;
    }
    if (window.history.length > 1) {
      window.history.back();
      return;
    }
    window.location.href = "/tv";
  }

  function onKey(event) {
    var action = KEYCODE[event.keyCode] || KEYNAME[event.key];
    if (!action) return;
    /*
     * The rows animate themselves: motion.js listens for arrow keys on the rail
     * and springs it 85% of its width, which is right for a keyboard and wrong
     * for a remote, where the ring has already moved exactly one poster. Without
     * this the row lurched a page on every press and the chosen film slid out of
     * sight (x=-931). preventDefault alone does not stop a bubbling listener.
     */
    event.stopPropagation();

    var fieldEl = event.target;
    var field = fieldEl && /^(INPUT|TEXTAREA|SELECT)$/.test(fieldEl.tagName);

    if (action === "back") {
      event.preventDefault();
      goBack();
      return;
    }

    if (action === "ok") {
      if (field) return;              /* let the on-screen keyboard send Enter */
      event.preventDefault();
      activate();
      return;
    }

    if (action === "play" || action === "pause") {
      var media = ownFilm() || playerEl || playerTarget();
      if (media && media.tagName === "VIDEO") {
        event.preventDefault();
        if (action === "pause" || (action === "play" && !media.paused)) {
          media.pause();
        } else {
          media.play();
        }
      }
      return;
    }

    /* Left and Right belong to the caret while typing, but Up and Down have to
     * escape the box — otherwise the search results under the field can never
     * be reached with a remote. */
    if (field && (action === "left" || action === "right")) return;
    /* A film on our own page keeps the remote: the arrows scrub it and Up/Down
     * move the volume. Somebody else's player cannot be read that way, so an
     * arrow there is a request to browse again: leave and carry on from where
     * the ring sits. */
    if (playerMode) {
      var mine = ownFilm();
      if (mine && (action === "left" || action === "right" ||
                   action === "up" || action === "down")) {
        event.preventDefault();
        filmKeys(mine, action);
        return;
      }
      leavePlayer();
    }

    event.preventDefault();
    var from = document.activeElement;
    if (!from || from === document.body) {
      focus(firstStop());
      return;
    }
    /* The top bar is the ceiling: from up there, Up stays put instead of
     * bouncing back into the page. */
    if (action === "up" && from.closest && from.closest(".nav")) return;

    var next = best(from, action);
    if (next) focus(next);
  }

  /* -------------------------------------------------------------------- init */

  function registerTizenKeys() {
    try {
      if (window.tizen && tizen.tvinputdevice) {
        tizen.tvinputdevice.registerKeyBatch([
          "MediaPlay", "MediaPause", "MediaPlayPause"
        ]);
      }
    } catch (error) {
      /* not a television, or an old firmware: the keydown fallback is enough */
    }
  }

  function init() {
    registerTizenKeys();
    document.addEventListener("keydown", onKey, true);
    document.addEventListener("mousedown", hideHint, true);

    var here = document.activeElement;
    if (!here || here === document.body) {
      // Scrolled as well as focused: a television that restores its last scroll
      // position would otherwise show the ring above the top of the screen.
      focus(firstStop());
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();

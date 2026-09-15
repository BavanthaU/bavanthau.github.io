/* The pixels-to-map sequence.

   The page ships as a plain numbered sequence: frame, then the paragraph that explains it.
   That is the fallback and it is complete on its own. Where there is room for the sticky
   composition and the reader has not asked for less motion, this turns the frames into one
   stage and lets the notes beside it choose which representation is showing.

   Native scrolling only. Nothing here is hijacked, and nothing is needed to understand it. */
(function () {
  var root = document.querySelector("[data-pxm]");
  if (!root) return;

  var frames = [].slice.call(root.querySelectorAll(".pxm-frame"));
  var notes = [].slice.call(root.querySelectorAll(".pxm-note"));
  var ticks = [].slice.call(root.querySelectorAll(".pxm-tick"));
  if (!frames.length || frames.length !== notes.length) return;

  var wide = window.matchMedia("(min-width: 58em)");
  var still = window.matchMedia("(prefers-reduced-motion: reduce)");
  var live = false;
  var current = -1;
  var queued = false;

  function paint(i) {
    if (i === current) return;
    current = i;
    frames.forEach(function (f, n) {
      var on = n === i;
      f.classList.toggle("is-on", on);
      var v = f.querySelector("[data-step-video]");
      if (!v) return;
      if (on) { v.play().catch(function () {}); } else { v.pause(); }
    });
    notes.forEach(function (n2, n) { n2.classList.toggle("is-on", n === i); });
    ticks.forEach(function (t, n) { t.classList.toggle("is-on", n === i); });
  }

  /* The step showing is the note sitting closest to the middle of the stage. */
  function measure() {
    queued = false;
    if (!live) return;
    var line = window.innerHeight * 0.48;
    var best = 0;
    var bestGap = Infinity;
    for (var i = 0; i < notes.length; i++) {
      var r = notes[i].getBoundingClientRect();
      var gap = Math.abs((r.top + r.bottom) / 2 - line);
      if (gap < bestGap) { bestGap = gap; best = i; }
    }
    paint(best);
  }

  function onScroll() {
    if (queued) return;
    queued = true;
    requestAnimationFrame(measure);
  }

  function enable() {
    if (live) return;
    live = true;
    root.classList.add("is-live");
    addEventListener("scroll", onScroll, { passive: true });
    addEventListener("resize", onScroll, { passive: true });
    current = -1;
    measure();
  }

  function disable() {
    if (!live) return;
    live = false;
    root.classList.remove("is-live");
    removeEventListener("scroll", onScroll);
    removeEventListener("resize", onScroll);
    frames.concat(notes, ticks).forEach(function (el) { el.classList.remove("is-on"); });
    frames.forEach(function (f) {
      var v = f.querySelector("[data-step-video]");
      if (v) v.pause();
    });
    current = -1;
  }

  function decide() {
    if (wide.matches && !still.matches) { enable(); } else { disable(); }
  }

  ["change"].forEach(function (ev) {
    if (wide.addEventListener) {
      wide.addEventListener(ev, decide);
      still.addEventListener(ev, decide);
    }
  });
  decide();
}());

/* The home page opens on the dark instrument ground, so the masthead joins it and hands
   itself back to the page ground once the reader is past the hero. */
(function () {
  var head = document.querySelector(".masthead");
  var dark = document.querySelector(".page-home .hero.ground-dark");
  if (!head || !dark) return;
  var queued = false;

  function apply() {
    queued = false;
    var edge = dark.getBoundingClientRect().bottom;
    head.classList.toggle("over-dark", edge > head.offsetHeight * 0.75);
  }
  function onScroll() {
    if (queued) return;
    queued = true;
    requestAnimationFrame(apply);
  }
  addEventListener("scroll", onScroll, { passive: true });
  addEventListener("resize", onScroll, { passive: true });
  apply();
}());

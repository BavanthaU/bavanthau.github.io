/* Progressive enhancement only. Every component below works without this file:
   videos show their poster with native controls off, the wipe shows three frames side by side,
   and the YouTube facade is a link-shaped button that does nothing until this runs. */
(function () {
  "use strict";

  var reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* ---- autoplay loops only while visible, and never under reduced motion ---- */
  var loops = document.querySelectorAll("video[data-autoloop]");
  if (loops.length && !reduced && "IntersectionObserver" in window) {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        var v = en.target;
        if (en.intersectionRatio >= 0.4) {
          if (v.paused && !v.dataset.userPaused) v.play().catch(function () {});
        } else if (!v.paused) {
          v.pause();
        }
      });
    }, { threshold: [0, 0.4, 1] });
    loops.forEach(function (v) { io.observe(v); });
  }

  /* ---- visible play and pause control, keyboard reachable ---- */
  document.querySelectorAll("[data-toggle]").forEach(function (btn) {
    var v = btn.parentNode.querySelector("video");
    if (!v) return;
    var sync = function () {
      var playing = !v.paused;
      btn.textContent = playing ? "Pause" : "Play";
      btn.setAttribute("aria-pressed", playing ? "true" : "false");
    };
    btn.addEventListener("click", function () {
      if (v.paused) { v.dataset.userPaused = ""; delete v.dataset.userPaused; v.play().catch(function () {}); }
      else { v.pause(); v.dataset.userPaused = "1"; }
      sync();
    });
    v.addEventListener("play", sync);
    v.addEventListener("pause", sync);
    sync();
  });

  /* ---- click to load for anything heavy ---- */
  document.querySelectorAll("[data-gate]").forEach(function (gate) {
    var btn = gate.querySelector("[data-gate-btn]");
    var tpl = gate.querySelector("[data-gate-src]");
    if (!btn || !tpl) return;
    btn.addEventListener("click", function () {
      var wrap = document.createElement("div");
      wrap.className = "v-wrap";
      wrap.innerHTML = tpl.textContent;
      var v = wrap.querySelector("video");
      gate.parentNode.replaceChild(wrap, gate);
      if (v) {
        v.setAttribute("controls", "");
        v.removeAttribute("preload");
        v.play().catch(function () {});
      }
    });
  });

  /* ---- RGB to depth to semantics ---- */
  document.querySelectorAll("[data-wipe]").forEach(function (fig) {
    var panes = fig.querySelectorAll("[data-pane]");
    var control = fig.querySelector("[data-wipe-control]");
    var input = fig.querySelector("[data-wipe-input]");
    if (panes.length !== 3 || !input) return;

    fig.classList.add("is-interactive");
    control.hidden = false;

    var apply = function (v) {
      // 0 to 100 blends RGB into depth, 100 to 200 blends depth into semantics
      var a = v <= 100 ? 1 - v / 100 : 0;
      var b = v <= 100 ? v / 100 : 1 - (v - 100) / 100;
      var c = v <= 100 ? 0 : (v - 100) / 100;
      panes[0].style.opacity = a;
      panes[1].style.opacity = b;
      panes[2].style.opacity = c;
    };
    input.addEventListener("input", function () { apply(+input.value); });
    apply(+input.value);
  });

  /* ---- YouTube facade: no third-party request until the visitor asks ---- */
  document.querySelectorAll("[data-yt]").forEach(function (fig) {
    var btn = fig.querySelector("[data-yt-btn]");
    var id = fig.getAttribute("data-yt");
    if (!btn || !id) return;
    btn.addEventListener("click", function () {
      var frame = document.createElement("iframe");
      frame.src = "https://www.youtube-nocookie.com/embed/" + id + "?autoplay=1&rel=0";
      frame.title = "Video player";
      frame.loading = "lazy";
      frame.allow = "accelerometer; autoplay; encrypted-media; picture-in-picture";
      frame.allowFullscreen = true;
      frame.className = "yt-frame";
      btn.parentNode.replaceChild(frame, btn);
    });
  });
})();

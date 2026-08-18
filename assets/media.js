/* Progressive enhancement only. Every component below works without this file:
   videos show their poster with native controls off, the wipe shows three frames side by side,
   and the YouTube facade is a link-shaped button that does nothing until this runs. */
(function () {
  "use strict";

  /* ---- explicit theme control, with the system preference as the default ---- */
  var themeButton = document.querySelector("[data-theme-toggle]");
  if (themeButton) {
    var root = document.documentElement;
    var label = themeButton.querySelector("[data-theme-label]");
    var systemDark = window.matchMedia("(prefers-color-scheme: dark)");

    var activeTheme = function () {
      return root.dataset.theme || (systemDark.matches ? "dark" : "light");
    };
    var syncTheme = function () {
      var current = activeTheme();
      var next = current === "dark" ? "light" : "dark";
      if (label) label.textContent = next.charAt(0).toUpperCase() + next.slice(1);
      themeButton.setAttribute("aria-label", "Switch to " + next + " theme");
      themeButton.setAttribute("title", "Switch to " + next + " theme");
    };

    themeButton.hidden = false;
    syncTheme();
    themeButton.addEventListener("click", function () {
      var next = activeTheme() === "dark" ? "light" : "dark";
      root.dataset.theme = next;
      try { localStorage.setItem("theme", next); } catch (e) {}
      syncTheme();
    });
    systemDark.addEventListener && systemDark.addEventListener("change", function () {
      if (!root.dataset.theme) syncTheme();
    });
  }

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

/* Segmented switcher. Without this the panels simply stack, which is a valid page. */
(function () {
  "use strict";
  document.querySelectorAll("[data-switch]").forEach(function (root) {
    var tabsBox = root.querySelector("[data-switch-tabs]");
    var tabs = Array.prototype.slice.call(root.querySelectorAll("[data-switch-tab]"));
    var panels = Array.prototype.slice.call(root.querySelectorAll("[data-switch-panel]"));
    if (!tabsBox || tabs.length !== panels.length || tabs.length < 2) return;

    tabsBox.hidden = false;
    root.classList.add("is-switchable");

    var show = function (i) {
      tabs.forEach(function (t, n) {
        t.setAttribute("aria-selected", n === i ? "true" : "false");
        t.tabIndex = n === i ? 0 : -1;
      });
      panels.forEach(function (p, n) {
        p.hidden = n !== i;
        if (n !== i) {
          var v = p.querySelector("video");
          if (v && !v.paused) v.pause();
        }
      });
    };

    tabs.forEach(function (t, i) {
      t.addEventListener("click", function () { show(i); });
      t.addEventListener("keydown", function (ev) {
        var d = ev.key === "ArrowRight" ? 1 : ev.key === "ArrowLeft" ? -1 : 0;
        if (!d) return;
        ev.preventDefault();
        var next = (i + d + tabs.length) % tabs.length;
        show(next);
        tabs[next].focus();
      });
    });
    show(0);
  });
})();

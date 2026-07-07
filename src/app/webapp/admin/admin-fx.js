/* V4 Lava Lamp Terminal FX — lava DOM + gooey filter + pointer 3D tilt.
   Self-contained: inject everything, no HTML edits beyond the script tag.
   Guards: reduced motion, coarse pointer (no tilt), weak device (perf-lite). */
(() => {
  "use strict";

  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const finePointer = window.matchMedia("(pointer: fine)").matches;
  const weakDevice =
    (navigator.deviceMemory && navigator.deviceMemory < 4) ||
    (navigator.connection && navigator.connection.saveData);
  if (weakDevice) document.documentElement.classList.add("perf-lite");

  /* ---- lava lamp (CSS metaball, matches the user dashboard) ----
     The proven recipe from the dashboard: semi-transparent brand blobs inside a
     container with `filter: blur() contrast()`. The heavy blur softens edges and
     the contrast() crushes them back so overlapping blobs PULL TOGETHER like
     water drops — a real gooey merge, no SVG filter (which failed to merge on
     mobile). Each blob also morphs its border-radius for organic squish. */
  function injectLava() {
    if (document.getElementById("astro-lava")) return;

    const lava = document.createElement("div");
    lava.id = "astro-lava";
    lava.setAttribute("aria-hidden", "true");
    lava.innerHTML =
      '<div class="glow"></div>' +
      '<div class="goo">' +
      '<i class="lava-blob lava-blob-1"></i><i class="lava-blob lava-blob-2"></i>' +
      '<i class="lava-blob lava-blob-3"></i><i class="lava-blob lava-blob-4"></i>' +
      '<i class="lava-blob lava-blob-5"></i>' +
      "</div>";

    document.body.prepend(lava);

    // Slow pointer parallax on the whole lamp (desktop only).
    if (finePointer && !reduceMotion) {
      let raf = 0;
      window.addEventListener(
        "pointermove",
        (e) => {
          if (raf) return;
          raf = requestAnimationFrame(() => {
            raf = 0;
            const nx = e.clientX / window.innerWidth - 0.5;
            const ny = e.clientY / window.innerHeight - 0.5;
            lava.style.setProperty("--lava-px", (nx * -26).toFixed(1));
            lava.style.setProperty("--lava-py", (ny * -18).toFixed(1));
          });
        },
        { passive: true }
      );
    }
  }

  /* ---- pointer 3D tilt ----
     Restrained to the LOGIN card only. Tilting every data card read as a
     gimmick and fought the "precise utility" product register (decorative
     motion that conveys no state). The login screen is a single signature
     moment with no data to read, so it earns the effect. */
  const TILT_SELECTOR = ".login-card";
  const MAX_H = 640; // login card can be tall
  const MAX_TILT = 5;

  function ensureGlare(el) {
    let g = el.querySelector(":scope > .fx-glare");
    if (!g) {
      g = document.createElement("i");
      g.className = "fx-glare";
      el.appendChild(g);
    }
    return g;
  }

  function attachTilt() {
    let current = null;
    let raf = 0;

    function reset(el) {
      el.classList.remove("fx-active");
      el.style.setProperty("--tiltX", "0");
      el.style.setProperty("--tiltY", "0");
      el.style.setProperty("--tiltZ", "0");
      el.style.setProperty("--glareO", "0");
    }

    document.addEventListener(
      "pointermove",
      (e) => {
        const hit = e.target && e.target.closest ? e.target.closest(TILT_SELECTOR) : null;

        if (current && current !== hit) {
          reset(current);
          current = null;
        }
        if (!hit) return;
        const r = hit.getBoundingClientRect();
        if (r.height > MAX_H) return;

        current = hit;
        if (raf) return;
        raf = requestAnimationFrame(() => {
          raf = 0;
          if (!current) return;
          const rect = current.getBoundingClientRect();
          const px = (e.clientX - rect.left) / rect.width;   // 0..1
          const py = (e.clientY - rect.top) / rect.height;
          const strong = current.classList.contains("login-card") ? 1.6 : 1;
          current.classList.add("fx-tilt", "fx-active");
          ensureGlare(current);
          current.style.setProperty("--tiltY", ((px - 0.5) * 2 * MAX_TILT * strong).toFixed(2));
          current.style.setProperty("--tiltX", ((0.5 - py) * 2 * MAX_TILT * strong).toFixed(2));
          current.style.setProperty("--tiltZ", "8");
          current.style.setProperty("--glareX", (px * 100).toFixed(1));
          current.style.setProperty("--glareY", (py * 100).toFixed(1));
          current.style.setProperty("--glareO", "1");
        });
      },
      { passive: true }
    );

    document.addEventListener(
      "pointerout",
      (e) => {
        if (!current) return;
        const to = e.relatedTarget;
        if (!to || !current.contains(to)) {
          reset(current);
          current = null;
        }
      },
      { passive: true }
    );
  }

  /* ---- Telegram WebApp: lock fullscreen + kill swipe-to-minimize ----
     Telegram's Close/⋯ chrome floats over the webview top (published as
     --tg-safe-top so the header can clear it). We also:
       - expand() + requestFullscreen() so the app opens locked to full height
         (mobile only — desktop Telegram has no true fullscreen and it just
         makes the window jump);
       - disableVerticalSwipes() so dragging down from the top no longer
         minimizes/closes the mini app (the reported bug). */
  function initTelegramSafeArea() {
    const tg = window.Telegram && window.Telegram.WebApp;
    if (!tg) return;

    const platform = tg.platform ? String(tg.platform).toLowerCase() : "";
    const ua = (navigator.userAgent || "").toLowerCase();
    const isDesktop =
      /tdesktop|macos|linux|web|windows|desktop/.test(platform) ||
      (!/android|iphone|ipad|ipod/.test(ua) && window.innerWidth > 768);

    try { tg.ready(); } catch (_) { /* ignore */ }

    const expand = () => { try { if (typeof tg.expand === "function") tg.expand(); } catch (_) { /* ignore */ } };
    const stopSwipes = () => { try { if (typeof tg.disableVerticalSwipes === "function") tg.disableVerticalSwipes(); } catch (_) { /* ignore */ } };
    const goFullscreen = () => {
      if (isDesktop) return;
      try { if (typeof tg.requestFullscreen === "function") tg.requestFullscreen(); } catch (_) { /* ignore */ }
      try { if (tg.viewport && typeof tg.viewport.requestFullscreen === "function") tg.viewport.requestFullscreen(); } catch (_) { /* ignore */ }
    };

    expand();
    setTimeout(expand, 300);      // some clients ignore the first expand pre-ready
    stopSwipes();
    goFullscreen();

    // blend the Telegram header/background into our dark canvas
    try { if (typeof tg.setBackgroundColor === "function") tg.setBackgroundColor("#0a141b"); } catch (_) { /* ignore */ }
    try { if (typeof tg.setHeaderColor === "function") tg.setHeaderColor("#0a141b"); } catch (_) { /* ignore */ }

    const apply = () => {
      const c = (tg.contentSafeAreaInset && tg.contentSafeAreaInset.top) || 0;
      const s = (tg.safeAreaInset && tg.safeAreaInset.top) || 0;
      let top = Math.max(0, Math.round(c + s));
      // Per-device fallback (same policy as the dashboard's safe-bottom fix):
      // trust a non-zero report; a zero on a fullscreen phone is a client
      // under-report while Telegram's Close/⋯ chrome still floats over the
      // top. Floor it so headers/drawers always clear the chrome — overshoot
      // is a little air, undershoot is buttons under the pill. Only inside a
      // real mobile Telegram in fullscreen (non-fullscreen mode keeps the
      // webview below Telegram's own header, where 0 is genuinely correct).
      if (top <= 0 && tg.isFullscreen && /android|ios/.test(platform)) {
        top = platform.indexOf("ios") === 0 ? 100 : 84;
      }
      document.documentElement.style.setProperty("--tg-safe-top", top + "px");
      document.body.classList.add("in-telegram");
    };
    apply();
    const reassert = () => { apply(); expand(); stopSwipes(); };
    ["safeAreaChanged", "contentSafeAreaChanged", "viewportChanged", "fullscreenChanged"].forEach((ev) => {
      try { tg.onEvent(ev, reassert); } catch (_) { /* ignore */ }
    });
  }

  /* ---- keyboard-aware viewport height ----
     iOS/Telegram webviews don't shrink 100dvh when the keyboard opens; the
     visual viewport does. Publish it as --app-vh so full-height layouts (the
     support chat) can track the keyboard: the composer stays glued above it
     and the thread shrinks instead of the whole page being shoved around. */
  function initVisualViewport() {
    const vv = window.visualViewport;
    if (!vv) return;
    let raf = 0;
    const apply = () => {
      raf = 0;
      document.documentElement.style.setProperty("--app-vh", Math.round(vv.height) + "px");
      // WebKit still shoves the page up to "reveal" the focused input even
      // though our layout already tracks the keyboard — leaves a dead gap
      // above. The support page owns all scrolling (body overflow hidden),
      // so pin the window itself back to the top.
      if (document.body.classList.contains("support-page") && (window.scrollY || window.pageYOffset)) {
        window.scrollTo(0, 0);
      }
    };
    const onResize = () => { if (!raf) raf = requestAnimationFrame(apply); };
    vv.addEventListener("resize", onResize, { passive: true });
    vv.addEventListener("scroll", onResize, { passive: true });
    apply();
  }

  /* ---- battery/heat saver ----
     When the mini app is hidden (Telegram backgrounded, phone locked, chat
     switch) pause every CSS animation via html.astro-hidden. Invisible to the
     user, but stops the GPU compositing the animated lava + glass blur while
     off-screen — a major heat source on always-open sessions. */
  function initVisibilityPause() {
    const root = document.documentElement;
    const apply = () => root.classList.toggle("astro-hidden", document.hidden);
    document.addEventListener("visibilitychange", apply, { passive: true });
    apply();
  }

  function boot() {
    initTelegramSafeArea();
    initVisualViewport();
    initVisibilityPause();
    injectLava();
    if (finePointer && !reduceMotion) attachTilt();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot, { once: true });
  } else {
    boot();
  }
})();

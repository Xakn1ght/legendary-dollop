// Suppress noisy [Telegram.WebView] console spam.
// Set localStorage.astro_tg_console_logs = '1' to re-enable for debugging.
(function () {
  'use strict';
  const KEY = 'astro_tg_console_logs';
  const isEnabled = () => { try { return localStorage.getItem(KEY) === '1'; } catch (_) { return false; } };
  const shouldFilter = (args) => {
    if (isEnabled()) return false;
    const first = args && args.length ? args[0] : null;
    return typeof first === 'string' && first.includes('[Telegram.WebView]');
  };
  const wrap = (name) => {
    try {
      const original = console[name];
      if (typeof original !== 'function') return;
      const bound = original.bind(console);
      console[name] = function (...args) { if (shouldFilter(args)) return; return bound(...args); };
    } catch (_) {}
  };
  wrap('log'); wrap('info'); wrap('debug'); wrap('warn'); wrap('error');
  window.AstroDebug = window.AstroDebug || {};
  window.AstroDebug.isTelegramConsoleLogsEnabled = function () { return isEnabled(); };
  window.AstroDebug.setTelegramConsoleLogs = function (on) {
    try { localStorage.setItem(KEY, on ? '1' : '0'); } catch (_) {}
    try { location.reload(); } catch (_) {}
  };
})();

// Security: if the bot opened the WebApp with a short-lived `?auth=...` token,
    // stash it in sessionStorage and remove it from the visible URL ASAP to reduce leaks
    // (address bar, screenshots, referer, logs).
    (function () {
      try {
        const url = new URL(window.location.href);
        const auth = url.searchParams.get('auth');
        if (auth && auth.length > 10) {
          let stored = false;
          try {
            sessionStorage.setItem('tma_url_auth', auth);
            stored = (sessionStorage.getItem('tma_url_auth') === auth);
          } catch (_) {
            stored = false;
          }
          // Only remove `auth` when we successfully stored it; otherwise keep it in the URL
          // so clients with disabled sessionStorage still work.
          if (stored) {
            url.searchParams.delete('auth');
            // Keep other params (e.g., ticket_id) intact.
            window.history.replaceState({}, document.title, url.pathname + (url.searchParams.toString() ? ('?' + url.searchParams.toString()) : '') + (url.hash || ''));
          }
        }
      } catch (_) {}
    })();

    // SECURITY: Block access if not running in Telegram WebApp
    // This check runs IMMEDIATELY before any other scripts to prevent unauthorized access
    (function(){
      'use strict';
      
      // Telegram-only gate. Accepted signals — each one can only exist after
      // a genuine Telegram launch:
      //   - live initData (Telegram injects it into the WebView)
      //   - tgWebAppData in the URL (some clients pass it this way)
      //   - session cookie / bearer in localStorage (minted by /login after
      //     HMAC-verifying initData; carries auth across internal page hops)
      // NOT accepted: the mere presence of the telegram-web-app.js object
      // (defined in any browser) or bare ?auth= URL tokens (raw-link leak).
      const tg = window.Telegram && window.Telegram.WebApp ? window.Telegram.WebApp : null;
      const hasInitData = !!(tg && tg.initData && tg.initData.length > 10);

      let hasUrlInitData = false;
      try {
        const urlParams = new URLSearchParams(window.location.search);
        const hashParams = new URLSearchParams(window.location.hash.replace(/^#/, ''));
        const fromQuery = urlParams.get('tgWebAppData') || urlParams.get('tg_web_app_data') || urlParams.get('init_data');
        const fromHash = hashParams.get('tgWebAppData') || hashParams.get('tg_web_app_data');
        hasUrlInitData = !!(fromQuery && fromQuery.length > 10) || !!(fromHash && fromHash.length > 10);
      } catch (_) {}

      let hasValidSession = false;
      try {
        const cookies = document.cookie.split(';');
        for (let cookie of cookies) {
          const [name] = cookie.trim().split('=');
          if (name === 'tma_session' || name === 'auth_token') {
            hasValidSession = true;
            break;
          }
        }
      } catch (_) {}

      let hasBearer = false;
      try {
        const bt = localStorage.getItem('tma_bearer_token');
        hasBearer = !!(bt && bt.length > 10);
      } catch (_) {}

      if (!hasInitData && !hasUrlInitData && !hasValidSession && !hasBearer) {
        // document.write() from a parser-inserted script does NOT replace the
        // document (it injects mid-parse), so the app used to keep booting
        // around the block screen. Instead: flag the block for every later
        // script (the React entries refuse to mount on it) and paint an
        // opaque max-z overlay that owns the whole viewport.
        window.__astroBlocked = true;
        try { document.title = 'Access Restricted'; } catch (_) {}
        var blockEl = document.createElement('div');
        blockEl.id = 'astro-access-blocked';
        blockEl.setAttribute('style',
          'position:fixed;inset:0;z-index:2147483647;background:#0d1a22;color:#F9F6EE;' +
          'display:flex;align-items:center;justify-content:center;text-align:center;' +
          'padding:20px;line-height:1.6;font-family:system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;');
        blockEl.innerHTML =
          '<div style="max-width:450px">' +
          '<div style="margin-bottom:20px"><svg viewBox="0 0 24 24" fill="none" stroke="#ec5652" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" width="64" height="64"><rect x="4" y="10" width="16" height="11" rx="2.5"/><path d="M8 10V7a4 4 0 0 1 8 0v3"/><circle cx="12" cy="15.5" r="1.4" fill="#ec5652" stroke="none"/></svg></div>' +
          '<h1 style="color:#ec5652;margin:0 0 20px;font-size:28px;font-weight:700">Access Restricted</h1>' +
          '<p style="margin:12px 0;opacity:.9;font-size:16px">This dashboard can only be accessed through the Telegram Mini App.</p>' +
          '<p style="margin:12px 0;opacity:.9;font-size:16px">Please open this page from within Telegram.</p>' +
          '<p style="margin:12px 0;opacity:.9;font-size:15px" dir="rtl">این داشبورد فقط از داخل تلگرام (مینی‌اپ) قابل دسترسی است.</p>' +
          '</div>';
        // <body> may not exist yet (we run in <head>) — <html> always does.
        (document.body || document.documentElement).appendChild(blockEl);
        // Stop the rest of head-boot (theme/lang boot is pointless now).
        throw new Error('Telegram WebApp required - access blocked');
      }
    })();

    // Apply theme/lang/accent ASAP to avoid a visible flash during boot.
    // data-boot hides content until i18n is applied, preventing a visible double-render.
    (function(){
      try { document.documentElement.setAttribute('data-boot', '1'); } catch(_) {}
      try{
        const theme = localStorage.getItem('theme');
        if (theme === 'light' || theme === 'dark') document.documentElement.setAttribute('data-theme', theme);
      }catch(_){}
      try{
        const lang = localStorage.getItem('lang');
        if (lang === 'fa' || lang === 'en') {
          document.documentElement.setAttribute('lang', lang);
          document.documentElement.setAttribute('dir', lang === 'fa' ? 'rtl' : 'ltr');
        }
      }catch(_){}
      try{
        const accent = localStorage.getItem('accent');
        // Keep in sync with ShellApp's ACCENT_ALLOWED — this stale list once
        // dropped the unlockable accents (vip/champion/legend), so platinum
        // users flashed red here and standalone pages lost the accent for good.
        const allowed = ['red','cyan','emerald','violet','amber','vip','champion','legend'];
        document.documentElement.setAttribute('data-accent', allowed.indexOf(accent) >= 0 ? accent : 'red');
      }catch(_){
        document.documentElement.setAttribute('data-accent', 'red');
      }
    })();

    // Perf-lite for weak devices: html[data-perf="lite"] makes glass.css drop
    // backdrop blur + freeze decorative animation (see PERF-LITE block there).
    // Heuristics cover weak Androids AND old iPhones; a one-shot FPS probe runs
    // on every device and persists lite mode if it proves slow in practice.
    // Manual override: localStorage.astro_perf = 'lite' | 'full' (or AstroPerf.set()).
    (function () {
      'use strict';
      const root = document.documentElement;
      const apply = (lite) => { try { root.setAttribute('data-perf', lite ? 'lite' : 'full'); } catch (_) {} };
      let forced = null;
      try { forced = localStorage.getItem('astro_perf'); } catch (_) {}
      if (forced === 'lite' || forced === 'full') {
        apply(forced === 'lite');
      } else {
        let lite = false;
        try {
          const ua = navigator.userAgent || '';
          const isAndroid = /Android/i.test(ua);
          const isIOS = /iPhone|iPad|iPod/i.test(ua);
          const andrVer = ua.match(/Android (\d+)/);
          const iosVer = ua.match(/OS (\d+)_/); // "iPhone OS 15_7 like Mac OS X"
          const mem = navigator.deviceMemory || 0;            // Chrome/Android only
          const cores = navigator.hardwareConcurrency || 0;
          if (isAndroid && mem && mem <= 4) lite = true;      // ≤4GB RAM (low/mid tier)
          if (isAndroid && cores && cores <= 4) lite = true;  // weak CPU
          if (andrVer && parseInt(andrVer[1], 10) <= 10) lite = true; // old OS = old GPU
          // Old iPhones: stuck on iOS ≤14 means iPhone 6s/7 era hardware; the
          // blur+animation stack is too heavy there.
          if (isIOS && iosVer && parseInt(iosVer[1], 10) <= 14) lite = true;
          if (localStorage.getItem('astro_perf_auto') === 'lite') lite = true; // earlier probe verdict
          apply(lite);
          if (!lite) {
            // Probe after boot jank settles; abort if backgrounded (rAF pauses → fake low fps).
            // Runs on ALL platforms: a phone that can't hold ~45fps on the live
            // background gets lite mode persisted for future opens.
            setTimeout(() => {
              if (document.hidden) return;
              let frames = 0;
              const t0 = performance.now();
              const tick = (t) => {
                if (document.hidden) return;
                frames++;
                if (t - t0 < 2000) { requestAnimationFrame(tick); return; }
                const fps = frames / ((t - t0) / 1000);
                window.__ASTRO_PROBE_FPS = Math.round(fps);
                if (fps < 45) {
                  try { localStorage.setItem('astro_perf_auto', 'lite'); } catch (_) {}
                  apply(true);
                }
              };
              requestAnimationFrame(tick);
            }, 3000);
          }
        } catch (_) { apply(false); }
      }
      window.AstroPerf = {
        mode: () => root.getAttribute('data-perf'),
        set: (m) => {
          try {
            if (m === 'auto') { localStorage.removeItem('astro_perf'); localStorage.removeItem('astro_perf_auto'); }
            else localStorage.setItem('astro_perf', m === 'lite' ? 'lite' : 'full');
          } catch (_) {}
          try { location.reload(); } catch (_) {}
        }
      };
    })();

    // Telegram fullscreen/expand ASAP (before the heavy dashboard script runs) to reduce the "multi-stage" opening.
    // Global guards so tg.ready() and tg.expand() fire exactly once across all scripts.
    (function(){
      const tg = window.Telegram && window.Telegram.WebApp ? window.Telegram.WebApp : null;
      if (!tg) return;

      window.__ASTRO_TG_READY_CALLED = false;
      window.__ASTRO_TG_EXPANDED = false;

      function tgReadyOnce() {
        if (window.__ASTRO_TG_READY_CALLED) return;
        window.__ASTRO_TG_READY_CALLED = true;
        try { tg.ready(); } catch(_) {}
      }
      function tgExpandOnce() {
        if (window.__ASTRO_TG_EXPANDED) return;
        try {
          if (typeof tg.expand === 'function') tg.expand();
          if (tg.isExpanded) window.__ASTRO_TG_EXPANDED = true;
        } catch(_) {}
      }
      window.__astroTgReadyOnce = tgReadyOnce;
      window.__astroTgExpandOnce = tgExpandOnce;

      tgReadyOnce();

      const platform = (tg.platform ? String(tg.platform).toLowerCase() : '');
      const ua = (navigator.userAgent || '').toLowerCase();
      const isDesktop = /tdesktop|macos|linux|web|windows|desktop/i.test(platform) || 
                       (!/android|iphone|ipad|ipod/i.test(ua) && window.innerWidth > 768);
      
      window.__ASTRO_DESKTOP_MODE = isDesktop;
      if (isDesktop) {
        try {
          tg.requestFullscreen = function() {};
          if (tg.viewport && tg.viewport.requestFullscreen) {
            tg.viewport.requestFullscreen = function() {};
          }
        } catch(_) {}
      }

      tgExpandOnce();
      setTimeout(tgExpandOnce, 300);

      try { if (typeof tg.disableVerticalSwipes === 'function') tg.disableVerticalSwipes(); } catch(_) {}
      
      if (!isDesktop) {
        try { if (typeof tg.enableClosingConfirmation === 'function') tg.enableClosingConfirmation(); } catch(_) {}
        try { if (typeof tg.requestFullscreen === 'function') tg.requestFullscreen(); } catch(_) {}
        try { if (tg.viewport && typeof tg.viewport.requestFullscreen === 'function') tg.viewport.requestFullscreen(); } catch(_) {}
      }

      try{
        const theme = document.documentElement.getAttribute('data-theme') || 'dark';
        const bg = (theme === 'light') ? '#f1ede5' : '#0a141b';
        if (typeof tg.setBackgroundColor === 'function') tg.setBackgroundColor(bg);
        if (typeof tg.setHeaderColor === 'function') tg.setHeaderColor(bg);
      }catch(_){}

      try{
        if (typeof tg.onEvent === 'function') {
          tg.onEvent('viewportChanged', () => { tgExpandOnce(); });
        }
      }catch(_){}

      // TOP DANGER ZONE: in fullscreen mini apps Telegram floats its native
      // Back/close/menu controls OVER the page's top strip. Publish the
      // measured overlap as --tg-safe-top so every surface (sheets, full
      // views) can keep interactive UI out of it. Clients often report 0
      // there, so fullscreen gets a per-OS floor (same lesson as the admin
      // panel's admin-fx.js: iOS 100px / Android 84px).
      try{
        const applyTopSafe = () => {
          try {
            const sa = tg.safeAreaInset || {};
            const csa = tg.contentSafeAreaInset || {};
            let px = Math.max(0, Math.round((sa.top || 0) + (csa.top || 0)));
            if (tg.isFullscreen && px < 60) {
              px = (platform.indexOf('ios') === 0) ? 100 : 84;
            }
            document.documentElement.style.setProperty('--tg-safe-top', px + 'px');
          } catch(_) {}
        };
        applyTopSafe();
        if (typeof tg.onEvent === 'function') {
          tg.onEvent('safeAreaChanged', applyTopSafe);
          tg.onEvent('contentSafeAreaChanged', applyTopSafe);
          tg.onEvent('fullscreenChanged', applyTopSafe);
          tg.onEvent('viewportChanged', applyTopSafe);
        }
      }catch(_){}

      // Android fullscreen puts the webview UNDER the system nav buttons and
      // env(safe-area-inset-bottom) reports 0 there, so the bottom nav merged
      // with the phone's buttons. Telegram reports the real overlap via
      // safeAreaInset; feed it into --astro-safe-bottom-extra, which the CSS
      // already adds to the nav + content padding. Android only — iOS gets the
      // correct value from env() and would double-pad.
      try{
        if (platform.indexOf('android') === 0) { // covers "android" + "android_x"
          const applySafeArea = () => {
            try {
              const sa = tg.safeAreaInset;
              // Trust a reported non-zero value. Zero/missing is unreliable on
              // Android (clients often report 0 even over a 3-button nav bar),
              // so floor it: assume a nav bar in fullscreen, breathing room
              // otherwise. Overshoot is a little air; undershoot is buttons
              // under the system bar.
              let px = sa ? Math.max(0, Math.round(sa.bottom || 0)) : 0;
              if (px <= 0) px = tg.isFullscreen ? 48 : 16;
              document.documentElement.style.setProperty('--astro-safe-bottom-extra', px + 'px');
            } catch(_) {}
          };
          applySafeArea();
          if (typeof tg.onEvent === 'function') {
            tg.onEvent('safeAreaChanged', applySafeArea);
            tg.onEvent('fullscreenChanged', applySafeArea);
            tg.onEvent('viewportChanged', applySafeArea);
          }
        }
      }catch(_){}
    })();

// Plain Android WEBVIEWS outside Telegram (the Orbit app embeds the dashboard)
// draw edge-to-edge under a transparent system navbar while env(safe-area-*)
// reports 0 — Pasha's screenshot had the ||| O < buttons ON TOP of a sheet's
// action row. Telegram sets --astro-safe-bottom-extra itself (block above);
// here we floor it for the no-Telegram webview case. Gate: the "; wv)" UA
// token marks a WebView (plain Chrome doesn't have it, so no dead air there).
(function () {
  try {
    var ua = navigator.userAgent || '';
    var isWv = /; wv\)/i.test(ua) || /Version\/[\d.]+ Chrome\/[\d.]+ Mobile/i.test(ua);
    // telegram-web-app.js defines window.Telegram.WebApp EVERYWHERE (it's in
    // our <head>), so "object exists" proves nothing. Real Telegram = live
    // initData or a real platform name (Orbit reports platform "unknown").
    var twa = window.Telegram && window.Telegram.WebApp;
    var hasTg = !!(twa && ((twa.initData && twa.initData.length > 10) || (twa.platform && twa.platform !== 'unknown')));
    if (/android/i.test(ua) && isWv && !hasTg) {
      var cur = parseInt(getComputedStyle(document.documentElement).getPropertyValue('--astro-safe-bottom-extra') || '0', 10) || 0;
      if (cur < 44) document.documentElement.style.setProperty('--astro-safe-bottom-extra', '44px');
    }
  } catch (_) {}
})();

// STICKY-HOVER KILLER (touch devices): Android/iOS webviews latch :hover onto
// the last tapped element, so every desktop hover style becomes a stuck state
// on phones (frozen FAB float, lifted+clipped profile stat tiles, washed
// buttons…). ~120 ungated :hover rules exist across the dashboard CSS —
// instead of gating them one by one forever, strip them from the CSSOM at
// runtime when the device can't hover. :active/:focus feedback is untouched
// (mixed selector lists only lose their :hover members). Rules inside
// @media (hover: hover) blocks are left alone — they can never match here.
(function () {
  'use strict';
  try {
    var canHover = window.matchMedia && matchMedia('(hover: hover)').matches
      && !matchMedia('(pointer: coarse)').matches;
    if (canHover) return;
  } catch (_) { return; }
  var done = (typeof WeakSet === 'function') ? new WeakSet() : null;

  function stripGroup(group) {
    var rules;
    try { rules = group.cssRules; } catch (_) { return; } // cross-origin — skip
    if (!rules) return;
    for (var i = rules.length - 1; i >= 0; i--) {
      var r = rules[i];
      try {
        if (r.type === 1 && r.selectorText && r.selectorText.indexOf(':hover') !== -1) {
          var kept = r.selectorText.split(',').filter(function (s) { return s.indexOf(':hover') === -1; });
          if (!kept.length) group.deleteRule(i);
          else {
            try { r.selectorText = kept.join(','); } catch (_) { group.deleteRule(i); }
          }
        } else if (r.cssRules && (r.type === 4 || r.type === 12)) { // @media / @supports
          var cond = '';
          try { cond = r.conditionText || (r.media && r.media.mediaText) || ''; } catch (_) { cond = ''; }
          if (/hover:\s*hover/i.test(cond)) continue; // already touch-safe
          stripGroup(r);
        }
      } catch (_) { /* one bad rule must not stop the sweep */ }
    }
  }

  function sweep() {
    try {
      for (var i = 0; i < document.styleSheets.length; i++) {
        var sh = document.styleSheets[i];
        var rules = null;
        try { rules = sh.cssRules; } catch (_) { continue; } // loading/cross-origin — retry next sweep
        if (!rules || !rules.length) continue;               // not loaded yet — retry next sweep
        if (done) { if (done.has(sh)) continue; done.add(sh); }
        stripGroup(sh);
      }
    } catch (_) {}
  }
  // Sheets finish loading after head-boot runs; sweep at readiness milestones
  // and once more late for lazily injected chunks.
  document.addEventListener('DOMContentLoaded', sweep);
  window.addEventListener('load', sweep);
  setTimeout(sweep, 2500);
  setTimeout(sweep, 6000);
})();

// Keyboard helper: keep the focused input visible above the on-screen keyboard.
// On Android the webview is NOT resized when the keyboard opens — it just covers
// the bottom of the page, so scrollIntoView alone can't help short pages or
// fixed-position modals. Measure the covered height (visualViewport primary,
// Telegram viewportHeight as backup), publish it as --kb + html.kb-open, give
// in-flow pages scroll room via body padding, then scroll the field into view
// ONCE per focus (repeat applies are no-ops while the height is stable — see
// the steady-state guard inside apply()). Fixed containers (modals/sheets/chat)
// reposition themselves via CSS rules keyed off html.kb-open. This module is
// the ONLY writer of html.kb-open + --kb; React pages must not run a second
// keyboard watcher on top of it (dual writers disagreed on Samsung resize-mode
// webviews and strobed the layout — support page, 2026-07-09).
// (No zoom: inputs are >=16px via glass.css.)
(function () {
  'use strict';
  var root = document.documentElement;
  var vv = window.visualViewport || null;
  function focusedField() {
    var el = document.activeElement;
    return (el && el.matches && el.matches('input, textarea, select, [contenteditable="true"]')) ? el : null;
  }
  var IS_ANDROID = /android/i.test(navigator.userAgent || '');
  var baseHeight = window.innerHeight; // refreshed whenever no field is focused
  // Guess-lift staleness: the 50% Android fallback has NO closing signal (the
  // webview reports nothing when the keyboard is back-dismissed), so it decays:
  // typing ('input' events), focus changes and viewport resizes all refresh
  // lastKbActivity; with no signs of life the guessed lift auto-drops and the
  // next keystroke re-lifts instantly. Measured lifts (vv/tg) are exempt —
  // they get real close events. Fixes the giant stuck bottom gap on Samsung
  // webviews (Orbit app screenshot, 2026-07-08).
  var KB_GUESS_STALE_MS = 25000;
  var lastKbActivity = 0;
  // NOTE: the VirtualKeyboard API is a trap here — it exists in this webview
  // but the keyboard isn't chromium-managed, so geometrychange reports height
  // 0 while the keyboard is actually covering the page. Trusting it disabled
  // the lift entirely. Don't reintroduce it.
  function kbHeight() {
    var h = 0;
    try { if (vv) h = Math.max(h, Math.round(window.innerHeight - vv.height - (vv.offsetTop || 0))); } catch (_) {}
    try {
      var tg = window.Telegram && window.Telegram.WebApp;
      if (tg && tg.viewportHeight) h = Math.max(h, Math.round(window.innerHeight - tg.viewportHeight));
    } catch (_) {}
    if (h > 80) return h; // below that it's nav-bar/viewport noise, not a keyboard
    // Webview shrank itself (adjustResize) — the keyboard is already handled natively.
    if (baseHeight - window.innerHeight > 80) return 0;
    // Last resort: while an input is focused assume half the screen. Samsung
    // keyboards with number row + suggestion bar measure ~49% of the webview,
    // so 42% left the composer clipped under the keyboard; slight over-lift
    // (a gap above a short keyboard) is the cheaper failure.
    // ponytail: over-lifts with external keyboards; the outside-tap blur below resets it.
    if (IS_ANDROID) {
      if (lastKbActivity && (Date.now() - lastKbActivity) > KB_GUESS_STALE_MS) return 0;
      return Math.round(window.innerHeight * 0.50);
    }
    return 0;
  }
  function inFixed(el) {
    for (var n = el; n && n !== document.body; n = n.parentElement) {
      try { if (getComputedStyle(n).position === 'fixed') return true; } catch (_) { return false; }
    }
    return false;
  }
  // Steady-state guard: iOS fires visualViewport resize/scroll bursts while
  // the keyboard animates AND whenever our own smooth scrollIntoView pans the
  // visual viewport. Re-running the full apply() for each one re-yanked the
  // chat list and re-issued scrollIntoView, which panned the viewport again —
  // a feedback loop the user saw as flashing/jumping (Pasha, 2026-07-09).
  // Rules: DOM writes only when the height really changed (>8px), and one
  // scrollIntoView per focus session (re-armed if the keyboard grows >100px,
  // e.g. a text-keyboard -> emoji-panel swap).
  var lastKb = -1; // last applied height; -1 = nothing applied yet
  var scrolledForFocus = false;
  var kbAtScroll = 0;
  function apply() {
    var el = focusedField();
    var kb = el ? kbHeight() : 0;
    if (!el) baseHeight = window.innerHeight; // keep the adjustResize baseline fresh
    var kbChanged = (lastKb < 0) || Math.abs(kb - lastKb) > 8;
    var needReveal = !!el && kb > 0 && (!scrolledForFocus || (kb - kbAtScroll) > 100);
    if (!kbChanged && !needReveal) return;
    if (kbChanged) {
      lastKb = kb;
      try {
        root.style.setProperty('--kb', kb + 'px');
        root.classList.toggle('kb-open', kb > 0);
      } catch (_) {}
    }
    if (!el || !kb) {
      if (document.body) document.body.style.paddingBottom = '';
      return;
    }
    if (kbChanged) {
      if (!inFixed(el) && document.body) document.body.style.paddingBottom = kb + 'px';
      // Chat view shrinks around the reply bar — keep the newest messages visible.
      var chat = el.closest && el.closest('.chat-view');
      if (chat) {
        var msgs = chat.querySelector('.chat-messages');
        if (msgs) msgs.scrollTop = msgs.scrollHeight;
      }
    }
    if (!needReveal) return;
    var r = el.getBoundingClientRect();
    var visibleBottom = window.innerHeight - kb;
    if (r.bottom > visibleBottom - 12 || r.top < 0) {
      scrolledForFocus = true;
      kbAtScroll = kb;
      try { el.scrollIntoView({ block: 'center', behavior: 'smooth' }); } catch (_) {
        try { el.scrollIntoView(); } catch (_) {}
      }
    } else {
      // Already visible: mark this focus as revealed so steady-state viewport
      // events stop re-measuring the field.
      scrolledForFocus = true;
      kbAtScroll = kb;
    }
  }
  var timer = null;
  function queue(delay) {
    if (timer) clearTimeout(timer);
    timer = setTimeout(function () { timer = null; apply(); }, delay || 80);
  }
  var staleTimer = null;
  function armStaleSweep() {
    // Re-check shortly after the guess goes stale so the gap self-heals even
    // with zero further user events (the exact stuck-screenshot scenario).
    if (staleTimer) clearTimeout(staleTimer);
    if (!root.classList.contains('kb-open')) return;
    staleTimer = setTimeout(function () { staleTimer = null; apply(); armStaleSweep(); }, KB_GUESS_STALE_MS + 500);
  }
  function touchKbActivity() { lastKbActivity = Date.now(); }
  document.addEventListener('focusin', function () {
    touchKbActivity();
    scrolledForFocus = false; // every focus session gets one fresh reveal
    kbAtScroll = 0;
    queue(320);
    setTimeout(armStaleSweep, 400);
  }, true);
  document.addEventListener('focusout', function () { queue(120); }, true);
  // Typing proves the keyboard is really up — keeps the guessed lift alive,
  // and re-lifts instantly if the stale sweep had dropped it mid-composition.
  document.addEventListener('input', function () {
    touchKbActivity();
    if (!root.classList.contains('kb-open') && focusedField()) { queue(60); setTimeout(armStaleSweep, 400); }
  }, true);
  // The webview gives NO signal when the keyboard is dismissed with the Android
  // back button — focus stays in the field, so the guessed lift got stuck and
  // left a dead gap. Recovery (and native chat feel): tapping anything that is
  // not the field itself or another control blurs the field, which closes the
  // keyboard if it is still up and always drops the lift. Buttons/links are
  // exempt so tapping Send doesn't collapse the composer mid-action.
  // A dismiss-tap must do NOTHING but dismiss: the blur collapses the keyboard
  // and the page re-lays-out mid-tap, so the tap's synthesized click fires on
  // whatever shifted under the finger (the bottom-nav Support tab kept
  // "opening tickets" — Pasha, 2026-07-08). Swallow that one click.
  // Swallow EVERY click in the window (not one-shot): some webviews emulate
  // a second mouse click after touchend and either one can land on a nav tab.
  var suppressClickUntil = 0;
  document.addEventListener('click', function (ev) {
    if (Date.now() < suppressClickUntil) {
      ev.stopPropagation();
      ev.preventDefault();
    }
  }, true);
  document.addEventListener('touchstart', function (ev) {
    var el = focusedField();
    if (!root.classList.contains('kb-open')) return;
    if (!el) {
      // Focused field vanished without a blur event (hidden/unmounted mid-lift,
      // a webview quirk): any touch clears the orphaned lift immediately.
      queue(40);
      return;
    }
    var t = ev.target;
    if (t === el) { touchKbActivity(); return; }
    try {
      if (t && t.closest && t.closest('input, textarea, select, [contenteditable="true"], button, a, label')) return;
    } catch (_) {}
    try { el.blur(); } catch (_) {}
    suppressClickUntil = Date.now() + 700;
  }, { capture: true, passive: true });
  // Same orphan guard for scrolling (reading the page with a phantom gap).
  document.addEventListener('scroll', function () {
    if (root.classList.contains('kb-open') && !focusedField()) queue(80);
  }, { capture: true, passive: true });
  if (vv) {
    try { vv.addEventListener('resize', function () { touchKbActivity(); queue(60); }); } catch (_) {}
  }
  try {
    var tg = window.Telegram && window.Telegram.WebApp;
    if (tg && typeof tg.onEvent === 'function') tg.onEvent('viewportChanged', function () { touchKbActivity(); queue(60); });
  } catch (_) {}
})();

// Idle freeze: pause the decorative drift after 45s without interaction
// (html.astro-idle, see glass.css). Any touch/scroll resumes instantly —
// the animation only stops while nobody is looking at it moving. Cuts
// sustained GPU heat on ProMotion iPhones during reading/idle.
(function () {
  'use strict';
  const root = document.documentElement;
  let timer = null;
  const arm = () => {
    if (root.classList.contains('astro-idle')) root.classList.remove('astro-idle');
    if (timer) clearTimeout(timer);
    timer = setTimeout(() => { root.classList.add('astro-idle'); }, 45000);
  };
  ['pointerdown', 'touchstart', 'wheel', 'keydown', 'scroll'].forEach((ev) => {
    document.addEventListener(ev, arm, { passive: true, capture: true });
  });
  arm();
})();

// Hidden diagnostics: tap the footer 5× within 2s to see what this device
// reports (perf mode, RAM/cores, fps probe, safe-area). For debugging perf
// and layout reports from users — no UI cost otherwise.
(function () {
  'use strict';
  let taps = 0, t0 = 0;
  document.addEventListener('click', (e) => {
    if (!e.target || !e.target.closest || !e.target.closest('footer')) return;
    const now = Date.now();
    if (now - t0 > 2000) { taps = 0; t0 = now; }
    if (++taps < 5) return;
    taps = 0;
    try {
      const tg = window.Telegram && window.Telegram.WebApp;
      const cs = getComputedStyle(document.documentElement);
      const ua = navigator.userAgent || '';
      const msg = [
        'perf: ' + document.documentElement.getAttribute('data-perf'),
        'mem: ' + (navigator.deviceMemory || '?') + 'GB, cores: ' + (navigator.hardwareConcurrency || '?'),
        'probeFps: ' + (window.__ASTRO_PROBE_FPS || 'n/a'),
        'tg v' + (tg && tg.version || '?') + ' ' + (tg && tg.platform || '?') + ' fs:' + (tg && tg.isFullscreen),
        'safeArea: ' + JSON.stringify(tg && tg.safeAreaInset || null),
        'extraVar: ' + (cs.getPropertyValue('--astro-safe-bottom-extra') || '(unset)'),
        'ua: ' + ua.slice(0, 80),
      ].join('\n');
      const wipeFirstRun = () => {
        try {
          ['astro_welcome_shown', 'hasSeenWelcome', 'astro_tour_v1', 'astro_device_id',
           'astro_perf', 'astro_perf_auto'].forEach((k) => localStorage.removeItem(k));
        } catch (_) {}
        // welcome_shown also lives in server prefs — clear it too or the
        // welcome screen stays blocked after a local-only wipe.
        const done = () => { try { location.reload(); } catch (_) {} };
        try {
          fetch('/api/dashboard/preferences', {
            method: 'POST',
            credentials: 'include',
            headers: {
              'Content-Type': 'application/json',
              'X-Telegram-Init': (tg && tg.initData) || '',
            },
            body: JSON.stringify({ welcome_shown: false }),
          }).then(done, done);
          setTimeout(done, 2500);
        } catch (_) { done(); }
      };
      if (tg && typeof tg.showPopup === 'function') {
        tg.showPopup(
          { title: 'Diagnostics', message: msg, buttons: [
            { id: 'close', type: 'close' },
            { id: 'reset', type: 'destructive', text: 'Reset first-run flags' },
          ] },
          (id) => { if (id === 'reset') wipeFirstRun(); }
        );
      } else if (window.confirm(msg + '\n\nReset first-run flags (welcome screen, perf mode)?')) {
        wipeFirstRun();
      }
    } catch (err) { try { window.alert('diag error: ' + err); } catch (_) {} }
  }, { passive: true });
})();

// Battery/heat saver: when the WebApp is hidden (user switches chats, locks the
// phone, backgrounds Telegram), pause ALL CSS animations and signal pollers to
// idle. Invisible to the user — they're not looking — but it stops the GPU from
// compositing the animated background + glass blur while off-screen.
// Adding html.astro-hidden lets CSS halt every animation in one rule.
(function () {
  'use strict';
  const root = document.documentElement;
  const apply = () => {
    const hidden = document.hidden;
    root.classList.toggle('astro-hidden', hidden);
    try {
      window.dispatchEvent(new CustomEvent('astro-visibility', { detail: { hidden } }));
    } catch (_) {}
  };
  document.addEventListener('visibilitychange', apply, { passive: true });
  apply();
})();

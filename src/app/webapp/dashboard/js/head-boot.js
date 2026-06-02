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
      
      // Primary check: Telegram WebApp object must exist
      const tg = window.Telegram && window.Telegram.WebApp ? window.Telegram.WebApp : null;
      const hasTelegramWebApp = !!(tg && typeof tg.initDataUnsafe !== 'undefined');
      const hasInitData = !!(tg && tg.initData && tg.initData.length > 10);
      
      // Fallback: Check for initData in URL (some Telegram clients pass it this way)
      let hasUrlInitData = false;
      try {
        const urlParams = new URLSearchParams(window.location.search);
        const hashParams = new URLSearchParams(window.location.hash.replace(/^#/, ''));
        const fromQuery = urlParams.get('tgWebAppData') || urlParams.get('tg_web_app_data') || urlParams.get('init_data');
        const fromHash = hashParams.get('tgWebAppData') || hashParams.get('tg_web_app_data');
        hasUrlInitData = !!(fromQuery && fromQuery.length > 10) || !!(fromHash && fromHash.length > 10);
      } catch (_) {}
      
      // Check for valid session cookie (minted after Telegram auth verification)
      let hasValidSession = false;
      try {
        const cookies = document.cookie.split(';');
        for (let cookie of cookies) {
          const [name] = cookie.trim().split('=');
          if (name === 'tma_session') {
            hasValidSession = true;
            break;
          }
        }
      } catch (_) {}
      
      // Check for auth token in URL (short-lived token minted by bot)
      let hasAuthToken = false;
      try {
        const urlParams = new URLSearchParams(window.location.search);
        const auth = urlParams.get('auth');
        hasAuthToken = !!(auth && auth.length > 10);
      } catch (_) {}
      
      // BLOCK ACCESS if none of the Telegram authentication methods are present
      // This ensures the dashboard can ONLY be accessed through Telegram Mini App
      if (!hasTelegramWebApp && !hasInitData && !hasUrlInitData && !hasValidSession && !hasAuthToken) {
        // Immediately replace page content with block message
        document.open();
        document.write('<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Access Restricted</title><style>body{font-family:system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0;background:#0d1a22;color:#F9F6EE;text-align:center;padding:20px;line-height:1.6;}div{max-width:450px;}h1{color:#ec5652;margin:0 0 20px;font-size:28px;font-weight:700;}p{margin:12px 0;opacity:0.9;font-size:16px;}.icon{font-size:64px;margin-bottom:20px;}</style></head><body><div><div class="icon">🔒</div><h1>Access Restricted</h1><p>This dashboard can only be accessed through the Telegram Mini App.</p><p>Please open this page from within Telegram.</p></div></body></html>');
        document.close();
        // Prevent any further script execution
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
        const allowed = ['red','cyan','emerald','violet','amber'];
        document.documentElement.setAttribute('data-accent', allowed.indexOf(accent) >= 0 ? accent : 'red');
      }catch(_){
        document.documentElement.setAttribute('data-accent', 'red');
      }
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
        const bg = (theme === 'light') ? '#d4dff0' : '#0a141b';
        if (typeof tg.setBackgroundColor === 'function') tg.setBackgroundColor(bg);
        if (typeof tg.setHeaderColor === 'function') tg.setHeaderColor(bg);
      }catch(_){}

      try{
        if (typeof tg.onEvent === 'function') {
          tg.onEvent('viewportChanged', () => { tgExpandOnce(); });
        }
      }catch(_){}
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

(() => {
  const existing = window.AstroUI;
  if (existing && existing.__ready) return;

  // Platform/Safe-area helpers (used by the WebApp shell pages)
  (function applyPlatformHints() {
    try {
      const tg = (window.Telegram && window.Telegram.WebApp) ? window.Telegram.WebApp : null;
      const tgPlatform = (tg && tg.platform) ? String(tg.platform).toLowerCase() : '';
      const ua = String(navigator.userAgent || '').toLowerCase();
      const isAndroid = tgPlatform === 'android' || ua.includes('android');
      const isIOS = tgPlatform === 'ios' || ua.includes('iphone') || ua.includes('ipad') || ua.includes('ipod');

      const root = document.documentElement;
      const body = document.body || document.documentElement;
      if (isAndroid) {
        body.classList.add('platform-android');
        root.setAttribute('data-os', 'android');
      } else if (isIOS) {
        body.classList.add('platform-ios');
        root.setAttribute('data-os', 'ios');
      } else {
        root.setAttribute('data-os', 'other');
      }

      // Telegram on Android doesn't consistently expose safe-area insets; add a small extra
      // padding so fixed bottom nav/actions don't sit on top of the system buttons.
      // head-boot.js owns this value when present (it tracks safeAreaChanged /
      // fullscreen) — only seed a default when nothing set it yet.
      if (!root.style.getPropertyValue('--astro-safe-bottom-extra')) {
        root.style.setProperty('--astro-safe-bottom-extra', isAndroid ? '16px' : '0px');
      }
    } catch (_) {}
  })();

  let _fullscreenLastAttemptAt = 0;
  let _viewportStable = false;
  let _viewportStableWaiters = [];
  let _isFullscreen = false;
  let _fullscreenWaiters = [];

  function setViewportStable(next) {
    const stable = !!next;
    if (_viewportStable === stable) return;
    _viewportStable = stable;
    try { document.documentElement.setAttribute('data-tg-viewport-stable', stable ? '1' : '0'); } catch (_) {}
    if (stable && _viewportStableWaiters.length) {
      const waiters = _viewportStableWaiters.slice();
      _viewportStableWaiters = [];
      waiters.forEach((fn) => { try { fn(); } catch (_) {} });
    }
  }

  function waitForViewportStable(timeoutMs = 1200) {
    if (_viewportStable) return Promise.resolve(true);
    return new Promise((resolve) => {
      let done = false;
      const finish = (v) => {
        if (done) return;
        done = true;
        resolve(!!v);
      };
      _viewportStableWaiters.push(() => finish(true));
      setTimeout(() => finish(false), Math.max(0, timeoutMs | 0));
    });
  }

  function setFullscreenActive(next) {
    const active = !!next;
    if (_isFullscreen === active) return;
    _isFullscreen = active;
    try { document.documentElement.setAttribute('data-tg-fullscreen', active ? '1' : '0'); } catch (_) {}
    if (active && _fullscreenWaiters.length) {
      const waiters = _fullscreenWaiters.slice();
      _fullscreenWaiters = [];
      waiters.forEach((fn) => { try { fn(); } catch (_) {} });
    }
  }

  function isFullscreenSupported() {
    const tg = (window.Telegram && window.Telegram.WebApp) ? window.Telegram.WebApp : null;
    if (!tg) return false;
    return !!(typeof tg.requestFullscreen === 'function' || (tg.viewport && typeof tg.viewport.requestFullscreen === 'function'));
  }

  function getIsFullscreen() {
    const tg = (window.Telegram && window.Telegram.WebApp) ? window.Telegram.WebApp : null;
    if (!tg) return false;
    try {
      if (typeof tg.isFullscreen === 'boolean') return tg.isFullscreen;
    } catch (_) {}
    return _isFullscreen;
  }

  function waitForFullscreen(timeoutMs = 1400) {
    if (!isFullscreenSupported()) return Promise.resolve(true);
    if (getIsFullscreen()) return Promise.resolve(true);
    return new Promise((resolve) => {
      let done = false;
      const finish = (v) => {
        if (done) return;
        done = true;
        resolve(!!v);
      };
      _fullscreenWaiters.push(() => finish(true));
      setTimeout(() => finish(false), Math.max(0, timeoutMs | 0));
    });
  }

  function waitForExpanded(timeoutMs = 1600) {
    const tg = (window.Telegram && window.Telegram.WebApp) ? window.Telegram.WebApp : null;
    if (!tg) return Promise.resolve(true);
    try { if (typeof tg.isExpanded === 'boolean' && tg.isExpanded) return Promise.resolve(true); } catch (_) {}
    return new Promise((resolve) => {
      let done = false;
      const finish = (v) => {
        if (done) return;
        done = true;
        resolve(!!v);
      };
      const check = (eventData) => {
        try {
          const expandedFlag =
            (eventData && (eventData.isExpanded === true || eventData.is_expanded === true)) ||
            (typeof tg.isExpanded === 'boolean' && tg.isExpanded === true) ||
            (typeof tg.viewportHeight === 'number' && typeof tg.viewportStableHeight === 'number' && tg.viewportHeight > 0 && Math.abs(tg.viewportHeight - tg.viewportStableHeight) < 2);
          if (expandedFlag) finish(true);
        } catch (_) {}
      };
      try {
        if (typeof tg.onEvent === 'function') tg.onEvent('viewportChanged', check);
      } catch (_) {}
      setTimeout(() => check(null), 120);
      setTimeout(() => check(null), 420);
      setTimeout(() => finish(false), Math.max(0, timeoutMs | 0));
    });
  }

  function goFullscreen({ request = false } = {}) {
    const tg = (window.Telegram && window.Telegram.WebApp) ? window.Telegram.WebApp : null;
    if (!tg) return;
    
    if (window.__ASTRO_DESKTOP_MODE) {
      if (window.__astroTgExpandOnce) window.__astroTgExpandOnce();
      return;
    }
    
    const now = Date.now();
    if (now - _fullscreenLastAttemptAt < 450) return;
    _fullscreenLastAttemptAt = now;
    
    if (window.__astroTgReadyOnce) window.__astroTgReadyOnce();
    if (window.__astroTgExpandOnce) window.__astroTgExpandOnce();

    if (request) {
      try { if (typeof tg.requestFullscreen === 'function') tg.requestFullscreen(); } catch (_) {}
      try { if (tg.viewport && typeof tg.viewport.requestFullscreen === 'function') tg.viewport.requestFullscreen(); } catch (_) {}
    }

    try { if (typeof tg.disableVerticalSwipes === 'function') tg.disableVerticalSwipes(); } catch (_) {}
  }

  function bootstrapTelegramViewport() {
    const tg = (window.Telegram && window.Telegram.WebApp) ? window.Telegram.WebApp : null;
    if (!tg) return;

    goFullscreen({ request: false });

    if (!window.__ASTRO_DESKTOP_MODE) {
      const onceOpts = { once: true, capture: true };
      const requestFs = () => goFullscreen({ request: true });
      document.addEventListener('click', requestFs, onceOpts);
      document.addEventListener('pointerdown', requestFs, onceOpts);
      document.addEventListener('touchstart', requestFs, Object.assign({ passive: true }, onceOpts));
    }

    try { setViewportStable(false); } catch (_) {}
    function recomputeStable(eventData) {
      try {
        const stableFlag =
          (eventData && (eventData.isStateStable === true || eventData.is_state_stable === true)) ||
          (typeof tg.isExpanded === 'boolean' && tg.isExpanded && Math.abs((tg.viewportHeight || 0) - (tg.viewportStableHeight || 0)) < 2);
        setViewportStable(!!stableFlag);
      } catch (_) {}
    }
    function recomputeFullscreen(eventData) {
      try {
        const flag =
          (eventData && (eventData.isFullscreen === true || eventData.is_fullscreen === true)) ||
          (typeof tg.isFullscreen === 'boolean' && tg.isFullscreen === true);
        setFullscreenActive(!!flag);
      } catch (_) {}
    }
    try {
      if (typeof tg.onEvent === 'function') {
        tg.onEvent('viewportChanged', recomputeStable);
        tg.onEvent('fullscreenChanged', recomputeFullscreen);
      }
    } catch (_) {}
    setTimeout(() => recomputeStable(null), 750);
    setTimeout(() => recomputeFullscreen(null), 750);

    try{
      if (!window.__astroFullscreenKeepAlive) {
        window.__astroFullscreenKeepAlive = setInterval(() => {
          if (!window.__ASTRO_DESKTOP_MODE) {
            try { if (typeof tg.enableClosingConfirmation === 'function') tg.enableClosingConfirmation(); } catch (_) {}
          }
          try { if (typeof tg.disableVerticalSwipes === 'function') tg.disableVerticalSwipes(); } catch (_) {}
        }, 5000);
      }
    }catch(_){}
  }

  function prefersReducedMotion() {
    try {
      return !!(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches);
    } catch (_) {
      return false;
    }
  }

  function ensureStyles() {
    if (document.getElementById('astro-ui-styles')) return;
    const style = document.createElement('style');
    style.id = 'astro-ui-styles';
    style.textContent = `
      :root{
        --astro-ui-overlay: rgba(0,0,0,0.55);
        --astro-ui-shadow: 0 18px 60px rgba(0,0,0,0.35);
      }
      [data-theme="light"]{
        --astro-ui-overlay: rgba(15, 23, 42, 0.28);
        --astro-ui-shadow: 0 18px 60px rgba(15, 23, 42, 0.18);
      }
      .astro-ui-overlay{
        position:fixed; inset:0;
        background: var(--astro-ui-overlay);
        display:none;
        align-items:center;
        justify-content:center;
        padding: 18px;
        z-index: 99999;
      }
      .astro-ui-overlay[data-open="1"]{ display:flex; }
      .astro-ui-modal{
        width: 100%;
        max-width: 420px;
        background: var(--panel, #1a2a36);
        border: 1px solid var(--line, rgba(255,255,255,0.12));
        border-radius: 18px;
        box-shadow: var(--astro-ui-shadow);
        backdrop-filter: blur(18px) saturate(180%);
        transform: translateY(8px);
        opacity: 0;
        transition: transform .18s ease, opacity .18s ease;
        color: var(--text, #fff);
      }
      .astro-ui-overlay[data-open="1"] .astro-ui-modal{
        transform: translateY(0);
        opacity: 1;
      }
      @media (prefers-reduced-motion: reduce){
        .astro-ui-modal{ transition:none; }
      }
      .astro-ui-head{
        padding: 14px 16px 0;
        display:flex;
        align-items:flex-start;
        justify-content:space-between;
        gap: 10px;
      }
      .astro-ui-title{
        font-weight: 800;
        font-size: 16px;
        line-height: 1.2;
        letter-spacing: 0.2px;
      }
      .astro-ui-x{
        width: 36px;
        height: 36px;
        border-radius: 10px;
        border: 1px solid var(--line, rgba(255,255,255,0.12));
        background: var(--chip, rgba(255,255,255,0.06));
        color: var(--text, #fff);
        display:inline-flex;
        align-items:center;
        justify-content:center;
        cursor:pointer;
        flex: 0 0 auto;
      }
      .astro-ui-body{
        padding: 10px 16px 0;
        font-size: 14px;
        line-height: 1.55;
        color: var(--text, #fff);
        opacity: 0.92;
        white-space: pre-line;
      }
      .astro-ui-input-wrap{
        padding: 12px 16px 0;
      }
      .astro-ui-input{
        width: 100%;
        padding: 12px 12px;
        border-radius: 12px;
        border: 1px solid var(--line, rgba(255,255,255,0.12));
        background: var(--panel2, rgba(255,255,255,0.04));
        color: var(--text, #fff);
        outline: none;
      }
      .astro-ui-input:focus{
        border-color: var(--brand, #ec5652);
        box-shadow: 0 0 0 3px rgba(var(--brandRgb), 0.18);
      }
      .astro-ui-code{
        font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
        font-size: 13px;
        padding: 10px 12px;
        border-radius: 12px;
        border: 1px solid var(--line, rgba(255,255,255,0.12));
        background: var(--panel2, rgba(255,255,255,0.04));
        overflow-wrap:anywhere;
      }
      .astro-ui-actions{
        padding: 14px 16px 16px;
        display:flex;
        gap: 10px;
        justify-content:flex-end;
        flex-wrap:wrap;
      }
      .astro-ui-btn{
        border-radius: 12px;
        border: 1px solid var(--line, rgba(255,255,255,0.12));
        background: var(--chip, rgba(255,255,255,0.06));
        color: var(--text, #fff);
        font-weight: 800;
        font-size: 13px;
        padding: 10px 14px;
        cursor:pointer;
        transition: transform .12s ease, filter .12s ease;
      }
      .astro-ui-btn:active{ transform: translateY(1px); }
      .astro-ui-btn.primary{
        background: var(--brand, #ec5652);
        border-color: var(--brand, #ec5652);
        color: #fff;
      }
      .astro-ui-btn.danger{
        background: var(--bad, #ef4444);
        border-color: var(--bad, #ef4444);
        color: #fff;
      }
      .astro-ui-toast{
        position: fixed;
        left: 50%;
        bottom: 96px;
        transform: translateX(-50%);
        z-index: 99998;
        padding: 10px 14px;
        border-radius: 14px;
        border: 1px solid var(--line, rgba(255,255,255,0.12));
        background: var(--panel, #1a2a36);
        color: var(--text, #fff);
        box-shadow: 0 16px 50px rgba(0,0,0,0.35);
        max-width: min(520px, calc(100vw - 24px));
        font-weight: 700;
        font-size: 13px;
        text-align: center;
        opacity: 0;
        transform: translateX(-50%) translateY(8px);
        transition: opacity .18s ease, transform .18s ease;
        pointer-events: none;
        white-space: pre-line;
      }
      .astro-ui-toast.show{
        opacity: 1;
        transform: translateX(-50%) translateY(0);
      }
    `;
    document.head.appendChild(style);
  }

  function ensureModalDom() {
    ensureStyles();
    let overlay = document.getElementById('astro-ui-overlay');
    if (overlay) return overlay;

    overlay = document.createElement('div');
    overlay.id = 'astro-ui-overlay';
    overlay.className = 'astro-ui-overlay';
    overlay.setAttribute('role', 'presentation');
    overlay.innerHTML = `
      <div class="astro-ui-modal" role="dialog" aria-modal="true" aria-live="polite">
        <div class="astro-ui-head">
          <div class="astro-ui-title" id="astroUiTitle"></div>
          <button class="astro-ui-x" type="button" aria-label="Close" data-action="close">
            <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
              <path d="M18 6L6 18"></path>
              <path d="M6 6l12 12"></path>
            </svg>
          </button>
        </div>
        <div class="astro-ui-body" id="astroUiBody"></div>
        <div class="astro-ui-input-wrap" id="astroUiInputWrap" style="display:none;">
          <input class="astro-ui-input" id="astroUiInput" />
        </div>
        <div class="astro-ui-actions" id="astroUiActions"></div>
      </div>
    `;
    document.body.appendChild(overlay);
    return overlay;
  }

  function setOpen(overlay, open) {
    overlay.setAttribute('data-open', open ? '1' : '0');
    if (!open) overlay.style.display = 'none';
    else overlay.style.display = 'flex';
  }

  function trapFocus(container, initialEl) {
    const selectors = [
      'button:not([disabled])',
      'input:not([disabled])',
      '[tabindex]:not([tabindex="-1"])',
    ].join(',');
    const getFocusable = () => Array.from(container.querySelectorAll(selectors)).filter(el => el.offsetParent !== null);

    function onKeyDown(e) {
      if (e.key !== 'Tab') return;
      const focusables = getFocusable();
      if (!focusables.length) return;
      const first = focusables[0];
      const last = focusables[focusables.length - 1];
      const active = document.activeElement;
      if (e.shiftKey && active === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && active === last) {
        e.preventDefault();
        first.focus();
      }
    }
    container.addEventListener('keydown', onKeyDown);
    const focusTarget = initialEl || getFocusable()[0];
    if (focusTarget) {
      setTimeout(() => {
        try { focusTarget.focus(); } catch (_) {}
      }, prefersReducedMotion() ? 0 : 10);
    }
    return () => container.removeEventListener('keydown', onKeyDown);
  }

  async function showModal(opts) {
    const overlay = ensureModalDom();
    const modal = overlay.querySelector('.astro-ui-modal');
    const titleEl = overlay.querySelector('#astroUiTitle');
    const bodyEl = overlay.querySelector('#astroUiBody');
    const actionsEl = overlay.querySelector('#astroUiActions');
    const inputWrap = overlay.querySelector('#astroUiInputWrap');
    const inputEl = overlay.querySelector('#astroUiInput');
    const closeBtn = overlay.querySelector('[data-action="close"]');

    const prevActive = document.activeElement;
    const title = opts.title || '';
    const message = opts.message || '';
    const kind = opts.kind || 'alert';

    titleEl.textContent = title;
    bodyEl.textContent = message;
    actionsEl.innerHTML = '';
    inputWrap.style.display = 'none';
    inputEl.value = '';
    inputEl.type = 'text';
    inputEl.inputMode = '';
    inputEl.placeholder = '';
    inputEl.readOnly = false;

    const buttons = opts.buttons || [];
    const resolveWith = (value) => {
      cleanup();
      setOpen(overlay, false);
      try { if (prevActive && prevActive.focus) prevActive.focus(); } catch (_) {}
      return value;
    };

    const onOverlayClick = (e) => {
      if (e.target === overlay && opts.dismissible !== false) {
        onCancel();
      }
    };

    const onKey = (e) => {
      if (e.key === 'Escape' && opts.dismissible !== false) {
        e.preventDefault();
        onCancel();
      }
      if (kind === 'prompt' && e.key === 'Enter' && !e.shiftKey) {
        const primary = actionsEl.querySelector('[data-role="primary"]');
        if (primary) { e.preventDefault(); primary.click(); }
      }
    };

    let removeTrap = null;
    function cleanup() {
      overlay.removeEventListener('click', onOverlayClick);
      document.removeEventListener('keydown', onKey, true);
      if (removeTrap) removeTrap();
      removeTrap = null;
    }

    let onCancel = () => {};

    return await new Promise((resolve) => {
      onCancel = () => {
        if (kind === 'confirm') resolve(resolveWith(false));
        else if (kind === 'prompt') resolve(resolveWith(null));
        else resolve(resolveWith(undefined));
      };

      if (opts.input) {
        inputWrap.style.display = '';
        inputEl.value = opts.input.value || '';
        inputEl.placeholder = opts.input.placeholder || '';
        if (opts.input.type) inputEl.type = opts.input.type;
        if (opts.input.inputMode) inputEl.inputMode = opts.input.inputMode;
        if (opts.input.readOnly) inputEl.readOnly = true;
      }

      buttons.forEach((b, idx) => {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'astro-ui-btn' + (b.primary ? ' primary' : '') + (b.danger ? ' danger' : '');
        btn.textContent = b.text || (idx === 0 ? 'OK' : 'Cancel');
        if (b.primary) btn.setAttribute('data-role', 'primary');
        btn.addEventListener('click', async () => {
          if (b.onClick) {
            const r = await b.onClick({ input: inputEl.value });
            resolve(resolveWith(r));
          } else {
            resolve(resolveWith(b.value));
          }
        });
        actionsEl.appendChild(btn);
      });

      closeBtn.onclick = onCancel;
      overlay.addEventListener('click', onOverlayClick);
      document.addEventListener('keydown', onKey, true);
      setOpen(overlay, true);
      removeTrap = trapFocus(modal, opts.input ? inputEl : actionsEl.querySelector('[data-role="primary"]') || actionsEl.querySelector('button'));
    });
  }

  function toast(message, type = 'info', durationMs = 2400) {
    ensureStyles();
    try {
      const el = document.createElement('div');
      el.className = 'astro-ui-toast';
      el.textContent = String(message || '');
      if (type === 'error') el.style.borderColor = 'rgba(239,68,68,0.35)';
      if (type === 'success') el.style.borderColor = 'rgba(16,185,129,0.35)';
      document.body.appendChild(el);
      requestAnimationFrame(() => el.classList.add('show'));
      setTimeout(() => {
        el.classList.remove('show');
        setTimeout(() => { try { el.remove(); } catch (_) {} }, prefersReducedMotion() ? 0 : 180);
      }, Math.max(1200, durationMs | 0));
    } catch (_) {}
  }

  // ═══════════════════════════════════════════════════════════════════════════
  // SWIPE-BACK GESTURE MODULE  v3
  // True iOS-quality swipe-from-edge-back gesture.
  //
  // Features:
  //   • Triggers only from the very edge of the screen (~16px)
  //   • Content follows finger 1:1 from the first pixel — zero dead zone
  //   • iOS-style parallax: previous page peeks in from the left at 30% speed
  //   • Realistic layered shadow on sliding content edge
  //   • Circular arrow indicator with color change + haptic at threshold
  //   • Spring physics on release (snap-back or slide-off)
  //   • Velocity-aware: fast swipes commit even below threshold distance
  //
  //   AstroUI.swipeBack.setup({ onBack, canSwipe, target })
  //   AstroUI.swipeBack.destroy()
  // ═══════════════════════════════════════════════════════════════════════════
  const swipeBack = (() => {
    let _active = false;
    let _cleanup = null;

    function setup(opts) {
      if (!opts) opts = {};
      if (_active) destroy();

      var EDGE      = opts.edgeZone  || 16;
      var THRESHOLD = opts.threshold || 80;
      var onBack    = typeof opts.onBack  === 'function' ? opts.onBack  : function(){};
      var canSwipe  = typeof opts.canSwipe === 'function' ? opts.canSwipe : function(){ return true; };
      var getTarget = typeof opts.target === 'function'  ? opts.target  : function(){ return document.querySelector('.content'); };

      // ── State ──
      var startX = 0, startY = 0, dx = 0, lastDx = 0, lastTime = 0;
      var velocity = 0;
      var phase = 'idle'; // idle | detecting | swiping | cancelled
      var hapticFired = false;
      var scrimEl = null, arrowEl = null, shadowEl = null;
      var savedStyles = null;

      // ── Haptic ──
      function haptic(style) {
        try { var t = window.Telegram && window.Telegram.WebApp; if (t && t.HapticFeedback) t.HapticFeedback.impactOccurred(style); } catch(e){}
      }

      // ── Overlay elements ──
      function getScrim() {
        if (!scrimEl) {
          scrimEl = document.createElement('div');
          scrimEl.className = '_swipe-scrim';
          scrimEl.style.cssText = 'position:fixed;inset:0;z-index:9997;background:rgba(0,0,0,0);pointer-events:none;';
          document.body.appendChild(scrimEl);
        }
        return scrimEl;
      }

      function getShadow() {
        if (!shadowEl) {
          shadowEl = document.createElement('div');
          shadowEl.className = '_swipe-shadow';
          shadowEl.style.cssText = 'position:fixed;top:0;bottom:0;width:12px;z-index:9999;pointer-events:none;opacity:0;' +
            'background:linear-gradient(to right,rgba(0,0,0,.12),transparent);';
          document.body.appendChild(shadowEl);
        }
        return shadowEl;
      }

      function getArrow() {
        if (!arrowEl) {
          arrowEl = document.createElement('div');
          arrowEl.className = '_swipe-arrow';
          arrowEl.style.cssText = 'position:fixed;top:50%;left:0;z-index:10001;width:36px;height:36px;border-radius:50%;' +
            'background:var(--brand,#ec5652);display:flex;align-items:center;justify-content:center;' +
            'transform:translate(-40px,-50%) scale(.5);opacity:0;pointer-events:none;will-change:transform,opacity;' +
            'box-shadow:0 2px 12px rgba(0,0,0,.3);';
          arrowEl.innerHTML = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="15 18 9 12 15 6"/></svg>';
          document.body.appendChild(arrowEl);
        }
        return arrowEl;
      }

      function removeOverlays() {
        [scrimEl, arrowEl, shadowEl].forEach(function(el) { if (el) try { el.remove(); } catch(e){} });
        scrimEl = arrowEl = shadowEl = null;
      }

      // ── Style save/restore for target ──
      function saveTargetStyles(el) {
        savedStyles = {};
        ['transform','transition','zIndex','position','background'].forEach(function(p) {
          savedStyles[p] = el.style[p] || '';
        });
      }
      function restoreTargetStyles(el) {
        if (!savedStyles) return;
        Object.keys(savedStyles).forEach(function(p) { el.style[p] = savedStyles[p]; });
        savedStyles = null;
      }

      // ── Touch: Start ──
      function onTouchStart(e) {
        if (phase !== 'idle') return;
        if (!canSwipe()) return;
        var t = e.touches[0];
        if (t.clientX > EDGE) return;
        startX = t.clientX;
        startY = t.clientY;
        dx = 0; lastDx = 0; velocity = 0;
        lastTime = Date.now();
        hapticFired = false;
        phase = 'detecting';
      }

      // ── Touch: Move ──
      function onTouchMove(e) {
        if (phase === 'idle' || phase === 'cancelled') return;

        var t = e.touches[0];
        var mx = t.clientX - startX;
        var my = t.clientY - startY;
        var now = Date.now();

        // ── Detection phase (~4px to decide direction) ──
        if (phase === 'detecting') {
          try { e.preventDefault(); } catch(ex){}
          var ax = Math.abs(mx), ay = Math.abs(my);
          if (ax < 3 && ay < 3) return;

          // Vertical intent → cancel, let browser scroll
          if (ay > ax * 1.3) { phase = 'cancelled'; return; }
          // Moving left → cancel
          if (mx < -1) { phase = 'cancelled'; return; }

          // Engage! Save target styles immediately
          phase = 'swiping';
          haptic('light');
          var target = getTarget();
          if (target) {
            saveTargetStyles(target);
            var cs = window.getComputedStyle(target);
            var pos = cs.position;
            if (pos === 'static' || pos === 'relative') {
              target.style.position = 'relative';
              if (cs.backgroundColor === 'rgba(0, 0, 0, 0)' || cs.backgroundColor === 'transparent') {
                target.style.background = 'var(--bg1, #0d1a22)';
              }
            }
            target.style.zIndex = '10000';
          }
        }

        if (phase !== 'swiping') return;
        try { e.preventDefault(); } catch(ex){}

        // Track velocity (for fast-swipe detection)
        var dt = now - lastTime;
        if (dt > 0) { velocity = (mx - lastDx) / dt; } // px/ms
        lastDx = mx; lastTime = now;

        dx = Math.max(0, mx);
        var target = getTarget();
        if (!target) return;
        var W = window.innerWidth;

        // ── Move content 1:1 with finger ──
        target.style.transition = 'none';
        target.style.transform = 'translate3d(' + dx + 'px,0,0)';

        // ── Shadow on left edge of sliding content ──
        var sh = getShadow();
        var shadowOpacity = Math.min(dx / 60, 1);
        sh.style.transform = 'translate3d(' + (dx - 20) + 'px,0,0)';
        sh.style.opacity = shadowOpacity.toFixed(2);

        // ── Scrim (darkens the area behind) ──
        var sc = getScrim();
        var scrimAlpha = Math.min(dx / (W * 0.5), 1) * 0.4;
        sc.style.background = 'rgba(0,0,0,' + scrimAlpha.toFixed(3) + ')';

        // ── Arrow indicator ──
        var ar = getArrow();
        var tp = Math.min(dx / THRESHOLD, 1); // threshold progress 0→1
        // Arrow slides in from left: starts at -40px, arrives at +10px
        var arX = -40 + 50 * tp;
        // Ease: make it decelerate as it approaches
        arX = -40 + 50 * (1 - Math.pow(1 - tp, 2));
        var arScale = 0.5 + tp * 0.5;
        var arOp = Math.min(tp * 2.5, 1);
        ar.style.transition = 'none';
        ar.style.transform = 'translate(' + arX.toFixed(1) + 'px,-50%) scale(' + arScale.toFixed(2) + ')';
        ar.style.opacity = arOp.toFixed(2);

        if (tp >= 1) {
          ar.style.background = 'var(--ok, #10b981)';
          if (!hapticFired) { hapticFired = true; haptic('medium'); }
        } else {
          ar.style.background = 'var(--brand, #ec5652)';
          hapticFired = false;
        }
      }

      // ── Touch: End ──
      function onTouchEnd() {
        if (phase === 'idle') return;

        var target = getTarget();
        // Commit if: dragged past threshold OR fast-swiped (velocity > 0.4 px/ms and dx > 30)
        var committed = (phase === 'swiping') && (dx >= THRESHOLD || (velocity > 0.4 && dx > 30));

        if (phase === 'swiping' && target) {
          var W = window.innerWidth;

          if (committed) {
            // ── Slide off → navigate back ──
            // Calculate remaining distance and use velocity to set duration
            var remaining = W - dx + 20;
            var speed = Math.max(velocity, 0.5); // at least 0.5 px/ms
            var dur = Math.min(Math.max(remaining / speed, 180), 350); // 180-350ms

            target.style.transition = 'transform ' + dur + 'ms cubic-bezier(.15,.6,.3,1)';
            target.style.transform = 'translate3d(' + (W + 20) + 'px,0,0)';
            haptic('heavy');

            // Animate overlays out
            if (scrimEl) { scrimEl.style.transition = 'background ' + dur + 'ms ease-out'; scrimEl.style.background = 'rgba(0,0,0,0)'; }
            if (shadowEl) { shadowEl.style.transition = 'opacity ' + dur + 'ms ease-out'; shadowEl.style.opacity = '0'; }
            if (arrowEl) {
              arrowEl.style.transition = 'all ' + Math.min(dur, 200) + 'ms ease-out';
              arrowEl.style.opacity = '0';
              arrowEl.style.transform = 'translate(24px,-50%) scale(1.1)';
            }

            setTimeout(function() {
              if (target) restoreTargetStyles(target);
              removeOverlays();
              try { onBack(); } catch(ex){}
            }, dur + 10);

          } else {
            // ── Snap back with spring ──
            target.style.transition = 'transform .3s cubic-bezier(.2,1,.3,1)';
            target.style.transform = 'translate3d(0,0,0)';

            if (scrimEl) { scrimEl.style.transition = 'background .25s ease-out'; scrimEl.style.background = 'rgba(0,0,0,0)'; }
            if (shadowEl) { shadowEl.style.transition = 'opacity .25s ease-out'; shadowEl.style.opacity = '0'; }
            if (arrowEl) {
              arrowEl.style.transition = 'all .2s ease-out';
              arrowEl.style.opacity = '0';
              arrowEl.style.transform = 'translate(-40px,-50%) scale(.4)';
            }

            setTimeout(function() {
              if (target) restoreTargetStyles(target);
              removeOverlays();
            }, 320);
          }
        } else {
          removeOverlays();
          if (committed) { try { onBack(); } catch(ex){} }
        }

        phase = 'idle';
        dx = 0; velocity = 0;
      }

      // ── Attach ──
      document.addEventListener('touchstart',  onTouchStart, { passive: true });
      document.addEventListener('touchmove',   onTouchMove,  { passive: false });
      document.addEventListener('touchend',    onTouchEnd,   { passive: true });
      document.addEventListener('touchcancel', onTouchEnd,   { passive: true });

      _active = true;
      _cleanup = function() {
        document.removeEventListener('touchstart',  onTouchStart);
        document.removeEventListener('touchmove',   onTouchMove);
        document.removeEventListener('touchend',    onTouchEnd);
        document.removeEventListener('touchcancel', onTouchEnd);
        removeOverlays();
      };
    }

    function destroy() {
      if (_cleanup) _cleanup();
      _cleanup = null;
      _active  = false;
    }

    return { setup: setup, destroy: destroy, get active() { return _active; } };
  })();
  // ═══════════════════════════════════════════════════════════════════════════

  window.AstroUI = Object.assign(existing || {}, {
    __ready: true,
    goFullscreen,
    waitForViewportStable,
    waitForFullscreen,
    waitForExpanded,
    swipeBack,
    toast,
    alert: async ({ title, message, okText } = {}) => {
      await showModal({
        kind: 'alert',
        title: title || '',
        message: message || '',
        buttons: [{ text: okText || 'OK', value: undefined, primary: true }],
      });
    },
    confirm: async ({ title, message, okText, cancelText, danger } = {}) => {
      const v = await showModal({
        kind: 'confirm',
        title: title || '',
        message: message || '',
        buttons: [
          { text: cancelText || 'Cancel', value: false },
          { text: okText || 'OK', value: true, primary: true, danger: !!danger },
        ],
      });
      return !!v;
    },
    // N-way chooser: resolves to the picked button's value, false on
    // dismiss/backdrop (confirm semantics). buttons render in given order.
    choose: async ({ title, message, buttons } = {}) => {
      const v = await showModal({
        kind: 'confirm',
        title: title || '',
        message: message || '',
        buttons: (buttons || []).map((b) => ({
          text: b.text, value: b.value, primary: !!b.primary, danger: !!b.danger,
        })),
      });
      return v;
    },
    prompt: async ({ title, message, placeholder, defaultValue, okText, cancelText, inputMode, readOnly } = {}) => {
      const v = await showModal({
        kind: 'prompt',
        title: title || '',
        message: message || '',
        input: { value: defaultValue || '', placeholder: placeholder || '', inputMode: inputMode || '', readOnly: !!readOnly },
        buttons: [
          { text: cancelText || 'Cancel', value: null },
          { text: okText || 'OK', primary: true, onClick: ({ input }) => input },
        ],
      });
      return v;
    },
    copyDialog: async ({ title, message, text, okText, copyText } = {}) => {
      const t = String(text || '');
      await showModal({
        kind: 'alert',
        title: title || '',
        message: message || '',
        input: { value: t, readOnly: true },
        buttons: [
          {
            text: copyText || 'Copy',
            value: undefined,
            onClick: async () => {
              try { await navigator.clipboard.writeText(t); toast('Copied', 'success', 1400); } catch (_) {}
            }
          },
          { text: okText || 'Close', value: undefined, primary: true },
        ],
      });
    },
  });

  // Run after API is registered.
  try { bootstrapTelegramViewport(); } catch (_) {}
})();

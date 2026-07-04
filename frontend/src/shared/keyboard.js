// On-screen keyboard handling for Android/iOS WebViews (incl. Telegram).
//
// Telegram's Android WebView often OVERLAYS the keyboard on the page and
// reports nothing: no window resize, no visualViewport change, sometimes not
// even a viewportChanged. So this module does NOT rely on detection to act:
//
//   • focusin on a text field (touch device) → IMMEDIATELY:
//       - assume a keyboard (~45% of screen, capped 420px) and publish it as
//         bottom padding via html.kb-open + --kb-height
//       - pin the field into the TOP THIRD of the screen with INSTANT
//         scrolls, retried several times (smooth scrolls get cancelled by
//         the keyboard animation; the top third is visible under ANY keyboard)
//   • focusout → remove padding.
//   • visualViewport / Telegram viewportChanged refine the height when they
//     do report (real value wins over the estimate via max()).
//
// Published for stylesheets:  html.kb-open  +  --kb-height (px).
// Optional on-device diagnostics: append ?kbdebug=1 to the page URL.

let started = false;
let vvKb = 0;
let tgKb = 0;
let estKb = 0;
let raf = 0;
let pinTimers = [];
let debugEl = null;

const isEditable = (el) =>
  !!el && (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA' || el.isContentEditable);

const isTouchLike = () => {
  try {
    if (window.matchMedia('(pointer: coarse)').matches) return true;
    if ((navigator.maxTouchPoints || 0) > 0) return true;
    const p = window.Telegram?.WebApp?.platform || '';
    return p === 'android' || p === 'ios';
  } catch (_) { return false; }
};

// Android Telegram overlays the keyboard without resizing or panning the
// WebView — the one platform where scroll-based fixes can't be trusted.
export function isAndroidLike() {
  try {
    if ((window.Telegram?.WebApp?.platform || '') === 'android') return true;
    return /android/i.test(navigator.userAgent || '');
  } catch (_) { return false; }
}

function scrollableAncestor(el) {
  let n = el.parentElement;
  while (n) {
    try {
      const cs = getComputedStyle(n);
      if (/(auto|scroll)/.test(cs.overflowY) && n.scrollHeight > n.clientHeight + 4) return n;
    } catch (_) { /* ignore */ }
    n = n.parentElement;
  }
  return document.scrollingElement || document.documentElement;
}

// Instantly place the field in the top third of the screen — visible under
// any keyboard. No smooth behavior: WebViews cancel smooth scrolls while the
// keyboard is animating.
export function pinFieldVisible(el) {
  try {
    if (!el || !el.getBoundingClientRect) return;
    // Fields inside fixed-position wrappers (e.g. the floating GB editor)
    // are already viewport-anchored — scrolling would only shift content
    // beneath them.
    for (let n = el; n && n !== document.body; n = n.parentElement) {
      try { if (getComputedStyle(n).position === 'fixed') return; } catch (_) { break; }
    }
    const r = el.getBoundingClientRect();
    const topTarget = Math.max(90, Math.round((window.innerHeight || 800) * 0.18));
    const delta = Math.round(r.top - topTarget);
    if (Math.abs(delta) < 8) return;
    const sc = scrollableAncestor(el);
    if (sc === document.scrollingElement || sc === document.documentElement || sc === document.body) {
      window.scrollBy(0, delta);
    } else {
      sc.scrollTop += delta;
    }
  } catch (_) { /* ignore */ }
}

function renderDebug() {
  if (!debugEl) return;
  const vv = window.visualViewport;
  debugEl.textContent =
    `vv:${vvKb} tg:${tgKb} est:${estKb} open:${document.documentElement.classList.contains('kb-open')}` +
    ` ih:${window.innerHeight} vvh:${vv ? Math.round(vv.height) : '-'}`;
}

function apply() {
  raf = 0;
  const kb = Math.max(vvKb, tgKb, estKb);
  const root = document.documentElement;
  root.style.setProperty('--kb-height', kb + 'px');
  root.classList.toggle('kb-open', kb > 60);
  renderDebug();
}

const schedule = () => { if (!raf) raf = requestAnimationFrame(apply); };

function startPinning(target) {
  pinTimers.forEach(clearTimeout);
  pinTimers = [60, 250, 600, 1000].map((ms) => setTimeout(() => {
    if (document.activeElement === target) pinFieldVisible(target);
  }, ms));
}

export function initKeyboardWatcher() {
  if (started) return;
  started = true;

  // Refinement layer 1: visualViewport (regular browsers, iOS).
  const vv = window.visualViewport;
  if (vv) {
    const onVv = () => {
      vvKb = Math.max(0, Math.round((window.innerHeight || 0) - vv.height));
      schedule();
    };
    vv.addEventListener('resize', onVv);
    vv.addEventListener('scroll', onVv);
    onVv();
  }

  // Refinement layer 2: Telegram's viewport events.
  try {
    const tg = window.Telegram?.WebApp;
    if (tg?.onEvent) {
      const onTg = () => {
        const vh = Number(tg.viewportHeight || 0);
        const sh = Number(tg.viewportStableHeight || 0);
        const byStable = (vh > 0 && sh > 0) ? sh - vh : 0;
        const byWindow = (vh > 0 && window.innerHeight > 0) ? window.innerHeight - vh : 0;
        tgKb = Math.max(0, Math.round(Math.max(byStable, byWindow)));
        schedule();
      };
      tg.onEvent('viewportChanged', onTg);
      onTg();
    }
  } catch (_) { /* ignore */ }

  // Action layer: act on focus immediately — no detection required.
  document.addEventListener('focusin', (e) => {
    if (!isEditable(e.target) || !isTouchLike()) return;
    estKb = Math.round(Math.min(420, (window.innerHeight || 800) * 0.45));
    schedule();
    startPinning(e.target);
  });
  document.addEventListener('focusout', () => {
    estKb = 0;
    pinTimers.forEach(clearTimeout);
    pinTimers = [];
    setTimeout(schedule, 60);
  });

  // interactive-widget=resizes-content path: the window itself shrinks when
  // the keyboard opens — keep the focused field pinned in the smaller view.
  window.addEventListener('resize', () => {
    const ae = document.activeElement;
    if (!isEditable(ae)) return;
    setTimeout(() => { if (document.activeElement === ae) pinFieldVisible(ae); }, 120);
  });

  // On-device diagnostics: ?kbdebug=1 shows live detection values.
  try {
    if (/[?&]kbdebug=1/.test(window.location.search)) {
      debugEl = document.createElement('div');
      debugEl.style.cssText =
        'position:fixed;top:4px;left:4px;z-index:99999;background:rgba(0,0,0,0.8);color:#0f0;' +
        'font:11px/1.4 monospace;padding:4px 8px;border-radius:6px;pointer-events:none;direction:ltr;';
      document.body.appendChild(debugEl);
      setInterval(renderDebug, 500);
    }
  } catch (_) { /* ignore */ }
}

// Current keyboard height in px (0 when closed / undetected).
export function keyboardHeight() {
  return Math.max(vvKb, tgKb, estKb);
}

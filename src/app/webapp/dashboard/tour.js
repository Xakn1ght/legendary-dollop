/**
 * AstroTour — Interactive spotlight product tour.
 *
 *   AstroTour.start(steps)          Start the tour
 *   AstroTour.stop()                End the tour (marks as completed)
 *   AstroTour.isCompleted()         Has the user finished/skipped the tour?
 *   AstroTour.reset()               Clear the "completed" flag so it shows again
 *
 * Each step: { target, title, desc, placement }
 *   target    — CSS selector string (null/empty = centered, no spotlight)
 *   title     — string  OR  { en: '…', fa: '…' }
 *   desc      — string  OR  { en: '…', fa: '…' }
 *   placement — 'auto' (default) | 'top' | 'bottom'
 *
 * To remove the feature entirely, just stop including this script.
 */
(() => {
  'use strict';

  /* ──────────────── constants ──────────────── */
  const STORAGE_KEY = 'astro_tour_v1';
  const PADDING     = 8;    // px around spotlight target
  const RADIUS      = 14;   // px border-radius of spotlight

  /* ──────────────── state ──────────────── */
  let active      = false;
  let steps       = [];
  let idx         = 0;
  let onCompleteCb = null;

  /* DOM references (created once per session) */
  let styleEl, overlayEl, spotEl, tipEl;
  let _keyHandler, _resizeHandler, _resizeTimer;

  /* ──────────────── helpers ──────────────── */
  function getLang() {
    try {
      if (window.AstroLang && typeof window.AstroLang.getLang === 'function')
        return window.AstroLang.getLang();
    } catch (_) {}
    return (document.documentElement.lang || 'en').slice(0, 2);
  }

  function t(val) {
    if (!val) return '';
    if (typeof val === 'string') return val;
    var lang = getLang();
    return val[lang] || val.en || val.fa || '';
  }

  function isRtl() { return getLang() === 'fa'; }

  function haptic(style) {
    try {
      var tg = window.Telegram && window.Telegram.WebApp;
      if (tg && tg.HapticFeedback && tg.HapticFeedback.impactOccurred)
        tg.HapticFeedback.impactOccurred(style);
    } catch (_) {}
  }

  function reducedMotion() {
    try { return !!(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches); }
    catch (_) { return false; }
  }

  /* ──────────────── persistence ──────────────── */
  function isCompleted() {
    try { return localStorage.getItem(STORAGE_KEY) === '1'; } catch (_) { return false; }
  }
  function markCompleted() {
    try { localStorage.setItem(STORAGE_KEY, '1'); } catch (_) {}
  }
  function reset() {
    try { localStorage.removeItem(STORAGE_KEY); } catch (_) {}
  }

  /* ──────────────── CSS ──────────────── */
  function injectStyles() {
    if (styleEl) return;
    styleEl = document.createElement('style');
    styleEl.id = 'astro-tour-css';
    styleEl.textContent = [
      /* overlay — blocks page interaction */
      '.atour-overlay{',
      '  position:fixed;inset:0;z-index:99993;',
      '  pointer-events:auto;',
      '}',

      /* spotlight hole */
      '.atour-spot{',
      '  position:fixed;z-index:99994;',
      '  border-radius:' + RADIUS + 'px;',
      '  box-shadow:0 0 0 9999px rgba(0,0,0,0.72);',
      '  pointer-events:none;',
      '  transition:all .3s cubic-bezier(.4,0,.2,1);',
      '}',
      '.atour-spot::after{',
      '  content:"";position:absolute;inset:-4px;',
      '  border-radius:inherit;',
      '  border:2px solid var(--brand,#ec5652);',
      '  opacity:.5;',
      '  animation:atour-pulse 2s ease-in-out infinite;',
      '}',
      '@keyframes atour-pulse{',
      '  0%,100%{opacity:.3;transform:scale(1)}',
      '  50%{opacity:.7;transform:scale(1.02)}',
      '}',

      /* tooltip card */
      '.atour-tip{',
      '  position:fixed;z-index:99995;',
      '  width:max(280px,min(340px,calc(100vw - 32px)));',
      '  background:var(--panel,#1a2a36);',
      '  border:1px solid var(--line,rgba(255,255,255,.12));',
      '  border-radius:18px;',
      '  padding:20px 18px 16px;',
      '  box-shadow:0 20px 60px rgba(0,0,0,.5);',
      '  backdrop-filter:blur(20px) saturate(180%);',
      '  -webkit-backdrop-filter:blur(20px) saturate(180%);',
      '  color:var(--text,#fff);',
      '  opacity:0;transform:translateY(10px);',
      '  transition:opacity .25s ease,transform .25s ease;',
      '}',
      '.atour-tip.show{opacity:1;transform:translateY(0)}',

      /* arrow pointer */
      '.atour-tip .atour-arrow{',
      '  position:absolute;width:14px;height:14px;',
      '  background:var(--panel,#1a2a36);',
      '  border:1px solid var(--line,rgba(255,255,255,.12));',
      '  border-radius:3px;',
      '  transform:rotate(45deg);',
      '  z-index:-1;',
      '}',
      '.atour-tip .atour-arrow.top{',
      '  top:-8px;left:50%;margin-left:-7px;',
      '  border-bottom:0;border-right:0;',
      '}',
      '.atour-tip .atour-arrow.bottom{',
      '  bottom:-8px;left:50%;margin-left:-7px;',
      '  border-top:0;border-left:0;',
      '}',

      /* title & description */
      '.atour-title{font-size:16px;font-weight:800;line-height:1.3;margin-bottom:6px}',
      '.atour-desc{font-size:13.5px;line-height:1.6;opacity:.85;margin-bottom:16px;white-space:pre-line}',

      /* progress dots */
      '.atour-dots{display:flex;gap:6px;margin-bottom:16px;flex-wrap:wrap}',
      '.atour-dot{',
      '  width:8px;height:8px;border-radius:50%;',
      '  background:var(--line,rgba(255,255,255,.15));',
      '  transition:all .2s ease;flex-shrink:0;',
      '}',
      '.atour-dot.cur{background:var(--brand,#ec5652);transform:scale(1.3)}',
      '.atour-dot.done{background:var(--ok,#10b981)}',

      /* footer */
      '.atour-foot{display:flex;align-items:center;justify-content:space-between;gap:8px}',
      '.atour-count{font-size:12px;opacity:.45;font-weight:600;white-space:nowrap}',
      '.atour-btns{display:flex;gap:8px;flex-wrap:wrap;justify-content:flex-end}',

      /* buttons */
      '.atour-btn{',
      '  border-radius:10px;',
      '  border:1px solid var(--line,rgba(255,255,255,.12));',
      '  background:var(--chip,rgba(255,255,255,.06));',
      '  color:var(--text,#fff);',
      '  font-weight:700;font-size:13px;',
      '  padding:8px 14px;cursor:pointer;',
      '  transition:transform .1s ease;',
      '  -webkit-tap-highlight-color:transparent;',
      '}',
      '.atour-btn:active{transform:translateY(1px)}',
      '.atour-btn.pri{background:var(--brand,#ec5652);border-color:var(--brand,#ec5652);color:#fff}',
      '.atour-btn.skip{background:transparent;border-color:transparent;opacity:.55;font-size:12px;padding:8px 10px}',

      /* welcome center mode (no target) */
      '.atour-spot.center{',
      '  left:50%;top:50%;width:0;height:0;',
      '  border-radius:50%;',
      '  transform:translate(-50%,-50%);',
      '}',

      /* reduced motion */
      '@media(prefers-reduced-motion:reduce){',
      '  .atour-spot,.atour-tip{transition:none}',
      '  .atour-spot::after{animation:none}',
      '}',
    ].join('\n');
    document.head.appendChild(styleEl);
  }

  /* ──────────────── DOM creation ──────────────── */
  function createDOM() {
    if (overlayEl) return;
    injectStyles();

    overlayEl = document.createElement('div');
    overlayEl.className = 'atour-overlay';

    spotEl = document.createElement('div');
    spotEl.className = 'atour-spot';

    tipEl = document.createElement('div');
    tipEl.className = 'atour-tip';

    document.body.appendChild(overlayEl);
    document.body.appendChild(spotEl);
    document.body.appendChild(tipEl);

    /* click on dark overlay = next */
    overlayEl.addEventListener('click', function (e) {
      if (e.target === overlayEl) next();
    });
  }

  function removeDOM() {
    try { overlayEl && overlayEl.remove(); } catch (_) {}
    try { spotEl && spotEl.remove(); } catch (_) {}
    try { tipEl && tipEl.remove(); } catch (_) {}
    overlayEl = spotEl = tipEl = null;
  }

  /* ──────────────── scrolling ──────────────── */

  /**
   * Scroll the page so `el` is vertically centered in the visible area.
   *
   * Uses three scroll methods in priority order to maximise reliability
   * across Telegram WebViews, Samsung browser, iOS WKWebView, etc.:
   *
   *   1. Direct `.content.scrollTop` — primary for the dashboard flex layout.
   *      Uses clientHeight (not getBoundingClientRect().height) for the
   *      visible area, which avoids a bug where the full document height
   *      is returned for document.scrollingElement.
   *   2. el.scrollIntoView({ block:'center' }) — native browser fallback.
   *   3. window.scrollBy — last resort for document-level scroll.
   *
   * For fixed/sticky elements (header, bottom nav) no scrolling is needed.
   */
  function scrollToTarget(el, cb) {
    if (!el) { setTimeout(cb, 30); return; }

    // Fixed/sticky ancestors mean the element is always visible.
    try {
      var node = el;
      while (node && node !== document.body && node !== document.documentElement) {
        var pos = window.getComputedStyle(node).position;
        if (pos === 'fixed' || pos === 'sticky') {
          setTimeout(cb, 50);
          return;
        }
        node = node.parentElement;
      }
    } catch (_) {}

    // ── Attempt scroll ──
    var animated = _doScrollToCenter(el);

    // ── Verify after scroll settles, force again if needed ──
    var delay = reducedMotion() ? 80 : (animated ? 480 : 120);
    setTimeout(function () {
      if (!_isElementVisible(el)) {
        _forceScrollToCenter(el);
      }
      setTimeout(cb, 80);
    }, delay);
  }

  /**
   * Try to scroll `.content` (and/or the document) so `el` is centred.
   * Returns true if a smooth animation was started.
   *
   * Only the first method that actually scrolls fires — the rest are
   * skipped so they don't fight each other.
   */
  function _doScrollToCenter(el) {
    var animated = false;
    var didScroll = false;

    // ── Method 1: scroll .content container directly ──
    var container = null;
    try { container = document.querySelector('.content'); } catch (_) {}

    if (container) {
      try {
        var cRect  = container.getBoundingClientRect();
        var eRect  = el.getBoundingClientRect();
        // clientHeight = reliable visible height (not full document height)
        var visH   = container.clientHeight;
        var elMid  = eRect.top + eRect.height / 2;
        var cMid   = cRect.top + visH / 2;
        var delta  = Math.round(elMid - cMid);

        if (Math.abs(delta) > 5 && container.scrollHeight > visH + 2) {
          var target = container.scrollTop + delta;
          var maxSc  = container.scrollHeight - visH;
          target = Math.max(0, Math.min(Math.round(target), maxSc));

          var startSc = container.scrollTop;
          var diff    = Math.abs(target - startSc);

          if (diff > 3) {
            if (!reducedMotion() && diff < 2000) {
              var dur = Math.min(400, Math.max(200, diff * 0.5));
              var t0  = null;
              var sc  = container;
              var sS  = startSc;
              var tS  = target;
              function _tick(ts) {
                if (!t0) t0 = ts;
                var p = Math.min((ts - t0) / dur, 1);
                var e = 1 - Math.pow(1 - p, 3);
                sc.scrollTop = sS + (tS - sS) * e;
                if (p < 1) requestAnimationFrame(_tick);
              }
              requestAnimationFrame(_tick);
              animated = true;
            } else {
              container.scrollTop = target;
            }
            didScroll = true;
          }
        }
      } catch (_) {}
    }

    // ── Method 2 (fallback): native scrollIntoView ──
    if (!didScroll) {
      try {
        el.scrollIntoView({ block: 'center', behavior: 'auto' });
        didScroll = true;
      } catch (_) {
        try { el.scrollIntoView(true); didScroll = true; } catch (_2) {}
      }
    }

    // ── Method 3 (last resort): window.scrollBy ──
    if (!didScroll) {
      try {
        var r   = el.getBoundingClientRect();
        var mid = window.innerHeight / 2;
        var d   = r.top + r.height / 2 - mid;
        if (Math.abs(d) > 30) window.scrollBy(0, Math.round(d));
      } catch (_) {}
    }

    return animated;
  }

  /** Force-scroll to center el — instant, no animation. */
  function _forceScrollToCenter(el) {
    try { el.scrollIntoView({ block: 'center', behavior: 'auto' }); } catch (_) {}

    try {
      var c = document.querySelector('.content');
      if (c) {
        var cR = c.getBoundingClientRect();
        var eR = el.getBoundingClientRect();
        var d  = eR.top + eR.height / 2 - cR.top - c.clientHeight / 2;
        if (Math.abs(d) > 5) c.scrollTop += Math.round(d);
      }
    } catch (_) {}

    try {
      var eR2 = el.getBoundingClientRect();
      var mid = window.innerHeight / 2;
      var d2  = eR2.top + eR2.height / 2 - mid;
      if (Math.abs(d2) > 30) window.scrollBy(0, Math.round(d2));
    } catch (_) {}
  }

  /** Check whether at least part of `el` is inside the viewport. */
  function _isElementVisible(el) {
    try {
      var r  = el.getBoundingClientRect();
      var vh = window.innerHeight;
      var visTop = Math.max(r.top, 0);
      var visBot = Math.min(r.bottom, vh);
      return (visBot - visTop) >= Math.min(r.height * 0.3, 20);
    } catch (_) { return true; }
  }

  /* ──────────────── positioning ──────────────── */
  function positionSpot(el) {
    if (!spotEl) return;
    if (!el) {
      spotEl.className = 'atour-spot center';
      spotEl.style.left = '50%';
      spotEl.style.top  = '50%';
      spotEl.style.width = '0';
      spotEl.style.height = '0';
      spotEl.style.transform = 'translate(-50%,-50%)';
      return;
    }
    spotEl.className = 'atour-spot';
    spotEl.style.transform = '';
    var r = el.getBoundingClientRect();
    spotEl.style.left   = Math.round(r.left   - PADDING) + 'px';
    spotEl.style.top    = Math.round(r.top    - PADDING) + 'px';
    spotEl.style.width  = Math.round(r.width  + PADDING * 2) + 'px';
    spotEl.style.height = Math.round(r.height + PADDING * 2) + 'px';
  }

  function positionTip(el, step) {
    if (!tipEl) return;
    var rtl      = isRtl();
    var total    = steps.length;
    var title    = t(step.title);
    var desc     = t(step.desc);
    var isFirst  = idx === 0;
    var isLast   = idx === total - 1;

    /* labels */
    var prevLbl  = rtl ? '\u0642\u0628\u0644\u06CC' : 'Previous';
    var nextLbl  = isLast
      ? (rtl ? '\u067E\u0627\u06CC\u0627\u0646' : 'Got it!')
      : (rtl ? '\u0628\u0639\u062F\u06CC' : 'Next');
    var skipLbl  = rtl ? '\u0631\u062F \u0634\u062F\u0646' : 'Skip';

    /* dots */
    var dots = '';
    for (var i = 0; i < total; i++) {
      var cls = 'atour-dot';
      if (i === idx) cls += ' cur';
      else if (i < idx) cls += ' done';
      dots += '<div class="' + cls + '"></div>';
    }

    /* buttons */
    var btns = '';
    if (!isFirst) btns += '<button class="atour-btn" data-a="prev">' + prevLbl + '</button>';
    btns += '<button class="atour-btn skip" data-a="skip">' + skipLbl + '</button>';
    btns += '<button class="atour-btn pri" data-a="next">' + nextLbl + '</button>';

    tipEl.style.direction = rtl ? 'rtl' : 'ltr';
    tipEl.innerHTML =
      '<div class="atour-arrow" id="atourArrow"></div>' +
      '<div class="atour-title">' + title + '</div>' +
      '<div class="atour-desc">' + desc + '</div>' +
      '<div class="atour-dots">' + dots + '</div>' +
      '<div class="atour-foot">' +
        '<span class="atour-count">' + (idx + 1) + ' / ' + total + '</span>' +
        '<div class="atour-btns">' + btns + '</div>' +
      '</div>';

    /* wire buttons */
    tipEl.querySelectorAll('[data-a]').forEach(function (b) {
      b.addEventListener('click', function (e) {
        e.stopPropagation();
        var a = b.getAttribute('data-a');
        if (a === 'next') next();
        else if (a === 'prev') prev();
        else skip();
      });
    });

    computeTipPosition(el, step);
  }

  /**
   * Compute and apply tooltip + arrow position.
   * Separated so we can call it again on re-measure without rebuilding innerHTML.
   */
  function computeTipPosition(el, step) {
    if (!tipEl) return;

    tipEl.classList.remove('show');

    /* force layout so we can measure tooltip */
    tipEl.style.left = '0';
    tipEl.style.top  = '0';
    tipEl.style.visibility = 'hidden';
    tipEl.style.opacity = '1';

    var tipRect  = tipEl.getBoundingClientRect();
    var tipW     = tipRect.width;
    var tipH     = tipRect.height;
    var vw       = window.innerWidth;
    var vh       = window.innerHeight;
    var margin   = 10;
    var arrowEl  = document.getElementById('atourArrow');

    tipEl.style.opacity = '';
    tipEl.style.visibility = '';

    if (!el) {
      /* center of screen */
      tipEl.style.left = Math.round(Math.max(margin, (vw - tipW) / 2)) + 'px';
      tipEl.style.top  = Math.round(Math.max(margin, (vh - tipH) / 2)) + 'px';
      if (arrowEl) arrowEl.style.display = 'none';
    } else {
      var r = el.getBoundingClientRect();
      var gap = 12;

      /* decide placement */
      var placement = step.placement || 'auto';
      var spaceBelow = vh - r.bottom - gap;
      var spaceAbove = r.top - gap;

      var goBelow;
      if (placement === 'top') goBelow = false;
      else if (placement === 'bottom') goBelow = true;
      else goBelow = (spaceBelow >= tipH + margin) || (spaceBelow >= spaceAbove);

      var top;
      if (goBelow) {
        top = r.bottom + gap;
      } else {
        top = r.top - gap - tipH;
      }

      /* horizontal: center on element, clamped to viewport */
      var left = r.left + r.width / 2 - tipW / 2;
      left = Math.max(margin, Math.min(left, vw - tipW - margin));

      /* clamp vertical */
      top = Math.max(margin, Math.min(top, vh - tipH - margin));

      tipEl.style.left = Math.round(left) + 'px';
      tipEl.style.top  = Math.round(top) + 'px';

      /* arrow */
      if (arrowEl) {
        arrowEl.style.display = '';
        var arrowLeft = (r.left + r.width / 2) - left - 7;
        arrowLeft = Math.max(18, Math.min(arrowLeft, tipW - 26));
        arrowEl.style.left = Math.round(arrowLeft) + 'px';
        arrowEl.style.marginLeft = '0';
        if (goBelow) {
          arrowEl.className = 'atour-arrow top';
          arrowEl.style.top = '-8px';
          arrowEl.style.bottom = '';
        } else {
          arrowEl.className = 'atour-arrow bottom';
          arrowEl.style.bottom = '-8px';
          arrowEl.style.top = '';
        }
      }
    }

    /* animate in */
    requestAnimationFrame(function () {
      requestAnimationFrame(function () {
        if (tipEl) tipEl.classList.add('show');
      });
    });
  }

  /* ──────────────── step management ──────────────── */
  function showStep(index) {
    if (!active) return;
    if (index < 0 || index >= steps.length) { stop(); return; }
    idx = index;
    var step = steps[idx];
    var targetEl = step.target ? document.querySelector(step.target) : null;

    // If element doesn't exist, skip this step
    if (step.target && !targetEl) {
      // Target not on screen (page still rendering, or tour replayed from a
      // different tab): show the step CENTERED instead of skipping ahead —
      // skipping chained past several steps and made one tap jump 1 → 5.
      targetEl = null;
    }

    // Hide tip during transition
    if (tipEl) tipEl.classList.remove('show');

    // Scroll to element, then position after scroll settles
    scrollToTarget(targetEl, function () {
      if (!active || idx !== index) return;

      // Fresh reference after scroll
      var el = step.target ? document.querySelector(step.target) : null;

      positionSpot(el);
      positionTip(el, step);
      haptic('light');

      // Re-measure after additional delay to fix:
      // - iOS Telegram header animation settling
      // - Samsung scroll momentum finishing
      // - any reflow/repaint after scroll
      if (el) {
        var savedTop = el.getBoundingClientRect().top;
        setTimeout(function () {
          if (!active || idx !== index) return;
          var el2 = step.target ? document.querySelector(step.target) : null;
          if (!el2) return;
          var newTop = el2.getBoundingClientRect().top;
          // If element moved more than 3px, reposition
          if (Math.abs(newTop - savedTop) > 3) {
            positionSpot(el2);
            computeTipPosition(el2, step);
          }
        }, 400);
      }
    });
  }

  function next() {
    if (idx >= steps.length - 1) { stop(); haptic('medium'); return; }
    showStep(idx + 1);
  }

  function prev() {
    if (idx <= 0) return;
    showStep(idx - 1);
  }

  function skip() {
    stop();
  }

  /* ──────────────── start / stop ──────────────── */
  function start(stepsConfig, opts) {
    if (active) stop(true);
    if (!stepsConfig || !stepsConfig.length) return;
    opts = opts || {};

    steps = stepsConfig;
    idx = 0;
    active = true;
    onCompleteCb = opts.onComplete || null;

    createDOM();

    // Scroll to top first
    try {
      var content = document.querySelector('.content');
      if (content) content.scrollTop = 0;
      window.scrollTo(0, 0);
    } catch (_) {}

    setTimeout(function () { showStep(0); }, 250);

    /* keyboard */
    _keyHandler = function (e) {
      if (!active) return;
      if (e.key === 'ArrowRight' || e.key === 'Enter') { e.preventDefault(); next(); }
      else if (e.key === 'ArrowLeft') { e.preventDefault(); prev(); }
      else if (e.key === 'Escape') { e.preventDefault(); skip(); }
    };
    document.addEventListener('keydown', _keyHandler, true);

    /* resize → reposition */
    _resizeHandler = function () {
      clearTimeout(_resizeTimer);
      _resizeTimer = setTimeout(function () { if (active) showStep(idx); }, 300);
    };
    window.addEventListener('resize', _resizeHandler);
  }

  function stop(skipMark) {
    if (!active && !overlayEl) return;
    active = false;

    if (_keyHandler)    { document.removeEventListener('keydown', _keyHandler, true); _keyHandler = null; }
    if (_resizeHandler) { window.removeEventListener('resize', _resizeHandler); _resizeHandler = null; }
    clearTimeout(_resizeTimer);

    removeDOM();
    if (!skipMark) markCompleted();
    if (!skipMark && onCompleteCb) { try { onCompleteCb(); } catch (_) {} }
    onCompleteCb = null;
  }

  /* ──────────────── public API ──────────────── */
  window.AstroTour = {
    start:       start,
    stop:        stop,
    next:        next,
    prev:        prev,
    skip:        skip,
    isCompleted: isCompleted,
    reset:       reset,
    get active() { return active; },
  };
})();

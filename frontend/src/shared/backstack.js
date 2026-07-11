// Unified back navigation: one stack drives the Telegram BackButton, the
// Android hardware/gesture back (via history states), and edge swipe-back.
//
// - Overlays (sheets, modals, menus, open chat) register with pushBack(onBack).
//   Each registration pushes ONE history state, so hardware back closes the
//   overlay instead of closing the Mini App.
// - setBaseBack(fn) is the page-level fallback (e.g. "go home" on a shell tab,
//   "go to dashboard" on support). It shows the BackButton without a history state.
// - goBack() routes any custom trigger (swipe) through the same logic.
//
// HARD SAFETY RULE (2026-07-11, Pasha: closing a sheet teleported him to the
// purchase page / apps guide): we NEVER call history.back() unless the CURRENT
// history entry is provably one of ours. Two real-world ways the ledger and
// the browser history used to drift apart, each leaking one silent back() into
// REAL history until it crossed the document boundary (landing on whatever
// page preceded the dashboard — purchase.html step 2, apps.html…):
//   1. overlay HANDOFF race: closing overlay A and opening overlay B in the
//      same React commit runs A's dispose (queues an ASYNC history.back())
//      before B's pushState (SYNC) — the queued back then ate B's state, not
//      A's. Fix: while a silent back is in flight, new states are DEFERRED and
//      materialized when it lands.
//   2. pushState rate-limiting: Safari throws (>100/30s) and Chrome can drop
//      excessive pushState calls during rapid tapping, leaving an entry with
//      NO real state. Fix: verify by readback; an entry that never
//      materialized is consumed without touching history.
// Any residual desync degrades to "overlay closes, history untouched" — worst
// case one dead back-press later, never an app exit.

import { useEffect, useRef } from 'react';

import { getWebApp } from './telegram.js';

let entries = [];        // [{ id, onBack, pushed }] — ours, newest last
let idSeq = 0;
let skipPops = 0;        // popstates we triggered ourselves (dispose cleanup)
let baseBack = null;
let initialized = false;
let navigatingAway = false; // full-page navigation in flight — don't touch history

function currentStateId() {
  try {
    return window.history.state ? window.history.state.astroBack : null;
  } catch (_) { return null; }
}

// Push the entry's history state and verify it actually landed (Safari's
// rate limiter throws; some webviews silently ignore the call).
function materialize(entry) {
  try {
    window.history.pushState({ astroBack: entry.id }, '', window.location.href);
    entry.pushed = currentStateId() === entry.id;
  } catch (_) {
    entry.pushed = false;
  }
}

// Materialize states that were deferred while a silent back() was in flight.
function flushDeferred() {
  if (skipPops > 0) return;
  for (const entry of entries) {
    if (!entry.pushed) materialize(entry);
  }
}

function updateButton() {
  try {
    const tg = getWebApp();
    if (!tg || !tg.BackButton) return;
    if (entries.length > 0 || baseBack) tg.BackButton.show();
    else tg.BackButton.hide();
  } catch (_) { /* ignore */ }
}

export function initBackStack() {
  if (initialized) return;
  initialized = true;

  window.addEventListener('popstate', () => {
    if (skipPops > 0) {
      skipPops--;
      if (skipPops === 0) flushDeferred();
      updateButton();
      return;
    }
    const top = entries.pop();
    if (top) {
      try { top.onBack(); } catch (_) { /* ignore */ }
      updateButton();
      return;
    }
    // No overlay: hardware back with a base handler acts like the BackButton.
    if (baseBack) {
      try { baseBack(); } catch (_) { /* ignore */ }
    }
  });

  try {
    const tg = getWebApp();
    tg?.BackButton?.onClick(() => goBack());
  } catch (_) { /* ignore */ }
  updateButton();
}

export function goBack() {
  if (entries.length > 0) {
    const top = entries[entries.length - 1];
    // Route through history only when the top state is really the current
    // one — that keeps the pushed state consumed consistently.
    if (top.pushed && currentStateId() === top.id) {
      try { window.history.back(); return true; } catch (_) { /* fall through */ }
    }
    // State missing (handoff race / rate-limited pushState): consume the
    // overlay directly and leave history alone.
    entries.pop();
    try { top.onBack(); } catch (_) { /* ignore */ }
    updateButton();
    return true;
  }
  if (baseBack) {
    try { baseBack(); } catch (_) { /* ignore */ }
    return true;
  }
  return false;
}

export function hasBackTarget() {
  return entries.length > 0 || !!baseBack;
}

export function hasOverlayOpen() {
  return entries.length > 0;
}

export function setBaseBack(fn) {
  baseBack = typeof fn === 'function' ? fn : null;
  updateButton();
}

export function pushBack(onBack) {
  const id = ++idSeq;
  const entry = { id, onBack, pushed: false };
  entries.push(entry);
  if (skipPops === 0) {
    materialize(entry);
  }
  // else: a silent back() is in flight — pushing now would hand it OUR state
  // to eat (the overlay-handoff race). flushDeferred() materializes this
  // entry as soon as the pending pop lands.
  updateButton();
  return function dispose() {
    const idx = entries.findIndex((e) => e.id === id);
    if (idx < 0) return; // already consumed by a back navigation
    entries.splice(idx, 1);
    // If a full-page navigation is in flight, calling history.back() here
    // would CANCEL it (the browser aborts the pending load and goes back
    // instead). The stale pushed state is discarded on unload anyway.
    if (navigatingAway) { updateButton(); return; }
    // Consume our history state silently — but ONLY when the current entry
    // is provably this one. Anything else (never materialized, buried by a
    // non-exclusive overlay, already eaten by the handoff race) is dropped
    // without navigating: a stray back() here is how closing a sheet used
    // to exit the whole document.
    if (entry.pushed && currentStateId() === id) {
      skipPops++;
      try { window.history.back(); } catch (_) { skipPops--; }
    }
    updateButton();
  };
}

// Call right before window.location.href = … so overlay cleanups triggered by
// the same click can't cancel the navigation with their history.back().
export function markNavigatingAway() {
  navigatingAway = true;
  // If the navigation never completes (bfcache restore / user cancels), re-arm.
  try {
    window.addEventListener('pageshow', () => { navigatingAway = false; }, { once: true });
    setTimeout(() => { navigatingAway = false; }, 5000);
  } catch (_) { /* ignore */ }
}

// React hook: while `open` is true the overlay owns one back-stack entry.
// Closed via back → onClose fires; closed via its own UI → entry disposed.
export function useBackClose(open, onClose) {
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;
  useEffect(() => {
    if (!open) return undefined;
    const dispose = pushBack(() => onCloseRef.current());
    return dispose;
  }, [open]);
}

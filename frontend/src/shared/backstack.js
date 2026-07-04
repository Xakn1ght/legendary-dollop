// Unified back navigation: one stack drives the Telegram BackButton, the
// Android hardware/gesture back (via history states), and edge swipe-back.
//
// - Overlays (sheets, modals, menus, open chat) register with pushBack(onBack).
//   Each registration pushes ONE history state, so hardware back closes the
//   overlay instead of closing the Mini App.
// - setBaseBack(fn) is the page-level fallback (e.g. "go home" on a shell tab,
//   "go to dashboard" on support). It shows the BackButton without a history state.
// - goBack() routes any custom trigger (swipe) through the same logic.

import { useEffect, useRef } from 'react';

import { getWebApp } from './telegram.js';

let entries = [];        // [{ id, onBack }] — one pushed history state each
let idSeq = 0;
let skipPops = 0;        // popstates we triggered ourselves (dispose cleanup)
let baseBack = null;
let initialized = false;
let navigatingAway = false; // full-page navigation in flight — don't touch history

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
    if (skipPops > 0) { skipPops--; updateButton(); return; }
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
    // Route through history so the pushed state is consumed consistently.
    try { window.history.back(); } catch (_) {
      const top = entries.pop();
      if (top) { try { top.onBack(); } catch (_2) { /* ignore */ } }
      updateButton();
    }
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
  entries.push({ id, onBack });
  try { window.history.pushState({ astroBack: id }, '', window.location.href); } catch (_) { /* ignore */ }
  updateButton();
  return function dispose() {
    const idx = entries.findIndex((e) => e.id === id);
    if (idx < 0) return; // already consumed by a back navigation
    entries.splice(idx, 1);
    // If a full-page navigation is in flight, calling history.back() here
    // would CANCEL it (the browser aborts the pending load and goes back
    // instead). The stale pushed state is discarded on unload anyway.
    if (navigatingAway) { updateButton(); return; }
    // Consume our history state silently (only safe when it's the newest one;
    // overlays are effectively exclusive so this holds in practice).
    skipPops++;
    try { window.history.back(); } catch (_) { skipPops--; }
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

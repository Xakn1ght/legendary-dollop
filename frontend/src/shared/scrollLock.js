// Body scroll lock for overlays (sheets, modals). While any overlay is open
// the page behind it must not scroll or rubber-band — touch scroll on a
// fixed backdrop chains to the page scroller in mobile webviews (Pasha's
// screenshot: notifications sheet open, page scrolling underneath).
//
// In this app <body> is the scroll container (html/body carry
// overflow-x:hidden, so overflow-y computes to auto and body overflows the
// 100%-height html box). The lock therefore just needs overflow:hidden on
// html+body (html.overlay-lock rule in glass.css) — the container keeps its
// scrollTop while hidden, so there's no jump and nothing to reposition.
// scrollTop is still saved/restored defensively (some webviews clamp it).
// Refcounted so stacked overlays (picker over modal) unlock only when the
// last one closes.

import { useEffect } from 'react';

let locks = 0;
let savedTop = 0;
let savedScroller = null;

function pageScroller() {
  const body = document.body;
  if (body && body.scrollHeight > body.clientHeight) return body;
  return document.scrollingElement || document.documentElement;
}

export function lockScroll() {
  locks += 1;
  if (locks > 1) return;
  savedScroller = pageScroller();
  savedTop = savedScroller ? savedScroller.scrollTop : 0;
  document.documentElement.classList.add('overlay-lock');
}

export function unlockScroll() {
  if (locks === 0) return;
  locks -= 1;
  if (locks > 0) return;
  document.documentElement.classList.remove('overlay-lock');
  if (savedScroller) {
    try { savedScroller.scrollTop = savedTop; } catch (_) { /* ignore */ }
    savedScroller = null;
  }
}

// Declarative variant for React overlays: locks while `active` is true.
export function useScrollLock(active) {
  useEffect(() => {
    if (!active) return undefined;
    lockScroll();
    return unlockScroll;
  }, [active]);
}

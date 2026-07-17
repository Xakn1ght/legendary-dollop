import React, { useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';

import { useScrollLock } from '../../shared/scrollLock.js';

// Generic bottom sheet matching legacy .sheet-backdrop/.sheet-panel markup
// (glass.css + index.css style these by class).
//
// Drag-to-dismiss (2026-07-08): grab the sheet and pull it DOWN to close.
//  - follows the finger 1:1 downward; upward is clamped to 0 (no stretch)
//  - release: closes past 33% of the panel height OR on a quick flick
//    (velocity > 0.11 px/ms), otherwise snaps back (200ms strong ease-out)
//  - drags never start on interactive controls, and inside scrollable
//    content ([data-sheet-scroll]) only when that scroller sits at the top —
//    so list scrolling keeps working and a pull-down at the top grabs the
//    sheet, native-app style.
export function Sheet({ open, onClose, labelledBy, children, panelId, backdropId }) {
  const panelRef = useRef(null);
  const drag = useRef(null); // { startY, startT, dy, active }

  // The page behind a sheet must be inert: freeze body scroll while open
  // (backdrop touchmove otherwise chains to the document in webviews).
  useScrollLock(open);

  useEffect(() => {
    const panel = panelRef.current;
    if (!panel) return undefined;

    const setY = (y, animate) => {
      panel.style.transition = animate ? 'transform 200ms cubic-bezier(0.23, 1, 0.32, 1)' : 'none';
      panel.style.transform = y == null ? '' : `translateX(-50%) translateY(${y}px)`;
    };

    const onDown = (ev) => {
      if (!panel.classList.contains('open')) return;
      const t = ev.target;
      if (t.closest && t.closest('button, a, input, textarea, select, [contenteditable="true"]')) return;
      const scroller = t.closest && t.closest('[data-sheet-scroll]');
      if (scroller && scroller.scrollTop > 2) return; // mid-list: let it scroll
      drag.current = {
        startY: ev.clientY, startT: Date.now(), dy: 0, active: false,
        fromScroller: !!scroller, pointerId: ev.pointerId,
      };
    };

    const onMove = (ev) => {
      const d = drag.current;
      if (!d) return;
      const dy = ev.clientY - d.startY;
      if (!d.active) {
        // Only commit to the drag once it's clearly a downward pull.
        if (dy > 10) {
          d.active = true;
          try { panel.setPointerCapture(d.pointerId); } catch (_) { /* ignore */ }
        } else if (dy < -6) {
          drag.current = null; // upward gesture: scrolling, not dismissing
          return;
        } else return;
      }
      d.dy = Math.max(0, dy); // no upward stretch
      if (ev.cancelable) ev.preventDefault();
      setY(d.dy, false);
    };

    const onUp = () => {
      const d = drag.current;
      drag.current = null;
      if (!d || !d.active) return;
      const dt = Math.max(1, Date.now() - d.startT);
      const velocity = d.dy / dt;
      const shouldClose = d.dy > panel.offsetHeight * 0.33 || velocity > 0.11;
      if (shouldClose) {
        // Finish the slide from the CURRENT position (no jump-cut), then let
        // the .open removal take over once the panel is already off-screen.
        setY(panel.offsetHeight + 40, true);
        setTimeout(() => {
          onClose && onClose();
          setY(null, false);
          panel.style.transition = '';
        }, 190);
      } else {
        setY(0, true);
        setTimeout(() => { setY(null, false); panel.style.transition = ''; }, 220);
      }
    };

    panel.addEventListener('pointerdown', onDown);
    panel.addEventListener('pointermove', onMove);
    panel.addEventListener('pointerup', onUp);
    panel.addEventListener('pointercancel', onUp);
    // Block scroll-chaining while a drag is live (iOS/Android webviews).
    const onTouchMove = (ev) => {
      if (drag.current && drag.current.active && ev.cancelable) ev.preventDefault();
    };
    panel.addEventListener('touchmove', onTouchMove, { passive: false });
    return () => {
      panel.removeEventListener('pointerdown', onDown);
      panel.removeEventListener('pointermove', onMove);
      panel.removeEventListener('pointerup', onUp);
      panel.removeEventListener('pointercancel', onUp);
      panel.removeEventListener('touchmove', onTouchMove);
    };
  }, [onClose]);

  // Any leftover inline transform must clear when the sheet re-opens.
  useEffect(() => {
    const panel = panelRef.current;
    if (panel && open) { panel.style.transform = ''; panel.style.transition = ''; }
  }, [open]);

  // Desktop Telegram Web: Escape dismisses like a tap on the backdrop.
  useEffect(() => {
    if (!open) return undefined;
    const onKey = (e) => { if (e.key === 'Escape') { e.stopPropagation(); onClose && onClose(); } };
    document.addEventListener('keydown', onKey, true);
    return () => document.removeEventListener('keydown', onKey, true);
  }, [open, onClose]);

  // Portal to <body>: rendered inside the page tree, any transformed/filtered
  // ancestor (page-transition containers) traps the sheet's z-index in its own
  // stacking context and the fixed bottom-nav paints OVER the sheet
  // (2026-07-09, Pasha: redeem/claim sheets "hidden behind navbar").
  return createPortal(
    <>
      <div
        className={`sheet-backdrop${open ? ' visible' : ''}`}
        id={backdropId}
        aria-hidden={!open}
        onClick={onClose}
      />
      <div
        className={`sheet-panel${open ? ' open' : ''}`}
        id={panelId}
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={labelledBy}
        aria-hidden={!open}
      >
        <div className="sheet-handle" />
        <div className="sheet-content" data-sheet-scroll="true">{children}</div>
      </div>
    </>,
    document.body,
  );
}

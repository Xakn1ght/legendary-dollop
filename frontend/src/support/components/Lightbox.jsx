import React, { useCallback, useEffect, useRef } from 'react';

import { useScrollLock } from '../../shared/scrollLock.js';

// Fullscreen photo viewer: pinch-zoom, double-tap zoom, pan, swipe-down to
// dismiss — all pointer events + transform-only (no layout thrash). Tap the
// backdrop or the X to close. The parent hands us an already-authorized
// blob/object URL; download re-uses that same blob (no new server surface).

const MIN_SCALE = 1;
const MAX_SCALE = 4;
const DOUBLE_TAP_SCALE = 2.5;
const TAP_MAX_MS = 350;
const DOUBLE_TAP_MS = 320;
const DISMISS_PX = 90; // swipe distance that closes the viewer

// Save the (already fetched, already authorized) image locally. Blob-anchor
// download works on Android/desktop; iOS Telegram suppresses programmatic
// downloads — there the native long-press "Save to Photos" is the path, so we
// open the blob in a new tab as a graceful fallback.
async function saveImage(src) {
  try {
    let blob;
    if (src.startsWith('blob:') || src.startsWith('data:')) {
      blob = await (await fetch(src)).blob();
    } else {
      blob = await (await fetch(src, { credentials: 'include' })).blob();
    }
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `astrobyte-${Date.now()}.jpg`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 30000);
    return true;
  } catch (_) {
    try { window.open(src, '_blank'); } catch (_2) { /* ignore */ }
    return false;
  }
}

export function Lightbox({ src, onClose }) {
  const wrapRef = useRef(null);
  const imgRef = useRef(null);
  useScrollLock(true); // mounted = open
  const st = useRef(null);
  if (!st.current) {
    st.current = {
      pointers: new Map(), // pointerId -> {x, y}
      tf: { scale: 1, tx: 0, ty: 0 },
      gesture: null,
      lastTap: { t: 0, x: 0, y: 0 },
    };
  }

  const applyTf = useCallback((animate) => {
    const img = imgRef.current;
    if (!img) return;
    const { scale, tx, ty } = st.current.tf;
    img.style.transition = animate ? 'transform 0.25s cubic-bezier(0.2, 0, 0.2, 1)' : 'none';
    img.style.transform = `translate3d(${tx}px, ${ty}px, 0) scale(${scale})`;
  }, []);

  // Keep the image from drifting fully off-screen; origin is the centre.
  const clampTf = useCallback((tf) => {
    const img = imgRef.current;
    const wrap = wrapRef.current;
    const scale = Math.min(MAX_SCALE, Math.max(MIN_SCALE, tf.scale));
    if (!img || !wrap) return { scale, tx: tf.tx, ty: tf.ty };
    const maxX = Math.max(0, (img.offsetWidth * scale - wrap.clientWidth) / 2);
    const maxY = Math.max(0, (img.offsetHeight * scale - wrap.clientHeight) / 2);
    return {
      scale,
      tx: Math.min(maxX, Math.max(-maxX, tf.tx)),
      ty: Math.min(maxY, Math.max(-maxY, tf.ty)),
    };
  }, []);

  const centerPoint = () => {
    const r = wrapRef.current.getBoundingClientRect();
    return { x: r.left + r.width / 2, y: r.top + r.height / 2 };
  };

  useEffect(() => {
    // New image: start at fit-to-screen.
    st.current.tf = { scale: 1, tx: 0, ty: 0 };
    st.current.pointers.clear();
    st.current.gesture = null;
    applyTf(false);
  }, [src, applyTf]);

  useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  const onPointerDown = (e) => {
    const s = st.current;
    try { wrapRef.current?.setPointerCapture?.(e.pointerId); } catch (_) { /* ignore */ }
    s.pointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
    if (s.pointers.size === 1) {
      s.gesture = {
        type: 'pan',
        startX: e.clientX,
        startY: e.clientY,
        startTf: { ...s.tf },
        startTime: Date.now(),
        moved: false,
        target: e.target, // real target (capture retargets later events)
      };
    } else if (s.pointers.size === 2) {
      const [a, b] = [...s.pointers.values()];
      s.gesture = {
        type: 'pinch',
        startDist: Math.hypot(a.x - b.x, a.y - b.y) || 1,
        startMid: { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 },
        startTf: { ...s.tf },
      };
    }
  };

  const onPointerMove = (e) => {
    const s = st.current;
    if (!s.pointers.has(e.pointerId)) return;
    s.pointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
    const g = s.gesture;
    if (!g) return;
    if (g.type === 'pinch' && s.pointers.size >= 2) {
      const [a, b] = [...s.pointers.values()];
      const dist = Math.hypot(a.x - b.x, a.y - b.y) || 1;
      const mid = { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 };
      const c = centerPoint();
      const scale = Math.min(MAX_SCALE, Math.max(MIN_SCALE, g.startTf.scale * (dist / g.startDist)));
      const k = scale / g.startTf.scale;
      // Keep the content under the fingers' midpoint anchored while scaling.
      s.tf = clampTf({
        scale,
        tx: mid.x - c.x - (g.startMid.x - c.x - g.startTf.tx) * k,
        ty: mid.y - c.y - (g.startMid.y - c.y - g.startTf.ty) * k,
      });
      applyTf(false);
    } else if (g.type === 'pan') {
      const dx = e.clientX - g.startX;
      const dy = e.clientY - g.startY;
      if (Math.abs(dx) > 8 || Math.abs(dy) > 8) g.moved = true;
      if (s.tf.scale > 1.01) {
        s.tf = clampTf({ scale: g.startTf.scale, tx: g.startTf.tx + dx, ty: g.startTf.ty + dy });
        applyTf(false);
      } else if (g.moved && Math.abs(dy) > Math.abs(dx)) {
        // Not zoomed: vertical drag = dismiss gesture (image follows the
        // finger, backdrop fades with distance).
        g.dismiss = dy;
        const img = imgRef.current;
        const wrap = wrapRef.current;
        if (img) {
          img.style.transition = 'none';
          img.style.transform = `translate3d(0, ${dy}px, 0) scale(${Math.max(0.85, 1 - Math.abs(dy) / 1200)})`;
        }
        if (wrap) wrap.style.background = `rgba(0,0,0,${Math.max(0.35, 0.92 - Math.abs(dy) / 500)})`;
      }
    }
  };

  const onPointerUp = (e) => {
    const s = st.current;
    const g = s.gesture;
    if (!s.pointers.delete(e.pointerId)) return;

    if (s.pointers.size === 1) {
      // Pinch ended with one finger still down: hand off to panning.
      const [p] = [...s.pointers.values()];
      s.gesture = { type: 'pan', startX: p.x, startY: p.y, startTf: { ...s.tf }, startTime: Date.now(), moved: true };
      return;
    }
    if (s.pointers.size > 0) return;

    s.gesture = null;

    // Swipe-dismiss resolution: past the threshold closes, otherwise spring back.
    if (g && g.type === 'pan' && typeof g.dismiss === 'number') {
      if (Math.abs(g.dismiss) > DISMISS_PX) { onClose(); return; }
      const wrap = wrapRef.current;
      if (wrap) wrap.style.background = '';
      applyTf(true);
      return;
    }

    if (!(g && g.type === 'pan' && !g.moved && Date.now() - g.startTime < TAP_MAX_MS)) return;

    // Clean tap: double-tap zooms, single tap on the backdrop closes.
    const now = Date.now();
    const isDouble = now - s.lastTap.t < DOUBLE_TAP_MS
      && Math.hypot(e.clientX - s.lastTap.x, e.clientY - s.lastTap.y) < 48;
    if (isDouble) {
      s.lastTap = { t: 0, x: 0, y: 0 };
      if (s.tf.scale > 1.01) {
        s.tf = { scale: 1, tx: 0, ty: 0 };
      } else {
        const c = centerPoint();
        const k = DOUBLE_TAP_SCALE;
        s.tf = clampTf({
          scale: k,
          tx: (e.clientX - c.x) * (1 - k) + s.tf.tx * k,
          ty: (e.clientY - c.y) * (1 - k) + s.tf.ty * k,
        });
      }
      applyTf(true);
      return;
    }
    s.lastTap = { t: now, x: e.clientX, y: e.clientY };
    if (g.target && g.target !== imgRef.current) onClose();
  };

  const onPointerCancel = (e) => {
    const s = st.current;
    s.pointers.delete(e.pointerId);
    if (s.pointers.size === 0) s.gesture = null;
  };

  return (
    <div
      className="photo-lightbox"
      id="photoLightbox"
      ref={wrapRef}
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={onPointerUp}
      onPointerCancel={onPointerCancel}
    >
      <img
        id="photoLightboxImg"
        ref={imgRef}
        src={src}
        alt=""
        draggable={false}
        onLoad={() => applyTf(false)}
      />
      <button
        className="lightbox-close"
        type="button"
        aria-label="Close"
        onPointerDown={(e) => e.stopPropagation()}
        onClick={(e) => { e.stopPropagation(); onClose(); }}
      >
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
          <line x1="6" y1="6" x2="18" y2="18" /><line x1="18" y1="6" x2="6" y2="18" />
        </svg>
      </button>
      <button
        className="lightbox-save"
        type="button"
        aria-label="Save image"
        onPointerDown={(e) => e.stopPropagation()}
        onClick={(e) => { e.stopPropagation(); saveImage(src); }}
      >
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><path d="M7 10l5 5 5-5" /><path d="M12 15V3" />
        </svg>
      </button>
    </div>
  );
}

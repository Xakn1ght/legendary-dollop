import React, { useEffect, useRef, useState } from 'react';

const PHONE_MQ = '(max-width: 640px)';

// Dashboard hero: a real WebGL brand crystal, lazy-loaded and capability-gated.
// Desktop-only (2026-07-20): on phones the whole card renders nothing — the
// hero plus one-per-row stats used to fill ~1.5 phone screens before any real
// data, and the WebGL loop cost GPU/battery on the device Pasha actually
// operates from. Falls back to a CSS orb when WebGL is unavailable, the device
// is weak, or the user prefers reduced motion (crystal renders one static frame in RM).
export function DashboardHero() {
  const canvasRef = useRef(null);
  const [use3d, setUse3d] = useState(false);
  const [isPhone, setIsPhone] = useState(() => window.matchMedia(PHONE_MQ).matches);

  useEffect(() => {
    const mq = window.matchMedia(PHONE_MQ);
    const onChange = (e) => setIsPhone(e.matches);
    if (mq.addEventListener) mq.addEventListener('change', onChange);
    else mq.addListener(onChange);
    return () => {
      if (mq.removeEventListener) mq.removeEventListener('change', onChange);
      else mq.removeListener(onChange);
    };
  }, []);

  useEffect(() => {
    // Phones never even fetch the three.js chunk (~475 KB) — not just hidden.
    if (isPhone) return undefined;
    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const weak = (navigator.deviceMemory && navigator.deviceMemory < 4)
      || (navigator.connection && navigator.connection.saveData);
    // WebGL availability probe
    let webgl = false;
    try {
      const c = document.createElement('canvas');
      webgl = !!(c.getContext('webgl2') || c.getContext('webgl'));
    } catch (_) { webgl = false; }
    if (weak || !webgl || !canvasRef.current) return undefined;

    let destroy = () => {};
    let alive = true;
    import('../hero3d.js')
      .then((m) => { if (alive && canvasRef.current) { setUse3d(true); destroy = m.mountCrystal(canvasRef.current, { reducedMotion: reduced }); } })
      .catch(() => { /* keep fallback */ });
    return () => { alive = false; try { destroy(); } catch (_) { /* ignore */ } };
  }, [isPhone]);

  if (isPhone) return null;

  return (
    <div className="glass-card hero3d">
      <div className="hero3d-copy">
        <div className="hero3d-eyebrow">Mission Control</div>
        <div className="hero3d-title">AstroByte Admin</div>
        <div className="hero3d-sub">Approvals, subscriptions, and support in one calm surface. Everything you touch here moves real money and real connectivity, so it stays clear and confident.</div>
      </div>
      <div className="hero3d-canvas-wrap">
        <canvas ref={canvasRef} style={{ display: use3d ? 'block' : 'none' }} />
        {!use3d && <div className="hero3d-fallback"><div className="hero3d-orb" /></div>}
      </div>
    </div>
  );
}

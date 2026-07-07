import React, { useEffect, useRef, useState } from 'react';

// Dashboard hero: a real WebGL brand crystal, lazy-loaded and capability-gated.
// Falls back to a CSS orb when WebGL is unavailable, the device is weak, or the
// user prefers reduced motion (crystal still renders one static frame in RM).
export function DashboardHero() {
  const canvasRef = useRef(null);
  const [use3d, setUse3d] = useState(false);

  useEffect(() => {
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
  }, []);

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

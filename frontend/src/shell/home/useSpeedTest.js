// Speed panel logic: ping 4s / download 6s / upload 8s intervals, paused when
// the panel is closed, the tab is hidden, or Telegram reports inactive.

import { useCallback, useEffect, useRef, useState } from 'react';

import { getWebApp } from '../../shared/telegram.js';
import { api } from '../api.js';

const MAX_POINTS = 50;

function smoothSeries(arr, alpha = 0.35) {
  if (!arr || arr.length === 0) return [];
  let s = arr[0];
  const out = [s];
  for (let i = 1; i < arr.length; i++) { s = alpha * arr[i] + (1 - alpha) * s; out.push(s); }
  return out;
}

export function useSpeedTest(open) {
  const [stats, setStats] = useState({ ping: null, down: null, up: null, updatedAt: null });
  const chartRef = useRef({ down: [], up: [], ping: [] });
  const canvasRef = useRef(null);
  const openRef = useRef(open);
  const activeRef = useRef(true);
  const timersRef = useRef({});
  openRef.current = open;

  const drawChart = useCallback(() => {
    const c = canvasRef.current;
    if (!c) return;
    const ctx = c.getContext('2d');
    const w = c.width = c.clientWidth;
    const h = c.height = c.clientHeight;
    ctx.clearRect(0, 0, w, h);
    ctx.strokeStyle = 'rgba(255,255,255,.04)';
    ctx.lineWidth = 1;
    for (let i = 0; i < 5; i++) {
      const y = Math.round(i * h / 5);
      ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(w, y); ctx.stroke();
    }
    const plot = (arr, color) => {
      if (arr.length < 2) return;
      const max = Math.max(1, ...arr);
      ctx.beginPath();
      ctx.strokeStyle = color;
      ctx.lineWidth = 2.5;
      arr.forEach((v, i) => {
        const x = i * (w / (MAX_POINTS - 1));
        const y = h - (v / max) * h * 0.85;
        if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
      });
      ctx.stroke();
    };
    plot(smoothSeries(chartRef.current.down), '#34d399');
    plot(smoothSeries(chartRef.current.up), '#ff6b47');
  }, []);

  const push = (list, v) => { list.push(v); if (list.length > MAX_POINTS) list.shift(); };
  const canRun = () => openRef.current && !document.hidden && activeRef.current;

  const measurePing = useCallback(async () => {
    if (!canRun()) return;
    const t0 = performance.now();
    try { await api('/api/dashboard/ping'); } catch (e) { /* ignore */ }
    const ms = Math.max(0, performance.now() - t0);
    push(chartRef.current.ping, ms);
    setStats((s) => ({ ...s, ping: Math.round(ms), updatedAt: Date.now() }));
    drawChart();
  }, [drawChart]);

  const measureDL = useCallback(async () => {
    if (!canRun()) return;
    const bytes = 200000;
    const t0 = performance.now();
    try {
      const r = await api('/api/dashboard/speed-dl?bytes=' + bytes, { raw: true });
      await r.arrayBuffer();
    } catch (e) { /* ignore */ }
    const dt = (performance.now() - t0) / 1000;
    const mbps = (bytes * 8 / 1e6) / Math.max(dt, 0.001);
    push(chartRef.current.down, mbps);
    setStats((s) => ({ ...s, down: mbps, updatedAt: Date.now() }));
    drawChart();
  }, [drawChart]);

  const measureUL = useCallback(async () => {
    if (!canRun()) return;
    const bytes = 100000;
    const body = new Uint8Array(bytes);
    const t0 = performance.now();
    try { await api('/api/dashboard/speed-ul', { method: 'POST', body }); } catch (e) { /* ignore */ }
    const dt = (performance.now() - t0) / 1000;
    const mbps = (bytes * 8 / 1e6) / Math.max(dt, 0.001);
    push(chartRef.current.up, mbps);
    setStats((s) => ({ ...s, up: mbps, updatedAt: Date.now() }));
    drawChart();
  }, [drawChart]);

  useEffect(() => {
    const timers = timersRef.current;
    const startIntervals = () => {
      if (timers.ping || !openRef.current || !activeRef.current) return;
      timers.ping = setInterval(measurePing, 4000);
      timers.dl = setInterval(measureDL, 6000);
      timers.ul = setInterval(measureUL, 8000);
    };
    const stopIntervals = () => {
      ['ping', 'dl', 'ul'].forEach((k) => { if (timers[k]) clearInterval(timers[k]); timers[k] = null; });
    };
    const kick = () => {
      setTimeout(measurePing, 500);
      setTimeout(measureDL, 1000);
      setTimeout(measureUL, 1500);
      startIntervals();
    };

    if (open) kick(); else stopIntervals();

    const onVisibility = () => {
      if (document.hidden) { activeRef.current = false; stopIntervals(); }
      else {
        activeRef.current = true;
        if (openRef.current) {
          setTimeout(measurePing, 300);
          setTimeout(measureDL, 700);
          setTimeout(measureUL, 1100);
          startIntervals();
        }
      }
    };
    document.addEventListener('visibilitychange', onVisibility);

    // Telegram active-state check every 2s (legacy parity).
    const tgCheck = setInterval(() => {
      const tg = getWebApp();
      const wasActive = activeRef.current;
      activeRef.current = !(tg && tg.isActive === false) && !document.hidden;
      if (wasActive && !activeRef.current) stopIntervals();
      else if (!wasActive && activeRef.current && openRef.current) startIntervals();
    }, 2000);

    return () => {
      stopIntervals();
      document.removeEventListener('visibilitychange', onVisibility);
      clearInterval(tgCheck);
    };
  }, [open, measurePing, measureDL, measureUL]);

  return { stats, canvasRef };
}

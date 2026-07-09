// One-shot speed test (2026-07-09 rewrite — the old panel polled tiny
// 200KB/100KB transfers every few seconds and timed the WHOLE request, so on
// any real connection it mostly measured round-trip latency, not bandwidth).
//
// A run is: warmup ping ×4 (median of the last 3) → streamed download
// (2MB, escalates to 8MB once if it finished too fast to trust) → upload
// via XHR progress events (2MB random bytes). The transfer clock starts at
// headers-done (download) / first progress event (upload), so TTFB and
// request setup don't pollute the throughput number. Live per-chunk samples
// feed the chart while the run is in flight.

import { useCallback, useEffect, useRef, useState } from 'react';

import { api, getInitData } from '../api.js';

const MAX_POINTS = 60;
// Parallel streams (2026-07-09 accuracy pass — Pasha vs Ookla): one TCP
// connection over a high-RTT path (~300ms to this box) is window-limited
// and never approaches line rate within a few MB. Ookla saturates with
// many parallel streams to nearby servers; we do the same toward OUR
// server (which is the number that matters for the VPN) and report the
// PEAK 1s window instead of the ramp-diluted average.
const DL_STREAMS = 3;
const DL_BYTES_PER_STREAM = 2 * 1024 * 1024;       // probe round: 6MB total
const DL_BYTES_PER_STREAM_BIG = 4 * 1024 * 1024;   // escalation: 12MB total
const UL_STREAMS = 2;
const UL_BYTES_PER_STREAM = 1024 * 1024;           // 2MB total upload
const PEAK_WINDOW_MS = 900;
const RUN_COOLDOWN_S = 30; // a full run can move ~10-35MB; don't let it be spammed

// Peak sustained throughput over any >=windowMs span of the aggregated
// byte-count samples [{t(ms), b(bytes)}] — two-pointer scan.
function peakWindowMbps(samples, windowMs = PEAK_WINDOW_MS) {
  let best = 0;
  let i = 0;
  for (let j = 1; j < samples.length; j++) {
    while (samples[j].t - samples[i + 1]?.t >= windowMs && i + 1 < j) i++;
    const dt = samples[j].t - samples[i].t;
    if (dt >= windowMs) {
      const mbps = ((samples[j].b - samples[i].b) * 8 / 1e6) / (dt / 1000);
      if (mbps > best) best = mbps;
    }
  }
  return best > 0 ? best : null;
}

function smoothSeries(arr, alpha = 0.35) {
  if (!arr || arr.length === 0) return [];
  let s = arr[0];
  const out = [s];
  for (let i = 1; i < arr.length; i++) { s = alpha * arr[i] + (1 - alpha) * s; out.push(s); }
  return out;
}

// crypto.getRandomValues caps at 64KB per call.
function randomBytes(n) {
  const buf = new Uint8Array(n);
  for (let i = 0; i < n; i += 65536) {
    crypto.getRandomValues(buf.subarray(i, Math.min(i + 65536, n)));
  }
  return buf;
}

export function useSpeedTest(open) {
  const [stats, setStats] = useState({ ping: null, down: null, up: null, updatedAt: null, phase: 'idle' });
  const [cooldownLeft, setCooldownLeft] = useState(0);
  const chartRef = useRef({ down: [], up: [] });
  const canvasRef = useRef(null);
  const abortRef = useRef(null);
  const runningRef = useRef(false);
  const ranOnceRef = useRef(false);
  const cooldownTimerRef = useRef(null);

  const drawChart = useCallback(() => {
    const c = canvasRef.current;
    if (!c) return;
    // Zero layout width = hidden or not laid out yet; sizing the bitmap to 0
    // would wipe it for good. Skip — a later redraw (run end / panel open)
    // catches up.
    if (!c.clientWidth) return;
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
    // One y-scale for both series (down/up visually comparable) and each
    // series stretched across the full width — a one-shot run yields few
    // points, which otherwise huddle in the first pixels of a fixed grid.
    const down = smoothSeries(chartRef.current.down);
    const up = smoothSeries(chartRef.current.up);
    const max = Math.max(1, ...down, ...up);
    const plot = (arr, color) => {
      if (arr.length < 2) return;
      ctx.beginPath();
      ctx.strokeStyle = color;
      ctx.lineWidth = 2.5;
      arr.forEach((v, i) => {
        const x = i * (w / (arr.length - 1));
        const y = h - (v / max) * h * 0.85;
        if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
      });
      ctx.stroke();
    };
    plot(down, '#34d399');
    plot(up, '#ff6b47');
  }, []);

  const pushSample = useCallback((key, mbps) => {
    const list = chartRef.current[key];
    list.push(mbps);
    if (list.length > MAX_POINTS) list.shift();
    drawChart();
  }, [drawChart]);

  // ── phases ─────────────────────────────────────────────────────────
  const measurePing = useCallback(async (signal) => {
    const times = [];
    for (let i = 0; i < 4; i++) {
      const t0 = performance.now();
      await api('/api/dashboard/ping', { signal });
      times.push(performance.now() - t0);
    }
    // First hit pays connection warmup — median of the rest.
    const rest = times.slice(1).sort((a, b) => a - b);
    return rest[Math.floor(rest.length / 2)];
  }, []);

  const measureDL = useCallback(async (signal, bytesPerStream, streams = DL_STREAMS) => {
    const t0 = performance.now();
    let total = 0;
    const samples = [{ t: 0, b: 0 }];
    let lastChart = 0;
    const note = () => {
      const now = performance.now() - t0;
      samples.push({ t: now, b: total });
      if (now - lastChart > 130) {
        lastChart = now;
        // live line: current best sustained window (falls back to avg early on)
        const cur = peakWindowMbps(samples, Math.min(PEAK_WINDOW_MS, Math.max(200, now / 2)))
          || (total * 8 / 1e6) / (now / 1000);
        pushSample('down', cur);
      }
    };

    const one = async () => {
      // unique query param defeats any HTTP-level connection coalescing cache
      const r = await api(`/api/dashboard/speed-dl?bytes=${bytesPerStream}&s=${Math.random().toString(36).slice(2)}`, { raw: true, signal });
      if (!r.body || !r.body.getReader) {
        // Ancient webview without streaming: count the body when it lands.
        const buf = await r.arrayBuffer();
        total += buf.byteLength;
        note();
        return;
      }
      const reader = r.body.getReader();
      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        total += value.byteLength;
        note();
      }
    };
    await Promise.all(Array.from({ length: streams }, one));

    const dt = Math.max((performance.now() - t0) / 1000, 0.05);
    const avg = (total * 8 / 1e6) / dt;
    return { mbps: peakWindowMbps(samples) || avg, dt };
  }, [pushSample]);

  const measureUL = useCallback((signal, pingMs) => {
    // Parallel XHR uploads; progress events aggregated across streams and
    // reported as the peak sustained window, mirroring the download side.
    const tSend = performance.now();
    let t0 = 0; // first progress event across ALL streams — transfer clock
    const loaded = new Array(UL_STREAMS).fill(0);
    const samples = [];
    let lastChart = 0;

    const note = () => {
      const now = performance.now();
      if (t0 === 0) { t0 = now; samples.push({ t: 0, b: 0 }); return; }
      const total = loaded.reduce((a, b) => a + b, 0);
      const t = now - t0;
      samples.push({ t, b: total });
      if (t - lastChart > 130) {
        lastChart = t;
        const cur = peakWindowMbps(samples, Math.min(PEAK_WINDOW_MS, Math.max(200, t / 2)))
          || (total * 8 / 1e6) / (t / 1000);
        pushSample('up', cur);
      }
    };

    const oneUpload = (idx) => new Promise((resolve, reject) => {
      const body = randomBytes(UL_BYTES_PER_STREAM);
      const xhr = new XMLHttpRequest();
      // Same auth surface as api(): initData header when present, bearer + cookies otherwise.
      xhr.open('POST', '/api/dashboard/speed-ul?v=' + Date.now() + '-' + idx);
      xhr.withCredentials = true;
      try {
        const init = getInitData();
        if (init) xhr.setRequestHeader('X-Telegram-Init', init);
        const bearer = localStorage.getItem('tma_bearer_token') || '';
        if (bearer) xhr.setRequestHeader('Authorization', 'Bearer ' + bearer);
      } catch (_) { /* ignore */ }
      const onAbort = () => { try { xhr.abort(); } catch (_) { /* ignore */ } };
      if (signal) signal.addEventListener('abort', onAbort, { once: true });
      const detach = () => { if (signal) signal.removeEventListener('abort', onAbort); };
      xhr.upload.onprogress = (e) => { loaded[idx] = e.loaded; note(); };
      xhr.onload = () => { detach(); loaded[idx] = UL_BYTES_PER_STREAM; note(); resolve(); };
      xhr.onerror = () => { detach(); reject(new Error('ul_failed')); };
      xhr.onabort = () => { detach(); reject(new Error('aborted')); };
      xhr.send(body);
    });

    return Promise.all(Array.from({ length: UL_STREAMS }, (_, i) => oneUpload(i))).then(() => {
      const peak = peakWindowMbps(samples);
      if (peak) return peak;
      const totalBytes = UL_STREAMS * UL_BYTES_PER_STREAM;
      if (t0 && samples.length > 1) {
        const last = samples[samples.length - 1];
        if (last.t > 0 && last.b > 0) return (last.b * 8 / 1e6) / (last.t / 1000);
      }
      // No usable progress events: total time minus the known round-trip.
      const dt = Math.max((performance.now() - tSend - (pingMs || 0)) / 1000, 0.05);
      return (totalBytes * 8 / 1e6) / dt;
    });
  }, [pushSample]);

  // ── run orchestration ──────────────────────────────────────────────
  const startCooldown = useCallback(() => {
    setCooldownLeft(RUN_COOLDOWN_S);
    if (cooldownTimerRef.current) clearInterval(cooldownTimerRef.current);
    const t0 = Date.now();
    cooldownTimerRef.current = setInterval(() => {
      const left = Math.max(0, RUN_COOLDOWN_S - Math.floor((Date.now() - t0) / 1000));
      setCooldownLeft(left);
      if (left <= 0 && cooldownTimerRef.current) {
        clearInterval(cooldownTimerRef.current);
        cooldownTimerRef.current = null;
      }
    }, 1000);
  }, []);

  const run = useCallback(async () => {
    if (runningRef.current) return;
    runningRef.current = true;
    ranOnceRef.current = true;
    const ctrl = new AbortController();
    abortRef.current = ctrl;
    chartRef.current.down = [];
    chartRef.current.up = [];
    drawChart();
    setStats({ ping: null, down: null, up: null, updatedAt: null, phase: 'ping' });
    try {
      const ping = await measurePing(ctrl.signal);
      setStats((s) => ({ ...s, ping: Math.round(ping), phase: 'down' }));

      let dl = await measureDL(ctrl.signal, DL_BYTES_PER_STREAM);
      // Finished too fast for a trustworthy peak window → one big round.
      if (dl.dt < 2.0) dl = await measureDL(ctrl.signal, DL_BYTES_PER_STREAM_BIG);
      // Fast connections can finish before 2 live samples land — backfill a
      // flat line at the final figure so the chart never renders empty.
      while (chartRef.current.down.length < 2) pushSample('down', dl.mbps);
      setStats((s) => ({ ...s, down: dl.mbps, phase: 'up' }));

      const up = await measureUL(ctrl.signal, ping);
      while (chartRef.current.up.length < 2) pushSample('up', up);
      setStats((s) => ({ ...s, up, phase: 'done', updatedAt: Date.now() }));
    } catch (_) {
      // Aborted (panel closed / app hidden) or network error — keep partials.
      setStats((s) => ({ ...s, phase: s.down != null || s.ping != null ? 'done' : 'idle', updatedAt: s.ping != null ? Date.now() : s.updatedAt }));
    } finally {
      runningRef.current = false;
      abortRef.current = null;
      startCooldown();
    }
  }, [drawChart, measurePing, measureDL, measureUL, startCooldown]);

  // Auto-run once when the panel first opens with no result yet; abort the
  // in-flight run when the panel closes or the app is hidden.
  useEffect(() => {
    if (open && !ranOnceRef.current) run();
    if (!open && abortRef.current) abortRef.current.abort();
    // Re-render the chart once layout exists (panel just un-hid, or the run
    // finished before first layout on very fast connections).
    if (open) requestAnimationFrame(drawChart);
    const onVis = () => { if (document.hidden && abortRef.current) abortRef.current.abort(); };
    document.addEventListener('visibilitychange', onVis);
    return () => document.removeEventListener('visibilitychange', onVis);
  }, [open, run, drawChart]);

  useEffect(() => {
    if (stats.phase === 'done') requestAnimationFrame(drawChart);
  }, [stats.phase, drawChart]);

  useEffect(() => () => {
    if (abortRef.current) abortRef.current.abort();
    if (cooldownTimerRef.current) clearInterval(cooldownTimerRef.current);
  }, []);

  const running = stats.phase === 'ping' || stats.phase === 'down' || stats.phase === 'up';
  return { stats, canvasRef, run, running, cooldownLeft };
}

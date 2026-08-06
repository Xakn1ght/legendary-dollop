import React, { useEffect, useState } from 'react';

import { apiJson } from '../api.js';
import { Icons } from '../icons.jsx';
import { fmtNum, parseTs } from '../util.js';

// Online-users time series (PasarGuard /api/users/counts/online via
// /api/admin/analytics/online). Hand-rolled SVG like RevenueCard — no chart
// lib. The panel computes the series from connection logs and the FIRST load
// of a window can take ~15s (server caches 10 min after that), hence the
// explicit slow-load copy instead of a bare spinner.
const W = 720, H = 150, PAD = 4;

const hourFmt = new Intl.DateTimeFormat('en-GB', { timeZone: 'Asia/Tehran', hour: '2-digit', minute: '2-digit', hour12: false });
function hourLabel(iso) {
  const d = parseTs(iso);
  return d ? hourFmt.format(d) : '';
}

function Chart({ series }) {
  const n = series.length;
  if (!n) return null;
  const step = (W - PAD * 2) / n;
  const cx = (i) => PAD + i * step + step / 2;
  const max = Math.max(1, ...series.map((p) => p.count));
  const cy = (v) => H - 18 - ((v || 0) * (H - 30)) / max;

  const pts = series.map((p, i) => `${cx(i)},${cy(p.count)}`).join(' ');
  const area = `${PAD},${H - 18} ${pts} ${W - PAD},${H - 18}`;
  const labelEvery = Math.ceil(n / 8);

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="rev-chart" preserveAspectRatio="none" role="img" aria-label="Online users over time">
      {[0.25, 0.5, 0.75].map((f) => (
        <line key={f} x1={PAD} x2={W - PAD} y1={H - 18 - f * (H - 30)} y2={H - 18 - f * (H - 30)} stroke="rgba(255,255,255,0.05)" strokeWidth="1" />
      ))}
      <polygon points={area} fill="color-mix(in srgb, var(--brand) 14%, transparent)" />
      <polyline points={pts} fill="none" stroke="var(--brand)" strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" />
      {series.map((p, i) => (
        <g key={p.t}>
          <title>{`${hourLabel(p.t)} — ${fmtNum(p.count)} online`}</title>
          <rect x={cx(i) - step / 2} y={0} width={Math.max(step, 1)} height={H - 18} fill="transparent" />
          {i % labelEvery === 0 && (
            <text x={cx(i)} y={H - 5} fontSize="9" fill="rgba(255,255,255,0.4)" textAnchor="middle">{hourLabel(p.t)}</text>
          )}
        </g>
      ))}
    </svg>
  );
}

export function OnlineCard() {
  const [data, setData] = useState(null);
  const [hours, setHours] = useState(24);
  const [err, setErr] = useState(false);

  useEffect(() => {
    let alive = true;
    setData(null); setErr(false);
    (async () => {
      try {
        const { data: d } = await apiJson(`/api/admin/analytics/online?hours=${hours}`);
        if (alive && d.ok) { setData(d); setErr(false); } else if (alive) setErr(true);
      } catch (_) { if (alive) setErr(true); }
    })();
    return () => { alive = false; };
  }, [hours]);

  const series = data?.series || [];
  const last = series.length ? series[series.length - 1].count : null;

  return (
    <div className="glass-card rev-card">
      <div className="rev-head">
        <div className="rev-title"><Icons.wifi width={16} height={16} /> Online Users</div>
        <div className="rev-controls">
          {[24, 48, 72].map((hs) => (
            <button key={hs} className={'chip-btn' + (hours === hs ? ' on' : '')} onClick={() => setHours(hs)}>{hs}h</button>
          ))}
        </div>
      </div>

      <div className="rev-kpis">
        <div className="rev-kpi">
          <div className="rev-kpi-label">Last hour</div>
          <div className="rev-kpi-value">{data ? fmtNum(last) : '…'}</div>
        </div>
        <div className="rev-kpi">
          <div className="rev-kpi-label">Peak ({hours}h)</div>
          <div className="rev-kpi-value">{data ? fmtNum(data.peak) : '…'}</div>
        </div>
        <div className="rev-kpi">
          <div className="rev-kpi-label">Unique ({hours}h)</div>
          <div className="rev-kpi-value">{data ? fmtNum(data.unique_in_window) : '…'}</div>
        </div>
      </div>

      {err && <div className="rev-empty">Could not load online history.</div>}
      {!err && !data && <div className="rev-empty">Loading — the first load of a window can take ~15 seconds.</div>}
      {!err && data && series.length === 0 && <div className="rev-empty">No online data for this window yet.</div>}
      {!err && data && series.length > 0 && <Chart series={series} />}
    </div>
  );
}

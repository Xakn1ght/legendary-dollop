import React, { useEffect, useMemo, useState } from 'react';

import { apiJson } from '../api.js';
import { Icons } from '../icons.jsx';
import { fmtNum } from '../util.js';

const fmtT = (n) => `${Number(n || 0).toLocaleString('en-US')}`;

// Hand-rolled SVG stacked-bar chart — no chart lib, ~free to render.
function Chart({ series }) {
  const W = 720, H = 180, PAD = 4;
  const max = Math.max(1, ...series.map((d) => d.total));
  const bw = (W - PAD * 2) / Math.max(series.length, 1);
  const colors = { subs: 'var(--brand)', charges: 'rgba(122,162,255,0.85)', vip: 'rgba(255,196,87,0.9)' };

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="rev-chart" preserveAspectRatio="none" role="img" aria-label="Daily revenue">
      {[0.25, 0.5, 0.75].map((f) => (
        <line key={f} x1={PAD} x2={W - PAD} y1={H - 18 - f * (H - 30)} y2={H - 18 - f * (H - 30)} stroke="rgba(255,255,255,0.05)" strokeWidth="1" />
      ))}
      {series.map((d, i) => {
        const x = PAD + i * bw;
        const scale = (H - 30) / max;
        let y = H - 18;
        const segs = ['subs', 'charges', 'vip'].map((k) => {
          const h = (d[k] || 0) * scale;
          y -= h;
          return { k, y, h };
        });
        return (
          <g key={d.date}>
            <title>{`${d.date}\n${fmtT(d.total)} toman — ${d.orders} orders${d.new_users ? `\n${d.new_users} new users` : ''}`}</title>
            <rect x={x + 1} y={0} width={Math.max(bw - 2, 1)} height={H - 18} fill="transparent" />
            {segs.map((s) => s.h > 0.5 && (
              <rect key={s.k} x={x + 1.5} y={s.y} width={Math.max(bw - 3, 1)} height={s.h} rx="2" fill={colors[s.k]} />
            ))}
            {series.length <= 32 && (i % Math.ceil(series.length / 8) === 0) && (
              <text x={x + bw / 2} y={H - 5} fontSize="9" fill="rgba(255,255,255,0.4)" textAnchor="middle">
                {d.date.slice(5)}
              </text>
            )}
          </g>
        );
      })}
    </svg>
  );
}

export function RevenueCard() {
  const [data, setData] = useState(null);
  const [days, setDays] = useState(30);
  const [err, setErr] = useState(false);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const { data: d } = await apiJson(`/api/admin/analytics/revenue?days=${days}`);
        if (alive && d.ok) { setData(d); setErr(false); } else if (alive) setErr(true);
      } catch (_) { if (alive) setErr(true); }
    })();
    return () => { alive = false; };
  }, [days]);

  const totals = data?.totals;
  const kpis = useMemo(() => ([
    { label: 'Today', ...(totals?.today || {}) },
    { label: '7 days', ...(totals?.week || {}) },
    { label: '30 days', ...(totals?.month || {}) },
    { label: 'All time', ...(totals?.all_time || {}) },
  ]), [totals]);

  function exportCsv() {
    const to = new Date().toISOString().slice(0, 10);
    const from = new Date(Date.now() - days * 86400e3).toISOString().slice(0, 10);
    window.open(`/api/admin/export/transactions?from=${from}&to=${to}`, '_blank');
  }

  return (
    <div className="glass-card rev-card">
      <div className="rev-head">
        <div className="rev-title"><Icons.money width={16} height={16} /> Revenue</div>
        <div className="rev-controls">
          {[14, 30, 90].map((d) => (
            <button key={d} className={'chip-btn' + (days === d ? ' on' : '')} onClick={() => setDays(d)}>{d}d</button>
          ))}
          <button className="chip-btn" onClick={exportCsv} title="Export CSV for this window">
            <Icons.download width={13} height={13} /> CSV
          </button>
        </div>
      </div>

      <div className="rev-kpis">
        {kpis.map((k) => (
          <div className="rev-kpi" key={k.label}>
            <div className="rev-kpi-label">{k.label}</div>
            <div className="rev-kpi-value">{data ? fmtT(k.amount) : '…'}<span className="rev-kpi-unit"> T</span></div>
            <div className="rev-kpi-sub">{data ? `${fmtNum(k.count)} orders` : ''}</div>
          </div>
        ))}
      </div>

      {err && <div className="rev-empty">Could not load revenue data.</div>}
      {!err && data && data.series.every((d) => d.total === 0) && (
        <div className="rev-empty">No revenue in this window yet.</div>
      )}
      {!err && data && <Chart series={data.series} />}

      <div className="rev-legend">
        <span><i style={{ background: 'var(--brand)' }} /> Purchases</span>
        <span><i style={{ background: 'rgba(122,162,255,0.85)' }} /> Charges</span>
        <span><i style={{ background: 'rgba(255,196,87,0.9)' }} /> VIP</span>
      </div>

      {data && data.plans && data.plans.length > 0 && (
        <div className="rev-plans">
          <div className="rev-plans-title">Top plans ({days}d)</div>
          {data.plans.slice(0, 5).map((p) => {
            const maxA = Math.max(1, ...data.plans.map((x) => x.amount));
            return (
              <div className="rev-plan-row" key={p.plan}>
                <span className="rev-plan-name">{p.plan}</span>
                <span className="rev-plan-bar"><i style={{ width: `${Math.max(4, (p.amount / maxA) * 100)}%` }} /></span>
                <span className="rev-plan-val">{fmtT(p.amount)} T · {p.count}</span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

import React, { useEffect, useState } from 'react';

import { apiJson } from '../api.js';
import { Icons } from '../icons.jsx';

function Dot({ ok }) {
  return <i className={'hdot ' + (ok === true ? 'ok' : ok === false ? 'bad' : 'unk')} />;
}

function ago(ts) {
  if (!ts) return 'never';
  const s = Math.max(0, Math.floor(Date.now() / 1000 - ts));
  if (s < 90) return `${s}s ago`;
  if (s < 5400) return `${Math.round(s / 60)}m ago`;
  return `${Math.round(s / 3600)}h ago`;
}

export function HealthCard() {
  const [h, setH] = useState(null);
  const [nodes, setNodes] = useState(null);

  useEffect(() => {
    let alive = true;
    const load = async () => {
      try {
        const { data } = await apiJson('/api/admin/system-health');
        if (alive && data.ok !== false) setH(data);
      } catch (_) { /* ignore */ }
      try {
        const { data } = await apiJson('/api/admin/nodes');
        if (alive && data.ok) setNodes(data);
      } catch (_) { /* ignore */ }
    };
    load();
    const id = setInterval(() => { if (!document.hidden) load(); }, 60000);
    return () => { alive = false; clearInterval(id); };
  }, []);

  const chips = [
    { name: 'Database', s: h?.db },
    { name: 'Redis', s: h?.redis },
    { name: 'Marzban', s: h?.marzban },
  ];

  return (
    <div className="glass-card health-card">
      <div className="rev-head">
        <div className="rev-title"><Icons.wifi width={16} height={16} /> System Health</div>
        {h?.sms_auto_approve && (
          <span className={'sms-pill' + (h.sms_auto_approve.enabled ? ' armed' : '')}>
            SMS auto-approve {h.sms_auto_approve.enabled ? 'ARMED' : 'off'}
          </span>
        )}
      </div>

      <div className="health-chips">
        {chips.map((c) => (
          <div className="health-chip" key={c.name} title={c.s?.error || ''}>
            <Dot ok={c.s ? c.s.ok : undefined} />
            <span>{c.name}</span>
            <em>{c.s ? `${c.s.latency_ms}ms` : '…'}</em>
          </div>
        ))}
        {nodes && (nodes.nodes || []).map((n) => (
          <div className="health-chip" key={'n' + n.id} title={n.message || n.status}>
            <Dot ok={n.up} />
            <span>{n.name || 'node'}</span>
            <em>{n.status}</em>
          </div>
        ))}
      </div>

      {h?.marzban?.ok && (
        <div className="health-sub">
          Marzban v{h.marzban.version} · {h.marzban.users_active ?? '?'} active / {h.marzban.total_users ?? '?'} users
        </div>
      )}

      <div className="health-jobs">
        {(h?.jobs || []).map((j) => (
          <div className="health-job" key={j.name} title={`${j.duration_ms ?? '?'}ms`}>
            <Dot ok={j.ok} />
            <span className="health-job-name">{j.name.replace(/_job$/, '').replace(/_/g, ' ')}</span>
            <em>{ago(j.last_run_at)}</em>
          </div>
        ))}
        {h && (!h.jobs || h.jobs.length === 0) && <div className="rev-empty">No job telemetry yet (needs one run after deploy).</div>}
      </div>
    </div>
  );
}

import React, { useCallback, useEffect, useState } from 'react';

import { apiJson, postJson } from '../api.js';
import { useModal } from './Modal.jsx';
import { useToast } from './Toast.jsx';
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
  const modal = useModal();
  const toast = useToast();
  const [h, setH] = useState(null);
  const [nodes, setNodes] = useState(null);
  const [smsBusy, setSmsBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const { data } = await apiJson('/api/admin/system-health');
      if (data.ok !== false) setH(data);
    } catch (_) { /* ignore */ }
    try {
      const { data } = await apiJson('/api/admin/nodes');
      if (data.ok) setNodes(data);
    } catch (_) { /* ignore */ }
  }, []);

  useEffect(() => {
    load();
    const id = setInterval(() => { if (!document.hidden) load(); }, 60000);
    return () => clearInterval(id);
  }, [load]);

  // Same confirm copy + endpoint as Settings ▸ SMS Auto-Approve — the pill
  // is a live switch, not just a status readout (Pasha 2026-07-09).
  async function toggleSms() {
    if (!h?.sms_auto_approve || smsBusy) return;
    const arming = !h.sms_auto_approve.enabled;
    const ok = await modal.confirm(
      arming ? 'ARM SMS auto-approve?' : 'Disarm SMS auto-approve?',
      arming
        ? 'Incoming PARSIANBANK deposit SMS will auto-approve the one unambiguous matching pending order (exact amount + time window). Ambiguous cases always stay manual.'
        : 'Auto-approval stops immediately; every receipt goes back to manual review.',
      { okText: arming ? 'ARM' : 'Disarm', danger: arming },
    );
    if (!ok) return;
    setSmsBusy(true);
    try {
      const { data } = await postJson('/api/admin/sms-control', { enabled: arming });
      if (data.ok) { toast(arming ? 'SMS auto-approve ARMED' : 'SMS auto-approve disarmed', 'success'); await load(); }
      else toast(data.error === 'source_chat_not_configured' ? 'SMS_SOURCE_CHAT_ID is not configured on the server' : 'Failed', 'error');
    } catch (_) { toast('Request failed', 'error'); }
    setSmsBusy(false);
  }

  const chips = [
    { name: 'Database', s: h?.db },
    { name: 'Redis', s: h?.redis },
    // key fallback: tolerate an admin bundle deployed ahead of/behind the API
    { name: 'PasarGuard', s: h?.pasarguard || h?.marzban },
  ];

  return (
    <div className="glass-card health-card">
      <div className="rev-head">
        <div className="rev-title"><Icons.wifi width={16} height={16} /> System Health</div>
        {h?.sms_auto_approve && (
          <button
            type="button"
            className={'sms-pill sms-pill-btn' + (h.sms_auto_approve.enabled ? ' armed' : '')}
            onClick={toggleSms}
            disabled={smsBusy}
            title={h.sms_auto_approve.enabled ? 'Tap to disarm' : 'Tap to arm'}
          >
            SMS auto-approve {smsBusy ? '…' : h.sms_auto_approve.enabled ? 'ARMED' : 'off'}
          </button>
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

      {(h?.pasarguard || h?.marzban)?.ok && (
        <div className="health-sub">
          {(() => { const p = h.pasarguard || h.marzban; return (
            <>PasarGuard v{p.version} · {p.users_active ?? '?'} active / {p.total_users ?? '?'} users</>
          ); })()}
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

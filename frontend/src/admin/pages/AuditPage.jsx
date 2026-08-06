import React, { useCallback, useEffect, useMemo, useState } from 'react';

import { apiJson } from '../api.js';
import { Icons } from '../icons.jsx';
import { fmtDateTime } from '../util.js';

const ACTION_GROUPS = ['', 'receipt', 'charge', 'vip', 'subscription', 'user', 'coupon', 'broadcast', 'sms', 'auth', 'expiry'];

const ACTION_COLOR = (a) => {
  if (/deny|delete|disarm|ban/.test(a)) return 'var(--danger)';
  if (/approve|arm|create/.test(a)) return 'var(--success)';
  if (/login/.test(a)) return 'rgba(122,162,255,0.95)';
  return 'var(--text)';
};

export function AuditPage() {
  const [data, setData] = useState(null);
  const [action, setAction] = useState('');
  const [q, setQ] = useState('');
  const [page, setPage] = useState(1);
  const [expanded, setExpanded] = useState(() => new Set());

  const load = useCallback(async () => {
    try {
      const params = new URLSearchParams({ page: String(page), limit: '50' });
      if (action) params.set('action', action);
      if (q.trim()) params.set('q', q.trim());
      const { data: d } = await apiJson(`/api/admin/audit?${params}`);
      if (d.ok) { setData(d); setExpanded(new Set()); }
    } catch (_) { /* ignore */ }
  }, [page, action, q]);

  useEffect(() => { load(); }, [load]);

  const pages = data ? Math.max(1, Math.ceil(data.total / data.limit)) : 1;

  // Collapse CONSECUTIVE identical action+target rows (job retries flood the
  // trail with dozens of e.g. sms.multi_deposit_deferred for one target) into
  // one row with an xN badge and the run's latest timestamp. Entries arrive
  // newest-first, so items[0] is the latest of each run. Click expands the run.
  const groups = useMemo(() => {
    const out = [];
    for (const e of (data?.entries || [])) {
      const key = `${e.action}|${e.target_type || ''}|${e.target_id || ''}`;
      const last = out[out.length - 1];
      if (last && last.key === key) last.items.push(e);
      else out.push({ key, items: [e] });
    }
    return out;
  }, [data]);

  const toggleRun = (id) => setExpanded((s) => {
    const n = new Set(s);
    if (n.has(id)) n.delete(id); else n.add(id);
    return n;
  });

  return (
    <div className="glass-card">
      <div className="table-header" style={{ padding: '16px 20px', display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'center' }}>
        <h3 style={{ margin: 0, fontSize: 16, display: 'flex', alignItems: 'center', gap: 8 }}>
          <Icons.audit width={17} height={17} /> Audit Trail
        </h3>
        <div className="rev-controls" style={{ flex: 1 }}>
          {ACTION_GROUPS.map((a) => (
            <button key={a || 'all'} className={'chip-btn' + (action === a ? ' on' : '')}
                    onClick={() => { setAction(a); setPage(1); }}>{a || 'all'}</button>
          ))}
        </div>
        <input type="text" className="coupon-user-input" placeholder="search…" value={q}
               onChange={(e) => { setQ(e.target.value); setPage(1); }} style={{ maxWidth: 200 }} />
      </div>

      <div className="table-responsive">
        <table>
          <thead><tr><th>When</th><th>Action</th><th>Target</th><th>Summary</th><th>Admin</th><th>IP</th></tr></thead>
          <tbody>
            {!data && <tr><td colSpan={6} style={{ textAlign: 'center', color: 'var(--text-muted)', padding: 32 }}>Loading…</td></tr>}
            {data && data.entries.length === 0 && (
              <tr><td colSpan={6} style={{ textAlign: 'center', color: 'var(--text-muted)', padding: 32 }}>
                No audit entries yet — they appear as soon as admin actions run.
              </td></tr>
            )}
            {data && groups.map((g) => {
              const e = g.items[0];
              const n = g.items.length;
              const open = expanded.has(e.id);
              const rows = [(
                <tr
                  key={e.id}
                  onClick={n > 1 ? () => toggleRun(e.id) : undefined}
                  style={n > 1 ? { cursor: 'pointer' } : undefined}
                  title={n > 1 ? `Run of ${n} identical entries — click to ${open ? 'collapse' : 'expand'}` : undefined}
                >
                  <td style={{ whiteSpace: 'nowrap', fontVariantNumeric: 'tabular-nums' }}>
                    {fmtDateTime(e.created_at)}
                  </td>
                  <td>
                    <span style={{ color: ACTION_COLOR(e.action), fontWeight: 700 }}>{e.action}</span>
                    {n > 1 && <span className="audit-run-badge">x{n}</span>}
                  </td>
                  <td>{e.target_type ? `${e.target_type}${e.target_id ? ` #${e.target_id}` : ''}` : '—'}</td>
                  <td style={{ maxWidth: 420, overflow: 'hidden', textOverflow: 'ellipsis' }}>{e.summary || '—'}</td>
                  <td>{e.admin_name || e.admin_chat_id || '—'}</td>
                  <td style={{ color: 'var(--text-muted)', fontSize: 12 }}>{e.ip || '—'}</td>
                </tr>
              )];
              if (open && n > 1) {
                for (const it of g.items.slice(1)) {
                  rows.push(
                    <tr key={it.id} className="audit-run-item">
                      <td style={{ whiteSpace: 'nowrap', fontVariantNumeric: 'tabular-nums' }}>{fmtDateTime(it.created_at)}</td>
                      <td><span style={{ color: ACTION_COLOR(it.action), fontWeight: 700 }}>{it.action}</span></td>
                      <td>{it.target_type ? `${it.target_type}${it.target_id ? ` #${it.target_id}` : ''}` : '—'}</td>
                      <td style={{ maxWidth: 420, overflow: 'hidden', textOverflow: 'ellipsis' }}>{it.summary || '—'}</td>
                      <td>{it.admin_name || it.admin_chat_id || '—'}</td>
                      <td style={{ color: 'var(--text-muted)', fontSize: 12 }}>{it.ip || '—'}</td>
                    </tr>,
                  );
                }
              }
              return rows;
            })}
          </tbody>
        </table>
      </div>

      {pages > 1 && (
        <div style={{ display: 'flex', gap: 8, justifyContent: 'center', padding: 14 }}>
          <button className="chip-btn" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>‹ prev</button>
          <span style={{ alignSelf: 'center', fontSize: 12, color: 'var(--text-muted)' }}>{page} / {pages}</span>
          <button className="chip-btn" disabled={page >= pages} onClick={() => setPage((p) => p + 1)}>next ›</button>
        </div>
      )}
    </div>
  );
}

import React, { useEffect, useMemo, useRef, useState } from 'react';

import { apiFetch, apiJson, postJson } from '../api.js';
import { useModal } from '../components/Modal.jsx';
import { useToast } from '../components/Toast.jsx';
import { STATUS_COLORS } from '../util.js';

const PER_PAGE = 50;

export function SubscriptionsPage() {
  const modal = useModal();
  const toast = useToast();
  const [subs, setSubs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [q, setQ] = useState('');
  const [sortBy, setSortBy] = useState('created');
  const [page, setPage] = useState(0);
  const [bulkMode, setBulkMode] = useState(false);
  const [selected, setSelected] = useState(() => new Set());
  const [detail, setDetail] = useState(null);
  const searchTimer = useRef(null);

  const load = async (search = '') => {
    setLoading(true);
    try {
      const { data } = await apiJson(`/api/admin/subscriptions?limit=2000${search ? '&search=' + encodeURIComponent(search) : ''}`);
      if (data.ok) setSubs(data.users || data.subscriptions || []);
    } catch (_) { /* ignore */ } finally { setLoading(false); }
  };
  useEffect(() => { load(); }, []);

  const view = useMemo(() => {
    let out = subs.slice();
    const query = q.trim().toLowerCase();
    if (query) out = out.filter((s) => (s.username || '').toLowerCase().includes(query) || (s.note || '').toLowerCase().includes(query));
    out.sort((a, b) => {
      switch (sortBy) {
        case 'created_asc': return new Date(a.created_at || 0) - new Date(b.created_at || 0);
        case 'expire': return (a.expire || 9999999999) - (b.expire || 9999999999);
        case 'expire_desc': return (b.expire || 0) - (a.expire || 0);
        case 'used': return (b.used_traffic_gb || 0) - (a.used_traffic_gb || 0);
        case 'used_asc': return (a.used_traffic_gb || 0) - (b.used_traffic_gb || 0);
        case 'username': return (a.username || '').localeCompare(b.username || '');
        default: return new Date(b.created_at || 0) - new Date(a.created_at || 0);
      }
    });
    return out;
  }, [subs, q, sortBy]);

  const totalPages = Math.max(1, Math.ceil(view.length / PER_PAGE));
  const curPage = Math.min(page, totalPages - 1);
  const start = curPage * PER_PAGE;
  const pageSubs = view.slice(start, start + PER_PAGE);
  const stats = useMemo(() => ({
    total: subs.length,
    active: subs.filter((s) => s.status === 'active').length,
    online: subs.filter((s) => s.is_online).length,
  }), [subs]);

  function onSearch(v) {
    setQ(v); setPage(0);
    if (searchTimer.current) clearTimeout(searchTimer.current);
    searchTimer.current = setTimeout(() => { /* client filter only; server search on refresh */ }, 150);
  }

  function toggleSel(username) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(username)) next.delete(username); else next.add(username);
      return next;
    });
  }

  async function bulk(action) {
    const names = [...selected];
    if (!names.length) return;
    const labels = { enable: 'Enable', disable: 'Disable', reset: 'Reset traffic for', delete: 'Delete' };
    const ok = await modal.confirm(`${labels[action]} ${names.length} sub(s)?`, action === 'delete' ? 'This permanently removes them from the panel.' : '', { danger: action === 'delete' || action === 'reset', okText: labels[action] });
    if (!ok) return;
    let done = 0;
    for (const name of names) {
      try {
        if (action === 'enable' || action === 'disable') {
          await postJson(`/api/admin/users/${encodeURIComponent(name)}/toggle-status`, { status: action === 'enable' ? 'active' : 'disabled' });
        } else if (action === 'reset') {
          await postJson(`/api/admin/subscriptions/${encodeURIComponent(name)}/extend`, { days: 0, traffic_gb: 0, traffic_mode: 'reset', days_mode: 'add' });
        } else if (action === 'delete') {
          await apiFetch(`/api/admin/subscriptions/${encodeURIComponent(name)}`, { method: 'DELETE' });
        }
        done++;
      } catch (_) { /* continue */ }
    }
    toast(`${labels[action]}: ${done}/${names.length} done`, 'success');
    setSelected(new Set());
    setBulkMode(false);
    load();
  }

  return (
    <>
      <div className="filter-bar glass-card" style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
        <div className="search-wrapper" style={{ flex: 1, minWidth: 180 }}>
          <input className="search-input input-field" placeholder="Search subscriptions…" value={q} onChange={(e) => onSearch(e.target.value)} />
        </div>
        <button className={'bulk-select-btn btn btn-secondary' + (bulkMode ? ' active' : '')} onClick={() => { setBulkMode((v) => !v); setSelected(new Set()); }}>{bulkMode ? 'Cancel' : 'Select'}</button>
        <select className="input-field" style={{ width: 'auto' }} value={sortBy} onChange={(e) => { setSortBy(e.target.value); setPage(0); }}>
          <option value="created">Created (new)</option>
          <option value="created_asc">Created (old)</option>
          <option value="expire">Expiry (soon)</option>
          <option value="expire_desc">Expiry (later)</option>
          <option value="used">Traffic ↓</option>
          <option value="used_asc">Traffic ↑</option>
          <option value="username">Username</option>
        </select>
        <button className="refresh-btn" onClick={() => load(q.trim())} title="Refresh" disabled={loading}>⟳</button>
      </div>

      {bulkMode && selected.size > 0 && (
        <div className="glass-card" style={{ marginTop: 16, padding: '12px 16px', display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
          <span style={{ fontWeight: 700 }}>{selected.size} selected</span>
          <button className="btn btn-secondary" onClick={() => bulk('enable')}>Enable</button>
          <button className="btn btn-secondary" onClick={() => bulk('disable')}>Disable</button>
          <button className="btn btn-secondary" onClick={() => bulk('reset')}>Reset traffic</button>
          <button className="btn btn-secondary btn-danger" onClick={() => bulk('delete')}>Delete</button>
        </div>
      )}

      <div className="stats-grid" style={{ display: 'flex', gap: 12, marginTop: 20, marginBottom: 20 }}>
        <div className="glass-card stat-card" style={{ padding: 16, flex: 1 }}><div className="stat-value" style={{ fontSize: 22 }}>{stats.total}</div><div className="stat-label">Total</div></div>
        <div className="glass-card stat-card" style={{ padding: 16, flex: 1 }}><div className="stat-value" style={{ fontSize: 22, color: 'var(--success)' }}>{stats.active}</div><div className="stat-label">Active</div></div>
        <div className="glass-card stat-card" style={{ padding: 16, flex: 1 }}><div className="stat-value" style={{ fontSize: 22, color: 'var(--brand)' }}>{stats.online}</div><div className="stat-label">Online</div></div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: 12 }}>
        {loading && <div style={{ gridColumn: '1/-1', textAlign: 'center', color: 'var(--text-muted)', padding: 40 }}>Loading…</div>}
        {!loading && pageSubs.length === 0 && <div style={{ gridColumn: '1/-1', textAlign: 'center', color: 'var(--text-muted)', padding: 40 }}>No subscriptions found</div>}
        {pageSubs.map((s) => {
          const used = parseFloat(s.used_traffic_gb) || 0;
          const limit = parseFloat(s.data_limit_gb) || 0;
          const pct = limit > 0 ? Math.min((used / limit) * 100, 100) : 0;
          const status = s.status || 'active';
          const dl = s.days_left;
          let expiryText = '∞'; let expiryColor = 'var(--text-muted)';
          if (dl !== null && dl !== undefined) {
            if (dl < 0) { expiryText = 'Expired'; expiryColor = 'var(--danger)'; }
            else if (dl === 0) { expiryText = 'Today'; expiryColor = 'var(--danger)'; }
            else if (dl <= 3) { expiryText = `${dl}d`; expiryColor = 'var(--danger)'; }
            else if (dl <= 7) { expiryText = `${dl}d`; expiryColor = 'var(--warning)'; }
            else expiryText = `${dl}d`;
          }
          const sel = selected.has(s.username);
          return (
            <div className="sub-card glass-card fx-tilt" key={s.username} style={{ padding: 14, cursor: 'pointer', outline: sel ? '2px solid var(--brand)' : 'none' }}
              onClick={() => (bulkMode ? toggleSel(s.username) : setDetail(s))}>
              <div className="sub-card-header" style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 10 }}>
                <div className="sub-card-user" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  {s.is_online && <span style={{ width: 6, height: 6, background: 'var(--success)', borderRadius: '50%', boxShadow: '0 0 6px var(--success)' }} />}
                  <span className="sub-card-name" style={{ fontWeight: 600 }}>{s.username}</span>
                </div>
                <span className="sub-card-status" style={{ color: STATUS_COLORS[status] || 'var(--text-muted)', fontSize: 11, fontWeight: 700 }}>{status.toUpperCase()}</span>
              </div>
              <div className="sub-card-stats" style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
                <div><span style={{ fontWeight: 700 }}>{used.toFixed(1)}/{limit > 0 ? limit.toFixed(0) : '∞'}</span> <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>GB</span></div>
                <div><span style={{ fontWeight: 700, color: expiryColor }}>{expiryText}</span> <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>left</span></div>
              </div>
              <div style={{ height: 6, background: 'rgba(255,255,255,0.08)', borderRadius: 3, overflow: 'hidden' }}>
                <div style={{ width: pct + '%', height: '100%', background: pct > 90 ? 'var(--danger)' : pct > 70 ? 'var(--warning)' : 'var(--success)' }} />
              </div>
            </div>
          );
        })}
      </div>

      <div className="pagination-bar glass-card" style={{ marginTop: 24, padding: '12px 16px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 12 }}>
        <span style={{ fontSize: 13, color: 'var(--text-muted)' }}>Showing {view.length ? start + 1 : 0}-{Math.min(start + PER_PAGE, view.length)} of {view.length}</span>
        <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
          <button className="btn btn-secondary" disabled={curPage === 0} onClick={() => setPage(curPage - 1)}>← Prev</button>
          <select className="input-field" style={{ width: 'auto' }} value={curPage} onChange={(e) => setPage(Number(e.target.value))}>
            {Array.from({ length: totalPages }, (_, i) => <option key={i} value={i}>Page {i + 1}</option>)}
          </select>
          <button className="btn btn-secondary" disabled={start + PER_PAGE >= view.length} onClick={() => setPage(curPage + 1)}>Next →</button>
        </div>
      </div>

      {detail && <SubDetail sub={detail} onClose={() => setDetail(null)} onChanged={() => { setDetail(null); load(q.trim()); }} />}
    </>
  );
}

function SubDetail({ sub, onClose, onChanged }) {
  const modal = useModal();
  const toast = useToast();
  const [days, setDays] = useState('');
  const [traffic, setTraffic] = useState('');
  const [trafficMode, setTrafficMode] = useState('add');
  const [daysMode, setDaysMode] = useState('add');
  const [busy, setBusy] = useState(false);

  const used = parseFloat(sub.used_traffic_gb) || 0;
  const limit = parseFloat(sub.data_limit_gb) || 0;

  async function save() {
    const d = parseInt(days) || 0;
    const t = parseInt(traffic) || 0;
    if (d === 0 && t === 0 && trafficMode !== 'reset') { onClose(); return; }
    setBusy(true);
    try {
      const { data } = await postJson(`/api/admin/subscriptions/${encodeURIComponent(sub.username)}/extend`, { days: d, traffic_gb: t, traffic_mode: trafficMode, days_mode: daysMode });
      if (data.ok) { toast('Subscription updated', 'success'); onChanged(); }
      else await modal.alert('Error', data.error || 'Update failed');
    } catch (_) { await modal.alert('Error', 'Connection error'); } finally { setBusy(false); }
  }
  async function toggle() {
    const newStatus = (sub.status === 'active') ? 'disabled' : 'active';
    await postJson(`/api/admin/users/${encodeURIComponent(sub.username)}/toggle-status`, { status: newStatus });
    toast(newStatus === 'active' ? 'Enabled' : 'Disabled', 'success');
    onChanged();
  }
  async function del() {
    const ok = await modal.confirm('Delete User?', `Permanently delete "${sub.username}" from the server. Cannot be undone.`, { danger: true, okText: 'Delete' });
    if (!ok) return;
    const res = await apiFetch(`/api/admin/subscriptions/${encodeURIComponent(sub.username)}`, { method: 'DELETE' });
    let data = {}; try { data = await res.json(); } catch (_) { data = {}; }
    if (data.ok) { toast('Deleted', 'success'); onChanged(); }
    else await modal.alert('Error', data.error || 'Failed to delete user');
  }
  async function usage() {
    const { data } = await apiJson(`/api/admin/subscriptions/${encodeURIComponent(sub.username)}/usage`);
    if (data.ok && Array.isArray(data.usages) && data.usages.length) {
      const lines = data.usages.map((u) => `${u.node_name}: ${((u.used_traffic || 0) / (1024 ** 3)).toFixed(2)} GB`).join('\n');
      await modal.alert('Server usage', lines);
    } else await modal.alert('No usage', 'No server usage data yet.');
  }

  return (
    <div className="v3-modal-backdrop open" onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="v3-modal" role="dialog" aria-modal="true" style={{ maxWidth: 480 }}>
        <div className="v3-modal-head">
          <div><div className="v3-modal-title">{sub.username}</div><div className="v3-modal-sub" style={{ color: STATUS_COLORS[sub.status] || 'var(--text-muted)' }}>{(sub.status || 'unknown').toUpperCase()}</div></div>
          <button className="mini-close" type="button" onClick={onClose}>✕</button>
        </div>
        <div className="v3-modal-body">
          <div className="sub-modal-row" style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 0' }}><span style={{ color: 'var(--text-muted)' }}>Traffic</span><span>{used.toFixed(2)} / {limit > 0 ? limit.toFixed(0) + ' GB' : '∞'}</span></div>
          <div className="sub-modal-row" style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 0' }}><span style={{ color: 'var(--text-muted)' }}>Expires</span><span>{sub.days_left != null ? sub.days_left + 'd left' : '∞'}</span></div>
          {sub.note && <div className="sub-modal-row" style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 0' }}><span style={{ color: 'var(--text-muted)' }}>Note</span><span>{sub.note}</span></div>}

          <div style={{ marginTop: 16, display: 'grid', gap: 10 }}>
            <div style={{ display: 'flex', gap: 8 }}>
              <input className="input-field" type="number" placeholder="Days" value={days} onChange={(e) => setDays(e.target.value)} />
              <select className="input-field" style={{ width: 130 }} value={daysMode} onChange={(e) => setDaysMode(e.target.value)}>
                <option value="add">Add days</option><option value="set">Set from now</option>
              </select>
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
              <input className="input-field" type="number" placeholder="Traffic GB" value={traffic} onChange={(e) => setTraffic(e.target.value)} disabled={trafficMode === 'reset'} />
              <select className="input-field" style={{ width: 130 }} value={trafficMode} onChange={(e) => setTrafficMode(e.target.value)}>
                <option value="add">Add to current</option><option value="set">Set limit</option><option value="reset">Reset used → 0</option>
              </select>
            </div>
          </div>
        </div>
        <div className="v3-modal-actions" style={{ flexWrap: 'wrap', gap: 8 }}>
          <button className="btn btn-secondary" onClick={usage}>Usage</button>
          <button className="btn btn-secondary" onClick={toggle}>{sub.status === 'active' ? 'Disable' : 'Enable'}</button>
          <button className="btn btn-secondary btn-danger" onClick={del}>Delete</button>
          <button className="btn btn-primary" onClick={save} disabled={busy}>{busy ? '…' : 'Save'}</button>
        </div>
      </div>
    </div>
  );
}

import React, { useEffect, useRef, useState } from 'react';

import { apiFetch, apiJson, postJson } from '../api.js';
import { useModal } from '../components/Modal.jsx';
import { useToast } from '../components/Toast.jsx';
import { Icons } from '../icons.jsx';
import { STATUS_COLORS, timeAgo } from '../util.js';

const PER_PAGE = 50;

// Server-driven pagination (2026-07-20): each page is ONE panel-backed request
// with native search/sort — replaces the old fetch-2000-then-filter-in-JS page,
// whose single call was the slowest in the panel (3s+).
export function SubscriptionsPage() {
  const modal = useModal();
  const toast = useToast();
  const [subs, setSubs] = useState([]);
  const [total, setTotal] = useState(0);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [q, setQ] = useState('');
  const [sortBy, setSortBy] = useState('created');
  const [page, setPage] = useState(0);
  const [bulkMode, setBulkMode] = useState(false);
  const [selected, setSelected] = useState(() => new Set());
  const [detail, setDetail] = useState(null);
  const searchTimer = useRef(null);
  const reqSeq = useRef(0);

  const load = async (search = q.trim(), pageIdx = page, sort = sortBy) => {
    const seq = ++reqSeq.current;
    setLoading(true);
    try {
      const params = new URLSearchParams({ page: String(pageIdx + 1), limit: String(PER_PAGE), sort });
      if (search) params.set('search', search);
      const { data } = await apiJson(`/api/admin/subscriptions?${params}`);
      if (seq !== reqSeq.current) return; // a newer request superseded this one
      if (data.ok) {
        setSubs(data.users || data.subscriptions || []);
        setTotal(Number(data.total) || 0);
        if (data.stats && data.stats.total != null) setStats(data.stats);
      }
    } catch (_) { /* ignore */ } finally { if (seq === reqSeq.current) setLoading(false); }
  };
  useEffect(() => { load('', 0, 'created'); }, []);

  const totalPages = Math.max(1, Math.ceil(total / PER_PAGE));
  const curPage = Math.min(page, totalPages - 1);
  const start = curPage * PER_PAGE;
  const pageSubs = subs;

  function onSearch(v) {
    setQ(v); setPage(0);
    if (searchTimer.current) clearTimeout(searchTimer.current);
    searchTimer.current = setTimeout(() => { load(v.trim(), 0); }, 350);
  }

  function onSort(v) {
    setSortBy(v); setPage(0);
    load(q.trim(), 0, v);
  }

  function goPage(idx) {
    setPage(idx);
    load(q.trim(), idx);
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
      <div className="stats-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(110px, 1fr))', gap: 12, marginBottom: 16 }}>
        <div className="glass-card stat-card" style={{ padding: 16 }}><div className="stat-label">Total</div><div className="stat-value">{stats ? stats.total : (loading ? '…' : total)}</div></div>
        <div className="glass-card stat-card" style={{ padding: 16 }}><div className="stat-label">Active</div><div className="stat-value" style={{ color: 'var(--success)' }}>{stats ? stats.active : '…'}</div></div>
        <div className="glass-card stat-card" style={{ padding: 16 }}><div className="stat-label">Online</div><div className="stat-value" style={{ color: 'var(--brand)' }}>{stats ? stats.online : '…'}</div></div>
      </div>

      <div className="filter-bar glass-card rcp-bar">
        <div className="search-wrapper rcp-search">
          <input className="search-input input-field" placeholder="Search subscriptions…" value={q} onChange={(e) => onSearch(e.target.value)} />
        </div>
        <div className="rcp-bar-row">
          <button className={'btn btn-secondary sb-select' + (bulkMode ? ' on' : '')} onClick={() => { setBulkMode((v) => !v); setSelected(new Set()); }}>{bulkMode ? 'Cancel' : 'Select'}</button>
          <select className="input-field" value={sortBy} onChange={(e) => onSort(e.target.value)}>
            <option value="created">Created (new)</option>
            <option value="created_asc">Created (old)</option>
            <option value="expire">Expiry (soon)</option>
            <option value="expire_desc">Expiry (later)</option>
            <option value="used">Traffic: high first</option>
            <option value="used_asc">Traffic: low first</option>
            <option value="username">Username</option>
          </select>
          <span className="rcp-count">{total}</span>
          <button className="refresh-btn" onClick={() => load(q.trim())} title="Refresh" disabled={loading}>
            <Icons.refresh width={15} height={15} />
          </button>
        </div>
      </div>

      {bulkMode && (
        <div className="glass-card sb-bulkbar">
          <span className="sb-bulk-count">{selected.size} selected</span>
          <button className="btn btn-secondary" onClick={() => setSelected(new Set(pageSubs.map((s) => s.username)))}>Page</button>
          <button className="btn btn-secondary" disabled={!selected.size} onClick={() => bulk('enable')}>Enable</button>
          <button className="btn btn-secondary" disabled={!selected.size} onClick={() => bulk('disable')}>Disable</button>
          <button className="btn btn-secondary" disabled={!selected.size} onClick={() => bulk('reset')}>Reset traffic</button>
          <button className="btn btn-secondary btn-danger" disabled={!selected.size} onClick={() => bulk('delete')}>Delete</button>
        </div>
      )}

      <div className="sb-grid">
        {loading && <div style={{ gridColumn: '1/-1', textAlign: 'center', color: 'var(--text-muted)', padding: 40 }}>Loading…</div>}
        {!loading && pageSubs.length === 0 && <div style={{ gridColumn: '1/-1', textAlign: 'center', color: 'var(--text-muted)', padding: 40 }}>No subscriptions found</div>}
        {pageSubs.map((s) => {
          const used = parseFloat(s.used_traffic_gb) || 0;
          const limit = parseFloat(s.data_limit_gb) || 0;
          const pct = limit > 0 ? Math.min((used / limit) * 100, 100) : 0;
          const status = s.status || 'active';
          const dl = s.days_left;
          let expiryText = 'no expiry'; let expiryCls = '';
          if (dl !== null && dl !== undefined) {
            if (dl < 0) { expiryText = 'Expired'; expiryCls = ' bad'; }
            else if (dl === 0) { expiryText = 'Today'; expiryCls = ' bad'; }
            else if (dl <= 3) { expiryText = `${dl}d left`; expiryCls = ' bad'; }
            else if (dl <= 7) { expiryText = `${dl}d left`; expiryCls = ' warn'; }
            else expiryText = `${dl}d left`;
          }
          const sel = selected.has(s.username);
          return (
            <div
              className={'sb-card glass-card fx-tilt' + (sel ? ' sel' : '')}
              key={s.username}
              role="button"
              tabIndex={0}
              onClick={() => (bulkMode ? toggleSel(s.username) : setDetail(s))}
              onKeyDown={(e) => { if (e.key === 'Enter') (bulkMode ? toggleSel(s.username) : setDetail(s)); }}
            >
              <div className="sb-head">
                {bulkMode && <span className={'sb-check' + (sel ? ' on' : '')} aria-hidden="true">{sel && <Icons.check width={11} height={11} />}</span>}
                {s.is_online && <span className="sb-online" title="Online now" />}
                <span className="sb-name" dir="ltr">{s.username}</span>
                <span className={'sb-st ' + status}>{status}</span>
              </div>
              <div className="sb-stats">
                <span className="sb-gb"><b>{used.toFixed(1)}</b> / {limit > 0 ? limit.toFixed(0) : '∞'} GB</span>
                <span className={'sb-exp' + expiryCls}>{expiryText}</span>
              </div>
              <div className="sb-bar"><i style={{ width: pct + '%' }} className={pct > 90 ? 'bad' : pct > 70 ? 'warn' : ''} /></div>
              {s.note && <div className="sb-note" title={s.note}>{s.note}</div>}
            </div>
          );
        })}
      </div>

      {totalPages > 1 && (
        <div className="pagination-bar glass-card usr-pager">
          <span className="usr-pager-info">{total ? start + 1 : 0}–{Math.min(start + pageSubs.length, total)} of {total}</span>
          <div className="usr-pager-nav">
            <button className="btn btn-secondary" disabled={curPage === 0 || loading} onClick={() => goPage(curPage - 1)}>Prev</button>
            <select className="input-field" value={curPage} onChange={(e) => goPage(Number(e.target.value))} disabled={loading}>
              {Array.from({ length: totalPages }, (_, i) => <option key={i} value={i}>Page {i + 1}</option>)}
            </select>
            <button className="btn btn-secondary" disabled={start + PER_PAGE >= total || loading} onClick={() => goPage(curPage + 1)}>Next</button>
          </div>
        </div>
      )}

      {detail && <SubDetail sub={detail} onClose={() => setDetail(null)} onChanged={() => { setDetail(null); load(q.trim()); }} />}
    </>
  );
}

// Read-only device/client view under the cap control. HWIDs only come from
// Hiddify-family clients; the recent config fetches (user-agent + time) cover
// everything else, so support can tell "which app is this user on" either way.
function DeviceList({ username, hwidLimit }) {
  const [d, setD] = useState(null); // null=loading, 'error', or payload

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const { data } = await apiJson(`/api/admin/subscriptions/${encodeURIComponent(username)}/devices`);
        if (alive) setD(data.ok ? data : 'error');
      } catch (_) { if (alive) setD('error'); }
    })();
    return () => { alive = false; };
  }, [username]);

  const cap = hwidLimit || 0;
  const head = (label) => (
    <div style={{ fontSize: 10.5, fontWeight: 700, letterSpacing: '0.07em', textTransform: 'uppercase', color: 'var(--text-muted)', margin: '10px 0 4px' }}>{label}</div>
  );

  if (d === null) return <>{head('Devices')}<div style={{ fontSize: 12, color: 'var(--text-muted)' }}>Loading devices…</div></>;
  if (d === 'error' || d.devices_available === false) {
    return <>{head('Devices')}<div style={{ fontSize: 12, color: 'var(--text-muted)' }}>Device info unavailable right now.</div></>;
  }

  const devices = d.devices || [];
  const fetches = d.recent_fetches || [];
  return (
    <>
      {head(`Devices (${d.device_count ?? devices.length}${cap ? `/${cap}` : ''})`)}
      {devices.length === 0 && (
        <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
          No devices registered{cap ? '' : ' (only Hiddify-family clients report device ids)'}.
        </div>
      )}
      {devices.length > 0 && (
        <div style={{ display: 'grid', gap: 4 }}>
          {devices.map((dev) => (
            <div key={dev.id ?? dev.hwid} style={{ display: 'flex', justifyContent: 'space-between', gap: 8, fontSize: 12, fontVariantNumeric: 'tabular-nums' }}>
              <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={dev.hwid || ''}>
                {[dev.device_model, dev.device_os, dev.os_version].filter(Boolean).join(' · ')
                  || (dev.hwid ? `hwid ${String(dev.hwid).slice(0, 10)}…` : 'unknown device')}
              </span>
              <span style={{ color: 'var(--text-muted)', flexShrink: 0 }} title="Last seen">{timeAgo(dev.last_seen)}</span>
            </div>
          ))}
        </div>
      )}

      {fetches.length > 0 && (
        <>
          {head('Recent config fetches')}
          <div style={{ display: 'grid', gap: 4 }}>
            {fetches.map((f, i) => (
              <div key={i} style={{ display: 'flex', justifyContent: 'space-between', gap: 8, fontSize: 12, fontVariantNumeric: 'tabular-nums' }}>
                <span dir="ltr" style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={f.user_agent || ''}>{f.user_agent || 'unknown client'}</span>
                <span style={{ color: 'var(--text-muted)', flexShrink: 0 }}>{timeAgo(f.at)}</span>
              </div>
            ))}
          </div>
        </>
      )}
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
  // Manual per-user device cap (PasarGuard hwid_limit). Only Hiddify-family
  // clients report device ids, so this is a targeted anti-sharing tool, not
  // a plan feature — see handle_admin_set_hwid_limit.
  async function deviceCap() {
    const cur = sub.hwid_limit || 0;
    const v = await modal.prompt('Device cap', `Max devices for "${sub.username}" (0 = unlimited). Current: ${cur || 'unlimited'}`, String(cur), { okText: 'Set' });
    if (v == null) return;
    const n = parseInt(v);
    if (Number.isNaN(n) || n < 0 || n > 50) { toast('Enter 0–50', 'error'); return; }
    const { data } = await postJson(`/api/admin/subscriptions/${encodeURIComponent(sub.username)}/hwid`, { limit: n });
    if (data.ok) { toast(n ? `Capped at ${n} device(s)` : 'Device cap removed', 'success'); onChanged(); }
    else await modal.alert('Error', data.error || 'Failed to set device cap');
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

          <DeviceList username={sub.username} hwidLimit={sub.hwid_limit} />

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
          <button className="btn btn-secondary" onClick={deviceCap} title="Max simultaneous devices (PasarGuard hwid)">
            Devices{sub.hwid_limit ? `: ${sub.hwid_limit}` : ''}
          </button>
          <button className="btn btn-secondary" onClick={toggle}>{sub.status === 'active' ? 'Disable' : 'Enable'}</button>
          <button className="btn btn-secondary btn-danger" onClick={del}>Delete</button>
          <button className="btn btn-primary" onClick={save} disabled={busy}>{busy ? '…' : 'Save'}</button>
        </div>
      </div>
    </div>
  );
}

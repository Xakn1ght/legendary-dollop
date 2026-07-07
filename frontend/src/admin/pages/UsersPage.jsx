import React, { useEffect, useMemo, useState } from 'react';

import { apiJson, postJson } from '../api.js';
import { useModal } from '../components/Modal.jsx';
import { useToast } from '../components/Toast.jsx';
import { Icons } from '../icons.jsx';
import { fmtNum } from '../util.js';

const PER_PAGE = 50;

export function UsersPage() {
  const modal = useModal();
  const toast = useToast();
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  // command palette can hand us a prefilled search (sessionStorage, one-shot)
  const [q, setQ] = useState(() => {
    try {
      const v = sessionStorage.getItem('admin_user_search') || '';
      sessionStorage.removeItem('admin_user_search');
      return v;
    } catch (_) { return ''; }
  });
  const [sortBy, setSortBy] = useState('created');
  const [page, setPage] = useState(0);

  const load = async () => {
    setLoading(true);
    try {
      const { data } = await apiJson('/api/admin/users?limit=1000');
      if (data.ok) setUsers(data.users || []);
    } catch (_) { /* ignore */ } finally { setLoading(false); }
  };
  useEffect(() => { load(); }, []);

  const view = useMemo(() => {
    let out = users.slice();
    const query = q.trim().toLowerCase();
    if (query) {
      out = out.filter((u) => (u.username || '').toLowerCase().includes(query)
        || (u.full_name || '').toLowerCase().includes(query)
        || String(u.chat_id || '').includes(query));
    }
    out.sort((a, b) => {
      switch (sortBy) {
        case 'credit': return (b.credit || 0) - (a.credit || 0);
        case 'credit_asc': return (a.credit || 0) - (b.credit || 0);
        case 'username': return (a.username || '').localeCompare(b.username || '');
        case 'level': return (b.level || 1) - (a.level || 1);
        default: return new Date(b.created_at || 0) - new Date(a.created_at || 0);
      }
    });
    return out;
  }, [users, q, sortBy]);

  const totalPages = Math.max(1, Math.ceil(view.length / PER_PAGE));
  const curPage = Math.min(page, totalPages - 1);
  const start = curPage * PER_PAGE;
  const pageUsers = view.slice(start, start + PER_PAGE);

  async function editCredit(u) {
    const val = await modal.prompt('Edit user credit', `@${u.username || u.chat_id}`, String(u.credit ?? ''));
    if (val === null) return;
    const credit = parseFloat(String(val).trim());
    if (!isFinite(credit)) { await modal.alert('Invalid value', 'Please enter a valid number.'); return; }
    await postJson(`/api/admin/users/${u.id}`, { credit });
    toast('Credit updated', 'success');
    load();
  }
  async function toggleBan(u) {
    const ok = await modal.confirm(u.banned ? 'Unban user?' : 'Ban user?', `@${u.username || u.chat_id}`, { danger: !u.banned });
    if (!ok) return;
    await postJson(`/api/admin/users/${u.id}`, { banned: !u.banned });
    toast(u.banned ? 'User unbanned' : 'User banned', 'success');
    load();
  }
  async function resetArcade(u) {
    const ok = await modal.confirm('Reset daily arcade limit?', 'This resets the daily arcade limit for this user.');
    if (!ok) return;
    await postJson(`/api/admin/users/${u.id}/reset-arcade`, {});
    toast('Arcade limit reset', 'success');
  }

  return (
    <>
      <div className="filter-bar glass-card" style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
        <div className="search-wrapper" style={{ flex: 1, minWidth: 180 }}>
          <input className="search-input input-field" placeholder="Search users…" value={q} onChange={(e) => { setQ(e.target.value); setPage(0); }} />
        </div>
        <select className="input-field" style={{ width: 'auto' }} value={sortBy} onChange={(e) => { setSortBy(e.target.value); setPage(0); }}>
          <option value="created">Newest</option>
          <option value="credit">Credit ↓</option>
          <option value="credit_asc">Credit ↑</option>
          <option value="username">Username</option>
          <option value="level">Level</option>
        </select>
        <button className="refresh-btn" onClick={load} title="Refresh" disabled={loading}>⟳</button>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 16, paddingTop: 20 }}>
        {loading && <div style={{ gridColumn: '1/-1', textAlign: 'center', color: 'var(--text-muted)', padding: 40 }}>Loading…</div>}
        {!loading && pageUsers.length === 0 && <div style={{ gridColumn: '1/-1', textAlign: 'center', color: 'var(--text-muted)', padding: 40 }}>No users found</div>}
        {pageUsers.map((u) => (
          <div className="glass-card fx-tilt" key={u.id} style={{ padding: 20 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 12 }}>
              <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
                <div style={{ width: 40, height: 40, background: 'rgba(255,255,255,0.1)', borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 700 }}>{(u.full_name || 'U')[0].toUpperCase()}</div>
                <div>
                  <div style={{ fontWeight: 600 }}>{u.full_name || 'Unknown'}</div>
                  <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>@{u.username || '—'}</div>
                </div>
              </div>
              <span className={'badge ' + (u.banned ? 'badge-danger' : 'badge-success')}>{u.banned ? 'BANNED' : 'ACTIVE'}</span>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 16 }}>
              <div style={{ background: 'rgba(0,0,0,0.2)', padding: 8, borderRadius: 8 }}>
                <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>CREDIT</div>
                <div style={{ fontWeight: 600 }}>{fmtNum(u.credit)}</div>
              </div>
              <div style={{ background: 'rgba(0,0,0,0.2)', padding: 8, borderRadius: 8 }}>
                <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>LEVEL</div>
                <div style={{ fontWeight: 600 }}>{u.level || 1}</div>
              </div>
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
              <button onClick={() => editCredit(u)} className="btn btn-secondary" style={{ flex: 1, padding: 8, fontSize: 12 }}>Edit</button>
              <button onClick={() => resetArcade(u)} className="btn btn-secondary" style={{ flex: 1, padding: 8, display: 'flex', alignItems: 'center', justifyContent: 'center' }} title="Reset Arcade Limit"><Icons.gamepad width={16} height={16} /></button>
              <button onClick={() => toggleBan(u)} className="btn" style={{ flex: 1, padding: 8, fontSize: 12, background: 'rgba(248,113,113,0.12)', color: 'var(--danger)' }}>{u.banned ? 'Unban' : 'Ban'}</button>
            </div>
          </div>
        ))}
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
    </>
  );
}

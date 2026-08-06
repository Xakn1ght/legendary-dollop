import React, { useEffect, useRef, useState } from 'react';

import { apiJson, postJson } from '../api.js';
import { useModal } from '../components/Modal.jsx';
import { useToast } from '../components/Toast.jsx';
import { Icons } from '../icons.jsx';
import { fmtDateTime, fmtNum } from '../util.js';

const PER_PAGE = 50;

const DIFF_LABELS = {
  easy: 'Easy — enemies 15% slower',
  normal: 'Normal (default)',
  hard: 'Hard — enemies 15% faster',
  boss_rush: 'Boss test (QA) — all bosses from level 2',
};

// Per-user arcade panel: coin grants + difficulty + daily-limit reset.
// Coins are arcade-only (skins/powers/retries) so grants can't mint money.
function ArcadeModal({ user, onClose }) {
  const toast = useToast();
  const [wallet, setWallet] = useState(null);
  const [loadError, setLoadError] = useState('');
  const [diffs, setDiffs] = useState(['easy', 'normal', 'hard', 'boss_rush']);
  const [grant, setGrant] = useState('');
  const [busy, setBusy] = useState(false);

  const load = async () => {
    setLoadError('');
    try {
      const { status, data } = await apiJson(`/api/admin/users/${user.id}/arcade`);
      if (data.ok) {
        setWallet(data.wallet);
        if (data.difficulties?.length) setDiffs(data.difficulties);
      } else if (status === 404) {
        // endpoint missing = the bot is running pre-arcade-panel code
        setLoadError('Endpoint not found (404) — the bot needs a restart to serve this panel.');
      } else {
        setLoadError(`Failed to load wallet (${status || 'network'}${data.error ? ': ' + data.error : ''}).`);
      }
    } catch (_) { setLoadError('Failed to load wallet (network).'); }
  };
  useEffect(() => { load(); }, [user.id]);

  async function adjust(body, okMsg) {
    setBusy(true);
    try {
      const { data } = await postJson(`/api/admin/users/${user.id}/arcade`, body);
      if (data?.ok) { setWallet(data.wallet); toast(okMsg, 'success'); }
      else toast(data?.error || 'Failed', 'error');
    } catch (_) { toast('Failed', 'error'); } finally { setBusy(false); }
  }

  async function grantCoins() {
    const n = parseInt(String(grant).trim(), 10);
    if (!isFinite(n) || !n) { toast('Enter a non-zero number', 'error'); return; }
    await adjust({ coins_delta: n }, n > 0 ? `+${n} coins granted` : `${n} coins removed`);
    setGrant('');
  }

  async function resetDaily() {
    setBusy(true);
    try {
      const { data } = await postJson(`/api/admin/users/${user.id}/reset-arcade`, {});
      if (!data?.ok) toast(data?.error || 'Reset failed', 'error');
      else if (data.reset) toast(`Today's run cleared (was ${fmtNum(data.cleared_best)})`, 'success');
      else toast('Gate already open — nothing to clear', 'success');
    } catch (_) { toast('Reset failed', 'error'); } finally { setBusy(false); }
  }

  return (
    <div className="v3-modal-backdrop open" onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="v3-modal" role="dialog" aria-modal="true">
        <div className="v3-modal-head">
          <div>
            <div className="v3-modal-title">Arcade — @{user.username || user.chat_id}</div>
            <div className="v3-modal-sub">Coins are arcade-only; they never convert to credit.</div>
          </div>
          <button className="mini-close" type="button" aria-label="Close" onClick={onClose}>✕</button>
        </div>
        <div className="v3-modal-body">
          {!wallet && !loadError && <div style={{ color: 'var(--text-muted)', padding: 12 }}>Loading…</div>}
          {!wallet && loadError && (
            <div style={{ padding: 12 }}>
              <div style={{ color: 'var(--danger)', marginBottom: 10 }}>{loadError}</div>
              <button className="btn btn-secondary" onClick={load}>Retry</button>
            </div>
          )}
          {wallet && (
            <>
              <div style={{ display: 'flex', gap: 8, marginBottom: 14 }}>
                <div style={{ flex: 1, background: 'rgba(255,210,63,0.08)', border: '1px solid rgba(255,210,63,0.3)', borderRadius: 10, padding: 10 }}>
                  <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>COINS</div>
                  <div style={{ fontWeight: 700, fontSize: 18 }}>{wallet.coins}</div>
                </div>
                <div style={{ flex: 1, background: 'rgba(0,0,0,0.2)', borderRadius: 10, padding: 10 }}>
                  <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>SKIN</div>
                  <div style={{ fontWeight: 700, fontSize: 14, paddingTop: 3 }}>{wallet.equipped_skin}</div>
                </div>
                <div style={{ flex: 1, background: 'rgba(0,0,0,0.2)', borderRadius: 10, padding: 10 }}>
                  <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>EXTRA LIVES</div>
                  <div style={{ fontWeight: 700, fontSize: 18 }}>{wallet.extra_lives}</div>
                </div>
              </div>

              <div style={{ marginBottom: 14 }}>
                <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 6 }}>Grant / remove coins</div>
                <div style={{ display: 'flex', gap: 8 }}>
                  <input
                    className="input-field" type="number" placeholder="e.g. 100 or -20"
                    value={grant} onChange={(e) => setGrant(e.target.value)}
                    onKeyDown={(e) => { if (e.key === 'Enter') grantCoins(); }}
                    style={{ flex: 1 }}
                  />
                  <button className="btn btn-primary" disabled={busy} onClick={grantCoins}>Apply</button>
                </div>
              </div>

              <div style={{ marginBottom: 14 }}>
                <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 6 }}>Difficulty (applies from their next run)</div>
                <select
                  className="input-field" value={wallet.difficulty || 'normal'} disabled={busy}
                  onChange={(e) => adjust({ difficulty: e.target.value }, `Difficulty set to ${e.target.value}`)}
                >
                  {diffs.map((d) => <option key={d} value={d}>{DIFF_LABELS[d] || d}</option>)}
                </select>
              </div>

              <button className="btn btn-secondary" disabled={busy} onClick={resetDaily} style={{ width: '100%' }}>
                Reset today's play limit
              </button>
            </>
          )}
        </div>
        <div className="v3-modal-actions">
          <button className="btn btn-primary" type="button" onClick={onClose}>Done</button>
        </div>
      </div>
    </div>
  );
}

function agoShort(v) {
  const d = v ? new Date(v) : null;
  if (!d || isNaN(d)) return '—';
  const s = Math.max(0, Math.floor((Date.now() - d.getTime()) / 1000));
  if (s < 3600) return `${Math.max(1, Math.floor(s / 60))}m`;
  if (s < 86400) return `${Math.floor(s / 3600)}h`;
  if (s < 86400 * 30) return `${Math.floor(s / 86400)}d`;
  return `${Math.floor(s / (86400 * 30))}mo`;
}

// Server-driven pagination (audit leftover, 2026-07-21): one 50-row request
// per page with native search — replaces the old fetch-1000-then-filter-in-JS
// page, same pattern as SubscriptionsPage. The backend orders newest-first and
// has no sort param, so the old client-side sort select is gone; the old
// Active/Banned/New(7d) overview cards needed the full list and are gone too
// (Total Users survives via /api/admin/stats).
export function UsersPage() {
  const modal = useModal();
  const toast = useToast();
  const [users, setUsers] = useState([]);
  const [total, setTotal] = useState(0);
  const [grandTotal, setGrandTotal] = useState(null);
  const [loading, setLoading] = useState(true);
  const [arcadeUser, setArcadeUser] = useState(null);
  // command palette can hand us a prefilled search (sessionStorage, one-shot)
  const [q, setQ] = useState(() => {
    try {
      const v = sessionStorage.getItem('admin_user_search') || '';
      sessionStorage.removeItem('admin_user_search');
      return v;
    } catch (_) { return ''; }
  });
  const [page, setPage] = useState(0);
  const searchTimer = useRef(null);
  const reqSeq = useRef(0);

  const load = async (search = q.trim(), pageIdx = page) => {
    const seq = ++reqSeq.current;
    setLoading(true);
    try {
      const params = new URLSearchParams({ page: String(pageIdx + 1), limit: String(PER_PAGE) });
      if (search) params.set('search', search);
      const { data } = await apiJson(`/api/admin/users?${params}`);
      if (seq !== reqSeq.current) return; // a newer request superseded this one
      if (data.ok) {
        setUsers(data.users || []);
        setTotal(Number(data.total) || 0);
      }
    } catch (_) { /* ignore */ } finally { if (seq === reqSeq.current) setLoading(false); }
  };
  useEffect(() => {
    load(q.trim(), 0);
    (async () => {
      try {
        const { data } = await apiJson('/api/admin/stats');
        if (data.ok && data.stats) setGrandTotal(data.stats.total_users);
      } catch (_) { /* ignore */ }
    })();
  }, []);

  const totalPages = Math.max(1, Math.ceil(total / PER_PAGE));
  const curPage = Math.min(page, totalPages - 1);
  const start = curPage * PER_PAGE;
  const pageUsers = users;

  function onSearch(v) {
    setQ(v); setPage(0);
    if (searchTimer.current) clearTimeout(searchTimer.current);
    searchTimer.current = setTimeout(() => { load(v.trim(), 0); }, 350);
  }

  function goPage(idx) {
    setPage(idx);
    load(q.trim(), idx);
  }

  async function editCredit(u) {
    const val = await modal.prompt('Edit user credit', `@${u.username || u.chat_id}`, String(u.credit ?? ''));
    if (val === null) return;
    const credit = parseFloat(String(val).trim());
    if (!isFinite(credit)) { await modal.alert('Invalid value', 'Please enter a valid number.'); return; }
    await postJson(`/api/admin/users/${u.id}`, { credit });
    toast('Credit updated', 'success');
    load(q.trim(), curPage);
  }
  async function toggleBan(u) {
    const ok = await modal.confirm(u.banned ? 'Unban user?' : 'Ban user?', `@${u.username || u.chat_id}`, { danger: !u.banned });
    if (!ok) return;
    await postJson(`/api/admin/users/${u.id}`, { banned: !u.banned });
    toast(u.banned ? 'User unbanned' : 'User banned', 'success');
    load(q.trim(), curPage);
  }
  // gamepad button → full arcade panel (coins / difficulty / daily reset)

  return (
    <>
      <div className="stats-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: 12, marginBottom: 16 }}>
        <div className="glass-card stat-card" style={{ padding: 16 }}><div className="stat-label">Total Users</div><div className="stat-value">{grandTotal == null ? '…' : fmtNum(grandTotal)}</div></div>
        <div className="glass-card stat-card" style={{ padding: 16 }}><div className="stat-label">Matching</div><div className="stat-value" style={{ color: 'var(--brand)' }}>{loading ? '…' : fmtNum(total)}</div></div>
      </div>

      <div className="filter-bar glass-card rcp-bar">
        <div className="search-wrapper rcp-search">
          <input className="search-input input-field" placeholder="Search users…" value={q} onChange={(e) => onSearch(e.target.value)} />
        </div>
        <div className="rcp-bar-row">
          <span className="rcp-count">{fmtNum(total)}</span>
          <button className="refresh-btn" onClick={() => load(q.trim(), curPage)} title="Refresh" disabled={loading}>
            <Icons.refresh width={15} height={15} />
          </button>
        </div>
      </div>

      <div className="rcp-grid usr-grid">
        {loading && <div style={{ gridColumn: '1/-1', textAlign: 'center', color: 'var(--text-muted)', padding: 40 }}>Loading…</div>}
        {!loading && pageUsers.length === 0 && <div style={{ gridColumn: '1/-1', textAlign: 'center', color: 'var(--text-muted)', padding: 40 }}>No users found</div>}
        {pageUsers.map((u) => (
          <div className="glass-card receipt-card fx-tilt" key={u.id}>
            <div className="rcp-head">
              <div className="receipt-avatar">{(u.full_name || u.username || 'U').trim().charAt(0).toUpperCase()}</div>
              <div className="rcp-who">
                <div className="receipt-name"><bdi>{u.full_name || 'Unknown'}</bdi></div>
                <div className="receipt-handle">@{u.username || '—'}</div>
              </div>
              <span className={'badge ' + (u.banned ? 'badge-danger' : 'badge-success')}>{u.banned ? 'BANNED' : 'ACTIVE'}</span>
            </div>

            <div className="rcp-meta">
              <div className="rcp-meta-l">
                <div className="rcp-plan">
                  <span className="rcp-gb">LVL {u.level || 1}</span>
                  {Number(u.stars) > 0 && <span className="usr-stars"><Icons.star width={10} height={10} /> {fmtNum(u.stars)}</span>}
                </div>
                <div className="rcp-sub">
                  <span className="rcp-service" dir="ltr">{u.chat_id}</span>
                  <span className="rcp-dot" aria-hidden="true" />
                  <time title={u.created_at ? fmtDateTime(u.created_at) : ''}>joined {agoShort(u.created_at)}</time>
                </div>
              </div>
              <div className="rcp-price" title="Store credit">{fmtNum(u.credit)}<span> T</span></div>
            </div>

            <div className="usr-actions">
              <button onClick={() => editCredit(u)} className="btn btn-secondary">Credit</button>
              <button onClick={() => setArcadeUser(u)} className="btn btn-secondary usr-arcade" title="Arcade: coins / difficulty / daily reset">
                <Icons.gamepad width={15} height={15} /> Arcade
              </button>
              <button onClick={() => toggleBan(u)} className={'btn usr-ban' + (u.banned ? ' unban' : '')}>{u.banned ? 'Unban' : 'Ban'}</button>
            </div>
          </div>
        ))}
      </div>

      {totalPages > 1 && (
        <div className="pagination-bar glass-card usr-pager">
          <span className="usr-pager-info">{total ? start + 1 : 0}–{Math.min(start + pageUsers.length, total)} of {fmtNum(total)}</span>
          <div className="usr-pager-nav">
            <button className="btn btn-secondary" disabled={curPage === 0 || loading} onClick={() => goPage(curPage - 1)}>Prev</button>
            <select className="input-field" value={curPage} onChange={(e) => goPage(Number(e.target.value))} disabled={loading}>
              {Array.from({ length: totalPages }, (_, i) => <option key={i} value={i}>Page {i + 1}</option>)}
            </select>
            <button className="btn btn-secondary" disabled={start + PER_PAGE >= total || loading} onClick={() => goPage(curPage + 1)}>Next</button>
          </div>
        </div>
      )}

      {arcadeUser && <ArcadeModal user={arcadeUser} onClose={() => setArcadeUser(null)} />}
    </>
  );
}

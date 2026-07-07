import React, { useEffect, useRef, useState } from 'react';

import { apiFetch, apiJson, postJson } from '../api.js';
import { useModal } from '../components/Modal.jsx';
import { useToast } from '../components/Toast.jsx';
import { Icons } from '../icons.jsx';
import { parseTs } from '../util.js';

export function VipPage() {
  const modal = useModal();
  const toast = useToast();
  const [vips, setVips] = useState([]);
  const [stats, setStats] = useState({});
  const [query, setQuery] = useState('');
  const [results, setResults] = useState(null);
  const [selected, setSelected] = useState(null);
  const [days, setDays] = useState('');
  const [granting, setGranting] = useState(false);
  const searchTimer = useRef(null);

  const load = async () => {
    try {
      const { data } = await apiJson('/api/admin/vip');
      if (data.ok) { setVips(data.users || []); setStats(data.stats || {}); }
    } catch (_) { /* ignore */ }
  };
  useEffect(() => { load(); }, []);

  function onSearch(v) {
    setQuery(v);
    setSelected(null);
    if (searchTimer.current) clearTimeout(searchTimer.current);
    if (v.trim().length < 2) { setResults(null); return; }
    searchTimer.current = setTimeout(async () => {
      try {
        const { data } = await apiJson(`/api/admin/vip/search?q=${encodeURIComponent(v.trim())}`);
        setResults(data.ok && Array.isArray(data.users) ? data.users : []);
      } catch (_) { setResults([]); }
    }, 300);
  }

  async function grant() {
    if (!selected) return;
    setGranting(true);
    try {
      const { data } = await postJson(`/api/admin/users/${selected.id}/vip`, { days: parseInt(days) || 0 });
      if (data.ok) {
        toast(`${selected.full_name || selected.username} is now VIP`, 'success');
        setSelected(null); setQuery(''); setResults(null); setDays('');
        load();
      } else {
        await modal.alert('Error', data.error || 'Failed to add VIP status');
      }
    } catch (_) {
      await modal.alert('Error', 'Connection failed');
    } finally {
      setGranting(false); // audit fix: was left disabled after failure
    }
  }

  async function extend(u) {
    const val = await modal.prompt('Extend VIP', 'Enter number of days to add:', '30');
    if (val === null) return;
    const n = parseInt(val);
    if (isNaN(n) || n <= 0) { await modal.alert('Invalid', 'Please enter a valid number of days'); return; }
    const { data } = await postJson(`/api/admin/users/${u.id}/vip`, { days: n });
    if (data.ok) { toast(`VIP extended by ${n} days`, 'success'); load(); }
    else await modal.alert('Error', data.error || 'Failed to extend VIP');
  }

  async function remove(u) {
    // audit fix: name passed via data lookup, not an inline-escaped onclick string (no XSS/apostrophe break)
    const ok = await modal.confirm('Remove VIP', `Remove VIP status from ${u.full_name || u.username || 'this user'}?`, { danger: true, okText: 'Remove' });
    if (!ok) return;
    const res = await apiFetch(`/api/admin/users/${u.id}/vip`, { method: 'DELETE' });
    let data = {}; try { data = await res.json(); } catch (_) { data = {}; }
    if (data.ok) { toast('VIP removed', 'success'); load(); }
    else await modal.alert('Error', data.error || 'Failed to remove VIP');
  }

  function vipStatus(u) {
    if (!u.vip_until) return { cls: 'lifetime', text: 'LIFETIME', lifetime: true, date: '∞' };
    const exp = parseTs(u.vip_until);
    const daysLeft = exp ? Math.ceil((exp - new Date()) / 86400000) : null;
    if (daysLeft !== null && daysLeft <= 0) return { cls: 'expiring', text: 'EXPIRED', date: exp.toLocaleDateString() };
    if (daysLeft !== null && daysLeft <= 7) return { cls: 'expiring', text: `${daysLeft}d left`, date: exp.toLocaleDateString() };
    return { cls: 'active', text: `${daysLeft}d left`, date: exp ? exp.toLocaleDateString() : '∞' };
  }

  return (
    <>
      <div className="stats-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 16, marginBottom: 24 }}>
        <div className="glass-card stat-card" style={{ padding: 20 }}><div className="stat-label">Total VIP</div><div className="stat-value">{stats.total_vip || 0}</div></div>
        <div className="glass-card stat-card" style={{ padding: 20 }}><div className="stat-label">Lifetime</div><div className="stat-value">{stats.lifetime_vip || 0}</div></div>
        <div className="glass-card stat-card" style={{ padding: 20 }}><div className="stat-label">Expiring Soon</div><div className="stat-value" style={{ color: 'var(--warning)' }}>{stats.expiring_soon || 0}</div></div>
      </div>

      <div className="glass-card" style={{ padding: 20, marginBottom: 24 }}>
        <h3 style={{ marginTop: 0, fontSize: 15 }}>Grant VIP</h3>
        <div style={{ position: 'relative' }}>
          <input className="input-field" placeholder="Search user by name / username / ID…" value={query} onChange={(e) => onSearch(e.target.value)} />
          {results && (
            <div style={{ position: 'absolute', left: 0, right: 0, top: '100%', zIndex: 20, marginTop: 6, background: 'var(--panel-2)', border: '1px solid var(--border-subtle)', borderRadius: 12, overflow: 'hidden' }}>
              {results.length === 0 && <div style={{ padding: 16, textAlign: 'center', color: 'var(--text-muted)' }}>No users found</div>}
              {results.map((u) => (
                <div key={u.id} className="vip-search-item" style={{ padding: 12, cursor: 'pointer', display: 'flex', justifyContent: 'space-between' }}
                  onClick={() => { setSelected(u); setQuery(u.full_name || u.username || `ID: ${u.chat_id}`); setResults(null); }}>
                  <div><div style={{ fontWeight: 600 }}>{u.full_name || u.username || 'Unknown'}</div><div style={{ fontSize: 12, color: 'var(--text-muted)' }}>@{u.username || 'N/A'} • {u.chat_id}</div></div>
                  {u.is_vip && <span className="vip-badge active">VIP</span>}
                </div>
              ))}
            </div>
          )}
        </div>
        <div style={{ display: 'flex', gap: 10, marginTop: 12 }}>
          <input className="input-field" type="number" placeholder="Days (0 = lifetime)" value={days} onChange={(e) => setDays(e.target.value)} style={{ maxWidth: 200 }} />
          <button className="btn btn-primary" disabled={!selected || granting} onClick={grant}>{granting ? 'Adding…' : 'Grant VIP'}</button>
        </div>
      </div>

      <div className="glass-card" style={{ padding: 0 }}>
        <div className="table-responsive">
          <table>
            <thead><tr><th>User</th><th>Chat ID</th><th>Status</th><th>Expires</th><th>Actions</th></tr></thead>
            <tbody>
              {vips.length === 0 && <tr><td colSpan={5} style={{ textAlign: 'center', color: 'var(--text-muted)', padding: 32 }}>No VIP users yet</td></tr>}
              {vips.map((u) => {
                const st = vipStatus(u);
                return (
                  <tr key={u.id}>
                    <td>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                        <div style={{ width: 36, height: 36, borderRadius: '50%', background: 'var(--bg-card)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 700, border: '1px solid var(--border-subtle)' }}>{(u.full_name || u.username || 'U').charAt(0).toUpperCase()}</div>
                        <div><div style={{ fontWeight: 600 }}>{u.full_name || u.username || 'Unknown'}</div><div style={{ fontSize: 12, color: 'var(--text-muted)' }}>@{u.username || 'N/A'}</div></div>
                      </div>
                    </td>
                    <td style={{ fontFamily: 'monospace', fontSize: 13 }}>{u.chat_id}</td>
                    <td><span className={'vip-status ' + st.cls} style={{ display: 'inline-flex', alignItems: 'center', gap: 5 }}>{st.lifetime && <span className="fx-star"><Icons.star width={12} height={12} /></span>}{st.text}</span></td>
                    <td style={{ fontSize: 13, color: 'var(--text-muted)' }}>{st.date}</td>
                    <td>
                      <div style={{ display: 'flex', gap: 8 }}>
                        <button className="btn btn-secondary" style={{ padding: '6px 10px' }} onClick={() => extend(u)}>Extend</button>
                        <button className="btn btn-secondary" style={{ padding: '6px 10px', color: 'var(--danger)' }} onClick={() => remove(u)}>Remove</button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}

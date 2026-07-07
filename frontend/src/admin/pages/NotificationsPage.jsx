import React, { useEffect, useMemo, useState } from 'react';

import { apiJson, postJson } from '../api.js';
import { useModal } from '../components/Modal.jsx';
import { useToast } from '../components/Toast.jsx';
import { fmtDateTime } from '../util.js';

export function NotificationsPage() {
  const modal = useModal();
  const toast = useToast();
  const [title, setTitle] = useState('');
  const [message, setMessage] = useState('');
  const [target, setTarget] = useState('all');
  const [toWebApp, setToWebApp] = useState(true);
  const [toBot, setToBot] = useState(false);
  const [users, setUsers] = useState([]);
  const [selectedIds, setSelectedIds] = useState(() => new Set());
  const [userQuery, setUserQuery] = useState('');
  const [broadcasts, setBroadcasts] = useState([]);
  const [busy, setBusy] = useState(false);

  const loadBroadcasts = async () => {
    try {
      const { data } = await apiJson('/api/admin/notifications/broadcasts/recent');
      if (data.ok) setBroadcasts(data.broadcasts || []);
    } catch (_) { /* ignore */ }
  };
  useEffect(() => { loadBroadcasts(); }, []);

  // Audit fix (JS#9): legacy fetched /api/admin/users with the default limit=20
  // so "specific users" could only ever target the 20 newest. Request 1000.
  async function loadUsersForPicker() {
    if (users.length) return;
    try {
      const { data } = await apiJson('/api/admin/users?limit=1000');
      setUsers(data.users || []);
    } catch (_) { /* ignore */ }
  }

  function pickTarget(t) {
    setTarget(t);
    if (t === 'specific') loadUsersForPicker();
  }

  const filteredUsers = useMemo(() => {
    const query = userQuery.trim().toLowerCase();
    if (!query) return users;
    return users.filter((u) => (u.full_name || '').toLowerCase().includes(query) || (u.username || '').toLowerCase().includes(query) || String(u.chat_id || '').includes(query));
  }, [users, userQuery]);

  function toggleUser(id) {
    setSelectedIds((prev) => {
      const n = new Set(prev);
      if (n.has(id)) n.delete(id); else n.add(id);
      return n;
    });
  }

  async function send(e) {
    e.preventDefault();
    if (!title) return modal.alert('Missing Title', 'Please enter a title for your broadcast.');
    if (!message) return modal.alert('Missing Message', 'Please enter a message for your broadcast.');
    if (!toWebApp && !toBot) return modal.alert('No Channel Selected', 'Select at least one channel (Dashboard or Telegram).');
    if (target === 'specific' && selectedIds.size === 0) return modal.alert('No Users Selected', 'Select at least one user to send to.');
    setBusy(true);
    try {
      const { data } = await postJson('/api/admin/notifications/send', {
        title, message, target, user_ids: [...selectedIds].map(String), send_to_webapp: toWebApp, send_to_bot: toBot,
      });
      if (data.ok) {
        toast('Broadcast sent', 'success');
        setTitle(''); setMessage(''); setSelectedIds(new Set()); setTarget('all'); setToWebApp(true); setToBot(false);
        loadBroadcasts();
      } else {
        await modal.alert('Error', data.error || 'Failed to send broadcast.');
      }
    } catch (_) {
      await modal.alert('Connection Error', 'Could not reach server. Please try again.');
    } finally { setBusy(false); }
  }

  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1fr) minmax(0, 360px)', gap: 20, alignItems: 'start' }}>
      <form className="glass-card" style={{ padding: 20 }} onSubmit={send}>
        <h3 style={{ marginTop: 0, fontSize: 15 }}>New Broadcast</h3>
        <input className="input-field" placeholder="Title" value={title} onChange={(e) => setTitle(e.target.value)} style={{ marginBottom: 12 }} />
        <textarea className="input-field" placeholder="Message" value={message} onChange={(e) => setMessage(e.target.value)} style={{ marginBottom: 12, minHeight: 120 }} />

        <div style={{ display: 'flex', gap: 10, marginBottom: 12, flexWrap: 'wrap' }}>
          <label style={{ display: 'flex', gap: 6, alignItems: 'center' }}><input type="checkbox" checked={toWebApp} onChange={(e) => setToWebApp(e.target.checked)} /> Dashboard</label>
          <label style={{ display: 'flex', gap: 6, alignItems: 'center' }}><input type="checkbox" checked={toBot} onChange={(e) => setToBot(e.target.checked)} /> Telegram</label>
        </div>

        <div style={{ display: 'flex', gap: 10, marginBottom: 12 }}>
          <button type="button" className={'btn ' + (target === 'all' ? 'btn-primary' : 'btn-secondary')} onClick={() => pickTarget('all')}>All users</button>
          <button type="button" className={'btn ' + (target === 'specific' ? 'btn-primary' : 'btn-secondary')} onClick={() => pickTarget('specific')}>Specific</button>
        </div>

        {target === 'specific' && (
          <div style={{ marginBottom: 12 }}>
            <input className="input-field" placeholder="Filter users…" value={userQuery} onChange={(e) => setUserQuery(e.target.value)} style={{ marginBottom: 8 }} />
            <div style={{ maxHeight: 220, overflow: 'auto', border: '1px solid var(--border-subtle)', borderRadius: 10, padding: 8 }}>
              {filteredUsers.map((u) => (
                <label key={u.id} className="user-list-item" style={{ display: 'flex', gap: 8, alignItems: 'center', padding: '6px 4px' }}>
                  <input type="checkbox" checked={selectedIds.has(u.id)} onChange={() => toggleUser(u.id)} />
                  <span>{u.full_name || u.username || u.chat_id}</span>
                </label>
              ))}
              {filteredUsers.length === 0 && <div style={{ color: 'var(--text-muted)', padding: 8 }}>No users</div>}
            </div>
            <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 6 }}>{selectedIds.size} selected</div>
          </div>
        )}

        <button type="submit" className="btn btn-primary" disabled={busy} style={{ width: '100%' }}>{busy ? 'Sending…' : 'Send Broadcast'}</button>
      </form>

      <div className="glass-card" style={{ padding: 20 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
          <h3 style={{ margin: 0, fontSize: 15 }}>Recent</h3>
          <button className="refresh-btn" onClick={loadBroadcasts} title="Refresh">⟳</button>
        </div>
        {broadcasts.length === 0 && <div style={{ color: 'var(--text-muted)' }}>No broadcasts yet</div>}
        {broadcasts.map((b, i) => (
          <div key={i} className="broadcast-item" style={{ padding: '10px 0', borderBottom: '1px solid var(--divider, rgba(255,255,255,0.06))' }}>
            <div style={{ fontWeight: 600 }}>{b.title}</div>
            <div style={{ fontSize: 13, color: 'var(--text-muted)', margin: '4px 0' }}>{b.message}</div>
            <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>{fmtDateTime(b.last_sent)} · {b.recipient_count} users</div>
          </div>
        ))}
      </div>
    </div>
  );
}

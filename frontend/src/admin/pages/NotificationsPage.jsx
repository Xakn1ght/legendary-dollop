import React, { useEffect, useMemo, useState } from 'react';

import { apiJson, postJson } from '../api.js';
import { useModal } from '../components/Modal.jsx';
import { useToast } from '../components/Toast.jsx';
import { Icons } from '../icons.jsx';
import { fmtDateTime } from '../util.js';

function Check({ on }) {
  return (
    <span className={'bc-check' + (on ? ' on' : '')} aria-hidden="true">
      {on && <Icons.check width={11} height={11} />}
    </span>
  );
}

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

    // Guard the send: one tap used to DM every user with no way back.
    const channels = [toWebApp && 'Dashboard', toBot && 'Telegram'].filter(Boolean).join(' and ');
    let audience = 'all users';
    if (target === 'specific') {
      if (selectedIds.size === 1) {
        const only = users.find((u) => selectedIds.has(u.id));
        audience = only ? (only.full_name || only.username || String(only.chat_id)) : '1 selected user';
      } else {
        audience = `${selectedIds.size} selected users`;
      }
    }
    const ok = await modal.confirm(
      'Send broadcast',
      `This will send the message to ${audience} via ${channels}. This cannot be undone.`,
      { okText: 'Send', danger: true },
    );
    if (!ok) return;

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
    <div className="page-two-col aside-right">
      <form className="glass-card bc-form" onSubmit={send}>
        <h3 className="bc-h">New Broadcast</h3>
        <input className="input-field" placeholder="Title" value={title} onChange={(e) => setTitle(e.target.value)} style={{ marginBottom: 12 }} />
        <textarea className="input-field" placeholder="Message" value={message} onChange={(e) => setMessage(e.target.value)} style={{ marginBottom: 12, minHeight: 120 }} />

        <div className="bc-label">Send via</div>
        <div className="bc-chips">
          <button type="button" className={'bc-chip' + (toWebApp ? ' on' : '')} aria-pressed={toWebApp} onClick={() => setToWebApp((v) => !v)}>
            <Check on={toWebApp} /> Dashboard
          </button>
          <button type="button" className={'bc-chip' + (toBot ? ' on' : '')} aria-pressed={toBot} onClick={() => setToBot((v) => !v)}>
            <Check on={toBot} /> Telegram
          </button>
        </div>

        <div className="bc-label">Audience</div>
        <div className="bc-chips">
          <button type="button" className={'bc-chip' + (target === 'all' ? ' on' : '')} aria-pressed={target === 'all'} onClick={() => pickTarget('all')}>All users</button>
          <button type="button" className={'bc-chip' + (target === 'specific' ? ' on' : '')} aria-pressed={target === 'specific'} onClick={() => pickTarget('specific')}>
            Specific{selectedIds.size > 0 ? ` · ${selectedIds.size}` : ''}
          </button>
        </div>

        {target === 'specific' && (
          <div className="bc-picker">
            <input className="input-field" placeholder="Filter users…" value={userQuery} onChange={(e) => setUserQuery(e.target.value)} />
            <div className="bc-picker-tools">
              <span className="bc-count">{selectedIds.size} selected</span>
              <button type="button" className="chip-btn" onClick={() => setSelectedIds(new Set([...selectedIds, ...filteredUsers.map((u) => u.id)]))}>
                Select shown
              </button>
              <button type="button" className="chip-btn" disabled={!selectedIds.size} onClick={() => setSelectedIds(new Set())}>Clear</button>
            </div>
            <div className="bc-user-list">
              {users.length === 0 && <div className="bc-empty">Loading users…</div>}
              {users.length > 0 && filteredUsers.length === 0 && <div className="bc-empty">No users match</div>}
              {filteredUsers.map((u) => {
                const on = selectedIds.has(u.id);
                return (
                  <button type="button" key={u.id} className={'bc-user' + (on ? ' on' : '')} role="checkbox" aria-checked={on} onClick={() => toggleUser(u.id)}>
                    <Check on={on} />
                    <span className="bc-user-name"><bdi>{u.full_name || u.username || u.chat_id}</bdi></span>
                    {u.username && <span className="bc-user-handle">@{u.username}</span>}
                  </button>
                );
              })}
            </div>
          </div>
        )}

        <button type="submit" className="btn btn-primary bc-send" disabled={busy}>{busy ? 'Sending…' : 'Send Broadcast'}</button>
      </form>

      <div className="glass-card bc-recent">
        <div className="bc-recent-head">
          <h3 className="bc-h">Recent</h3>
          <button className="refresh-btn" type="button" onClick={loadBroadcasts} title="Refresh">
            <Icons.refresh width={15} height={15} />
          </button>
        </div>
        {broadcasts.length === 0 && <div className="bc-empty">No broadcasts yet</div>}
        {broadcasts.map((b, i) => (
          <div key={i} className="bc-item">
            <div className="bc-item-title"><bdi>{b.title}</bdi></div>
            <div className="bc-item-msg" dir="auto">{b.message}</div>
            <div className="bc-item-meta">{fmtDateTime(b.last_sent)} · {b.recipient_count} users</div>
          </div>
        ))}
      </div>
    </div>
  );
}

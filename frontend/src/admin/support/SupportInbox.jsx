import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { apiFetch, apiJson, verifySession } from '../api.js';
import { useModal } from '../components/Modal.jsx';
import { useToast } from '../components/Toast.jsx';
import { Icons } from '../icons.jsx';
import { fmtDateTime, parseTs, timeAgo } from '../util.js';
import { createAdminSupportRealtime } from './realtime.js';

let seq = 0;
const nextKey = () => 'm' + (++seq) + '-' + Date.now();
const STATUS = { open: 'var(--success)', pending: 'var(--warning)', closed: 'var(--muted)', archived: 'var(--muted2)' };

const CANNED_KEY = 'admin_canned_replies';
const CANNED_DEFAULTS = [
  'سلام! ممنون از پیام شما. در حال بررسی هستیم و به‌زودی پاسخ می‌دهیم. 🙏',
  'مشکل شما بررسی و برطرف شد. لطفاً دوباره امتحان کنید و اگر مشکلی بود خبر بدهید.',
  'لطفاً یک اسکرین‌شات از خطا بفرستید تا دقیق‌تر بررسی کنیم.',
  'لطفاً یک‌بار کانفیگ را حذف و دوباره از داشبورد دریافت کنید.',
];

function loadCanned() {
  try {
    const raw = JSON.parse(localStorage.getItem(CANNED_KEY) || 'null');
    if (Array.isArray(raw) && raw.length) return raw;
  } catch (_) { /* ignore */ }
  return CANNED_DEFAULTS;
}

function sortTickets(list) {
  // VIP (priority=high) OPEN tickets pin to the top; within each band, newest first.
  const rank = (t) => (t.priority === 'high' && t.status !== 'closed' && t.status !== 'archived' ? 0 : 1);
  return [...list].sort((a, b) => (rank(a) - rank(b))
    || (parseTs(b.updated_at || b.created_at)?.getTime() || 0) - (parseTs(a.updated_at || a.created_at)?.getTime() || 0));
}

const tShort = (v) => {
  const d = parseTs(v);
  return d ? d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '';
};
const dayKey = (v) => {
  const d = parseTs(v);
  return d ? d.toDateString() : '';
};
const dayLabel = (v) => {
  const d = parseTs(v);
  if (!d) return '';
  const today = new Date(); const yest = new Date(Date.now() - 86400e3);
  if (d.toDateString() === today.toDateString()) return 'Today';
  if (d.toDateString() === yest.toDateString()) return 'Yesterday';
  return d.toLocaleDateString([], { month: 'short', day: 'numeric' });
};

export function SupportInbox() {
  const modal = useModal();
  const toast = useToast();
  const [tickets, setTickets] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('all');
  const [q, setQ] = useState('');
  const [selected, setSelected] = useState(null);
  const [messages, setMessages] = useState([]);
  const [msgLoading, setMsgLoading] = useState(false);
  const [draft, setDraft] = useState('');
  const [sending, setSending] = useState(false);
  const [canned, setCanned] = useState(loadCanned);
  const [cannedOpen, setCannedOpen] = useState(false);
  const [ctxUser, setCtxUser] = useState(null);      // user-context sidebar data
  const [ctxOpen, setCtxOpen] = useState(false);     // mobile drawer toggle

  const [userTyping, setUserTyping] = useState(false);
  const [lightbox, setLightbox] = useState(null);

  const selRef = useRef(null); selRef.current = selected;
  const rtRef = useRef(null);
  const threadRef = useRef(null);
  const pendingRef = useRef(new Map());
  const typingHideRef = useRef(0);
  const typingEmitRef = useRef(0);
  const ctxRef = useRef(null);
  const dragRef = useRef(null);

  const loadTickets = useCallback(async (skeleton = true) => {
    if (skeleton) setLoading(true);
    try {
      const { data } = await apiJson('/api/admin/tickets');
      if (data.ok) setTickets(sortTickets(data.tickets || []));
    } catch (_) { /* ignore */ } finally { setLoading(false); }
  }, []);

  const toState = (list) => (list || []).map((m) => ({
    key: nextKey(), from_admin: !!m.from_admin, message: m.message || m.text || '',
    created_at: m.created_at, content_type: m.content_type, file_name: m.file_name,
  }));

  const openTicket = useCallback(async (id) => {
    setMsgLoading(true);
    try {
      const { data } = await apiJson(`/api/admin/tickets/${id}`);
      if (data.ok && data.ticket) {
        setSelected(data.ticket); selRef.current = data.ticket;
        setMessages(toState(data.ticket.messages));
        setTickets((cur) => cur.map((t) => (t.id === id ? { ...t, unread_count: 0 } : t)));
        rtRef.current?.watchTicket(id);
        // user-context sidebar: everything about this customer beside the chat
        setCtxUser(null);
        if (data.ticket.user_id) {
          apiJson(`/api/admin/users/${data.ticket.user_id}`)
            .then(({ data: u }) => { if (u.ok && u.user) setCtxUser(u.user); })
            .catch(() => { /* sidebar is best-effort */ });
        }
      } else toast('Failed to load ticket', 'error');
    } catch (_) { toast('Failed to load ticket', 'error'); } finally { setMsgLoading(false); }
  }, [toast]);

  const pollMessages = useCallback(async (id) => {
    if (!selRef.current || selRef.current.id !== id) return;
    const { data } = await apiJson(`/api/admin/tickets/${id}`);
    if (data.ok && data.ticket) {
      const msgs = data.ticket.messages || [];
      setMessages((cur) => (msgs.length <= cur.length ? cur : [...cur, ...toState(msgs.slice(cur.length))]));
    }
  }, []);

  const onEvent = useCallback((data) => {
    if (data.type === 'new_message') {
      const id = data.ticket_id; const p = data.data || {};
      const isPhoto = p.content_type === 'photo';
      const text = isPhoto ? 'Photo' : (p.text || '');
      const viewing = selRef.current && id === selRef.current.id;
      setTickets((cur) => {
        const i = cur.findIndex((x) => x.id === id);
        if (i < 0) { loadTickets(false); return cur; }
        const upd = { ...cur[i], last_message: text, updated_at: p.created_at || cur[i].updated_at };
        if (p.sender === 'user') upd.unread_count = viewing ? 0 : (Number(upd.unread_count) || 0) + 1;
        const next = [...cur]; next.splice(i, 1); return [upd, ...next];
      });
      if (viewing) {
        if (p.sender === 'user') { setUserTyping(false); clearTimeout(typingHideRef.current); }
        let handled = false;
        if (p.sender === 'admin' && !isPhoto) {
          const key = String(id) + '|' + String(text);
          const pend = pendingRef.current.get(key);
          if (pend && pend.expiresAt > Date.now()) {
            handled = true; pendingRef.current.delete(key);
            setMessages((cur) => cur.map((m) => (m.key === pend.key ? { ...m, pending: false, created_at: p.created_at || m.created_at } : m)));
          }
        }
        if (p.sender === 'admin' && isPhoto) {
          // Our own upload echoes back over the WS — adopt the optimistic
          // bubble instead of appending a second copy of the same photo.
          handled = true;
          setMessages((cur) => {
            const ri = [...cur].reverse().findIndex((m) => m.from_admin && m.content_type === 'photo'
              && (m.uploadPending || (p.file_name && m.file_name === p.file_name) || (!m.file_name && m.local_url)));
            if (ri < 0) {
              return [...cur, { key: nextKey(), from_admin: true, message: '', created_at: p.created_at, content_type: 'photo', file_name: p.file_name }];
            }
            const idx = cur.length - 1 - ri;
            return cur.map((m, i) => (i === idx
              ? { ...m, uploadPending: false, file_name: p.file_name || m.file_name, created_at: p.created_at || m.created_at }
              : m));
          });
        }
        if (!handled) {
          setMessages((cur) => [...cur, { key: nextKey(), from_admin: p.sender === 'admin', message: isPhoto ? '' : text, created_at: p.created_at, content_type: p.content_type, file_name: p.file_name }]);
        }
      }
    } else if (data.type === 'typing') {
      // typing contract from the user lane: {type:'typing', ticket_id, from:'user'}
      if (data.from === 'user' && selRef.current && data.ticket_id === selRef.current.id) {
        setUserTyping(true);
        clearTimeout(typingHideRef.current);
        typingHideRef.current = setTimeout(() => setUserTyping(false), 4000);
      }
    } else if (data.type === 'tickets_updated') {
      loadTickets(false);
    } else if (data.type === 'status_change') {
      const id = data.ticket_id; const p = data.data || {};
      setTickets((cur) => cur.map((t) => (t.id === id ? { ...t, status: p.status || t.status } : t)));
      if (selRef.current && id === selRef.current.id) setSelected((c) => (c ? { ...c, status: p.status || c.status } : c));
    }
  }, [loadTickets]);

  useEffect(() => {
    (async () => { await verifySession(); await loadTickets(); })();
    const rt = createAdminSupportRealtime({ onEvent, pollTickets: () => loadTickets(false), pollMessages });
    rtRef.current = rt; rt.connect();
    return () => rt.destroy();
  }, [onEvent, loadTickets, pollMessages]);

  useEffect(() => {
    if (threadRef.current) threadRef.current.scrollTop = threadRef.current.scrollHeight;
  }, [messages]);

  // photos finish loading after the auto-scroll above — nudge back to bottom
  const onPhotoLoad = useCallback(() => {
    const el = threadRef.current;
    if (!el) return;
    const nearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 480;
    if (nearBottom) el.scrollTop = el.scrollHeight;
  }, []);

  // keyboard open/close resizes the visual viewport (tracked as --app-vh by
  // admin-fx) — keep the conversation pinned to the newest message through it
  useEffect(() => {
    const vv = window.visualViewport;
    if (!vv) return undefined;
    const onResize = () => {
      const el = threadRef.current;
      if (!el) return;
      const nearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 320;
      if (nearBottom) requestAnimationFrame(() => { el.scrollTop = el.scrollHeight; });
    };
    vv.addEventListener('resize', onResize, { passive: true });
    return () => vv.removeEventListener('resize', onResize);
  }, []);

  const view = useMemo(() => {
    let out = tickets;
    // Archived chats live ONLY in their own tab — archiving moves a ticket
    // out of the working inbox instead of lingering under All/Closed.
    if (filter === 'archived') out = out.filter((t) => t.status === 'archived');
    else if (filter === 'open') out = out.filter((t) => t.status === 'open' || t.status === 'pending');
    else if (filter === 'closed') out = out.filter((t) => t.status === 'closed');
    else out = out.filter((t) => t.status !== 'archived');
    const query = q.trim().toLowerCase();
    if (query) out = out.filter((t) => [t.user_name, t.subject, t.last_message, String(t.user_ticket_number || t.id)].filter(Boolean).join(' ').toLowerCase().includes(query));
    return out;
  }, [tickets, filter, q]);

  async function send() {
    const msg = draft.trim();
    const ticket = selRef.current;
    if (!msg || !ticket) return;
    if (ticket.status === 'closed' || ticket.status === 'archived') { toast('This ticket is closed', 'error'); return; }
    setSending(true);
    const key = nextKey();
    setMessages((cur) => [...cur, { key, from_admin: true, message: msg, created_at: null, pending: true }]);
    pendingRef.current.set(String(ticket.id) + '|' + msg, { key, expiresAt: Date.now() + 15000 });
    setDraft('');
    try {
      const res = await apiFetch(`/api/admin/tickets/${ticket.id}/reply`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ message: msg }) });
      let data = {}; try { data = await res.json(); } catch (_) { data = {}; }
      if (res.ok && data.ok) {
        setMessages((cur) => cur.map((m) => (m.key === key ? { ...m, pending: false, created_at: m.created_at || new Date().toISOString() } : m)));
        setTickets((cur) => sortTickets(cur.map((t) => (t.id === ticket.id ? { ...t, last_message: msg, updated_at: new Date().toISOString() } : t))));
      } else {
        // audit fix: any non-ok (not just ticket_closed) surfaces + restores the draft
        const closed = data.error === 'ticket_closed';
        toast(closed ? 'This ticket is closed' : 'Failed to send reply', 'error');
        setMessages((cur) => cur.filter((m) => m.key !== key));
        setDraft(msg);
      }
    } catch (_) {
      toast('Failed to send reply', 'error');
      setMessages((cur) => cur.filter((m) => m.key !== key));
      setDraft(msg);
    } finally { setSending(false); }
  }

  async function sendPhoto(file) {
    const ticket = selRef.current;
    if (!ticket || !file) return;
    if (file.size > 8 * 1024 * 1024) { toast('Photo too large (max 8MB)', 'error'); return; }
    const local = URL.createObjectURL(file);
    const key = nextKey();
    setMessages((cur) => [...cur, { key, from_admin: true, message: '', created_at: new Date().toISOString(), content_type: 'photo', local_url: local, uploadPending: true }]);
    try {
      const fd = new FormData();
      fd.append('photo', file, file.name || 'photo.jpg');
      const res = await apiFetch(`/api/admin/tickets/${ticket.id}/photo`, { method: 'POST', body: fd });
      let data = {}; try { data = await res.json(); } catch (_) { data = {}; }
      if (!data.ok) throw new Error('upload_failed');
      setMessages((cur) => cur.map((m) => (m.key === key ? { ...m, uploadPending: false, file_name: data.file_name || '' } : m)));
    } catch (_) {
      toast('Photo failed to send', 'error');
      setMessages((cur) => cur.filter((m) => m.key !== key));
    }
  }

  async function action(kind) {
    const ticket = selRef.current;
    if (!ticket) return;
    if (kind === 'delete') {
      const ok = await modal.confirm('Delete ticket', 'Permanently delete this ticket and its messages?', { danger: true, okText: 'Delete' });
      if (!ok) return;
      const res = await apiFetch(`/api/admin/tickets/${ticket.id}`, { method: 'DELETE' });
      let data = {}; try { data = await res.json(); } catch (_) { data = {}; }
      if (data.ok) { toast('Ticket deleted', 'success'); setTickets((c) => c.filter((t) => t.id !== ticket.id)); setSelected(null); }
      else toast('Failed to delete', 'error');
      return;
    }
    const res = await apiFetch(`/api/admin/tickets/${ticket.id}/${kind}`, { method: 'POST' });
    let data = {}; try { data = await res.json(); } catch (_) { data = {}; }
    if (res.ok && data.ok !== false) {
      const nextStatus = kind === 'close' ? 'closed' : kind === 'archive' ? 'archived' : 'open';
      toast(`Ticket ${nextStatus}`, 'success');
      setSelected((c) => (c ? { ...c, status: nextStatus } : c));
      setTickets((c) => c.map((t) => (t.id === ticket.id ? { ...t, status: nextStatus } : t)));
    } else toast(`Failed to ${kind}`, 'error');
  }

  const photoUrl = (m) => m.local_url || `/api/admin/tickets/${selected.id}/photo/${encodeURIComponent(m.file_name || '')}`;
  const isClosed = selected && (selected.status === 'closed' || selected.status === 'archived');

  function goBack() {
    rtRef.current?.unwatchTicket();
    setSelected(null); selRef.current = null;
    setMessages([]); setUserTyping(false); setCtxOpen(false); setCannedOpen(false);
  }

  // Swipe-right-to-dismiss for the customer drawer (touch). Horizontal-intent
  // gate so the services list still scrolls vertically inside it.
  function ctxPointerDown(e) {
    if (!ctxOpen || e.pointerType === 'mouse') return;
    dragRef.current = { x: e.clientX, y: e.clientY, t: Date.now(), active: false, id: e.pointerId };
  }
  function ctxPointerMove(e) {
    const d = dragRef.current;
    const el = ctxRef.current;
    if (!d || !el || e.pointerId !== d.id) return;
    const dx = e.clientX - d.x;
    const dy = e.clientY - d.y;
    if (!d.active) {
      if (Math.abs(dx) < 14 || Math.abs(dx) < Math.abs(dy) * 1.4) return;
      d.active = true;
      try { el.setPointerCapture(e.pointerId); } catch (_) { /* ignore */ }
      el.style.transition = 'none';
    }
    el.style.transform = `translateX(${Math.max(0, dx)}px)`;
  }
  function ctxPointerUp(e) {
    const d = dragRef.current;
    const el = ctxRef.current;
    dragRef.current = null;
    if (!d || !el) return;
    el.style.transition = '';
    if (!d.active) return;
    const dx = Math.max(0, e.clientX - d.x);
    const vel = dx / Math.max(1, Date.now() - d.t); // px per ms
    el.style.transform = '';
    if (dx > el.offsetWidth * 0.35 || vel > 0.5) setCtxOpen(false);
  }

  function insertCanned(text) {
    setDraft((d) => (d ? d + '\n' + text : text));
    setCannedOpen(false);
  }

  function addCanned() {
    const text = window.prompt('New canned reply:');
    if (!text || !text.trim()) return;
    const next = [...canned, text.trim()];
    setCanned(next);
    try { localStorage.setItem(CANNED_KEY, JSON.stringify(next)); } catch (_) { /* ignore */ }
  }

  function removeCanned(i) {
    const next = canned.filter((_, j) => j !== i);
    setCanned(next.length ? next : CANNED_DEFAULTS);
    try { localStorage.setItem(CANNED_KEY, JSON.stringify(next.length ? next : CANNED_DEFAULTS)); } catch (_) { /* ignore */ }
  }

  return (
    <div className={'sup-inbox' + (selected ? ' chat-open' : '') + (ctxOpen ? ' ctx-open' : '')}>
      <aside className="sup-list glass-card">
        <div className="sup-list-head">
          <a className="btn btn-secondary sup-home" href="/admin/dashboard" aria-label="Back to panel">‹ Panel</a>
          <div>
            <div className="sup-title">Support</div>
            <div className="sup-sub">{tickets.reduce((s, t) => s + (t.unread_count || 0), 0)} unread · {tickets.length} total</div>
          </div>
        </div>
        <div className="sup-search">
          <Icons.search width={16} height={16} />
          <input placeholder="Search tickets…" value={q} onChange={(e) => setQ(e.target.value)} />
        </div>
        <div className="sup-filters">
          {['all', 'open', 'closed', 'archived'].map((f) => (
            <button key={f} className={'sup-filter' + (filter === f ? ' active' : '')} onClick={() => setFilter(f)}>{f[0].toUpperCase() + f.slice(1)}</button>
          ))}
        </div>
        <div className="sup-rows">
          {loading && Array.from({ length: 5 }).map((_, i) => <div key={i} className="sup-row-skel" />)}
          {!loading && view.length === 0 && <div className="sup-empty">No tickets</div>}
          {!loading && view.map((t) => (
            <button key={t.id} className={'sup-row' + (selected?.id === t.id ? ' active' : '')} onClick={() => openTicket(t.id)}>
              <div className="sup-row-avatar">{(t.user_name || 'U').charAt(0).toUpperCase()}</div>
              <div className="sup-row-main">
                <div className="sup-row-top">
                  <span className="sup-row-name">
                    {t.user_name || 'User'}
                    {t.priority === 'high' && <span className="sup-vip-chip" title="VIP customer"><Icons.crown width={11} height={11} /> VIP</span>}
                  </span>
                  <span className="sup-row-time">{timeAgo(t.updated_at || t.created_at)}</span>
                </div>
                <div className="sup-row-bottom">
                  <span className="sup-row-msg">{t.last_message || t.subject || '—'}</span>
                  {t.unread_count > 0 && <span className="sup-row-badge">{t.unread_count}</span>}
                </div>
              </div>
              <span className="sup-row-status" style={{ background: STATUS[t.status] || 'var(--muted)' }} />
            </button>
          ))}
        </div>
      </aside>

      <section className="sup-chat glass-card">
        {!selected && (
          <div className="sup-chat-empty">
            <Icons.support width={40} height={40} />
            <div>Select a ticket to view the conversation</div>
          </div>
        )}
        {selected && (
          <>
            <header className="sup-chat-head">
              <button className="sup-back" onClick={goBack} aria-label="Back to tickets">
                <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"><path d="M15 18l-6-6 6-6" /></svg>
              </button>
              <div className="sup-row-avatar sup-chat-avatar">{(selected.user_name || 'U').charAt(0).toUpperCase()}</div>
              <div className="sup-chat-id">
                <div className="sup-chat-title">
                  {selected.user_name || 'User'}
                  {selected.priority === 'high' && <span className="sup-vip-chip" title="VIP customer"><Icons.crown width={11} height={11} /> VIP</span>}
                  {' '}<span className="sup-chat-num">#{selected.user_ticket_number || selected.id}</span>
                </div>
                <div className="sup-chat-meta">
                  <span className="sup-chat-status" style={{ color: STATUS[selected.status] }}>{(selected.status || 'open').toUpperCase()}</span>
                  {selected.category && <span> · {selected.category}</span>}
                  {selected.subscription_username && <span className="sup-chat-svc"> · {selected.subscription_username}</span>}
                </div>
              </div>
              <div className="sup-chat-actions">
                <button className="sup-hbtn sup-ctx-toggle" onClick={() => setCtxOpen((v) => !v)} title="Customer info">
                  <Icons.users width={16} height={16} />
                </button>
                {isClosed
                  ? <button className="sup-hbtn" title="Reopen ticket" onClick={() => action('reopen')}>
                      <Icons.refresh width={16} height={16} /><span>Reopen</span>
                    </button>
                  : <button className="sup-hbtn" title="Close ticket" onClick={() => action('close')}>
                      <Icons.check width={16} height={16} /><span>Close</span>
                    </button>}
                <button className="sup-hbtn" title="Archive" onClick={() => action('archive')}>
                  <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="21 8 21 21 3 21 3 8" /><rect x="1" y="3" width="22" height="5" /><line x1="10" y1="12" x2="14" y2="12" /></svg>
                </button>
                <button className="sup-hbtn danger" title="Delete ticket" onClick={() => action('delete')}>
                  <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="3 6 5 6 21 6" /><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" /></svg>
                </button>
              </div>
            </header>

            <div className="sup-thread" ref={threadRef}>
              {msgLoading && <div className="sup-empty">Loading…</div>}
              {!msgLoading && messages.length === 0 && <div className="sup-empty">No messages yet</div>}
              {!msgLoading && messages.map((m, i) => {
                const prev = messages[i - 1];
                const newDay = !prev || dayKey(prev.created_at) !== dayKey(m.created_at);
                const grouped = !newDay && prev && prev.from_admin === m.from_admin && !prev.content_type && !m.content_type;
                return (
                  <React.Fragment key={m.key}>
                    {newDay && m.created_at && <div className="sup-day"><span>{dayLabel(m.created_at)}</span></div>}
                    <div className={'sup-bubble ' + (m.from_admin ? 'admin' : 'user') + (grouped ? ' grouped' : '') + (m.content_type === 'photo' ? ' has-photo' : '')}>
                      {m.content_type === 'photo'
                        ? (
                          <button type="button" className="sup-photo-btn" onClick={() => setLightbox(photoUrl(m))}>
                            <img className="sup-photo" src={photoUrl(m)} alt="attachment" loading="lazy" onLoad={onPhotoLoad} />
                          </button>
                        )
                        : <span className="sup-bubble-text" dir="auto">{m.message}</span>}
                      <span className="sup-bubble-time">
                        {m.pending ? 'sending…' : m.uploadPending ? 'uploading…' : m.failedText ? m.failedText : tShort(m.created_at)}
                      </span>
                    </div>
                  </React.Fragment>
                );
              })}
              {userTyping && (
                <div className="sup-bubble user sup-typing" aria-label="user is typing">
                  <span className="sup-typing-dot" /><span className="sup-typing-dot" /><span className="sup-typing-dot" />
                </div>
              )}
            </div>

            {cannedOpen && (
              <div className="sup-canned">
                <div className="sup-canned-head">
                  <span>Canned replies</span>
                  <button className="chip-btn" onClick={addCanned}>+ add</button>
                </div>
                {canned.map((c, i) => (
                  <div className="sup-canned-row" key={i}>
                    <button className="sup-canned-text" onClick={() => insertCanned(c)}>{c}</button>
                    <button className="sup-canned-del" title="Delete" onClick={() => removeCanned(i)}><Icons.close width={12} height={12} /></button>
                  </div>
                ))}
              </div>
            )}

            <div className={'sup-composer' + (isClosed ? ' disabled' : '')}>
              <button
                type="button"
                className={'sup-attach' + (cannedOpen ? ' on' : '')}
                title="Canned replies"
                disabled={isClosed}
                onClick={() => setCannedOpen((v) => !v)}
              >
                <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2"><path d="M13 2 3 14h9l-1 8 10-12h-9l1-8z" /></svg>
              </button>
              <label className="sup-attach" title="Attach photo">
                <input type="file" accept="image/*" hidden disabled={isClosed} onChange={(e) => { const f = e.target.files?.[0]; if (f) sendPhoto(f); e.target.value = ''; }} />
                <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48" /></svg>
              </label>
              <textarea
                placeholder={isClosed ? 'This ticket is closed' : 'Type a reply…'}
                value={draft}
                disabled={isClosed}
                rows={1}
                enterKeyHint="send"
                onChange={(e) => {
                  setDraft(e.target.value);
                  const now = Date.now();
                  if (now - typingEmitRef.current > 1500 && selRef.current) {
                    typingEmitRef.current = now;
                    rtRef.current?.sendTyping(selRef.current.id);
                  }
                }}
                onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); } }}
              />
              <button className="btn btn-primary sup-send" disabled={isClosed || sending || !draft.trim()} onClick={send} aria-label="Send reply">
                <Icons.send width={17} height={17} />
                <span className="sup-send-label">{sending ? '…' : 'Send'}</span>
              </button>
            </div>
          </>
        )}
      </section>

      {/* real <button>: iOS only dispatches taps to "clickable" elements — a
          plain div scrim lets WebKit redirect the tap to the chat behind it */}
      {selected && (
        <button
          type="button"
          className={'sup-ctx-scrim' + (ctxOpen ? ' on' : '')}
          onClick={() => setCtxOpen(false)}
          aria-label="Close customer info"
          tabIndex={ctxOpen ? 0 : -1}
        />
      )}
      {selected && (
        <aside
          className={'sup-ctx glass-card' + (ctxOpen ? ' open' : '')}
          ref={ctxRef}
          onPointerDown={ctxPointerDown}
          onPointerMove={ctxPointerMove}
          onPointerUp={ctxPointerUp}
          onPointerCancel={ctxPointerUp}
        >
          <div className="sup-ctx-head">
            <span>Customer</span>
            <button className="sup-ctx-close" aria-label="Close customer info" onClick={() => setCtxOpen(false)}><Icons.close width={16} height={16} /></button>
          </div>
          {!ctxUser && <div className="sup-empty">Loading profile…</div>}
          {ctxUser && (
            <>
              <div className="sup-ctx-ident">
                <div className="sup-row-avatar">{(ctxUser.full_name || ctxUser.username || 'U').charAt(0).toUpperCase()}</div>
                <div>
                  <div className="sup-ctx-name">
                    {ctxUser.full_name || ctxUser.username || 'User'}
                    {ctxUser.is_vip && <span className="receipt-vip" title="VIP"><Icons.crown width={13} height={13} /></span>}
                  </div>
                  <div className="sup-ctx-sub">{ctxUser.username ? '@' + ctxUser.username : ''} · {ctxUser.chat_id}</div>
                </div>
              </div>

              <div className="sup-ctx-stats">
                <div><em>Credit</em><b>{Number(ctxUser.credit || 0).toLocaleString()} T</b></div>
                <div><em>Stars</em><b>{ctxUser.stars ?? 0}</b></div>
                <div><em>Status</em><b style={{ color: ctxUser.banned ? 'var(--danger)' : 'var(--success)' }}>{ctxUser.banned ? 'BANNED' : 'OK'}</b></div>
                <div><em>Joined</em><b>{parseTs(ctxUser.created_at)?.toLocaleDateString() || '—'}</b></div>
              </div>

              <div className="sup-ctx-subs-title">Services ({(ctxUser.subscriptions || []).length})</div>
              <div className="sup-ctx-subs">
                {(ctxUser.subscriptions || []).length === 0 && <div className="sup-empty">No services</div>}
                {(ctxUser.subscriptions || []).map((s) => (
                  <div className="sup-ctx-sub-row" key={s.id}>
                    <span className="sup-ctx-svc">
                      {s.username || `#${s.id}`}
                      {/* live from the panel: user connected within the last 3 min */}
                      {s.is_online && <span className="sup-online-dot" title="Online now" />}
                    </span>
                    <span className="sup-ctx-plan">{s.plan_name || ''}</span>
                    <span className="sup-row-status" style={{ background: s.status === 'active' ? 'var(--success)' : s.status === 'pending' ? 'var(--warning)' : 'var(--muted)' }} />
                  </div>
                ))}
              </div>

              <a className="btn btn-secondary" style={{ marginTop: 'auto' }} href="/admin/users" onClick={() => { try { sessionStorage.setItem('admin_user_search', String(ctxUser.chat_id || ctxUser.username || '')); } catch (_) { /* ignore */ } }}>
                Open in Users
              </a>
            </>
          )}
        </aside>
      )}

      {lightbox && (
        <div className="lightbox-backdrop">
          {/* real <button> scrim: iOS won't synthesize clicks on a plain div,
              which left the fullscreen photo impossible to dismiss by tap */}
          <button type="button" className="lightbox-scrim" aria-label="Close photo" onClick={() => setLightbox(null)} />
          <img src={lightbox} alt="attachment zoom" className="lightbox-img" onClick={(e) => e.stopPropagation()} />
          <button className="lightbox-close" onClick={() => setLightbox(null)}><Icons.close width={18} height={18} /></button>
        </div>
      )}
    </div>
  );
}

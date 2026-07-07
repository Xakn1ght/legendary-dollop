import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { api, canUseSessionStorage, getAuthToken, getRawAuthHeaders, withUrlAuth } from '../shared/auth.js';
import { goBack as backStackGo, initBackStack, setBaseBack, useBackClose } from '../shared/backstack.js';
import { detectPlatform, getWebApp, hapticNotify } from '../shared/telegram.js';
import { astroConfirm, setupSwipeBack } from '../shared/ui.js';

import { ChatView } from './components/ChatView.jsx';
import { CreateTicketModal } from './components/CreateTicketModal.jsx';
import { TicketsList } from './components/TicketsList.jsx';
import { createSupportRealtime } from './realtime.js';
import { localizeValidationError, makeT, parseTs } from './translations.js';

let msgKeySeq = 0;
const nextKey = () => 'm' + (++msgKeySeq) + '-' + Date.now();

function detectSupportLanguage() {
  let saved = null;
  try { saved = localStorage.getItem('lang'); } catch (_) { /* ignore */ }
  if (saved === 'fa' || saved === 'en') return saved;
  try {
    const lc = getWebApp()?.initDataUnsafe?.user?.language_code;
    if (lc && /^fa/i.test(lc)) return 'fa';
  } catch (_) { /* ignore */ }
  return 'en';
}

function sortTickets(list) {
  return [...list].sort((a, b) => {
    const ta = parseTs(a.updated_at || a.created_at).getTime() || 0;
    const tb = parseTs(b.updated_at || b.created_at).getTime() || 0;
    return tb - ta;
  });
}

export function SupportApp() {
  const [lang, setLang] = useState(() => detectSupportLanguage());
  const [tickets, setTickets] = useState([]);
  const [ticketsLoading, setTicketsLoading] = useState(true);
  const [filter, setFilter] = useState('all');
  const [subs, setSubs] = useState([]);
  const [chatActive, setChatActive] = useState(false);
  const [selectedTicket, setSelectedTicket] = useState(null);
  const [messages, setMessages] = useState([]);
  const [messagesLoading, setMessagesLoading] = useState(false);
  const [modalActive, setModalActive] = useState(false);
  const [modalInitialSub, setModalInitialSub] = useState('');
  const [toast, setToast] = useState(null); // { msg, type }
  const [overlayText, setOverlayText] = useState(null);
  const [adminTyping, setAdminTyping] = useState(false);

  const t = useMemo(() => makeT(lang), [lang]);

  const langRef = useRef(lang);
  const selectedTicketRef = useRef(null);
  const chatActiveRef = useRef(false);
  const realtimeRef = useRef(null);
  const toastTimerRef = useRef(null);
  // Optimistic echo dedupe: 'ticketId|text' -> { key, expiresAt }
  const pendingMapRef = useRef(new Map());
  // Failed photo uploads keep their File around for tap-to-retry: key -> File
  const photoFilesRef = useRef(new Map());
  // Sync bookkeeping for the WS-echo vs POST-response race (state updaters run
  // async, so dedupe decisions must be made from refs, not inside setMessages).
  const photoUploadsInFlightRef = useRef(0);
  const sentPhotoNamesRef = useRef(new Set());
  const typingHideTimerRef = useRef(null);
  const typingLastSentRef = useRef(0);
  langRef.current = lang;
  selectedTicketRef.current = selectedTicket;
  chatActiveRef.current = chatActive;

  const hideAdminTyping = useCallback(() => {
    clearTimeout(typingHideTimerRef.current);
    setAdminTyping(false);
  }, []);

  const showToast = useCallback((msg, type = 'success') => {
    clearTimeout(toastTimerRef.current);
    setToast({ msg, type });
    toastTimerRef.current = setTimeout(() => setToast(null), 3000);
  }, []);

  const applyLanguage = useCallback((l) => {
    document.documentElement.setAttribute('dir', l === 'fa' ? 'rtl' : 'ltr');
    document.documentElement.setAttribute('lang', l);
  }, []);

  const loadTickets = useCallback(async (showSkeleton = true) => {
    if (showSkeleton) setTicketsLoading(true);
    const data = await api('/api/dashboard/tickets');
    if (data.ok) {
      setTickets(sortTickets(data.tickets || []));
    } else {
      showToast(makeT(langRef.current)('failedToLoad'), 'error');
    }
    setTicketsLoading(false);
  }, [showToast]);

  const loadSubscriptions = useCallback(async () => {
    const res = await api('/api/dashboard/subscriptions');
    if (res.ok && res.subscriptions) setSubs(res.subscriptions);
  }, []);

  const serverMessagesToState = (list) => (list || []).map((m) => ({
    key: nextKey(),
    from_admin: !!m.from_admin,
    message: m.message,
    created_at: m.created_at,
    content_type: m.content_type,
    file_name: m.file_name,
  }));

  // Poll fallback: append server messages beyond what we already show.
  const pollMessages = useCallback(async (ticketId) => {
    if (!selectedTicketRef.current || selectedTicketRef.current.id !== ticketId) return;
    const res = await api(`/api/dashboard/tickets/${ticketId}`);
    if (res.ok && res.ticket) {
      const msgs = res.ticket.messages || [];
      setMessages((cur) => {
        if (msgs.length <= cur.length) return cur;
        return [...cur, ...serverMessagesToState(msgs.slice(cur.length))];
      });
      const last = (res.ticket.messages || [])[res.ticket.messages.length - 1];
      if (last) {
        setTickets((cur) => sortTickets(cur.map((tk) => (tk.id === ticketId
          ? { ...tk, last_message: last.message || '', updated_at: last.created_at || tk.updated_at }
          : tk))));
      }
    }
  }, []);

  const onRealtimeEvent = useCallback((data) => {
    const tt = makeT(langRef.current);
    if (data.type === 'new_message') {
      const ticketId = data.ticket_id;
      const payload = data.data || {};
      const sender = payload.sender;
      const isPhotoMsg = payload.content_type === 'photo';
      const text = isPhotoMsg ? tt('photoLabel') : (payload.text || '');
      const createdAt = payload.created_at;
      const viewing = selectedTicketRef.current && ticketId === selectedTicketRef.current.id;

      setTickets((cur) => {
        const idx = cur.findIndex((x) => x.id === ticketId);
        if (idx < 0) { loadTickets(false); return cur; }
        const updated = { ...cur[idx], last_message: text, updated_at: createdAt || cur[idx].updated_at };
        if (sender === 'admin') {
          updated.unread_count = viewing ? 0 : (Number(updated.unread_count) || 0) + 1;
        }
        const next = [...cur];
        next.splice(idx, 1);
        return [updated, ...next];
      });

      if (viewing) {
        if (sender === 'admin') hideAdminTyping();
        let handled = false;
        if (sender === 'user' && isPhotoMsg) {
          const fname = payload.file_name || '';
          if (fname && sentPhotoNamesRef.current.has(fname)) {
            // POST response landed first and already adopted the bubble.
            handled = true;
          } else if (photoUploadsInFlightRef.current > 0) {
            // Echo raced ahead of the POST response: adopt the oldest
            // still-pending optimistic bubble.
            handled = true;
            setMessages((cur) => {
              const i = cur.findIndex((m) => m.uploadPending);
              if (i < 0) return cur;
              const next = [...cur];
              next[i] = { ...next[i], uploadPending: false, uploadFailed: false, file_name: fname || next[i].file_name };
              return next;
            });
          }
        } else if (sender === 'user') {
          const key = String(ticketId) + '|' + String(text || '');
          const pending = pendingMapRef.current.get(key);
          if (pending && pending.expiresAt > Date.now()) {
            handled = true;
            pendingMapRef.current.delete(key);
            setMessages((cur) => cur.map((m) => (m.key === pending.key
              ? { ...m, pending: false, created_at: createdAt || m.created_at }
              : m)));
          }
        }
        if (!handled) {
          setMessages((cur) => [...cur, {
            key: nextKey(),
            from_admin: sender === 'admin',
            message: isPhotoMsg ? '' : text,
            created_at: createdAt,
            content_type: payload.content_type,
            file_name: payload.file_name,
          }]);
        }
      }
      hapticNotify('success');
    } else if (data.type === 'tickets_updated') {
      loadTickets(false);
    } else if (data.type === 'status_change') {
      const ticketId = data.ticket_id;
      const payload = data.data || {};
      setTickets((cur) => {
        const idx = cur.findIndex((x) => x.id === ticketId);
        if (idx < 0) { loadTickets(false); return cur; }
        const updated = { ...cur[idx], status: payload.status || cur[idx].status, updated_at: payload.updated_at || cur[idx].updated_at };
        const next = [...cur];
        next.splice(idx, 1);
        return [updated, ...next];
      });
      if (selectedTicketRef.current && ticketId === selectedTicketRef.current.id) {
        setSelectedTicket((cur) => (cur ? { ...cur, status: payload.status || cur.status } : cur));
      }
    } else if (data.type === 'typing') {
      // Admin is typing in the ticket we're viewing: show dots, auto-hide
      // after 4s unless another hint arrives.
      if (data.from === 'admin' && selectedTicketRef.current && data.ticket_id === selectedTicketRef.current.id) {
        clearTimeout(typingHideTimerRef.current);
        setAdminTyping(true);
        typingHideTimerRef.current = setTimeout(() => setAdminTyping(false), 4000);
      }
    }
  }, [loadTickets, hideAdminTyping]);

  const openTicket = useCallback(async (id) => {
    setChatActive(true);
    setMessagesLoading(true);
    hideAdminTyping();
    const data = await api(`/api/dashboard/tickets/${id}`);
    if (data.ok) {
      setSelectedTicket(data.ticket);
      selectedTicketRef.current = data.ticket;
      setMessages(serverMessagesToState(data.ticket.messages));
      setMessagesLoading(false);
      // Backend marks admin messages read in /tickets/{id}; clear the badge locally too.
      setTickets((cur) => cur.map((tk) => (tk.id === id ? { ...tk, unread_count: 0 } : tk)));
      realtimeRef.current?.watchTicket(id);
    } else {
      setChatActive(false);
      setMessagesLoading(false);
      showToast(makeT(langRef.current)('failedToLoad'), 'error');
    }
  }, [showToast, hideAdminTyping]);

  const closeChat = useCallback(() => {
    setChatActive(false);
    realtimeRef.current?.unwatchTicket();
    setSelectedTicket(null);
    selectedTicketRef.current = null;
    setMessages([]);
    hideAdminTyping();
    photoFilesRef.current.clear();
  }, [hideAdminTyping]);

  const sendReply = useCallback(async (msg) => {
    const tt = makeT(langRef.current);
    const ticket = selectedTicketRef.current;
    if (!ticket) return;
    if (ticket.status === 'closed' || ticket.status === 'archived') {
      showToast(langRef.current === 'fa' ? 'این تیکت بسته شده است' : 'This ticket is closed', 'error');
      return;
    }
    const key = nextKey();
    setMessages((cur) => [...cur, { key, from_admin: false, message: msg, created_at: null, pending: true }]);
    pendingMapRef.current.set(String(ticket.id) + '|' + msg, { key, expiresAt: Date.now() + 15000 });

    const res = await api(`/api/dashboard/tickets/${ticket.id}/reply`, { method: 'POST', body: JSON.stringify({ message: msg }) });
    if (res.ok) {
      setMessages((cur) => cur.map((m) => (m.key === key && m.pending
        ? { ...m, pending: false, created_at: m.created_at || new Date().toISOString() }
        : m)));
      const nowIso = new Date().toISOString();
      setTickets((cur) => cur.map((tk) => (tk.id === ticket.id ? { ...tk, last_message: msg, updated_at: nowIso } : tk)));
      hapticNotify('success');
    } else {
      const failedText = res.error === 'ticket_closed'
        ? (langRef.current === 'fa' ? 'بسته شده' : 'Closed')
        : tt('failedToSend');
      showToast(res.error === 'ticket_closed'
        ? (langRef.current === 'fa' ? 'این تیکت بسته شده است' : 'This ticket is closed')
        : tt('failedToSend'), 'error');
      setMessages((cur) => cur.map((m) => (m.key === key ? { ...m, pending: false, failedText } : m)));
      hapticNotify('error');
    }
  }, [showToast]);

  // Shared photo upload path for first attempt and tap-to-retry.
  const uploadPhotoFor = useCallback(async (key, ticketId, file) => {
    const tt = makeT(langRef.current);
    photoUploadsInFlightRef.current += 1;
    try {
      const fd = new FormData();
      fd.append('photo', file, file.name || 'photo.jpg');
      const res = await fetch(withUrlAuth(`/api/dashboard/tickets/${ticketId}/photo`), {
        method: 'POST', credentials: 'include', headers: await getRawAuthHeaders(), body: fd,
      });
      const data = await res.json().catch(() => ({}));
      if (!data.ok) throw new Error(data.error || 'upload_failed');
      if (data.file_name) {
        sentPhotoNamesRef.current.add(data.file_name);
        if (sentPhotoNamesRef.current.size > 50) {
          sentPhotoNamesRef.current.delete(sentPhotoNamesRef.current.values().next().value);
        }
      }
      photoFilesRef.current.delete(key);
      setMessages((cur) => cur.map((m) => (m.key === key
        ? { ...m, uploadPending: false, uploadFailed: false, file_name: m.file_name || data.file_name || '' }
        : m)));
      setTickets((cur) => cur.map((tk) => (tk.id === ticketId
        ? { ...tk, last_message: tt('photoLabel'), updated_at: data.created_at || tk.updated_at }
        : tk)));
    } catch (_) {
      showToast(tt('photoSendFailed'), 'error');
      // If the WS echo already adopted this bubble the upload actually landed;
      // only a still-pending bubble flips to the visible failed state.
      setMessages((cur) => cur.map((m) => (m.key === key && m.uploadPending
        ? { ...m, uploadPending: false, uploadFailed: true }
        : m)));
      hapticNotify('error');
    } finally {
      photoUploadsInFlightRef.current -= 1;
    }
  }, [showToast]);

  const sendPhoto = useCallback(async (file) => {
    const tt = makeT(langRef.current);
    const ticket = selectedTicketRef.current;
    if (!ticket || !file) return;
    if (ticket.status === 'closed' || ticket.status === 'archived') {
      showToast(langRef.current === 'fa' ? 'این تیکت بسته شده است' : 'This ticket is closed', 'error');
      return;
    }
    if (file.size > 8 * 1024 * 1024) { showToast(tt('photoTooLarge'), 'error'); return; }
    const localUrl = URL.createObjectURL(file);
    const key = nextKey();
    photoFilesRef.current.set(key, file);
    setMessages((cur) => [...cur, {
      key, from_admin: false, message: '', created_at: new Date().toISOString(),
      content_type: 'photo', local_url: localUrl, uploadPending: true,
    }]);
    await uploadPhotoFor(key, ticket.id, file);
  }, [showToast, uploadPhotoFor]);

  const retryPhoto = useCallback((key) => {
    const ticket = selectedTicketRef.current;
    const file = photoFilesRef.current.get(key);
    if (!ticket || !file) return;
    setMessages((cur) => cur.map((m) => (m.key === key ? { ...m, uploadPending: true, uploadFailed: false } : m)));
    uploadPhotoFor(key, ticket.id, file);
  }, [uploadPhotoFor]);

  // Throttled typing hint towards the admin side (server rate-limits again).
  const onTyping = useCallback(() => {
    const ticket = selectedTicketRef.current;
    if (!ticket || !chatActiveRef.current) return;
    const now = Date.now();
    if (now - typingLastSentRef.current < 1500) return;
    typingLastSentRef.current = now;
    realtimeRef.current?.sendTyping(ticket.id);
  }, []);

  const createTicket = useCallback(async ({ category, subId, message }) => {
    const tt = makeT(langRef.current);
    if (message.length < 10) {
      showToast(tt('messageTooShort'), 'error');
      return false;
    }
    const payload = { category, message };
    if (subId) payload.subscription_id = parseInt(subId, 10);
    const res = await api('/api/dashboard/tickets', { method: 'POST', body: JSON.stringify(payload) });
    if (res.ok) {
      setModalActive(false);
      showToast(tt('ticketCreated'), 'success');
      const nowIso = new Date().toISOString();
      const newTicket = {
        id: Number(res.ticket_id) || 0,
        user_ticket_number: Number(res.user_ticket_number) || Number(res.ticket_id) || 0,
        category,
        status: 'pending',
        created_at: nowIso,
        updated_at: nowIso,
        last_message: message,
        subscription_username: subId ? (subs.find((s) => String(s.id) === String(subId))?.username || null) : null,
      };
      if (newTicket.id) setTickets((cur) => [newTicket, ...cur]);
      else loadTickets(false);
      return true;
    }
    const localized = localizeValidationError(res, tt, langRef.current);
    showToast(localized || res.message || tt('errorCreating'), 'error');
    return false;
  }, [showToast, subs, loadTickets]);

  const deleteTicket = useCallback(async () => {
    const tt = makeT(langRef.current);
    const ticket = selectedTicketRef.current;
    if (!ticket) return;
    const ok = await astroConfirm({
      title: langRef.current === 'fa' ? 'حذف تیکت' : 'Delete ticket',
      message: tt('deleteConfirm'),
      okText: langRef.current === 'fa' ? 'حذف' : 'Delete',
      cancelText: langRef.current === 'fa' ? 'لغو' : 'Cancel',
      danger: true,
    });
    if (!ok) return;
    setOverlayText(tt('deletingTicket'));
    const res = await api(`/api/dashboard/tickets/${ticket.id}`, { method: 'DELETE' });
    setOverlayText(null);
    if (res.ok) {
      showToast(tt('ticketDeleted'), 'success');
      setTickets((cur) => cur.filter((tk) => tk.id !== ticket.id));
      closeChat();
    } else {
      showToast(tt('errorDeleting'), 'error');
    }
  }, [showToast, closeChat]);

  const goBackHome = useCallback(() => {
    setOverlayText(makeT(langRef.current)('redirecting'));
    const authToken = getAuthToken();
    const propagate = !canUseSessionStorage();
    window.location.href = `/webapp/dashboard${(authToken && propagate) ? ('?auth=' + encodeURIComponent(authToken)) : ''}`;
  }, []);

  // Back closes chat/modal first (Telegram button + hardware/gesture back).
  useBackClose(chatActive, () => closeChat());
  useBackClose(modalActive, () => setModalActive(false));

  useEffect(() => {
    detectPlatform();
    applyLanguage(lang);
    try { document.documentElement.removeAttribute('data-boot'); } catch (_) { /* ignore */ }

    // Unified back: overlays pop first, otherwise leave to the dashboard.
    initBackStack();
    setBaseBack(() => goBackHome());

    // Cross-tab language sync (support has no lang.js; storage events only).
    const onStorage = (e) => {
      if (e.key === 'lang' && (e.newValue === 'fa' || e.newValue === 'en')) {
        setLang(e.newValue);
        applyLanguage(e.newValue);
      }
    };
    window.addEventListener('storage', onStorage);

    const realtime = createSupportRealtime({
      onEvent: onRealtimeEvent,
      pollTickets: () => loadTickets(false),
      pollMessages,
    });
    realtimeRef.current = realtime;
    realtime.connect();
    // Debug/headless-test hook: inject a synthetic realtime event.
    try { window.__astroSupportRt = { inject: (d) => onRealtimeEvent(d) }; } catch (_) { /* ignore */ }

    const urlParams = new URLSearchParams(window.location.search);
    const preSelectedSubId = urlParams.get('sub_id');
    const targetTicketId = parseInt(urlParams.get('ticket_id'), 10);

    loadTickets().then(() => {
      if (!Number.isNaN(targetTicketId) && targetTicketId) {
        setTimeout(() => openTicket(targetTicketId), 300);
      }
    });
    loadSubscriptions();
    if (preSelectedSubId) {
      setTimeout(() => {
        setModalInitialSub(String(preSelectedSubId));
        setModalActive(true);
      }, 500);
    }

    // Smart swipe-back through the shared back stack (chat/modal close first).
    let destroySwipe = () => {};
    const swipeTimer = setTimeout(() => {
      if (!window.AstroUI?.swipeBack) return;
      try {
        window.AstroUI.swipeBack.setup({
          edgeZone: 16, threshold: 80,
          onBack: () => backStackGo(),
          canSwipe: () => true,
          target: () => {
            if (chatActiveRef.current) return document.getElementById('chatView');
            return document.querySelector('.content');
          },
        });
        destroySwipe = () => { try { window.AstroUI.swipeBack.destroy(); } catch (_) { /* ignore */ } };
      } catch (_) { /* ignore */ }
    }, 0);

    return () => {
      window.removeEventListener('storage', onStorage);
      clearTimeout(swipeTimer);
      destroySwipe();
      realtime.destroy();
      clearTimeout(toastTimerRef.current);
      clearTimeout(typingHideTimerRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- mount-only boot sequence
  }, []);

  return (
    <>
      <div className="space-bg" />
      <div className="container" id="mainContainer">
        <div id="ticketsView" style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
          <div className="header">
            <button className="back-btn" onClick={goBackHome}>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M15 18l-6-6 6-6" strokeLinecap="round" strokeLinejoin="round" /></svg>
            </button>
            <div className="header-content">
              <div className="header-title" id="pageTitle">{t('support')}</div>
              <div className="header-subtitle" id="pageSubtitle">{t('helpCenter')}</div>
            </div>
          </div>
          <div className="filter-tabs">
            {['all', 'open', 'closed'].map((f) => (
              <div
                key={f}
                className={`filter-tab${filter === f ? ' active' : ''}`}
                data-filter={f}
                onClick={() => setFilter(f)}
              >
                {t(f)}
              </div>
            ))}
          </div>
          <TicketsList
            t={t}
            lang={lang}
            tickets={tickets}
            filter={filter}
            loading={ticketsLoading}
            onOpen={openTicket}
            onCreate={() => { setModalInitialSub(''); setModalActive(true); }}
          />
          {/* FAB only when there are tickets; the empty state carries its own big CTA. */}
          {(ticketsLoading || tickets.length > 0) && (
            <button className="fab" onClick={() => { setModalInitialSub(''); setModalActive(true); }} aria-label={t('newTicket')}>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><line x1="12" y1="5" x2="12" y2="19" strokeLinecap="round" /><line x1="5" y1="12" x2="19" y2="12" strokeLinecap="round" /></svg>
            </button>
          )}
        </div>

        <ChatView
          t={t}
          lang={lang}
          active={chatActive}
          ticket={selectedTicket}
          messages={messages}
          messagesLoading={messagesLoading}
          adminTyping={adminTyping}
          onClose={closeChat}
          onDelete={deleteTicket}
          onSend={sendReply}
          onSendPhoto={sendPhoto}
          onRetryPhoto={retryPhoto}
          onTyping={onTyping}
        />
      </div>

      <CreateTicketModal
        t={t}
        active={modalActive}
        subs={subs}
        initialSubId={modalInitialSub}
        onSubmit={createTicket}
        onClose={() => setModalActive(false)}
      />

      <div className={`toast${toast ? ' show ' + toast.type : ''}`} id="toast">
        <div className="toast-icon">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="20 6 9 17 4 12" /></svg>
        </div>
        <span className="toast-message">{toast?.msg || ''}</span>
      </div>

      <div className={`loading-overlay${overlayText ? ' active' : ''}`} id="loadingOverlay">
        <div className="loading-spinner" />
        <div className="loading-text" id="loadingText">{overlayText || t('loading')}</div>
      </div>
    </>
  );
}

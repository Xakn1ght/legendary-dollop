import React, { useEffect, useRef, useState } from 'react';

import { getRawAuthHeaders, withUrlAuth } from '../../shared/auth.js';
import { useBackClose } from '../../shared/backstack.js';
import { parseTs } from '../translations.js';

import { Lightbox } from './Lightbox.jsx';

// file_name -> objectURL (persists across chat opens; photos are immutable)
const photoCache = new Map();

// Consecutive same-sender messages within this window render as one visual group.
const GROUP_WINDOW_MS = 3 * 60 * 1000;

function sameGroup(a, b) {
  if (!a || !b || !!a.from_admin !== !!b.from_admin) return false;
  const ta = parseTs(a.created_at).getTime();
  const tb = parseTs(b.created_at).getTime();
  // Optimistic bubbles may not have a timestamp yet: group by sender alone.
  if (Number.isNaN(ta) || Number.isNaN(tb)) return true;
  return Math.abs(tb - ta) <= GROUP_WINDOW_MS;
}

function PhotoBubble({ ticketId, fileName, localUrl, uploadPending, uploadFailed, onOpenLightbox, onRetry }) {
  const [src, setSrc] = useState(localUrl || photoCache.get(fileName) || '');
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    if (src || !fileName || !ticketId) return;
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(withUrlAuth(`/api/dashboard/tickets/${ticketId}/photo/${fileName}`), {
          credentials: 'include',
          headers: await getRawAuthHeaders(),
        });
        if (!res.ok) throw new Error('http ' + res.status);
        const url = URL.createObjectURL(await res.blob());
        photoCache.set(fileName, url);
        if (!cancelled) setSrc(url);
      } catch (_) {
        if (!cancelled) setFailed(true);
      }
    })();
    return () => { cancelled = true; };
  }, [src, fileName, ticketId]);

  // Placeholders keep the exact final square so hydration never shifts layout.
  if (failed) {
    return (
      <div className="message-bubble msg-photo">
        <div className="msg-photo-ph">
          <div className="msg-photo-fail">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" width="22" height="22" aria-hidden="true"><rect x="3" y="3" width="18" height="18" rx="3" /><circle cx="8.5" cy="8.5" r="1.5" /><path d="M21 15l-5-5L5 21" /><line x1="3" y1="3" x2="21" y2="21" /></svg>
          </div>
        </div>
      </div>
    );
  }
  if (!src) {
    return (
      <div className="message-bubble msg-photo">
        <div className="msg-photo-ph"><div className="msg-photo-spin" style={{ margin: 0 }} /></div>
      </div>
    );
  }
  const onClick = uploadFailed ? onRetry : (uploadPending ? undefined : () => onOpenLightbox(src));
  return (
    <div
      className={`message-bubble msg-photo${uploadPending ? ' upload-pending' : ''}${uploadFailed ? ' upload-failed' : ''}`}
      onClick={onClick}
      role={uploadFailed ? 'button' : undefined}
      aria-label={uploadFailed ? 'Retry upload' : undefined}
    >
      <img src={src} alt="" />
      {uploadPending && <div className="msg-photo-overlay"><div className="msg-photo-spin" style={{ margin: 0 }} /></div>}
      {uploadFailed && (
        <div className="msg-photo-overlay">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="M21 12a9 9 0 1 1-2.64-6.36" /><polyline points="21 3 21 9 15 9" />
          </svg>
        </div>
      )}
    </div>
  );
}

// The user's own Telegram avatar (authed blob; the endpoint 404s when they
// have no photo — falls back to the generic icon).
let _myAvatarUrl; // undefined = not fetched, null = no photo, string = blob url
function useMyAvatar() {
  const [url, setUrl] = useState(_myAvatarUrl || null);
  useEffect(() => {
    if (_myAvatarUrl !== undefined) return;
    _myAvatarUrl = null;
    (async () => {
      try {
        const { getRawAuthHeaders } = await import('../../shared/auth.js');
        const r = await fetch('/api/dashboard/profile-photo', { headers: await getRawAuthHeaders(), credentials: 'include' });
        if (!r.ok) return;
        _myAvatarUrl = URL.createObjectURL(await r.blob());
        setUrl(_myAvatarUrl);
      } catch (_) { /* keep fallback icon */ }
    })();
  }, []);
  return url;
}

function Message({ m, lang, t, ticketId, grpFollow, isGroupEnd, onOpenLightbox, onRetryPhoto, myAvatar }) {
  // Grouped bubbles hide their timestamp; a tap reveals it.
  const [timeRevealed, setTimeRevealed] = useState(false);
  const locale = lang === 'fa' ? 'fa-IR' : 'en-US';
  const statusLine = m.pending
    ? t('sending')
    : m.failedText
      ? m.failedText
      : m.uploadFailed
        ? t('photoFailedRetry')
        : (m.created_at ? parseTs(m.created_at).toLocaleTimeString(locale, { hour: '2-digit', minute: '2-digit' }) : '');
  const showTime = !!statusLine && (isGroupEnd || m.pending || !!m.failedText || m.uploadFailed || timeRevealed);
  return (
    <div
      className={`message ${m.from_admin ? 'admin' : 'user'}${m.pending ? ' pending' : ''}${grpFollow ? ' grp-follow' : ''}`}
      style={m.pending ? { opacity: 0.7 } : undefined}
    >
      <div className="message-avatar">
        {!m.from_admin && myAvatar
          ? <img src={myAvatar} alt="" style={{ width: '100%', height: '100%', objectFit: 'cover', borderRadius: '50%' }} />
          : (
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" /><circle cx="12" cy="7" r="4" />
            </svg>
          )}
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', maxWidth: '100%' }}>
        {m.content_type === 'photo'
          ? (
            <PhotoBubble
              ticketId={ticketId}
              fileName={m.file_name}
              localUrl={m.local_url}
              uploadPending={m.uploadPending}
              uploadFailed={m.uploadFailed}
              onOpenLightbox={onOpenLightbox}
              onRetry={() => onRetryPhoto(m.key)}
            />
          )
          : (
            <div className="message-bubble" onClick={() => { if (!isGroupEnd) setTimeRevealed((v) => !v); }}>
              {m.message}
            </div>
          )}
        {showTime && <div className="message-time">{statusLine}</div>}
      </div>
    </div>
  );
}

export function ChatView({
  t, lang, active, ticket, messages, messagesLoading, adminTyping,
  onClose, onDelete, onSend, onSendPhoto, onRetryPhoto, onTyping,
}) {
  const [draft, setDraft] = useState('');
  const [lightboxSrc, setLightboxSrc] = useState('');
  const myAvatar = useMyAvatar();
  // Reacts LIVE to a status_change pushed over the WS (admin closed/reopened
  // the ticket): banner + disabled composer, no refresh needed.
  const isClosed = !!ticket && (ticket.status === 'closed' || ticket.status === 'archived');
  const messagesRef = useRef(null);
  const chatViewRef = useRef(null);
  const inputRef = useRef(null);
  const photoInputRef = useRef(null);
  const preventBlurUntilRef = useRef(0);
  const sendingRef = useRef(false);

  // Hardware/gesture back closes the lightbox before the chat.
  useBackClose(!!lightboxSrc, () => setLightboxSrc(''));

  // Android (Telegram WebView) keeps the layout viewport full-height when
  // the keyboard opens, leaving the fixed reply bar hidden behind it. Size
  // the fixed chat view to the *visual* viewport while the keyboard is up.
  useEffect(() => {
    const vv = window.visualViewport;
    if (!vv) return undefined;
    let raf = 0;
    const apply = () => {
      raf = 0;
      const el = chatViewRef.current;
      if (!el) return;
      const kb = Math.max(0, Math.round((window.innerHeight || 0) - vv.height));
      if (kb > 60) {
        el.style.height = Math.round(vv.height) + 'px';
        el.style.top = Math.round(vv.offsetTop) + 'px';
        el.style.bottom = 'auto';
        el.classList.add('kb-open');
        const m = messagesRef.current;
        if (m) m.scrollTop = m.scrollHeight;
      } else {
        el.style.height = '';
        el.style.top = '';
        el.style.bottom = '';
        el.classList.remove('kb-open');
      }
    };
    const onChange = () => { if (!raf) raf = requestAnimationFrame(apply); };
    vv.addEventListener('resize', onChange);
    vv.addEventListener('scroll', onChange);
    return () => {
      vv.removeEventListener('resize', onChange);
      vv.removeEventListener('scroll', onChange);
      if (raf) cancelAnimationFrame(raf);
    };
  }, []);

  // Auto-scroll on new messages: always for the user's own sends, otherwise
  // only when already near the bottom (photo bubbles are ~190px tall, so the
  // threshold must be taller than one of them).
  const prevCountRef = useRef(0);
  useEffect(() => {
    const el = messagesRef.current;
    if (!el) return;
    const nearBottom = (el.scrollHeight - el.scrollTop - el.clientHeight) < 260;
    const last = messages[messages.length - 1];
    const ownSend = !!last && !last.from_admin && (last.pending || last.uploadPending);
    if (messages.length > prevCountRef.current && (nearBottom || ownSend || prevCountRef.current === 0)) {
      el.scrollTop = el.scrollHeight;
    }
    prevCountRef.current = messages.length;
  }, [messages]);

  // Keep the typing indicator in view when it pops in.
  useEffect(() => {
    if (!adminTyping) return;
    const el = messagesRef.current;
    if (!el) return;
    const nearBottom = (el.scrollHeight - el.scrollTop - el.clientHeight) < 260;
    if (nearBottom) el.scrollTop = el.scrollHeight;
  }, [adminTyping]);

  const autoResize = (el) => {
    el.style.height = 'auto';
    el.style.height = Math.min(el.scrollHeight, 100) + 'px';
  };

  const keepKeyboardOpen = () => {
    const el = inputRef.current;
    if (!el) return;
    el.focus();
    requestAnimationFrame(() => el.focus());
    [0, 10, 50, 100].forEach((ms) => setTimeout(() => el.focus(), ms));
  };

  const doSend = async () => {
    const msg = draft.trim();
    if (!msg || sendingRef.current) return;
    sendingRef.current = true;
    setDraft('');
    if (inputRef.current) inputRef.current.style.height = 'auto';
    try { await onSend(msg); } finally { sendingRef.current = false; }
  };

  const sendKeepKeyboard = async () => {
    preventBlurUntilRef.current = Date.now() + 2000;
    inputRef.current?.focus();
    keepKeyboardOpen();
    await doSend();
    keepKeyboardOpen();
  };

  // Ticket closed while typing → drop focus/keyboard along with the composer.
  useEffect(() => {
    if (isClosed) {
      preventBlurUntilRef.current = 0;
      try { inputRef.current?.blur(); } catch (_) { /* ignore */ }
    }
  }, [isClosed]);

  return (
    <>
      <div className={`chat-backdrop${active ? ' active' : ''}`} id="chatBackdrop" onClick={onClose} />
      <div className={`chat-view${active ? ' active' : ''}`} id="chatView" ref={chatViewRef}>
        <div className="header">
          <button className="back-btn" onClick={onClose}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M15 18l-6-6 6-6" strokeLinecap="round" strokeLinejoin="round" /></svg>
          </button>
          <div className="header-content">
            <div className="header-title" id="chatTitle">
              {ticket ? `${t('support')} #${ticket.user_ticket_number || ticket.id}` : ''}
            </div>
            <div className="header-subtitle" id="chatStatus">
              {isClosed && <span style={{ color: 'var(--danger)', fontWeight: 700 }}>{(t('closed') || 'CLOSED').toUpperCase()} · </span>}
              {ticket ? (t(ticket.category) || ticket.category || '').toUpperCase() : ''}
            </div>
          </div>
          <button
            className="back-btn"
            style={{ color: 'var(--danger)', borderColor: 'rgba(239, 68, 68, 0.3)' }}
            onClick={onDelete}
            aria-label="Delete ticket"
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><polyline points="3 6 5 6 21 6" /><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" /></svg>
          </button>
        </div>

        <div className="chat-messages" id="messagesArea" ref={messagesRef}>
          {messagesLoading && (
            <>
              <div className="skeleton-message"><div className="skeleton skeleton-avatar" /><div className="skeleton skeleton-bubble" style={{ height: 60 }} /></div>
              <div className="skeleton-message right"><div className="skeleton skeleton-avatar" /><div className="skeleton skeleton-bubble" style={{ height: 40 }} /></div>
              <div className="skeleton-message"><div className="skeleton skeleton-avatar" /><div className="skeleton skeleton-bubble" style={{ height: 80 }} /></div>
            </>
          )}
          {!messagesLoading && messages.length === 0 && (
            <div style={{ textAlign: 'center', color: 'var(--text-muted)', marginTop: 40 }}>{t('noMessages')}</div>
          )}
          {!messagesLoading && messages.map((m, i) => (
            <Message
              key={m.key}
              m={m}
              lang={lang}
              t={t}
              ticketId={ticket?.id}
              grpFollow={sameGroup(messages[i - 1], m)}
              isGroupEnd={!sameGroup(m, messages[i + 1])}
              onOpenLightbox={setLightboxSrc}
              onRetryPhoto={onRetryPhoto}
              myAvatar={myAvatar}
            />
          ))}
          {!messagesLoading && adminTyping && (
            <div className="message admin typing-msg">
              <div className="message-avatar">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" /><circle cx="12" cy="7" r="4" />
                </svg>
              </div>
              <div className="message-bubble typing-bubble">
                <span className="typing-dot" /><span className="typing-dot" /><span className="typing-dot" />
              </div>
            </div>
          )}
        </div>

        {isClosed && (
          <div className="reply-area" style={{ justifyContent: 'center' }}>
            <div style={{
              display: 'flex', alignItems: 'center', gap: 8, padding: '12px 16px',
              color: 'var(--text-muted)', fontSize: 14, fontWeight: 600,
            }}>
              <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="11" width="18" height="11" rx="2" /><path d="M7 11V7a5 5 0 0 1 10 0v4" /></svg>
              {lang === 'fa' ? 'این تیکت بسته شده است' : 'This ticket is closed'}
            </div>
          </div>
        )}
        {!isClosed && (
        <div className="reply-area">
          <button className="attach-btn" id="attachBtn" type="button" title="Send photo" onClick={() => photoInputRef.current?.click()}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <rect x="3" y="3" width="18" height="18" rx="3" /><circle cx="8.5" cy="8.5" r="1.5" /><path d="M21 15l-5-5L5 21" />
            </svg>
          </button>
          <input
            type="file"
            id="photoInput"
            ref={photoInputRef}
            accept="image/*"
            style={{ display: 'none' }}
            onChange={(e) => {
              const f = e.target.files && e.target.files[0];
              // Reset so picking the same file again still fires a change event.
              e.target.value = '';
              if (f) onSendPhoto(f);
            }}
          />
          <textarea
            className="reply-input"
            id="replyInput"
            ref={inputRef}
            rows={1}
            placeholder={t('typeMessage')}
            value={draft}
            onChange={(e) => { setDraft(e.target.value); autoResize(e.target); if (e.target.value.trim()) onTyping?.(); }}
            onKeyDown={(e) => {
              // Enter inserts a newline (send is button-only, legacy parity)
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                const el = e.target;
                const start = el.selectionStart, end = el.selectionEnd;
                const next = draft.substring(0, start) + '\n' + draft.substring(end);
                setDraft(next);
                requestAnimationFrame(() => {
                  el.selectionStart = el.selectionEnd = start + 1;
                  autoResize(el);
                });
              }
            }}
            onBlur={() => {
              if (Date.now() < preventBlurUntilRef.current) {
                setTimeout(() => inputRef.current?.focus(), 0);
              }
            }}
          />
          <button
            className="send-btn"
            id="sendBtn"
            type="button"
            onTouchStart={(e) => { e.preventDefault(); preventBlurUntilRef.current = Date.now() + 2000; inputRef.current?.focus(); }}
            onTouchEnd={(e) => { e.preventDefault(); e.stopPropagation(); sendKeepKeyboard(); }}
            onMouseDown={(e) => { e.preventDefault(); preventBlurUntilRef.current = Date.now() + 2000; }}
            onClick={(e) => { e.preventDefault(); e.stopPropagation(); sendKeepKeyboard(); }}
          >
            <svg viewBox="0 0 24 24"><path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z" /></svg>
          </button>
        </div>
        )}
      </div>

      {lightboxSrc && <Lightbox src={lightboxSrc} onClose={() => setLightboxSrc('')} />}
    </>
  );
}

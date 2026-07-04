import React, { useEffect, useRef, useState } from 'react';

import { getRawAuthHeaders, withUrlAuth } from '../../shared/auth.js';
import { hapticImpact } from '../../shared/telegram.js';
import { parseTs } from '../translations.js';

// file_name -> objectURL (persists across chat opens; photos are immutable)
const photoCache = new Map();

function isPhoneDevice() {
  const hasTouch = 'ontouchstart' in window || navigator.maxTouchPoints > 0;
  const isSmallScreen = window.innerWidth <= 480;
  const isMobileUA = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);
  const isTablet = window.innerWidth > 480 && window.innerWidth <= 768 && hasTouch;
  return hasTouch && isSmallScreen && isMobileUA && !isTablet;
}

function PhotoBubble({ ticketId, fileName, localUrl, uploadPending, onOpenLightbox }) {
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

  if (failed) {
    return (
      <div className="message-bubble msg-photo">
        <div className="msg-photo-fail">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" width="22" height="22" aria-hidden="true"><rect x="3" y="3" width="18" height="18" rx="3" /><circle cx="8.5" cy="8.5" r="1.5" /><path d="M21 15l-5-5L5 21" /><line x1="3" y1="3" x2="21" y2="21" /></svg>
        </div>
      </div>
    );
  }
  if (!src) return <div className="message-bubble msg-photo"><div className="msg-photo-spin" /></div>;
  return (
    <div className={`message-bubble msg-photo${uploadPending ? ' upload-pending' : ''}`} onClick={() => onOpenLightbox(src)}>
      <img src={src} alt="" />
    </div>
  );
}

function Message({ m, lang, t, ticketId, onOpenLightbox }) {
  const locale = lang === 'fa' ? 'fa-IR' : 'en-US';
  const time = m.pending
    ? t('sending')
    : m.failedText
      ? m.failedText
      : (m.created_at ? parseTs(m.created_at).toLocaleTimeString(locale, { hour: '2-digit', minute: '2-digit' }) : '');
  return (
    <div className={`message ${m.from_admin ? 'admin' : 'user'}${m.pending ? ' pending' : ''}`} style={m.pending ? { opacity: 0.7 } : undefined}>
      <div className="message-avatar">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" /><circle cx="12" cy="7" r="4" />
        </svg>
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', maxWidth: '100%' }}>
        {m.content_type === 'photo'
          ? <PhotoBubble ticketId={ticketId} fileName={m.file_name} localUrl={m.local_url} uploadPending={m.uploadPending} onOpenLightbox={onOpenLightbox} />
          : <div className="message-bubble">{m.message}</div>}
        <div className="message-time">{time}</div>
      </div>
    </div>
  );
}

export function ChatView({
  t, lang, active, ticket, messages, messagesLoading,
  onClose, onDelete, onSend, onSendPhoto,
}) {
  const [draft, setDraft] = useState('');
  const [lightboxSrc, setLightboxSrc] = useState('');
  const messagesRef = useRef(null);
  const chatViewRef = useRef(null);
  const inputRef = useRef(null);
  const photoInputRef = useRef(null);
  const preventBlurUntilRef = useRef(0);
  const sendingRef = useRef(false);
  const [showDismissBtn, setShowDismissBtn] = useState(false);

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

  useEffect(() => {
    setShowDismissBtn(isPhoneDevice());
    let timer;
    const onResize = () => {
      clearTimeout(timer);
      timer = setTimeout(() => setShowDismissBtn(isPhoneDevice()), 100);
    };
    window.addEventListener('resize', onResize);
    return () => { window.removeEventListener('resize', onResize); clearTimeout(timer); };
  }, []);

  // Auto-scroll on new messages when the user is near the bottom.
  const prevCountRef = useRef(0);
  useEffect(() => {
    const el = messagesRef.current;
    if (!el) return;
    const nearBottom = (el.scrollHeight - el.scrollTop - el.clientHeight) < 120;
    if (messages.length > prevCountRef.current && (nearBottom || prevCountRef.current === 0)) {
      el.scrollTop = el.scrollHeight;
    }
    prevCountRef.current = messages.length;
  }, [messages]);

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

  const dismissKeyboard = () => {
    preventBlurUntilRef.current = 0;
    inputRef.current?.blur();
    document.activeElement?.blur();
    hapticImpact('light');
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
          {!messagesLoading && messages.map((m) => (
            <Message key={m.key} m={m} lang={lang} t={t} ticketId={ticket?.id} onOpenLightbox={setLightboxSrc} />
          ))}
        </div>

        <div className="reply-area">
          {showDismissBtn && (
            <button
              className="keyboard-dismiss-btn"
              id="keyboardDismissBtn"
              type="button"
              title="Hide keyboard"
              style={{ display: 'flex' }}
              onTouchEnd={(e) => { e.preventDefault(); e.stopPropagation(); dismissKeyboard(); }}
              onClick={(e) => { e.preventDefault(); dismissKeyboard(); }}
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M4 6h16M4 10h16M4 14h16M8 18l4 3 4-3" />
              </svg>
            </button>
          )}
          <button className="attach-btn" id="attachBtn" type="button" title="Send photo" onClick={() => photoInputRef.current?.click()}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <rect x="3" y="3" width="18" height="18" rx="3" /><circle cx="8.5" cy="8.5" r="1.5" /><path d="M21 15l-5-5L5 21" />
            </svg>
          </button>
          <input
            type="file"
            id="photoInput"
            ref={photoInputRef}
            accept="image/jpeg,image/png,image/webp"
            style={{ display: 'none' }}
            onChange={(e) => {
              const f = e.target.files && e.target.files[0];
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
            onChange={(e) => { setDraft(e.target.value); autoResize(e.target); }}
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
      </div>

      <div className={`photo-lightbox${lightboxSrc ? ' active' : ''}`} id="photoLightbox" onClick={() => setLightboxSrc('')}>
        <img id="photoLightboxImg" src={lightboxSrc || undefined} alt="" />
      </div>
    </>
  );
}

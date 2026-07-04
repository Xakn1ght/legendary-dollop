import React, { useEffect, useRef } from 'react';

import { fmtNum, getLocale } from '../format.js';

import { Sheet } from './Sheet.jsx';

// Old DB rows carry emoji-prefixed titles (✅/❌/…) — strip for icon-only UI.
function cleanTitle(title) {
  return String(title || '').replace(/^[\u{1F300}-\u{1FAFF}\u{2600}-\u{27BF}\u{2B00}-\u{2BFF}\u{FE0F}\s]+/u, '').trim() || String(title || '');
}

// Status icon by notification type (API field), falling back to title text.
function notifVisual(n) {
  const ty = String(n.type || '');
  const title = String(n.title || '');
  if (/approved|granted|activated|success/.test(ty) || /فعال شد|تایید شد/.test(title)) {
    return {
      cls: 'ok',
      icon: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10" /><path d="m8.5 12.5 2.5 2.5 5-6" /></svg>,
    };
  }
  if (/denied|rejected|failed|error/.test(ty) || /رد شد|ناموفق/.test(title)) {
    return {
      cls: 'bad',
      icon: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10" /><path d="m9 9 6 6M15 9l-6 6" /></svg>,
    };
  }
  if (/ticket|message/.test(ty)) {
    return {
      cls: 'info',
      icon: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" /></svg>,
    };
  }
  return {
    cls: 'info',
    icon: <svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 22c1.1 0 2-.9 2-2h-4c0 1.1.9 2 2 2zm6-6v-5c0-3.07-1.63-5.64-4.5-6.32V4c0-.83-.67-1.5-1.5-1.5s-1.5.67-1.5 1.5v.68C7.64 5.36 6 7.92 6 11v5l-2 2v1h16v-1l-2-2z" /></svg>,
  };
}

function formatNotifTime(n, t, lang) {
  try {
    let dateStr = n.created_at;
    if (dateStr && !dateStr.endsWith('Z') && !dateStr.includes('+') && !dateStr.includes('-', 10)) {
      dateStr += 'Z';
    }
    // Full locale time (legacy mixed Persian hours with Latin minutes).
    return new Date(dateStr).toLocaleTimeString(getLocale(lang), { hour: '2-digit', minute: '2-digit' });
  } catch (e) {
    return formatTimeAgo(n.created_at, t, lang);
  }
}

function formatTimeAgo(dateString, t, lang) {
  if (!dateString) return '';
  try {
    let dateStr = dateString;
    if (!dateStr.endsWith('Z') && !dateStr.includes('+') && !dateStr.includes('-', 10)) dateStr += 'Z';
    const date = new Date(dateStr);
    const seconds = Math.floor((new Date() - date) / 1000);
    if (seconds < 0) return t('justNow');
    if (seconds < 60) return t('justNow') || 'Just now';
    if (seconds < 3600) return `${fmtNum(Math.floor(seconds / 60), lang, 0)} ${t('minutesAgo') || 'min ago'}`;
    if (seconds < 86400) return `${fmtNum(Math.floor(seconds / 3600), lang, 0)} ${t('hoursAgo') || 'hr ago'}`;
    if (seconds < 604800) return `${fmtNum(Math.floor(seconds / 86400), lang, 0)} ${t('daysAgo') || 'd ago'}`;
    return date.toLocaleDateString(getLocale(lang), { month: 'short', day: 'numeric' });
  } catch (e) {
    return '';
  }
}

export function NotificationsPanel({ t, lang, open, notifications, onClose, onMarkAllRead, onClearHistory, onItemClick }) {
  const listRef = useRef(null);

  // "has-more" fade indicator when scrollable (legacy parity).
  useEffect(() => {
    if (!open) return;
    const container = listRef.current;
    if (!container) return;
    const timer = setTimeout(() => {
      container.classList.toggle('has-more', container.scrollHeight > container.clientHeight);
    }, 50);
    const onScroll = () => {
      const nearBottom = container.scrollHeight - container.scrollTop - container.clientHeight < 20;
      container.classList.toggle('has-more', !nearBottom);
    };
    container.addEventListener('scroll', onScroll, { passive: true });
    return () => { clearTimeout(timer); container.removeEventListener('scroll', onScroll); };
  }, [open, notifications]);

  return (
    <Sheet open={open} onClose={onClose} panelId="notificationsPanel" backdropId="notificationsBackdrop" labelledBy="notificationsPanelTitle">
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
        <h2 id="notificationsPanelTitle" style={{ fontSize: 18, fontWeight: 800 }}>{t('notifications')}</h2>
        <div style={{ display: 'flex', gap: 12 }}>
          <button
            id="clearHistoryBtn"
            onClick={onClearHistory}
            style={{ background: 'none', border: 'none', color: 'var(--muted)', fontSize: 13, fontWeight: 600, cursor: 'pointer', transition: 'color 0.2s' }}
          >
            {t('clearHistory')}
          </button>
          <button
            id="markAllReadBtn"
            onClick={() => { onMarkAllRead(); onClose(); }}
            style={{ background: 'none', border: 'none', color: 'var(--brand)', fontSize: 13, fontWeight: 600, cursor: 'pointer' }}
          >
            {t('markAllAsRead')}
          </button>
        </div>
      </div>
      <div id="notificationsList" ref={listRef} style={{ maxHeight: 400, overflowY: 'auto', overflowX: 'hidden' }}>
        {notifications.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '40px 20px', color: 'var(--muted)' }}>
            <svg viewBox="0 0 24 24" style={{ width: 48, height: 48, opacity: 0.5, marginBottom: 12 }} fill="currentColor" xmlns="http://www.w3.org/2000/svg">
              <path d="M12 22c1.1 0 2-.9 2-2h-4c0 1.1.9 2 2 2zm6-6v-5c0-3.07-1.63-5.64-4.5-6.32V4c0-.83-.67-1.5-1.5-1.5s-1.5.67-1.5 1.5v.68C7.64 5.36 6 7.92 6 11v5l-2 2v1h16v-1l-2-2zm-2 1H8v-6c0-2.48 1.51-4.5 4-4.5s4 2.02 4 4.5v6z" />
            </svg>
            <div>{t('noNotifications') || 'No notifications'}</div>
          </div>
        ) : notifications.map((n) => {
          const vis = notifVisual(n);
          return (
            <div
              key={n.id}
              className={`notification-item ${n.read ? 'read' : 'unread'}`}
              onClick={() => onItemClick(n)}
              role="button"
              tabIndex={0}
              onKeyDown={(e) => { if (e.key === 'Enter') onItemClick(n); }}
            >
              <div className="notification-header">
                <div className="notification-title">
                  <span className={`notification-icon ${vis.cls}`} aria-hidden="true">{vis.icon}</span>
                  {/* Unread dot at the reading start: right of the title in fa, left in en. */}
                  {!n.read && <span className="unread-indicator" aria-hidden="true" />}
                  {cleanTitle(n.title)}
                </div>
                <div className="notification-time">{formatNotifTime(n, t, lang)}</div>
              </div>
              <div className="notification-message">{n.message}</div>
            </div>
          );
        })}
      </div>
    </Sheet>
  );
}

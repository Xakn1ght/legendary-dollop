import React from 'react';

import { parseTs } from '../translations.js';

const CATEGORY_ICONS = {
  money: <path d="M12 2v20m-5-5h10M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6" />,
  connection: <path d="M5 12.55a11 11 0 0 1 14.08 0M1.64 9.5a15 15 0 0 1 20.72 0M12 18a3 3 0 1 1 0-6 3 3 0 0 1 0 6z" />,
  other: (
    <>
      <circle cx="12" cy="12" r="10" />
      <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3" />
      <line x1="12" y1="17" x2="12.01" y2="17" />
    </>
  ),
};

export function TicketsList({ t, lang, tickets, filter, loading, onOpen }) {
  const locale = lang === 'fa' ? 'fa-IR' : 'en-US';
  const filtered = filter === 'all' ? tickets : tickets.filter((tk) => tk.status === filter);

  if (loading) {
    return (
      <div className="tickets-list" id="ticketsList">
        {[0, 1, 2].map((i) => (
          <div className="skeleton-card" key={i}>
            <div className="skeleton-header">
              <div className="skeleton skeleton-badge" />
              <div className="skeleton skeleton-status" />
            </div>
            <div className="skeleton skeleton-line w-50 h-16" />
            <div className="skeleton skeleton-line w-100" />
            <div className="skeleton skeleton-line w-70" />
            <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 12 }}>
              <div className="skeleton skeleton-line w-30 h-8" style={{ margin: 0 }} />
              <div className="skeleton skeleton-line w-30 h-8" style={{ margin: 0 }} />
            </div>
          </div>
        ))}
      </div>
    );
  }

  if (filtered.length === 0) {
    return (
      <div className="tickets-list" id="ticketsList">
        <div className="empty-state">
          <div className="empty-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" strokeWidth="2" /></svg>
          </div>
          <div style={{ fontSize: 16, fontWeight: 600, marginBottom: 6 }}>{t('noTickets')}</div>
          <div style={{ fontSize: 13 }}>{t('createTicketPrompt')}</div>
        </div>
      </div>
    );
  }

  return (
    <div className="tickets-list" id="ticketsList">
      {filtered.map((tk) => {
        const date = parseTs(tk.updated_at || tk.created_at).toLocaleDateString(locale);
        const statusText = t(tk.status) || tk.status;
        const categoryText = t(tk.category) || (tk.category || '').charAt(0).toUpperCase() + (tk.category || '').slice(1);
        const unreadCount = Number(tk.unread_count || 0) || 0;
        return (
          <div
            key={tk.id}
            className={`ticket-card${unreadCount > 0 ? ' unread' : ''}`}
            data-ticket-id={tk.id}
            role="button"
            tabIndex={0}
            onClick={() => onOpen(tk.id)}
            onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onOpen(tk.id); } }}
          >
            <div className="ticket-header">
              <span className="ticket-id">#{tk.user_ticket_number || tk.id}</span>
              <span className="ticket-header-right">
                {unreadCount > 0 && (
                  <span className="unread-pill" data-role="unread">{unreadCount > 99 ? '99+' : unreadCount}</span>
                )}
                <span className={`ticket-status status-${tk.status}`}>{statusText}</span>
              </span>
            </div>
            <div className="ticket-category">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                {CATEGORY_ICONS[tk.category] || CATEGORY_ICONS.other}
              </svg>
              {categoryText}
            </div>
            <div className="ticket-preview" data-role="preview">{tk.last_message || t('noMessagesYet')}</div>
            <div className="ticket-footer">
              <span data-role="date">{date}</span>
              {tk.subscription_username ? <span>{tk.subscription_username}</span> : null}
            </div>
          </div>
        );
      })}
    </div>
  );
}

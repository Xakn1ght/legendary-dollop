import React, { useEffect, useState } from 'react';

import { apiJson } from '../api.js';
import { DashboardHero } from '../components/DashboardHero.jsx';
import { ExpiryCard } from '../components/ExpiryCard.jsx';
import { HealthCard } from '../components/HealthCard.jsx';
import { OnlineCard } from '../components/OnlineCard.jsx';
import { RevenueCard } from '../components/RevenueCard.jsx';
import { fmtDateTime, fmtNum, parseTs } from '../util.js';

// Stats + recent-activity, ported from loadDashboard/displayStats/loadRecentActivity.
// Audit fix: legacy read stats.total_revenue / stats.active_servers which the
// backend never returns → cards showed 0 forever. We render only the fields the
// /api/admin/stats endpoint actually provides.
export function DashboardPage() {
  const [stats, setStats] = useState(null);
  const [activity, setActivity] = useState('loading');

  useEffect(() => {
    (async () => {
      try {
        const { data } = await apiJson('/api/admin/stats');
        if (data.ok) setStats(data.stats || {});
      } catch (_) { /* ignore */ }
      try {
        const { data } = await apiJson('/api/admin/tickets');
        if (data.ok && Array.isArray(data.tickets)) {
          const rows = data.tickets.slice().sort(
            (a, b) => (parseTs(b.updated_at || b.created_at)?.getTime() || 0) - (parseTs(a.updated_at || a.created_at)?.getTime() || 0),
          ).slice(0, 10);
          setActivity(rows);
        } else setActivity([]);
      } catch (_) { setActivity('error'); }
    })();
  }, []);

  const cards = [
    { label: 'Total Users', value: fmtNum(stats?.total_users), color: 'var(--text)' },
    { label: 'Active Subscriptions', value: fmtNum(stats?.active_subscriptions), color: 'var(--success)' },
    { label: 'Total Subscriptions', value: fmtNum(stats?.total_subscriptions), color: 'var(--brand)' },
    { label: 'Pending Tickets', value: fmtNum(stats?.pending_tickets), color: 'var(--warning)' },
  ];

  // .dash-page flips to flex on phones so CSS `order` puts the decision
  // surfaces (money, health, expiring) above the vanity stats — the audit
  // measured 3-4 scrolls before any actionable data on a 390px viewport.
  return (
    <div className="dash-page">
      <DashboardHero />
      <div className="stats-grid dash-stats dash-sec-stats" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 16, marginTop: 20 }}>
        {cards.map((c) => (
          <div className="glass-card stat-card" key={c.label} style={{ padding: 20 }}>
            <div className="stat-label">{c.label}</div>
            <div className="stat-value" style={{ color: c.color }}>{stats ? c.value : '…'}</div>
          </div>
        ))}
      </div>

      <div className="dash-sec-rev" style={{ marginTop: 20 }}>
        <RevenueCard />
      </div>

      <div className="dash-duo dash-sec-duo">
        <HealthCard />
        <ExpiryCard />
      </div>

      <div className="dash-sec-online" style={{ marginTop: 20 }}>
        <OnlineCard />
      </div>

      <div className="glass-card act-card dash-sec-act">
        <div className="act-head">
          <h3>Recent Activity</h3>
          <a className="chip-btn" href="/admin/support.html">Open inbox</a>
        </div>
        {activity === 'loading' && <div className="act-state">Loading activity…</div>}
        {activity === 'error' && <div className="act-state" style={{ color: 'var(--danger)' }}>Failed to load activity</div>}
        {Array.isArray(activity) && activity.length === 0 && <div className="act-state">No recent activity</div>}
        {Array.isArray(activity) && activity.length > 0 && (
          <div className="act-feed">
            {activity.map((t) => <ActivityRow key={t.id} t={t} />)}
          </div>
        )}
      </div>
    </div>
  );
}

/* ── Recent-activity feed (2026-07-09 redesign) ──────────────────────
   The old 4-column table overflowed phones sideways (Time/Status lived
   off-screen) and unbroken message strings stretched the Action column.
   Feed rows: type icon | user + status pill + one-line snippet | short
   relative time. Whole row links to the support inbox. */

function agoShort(d) {
  if (!d) return '—';
  const s = Math.max(0, Math.floor((Date.now() - d.getTime()) / 1000));
  if (s < 60) return 'now';
  if (s < 3600) return `${Math.floor(s / 60)}m`;
  if (s < 86400) return `${Math.floor(s / 3600)}h`;
  return `${Math.floor(s / 86400)}d`;
}

function ActivityRow({ t }) {
  const isPhoto = t.last_message_type === 'photo' || /^\u{1F4F7}/u.test(t.last_message || '');
  // Old cached rows may still carry the legacy camera emoji — strip it.
  const snippet = isPhoto ? 'Photo' : (t.last_message || t.subject || 'Updated ticket').replace(/^\u{1F4F7}\s*/u, '');
  const when = parseTs(t.updated_at || t.created_at);
  const status = String(t.status || '').toLowerCase();
  return (
    <a className="act-row" href="/admin/support.html">
      <span className={'act-ic' + (isPhoto ? ' photo' : '')} aria-hidden="true">
        {isPhoto
          ? (
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" width="15" height="15">
              <path d="M14.5 4h-5L7 7H4a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-3l-2.5-3z" /><circle cx="12" cy="13" r="3" />
            </svg>
          )
          : (
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" width="15" height="15">
              <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
            </svg>
          )}
      </span>
      <span className="act-main">
        <span className="act-top">
          <b className="act-user" dir="auto">{t.user_name || 'User'}</b>
          {status && <i className={'act-st ' + status}>{status}</i>}
          {Number(t.unread_count) > 0 && <em className="act-unread">{t.unread_count}</em>}
        </span>
        <span className="act-snippet" dir="auto">{snippet}</span>
      </span>
      <time className="act-time" title={when ? fmtDateTime(t.updated_at || t.created_at) : ''}>{agoShort(when)}</time>
    </a>
  );
}

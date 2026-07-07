import React, { useEffect, useState } from 'react';

import { apiJson } from '../api.js';
import { DashboardHero } from '../components/DashboardHero.jsx';
import { ExpiryCard } from '../components/ExpiryCard.jsx';
import { HealthCard } from '../components/HealthCard.jsx';
import { RevenueCard } from '../components/RevenueCard.jsx';
import { fmtNum, fmtToman, parseTs } from '../util.js';

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

  const statusColor = (s) => (s === 'open' ? 'var(--success)' : s === 'pending' ? 'var(--warning)' : 'var(--text-muted)');

  return (
    <>
      <DashboardHero />
      <div className="stats-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 16, marginTop: 20 }}>
        {cards.map((c) => (
          <div className="glass-card stat-card" key={c.label} style={{ padding: 20 }}>
            <div className="stat-label">{c.label}</div>
            <div className="stat-value" style={{ color: c.color }}>{stats ? c.value : '…'}</div>
          </div>
        ))}
      </div>

      <div style={{ marginTop: 20 }}>
        <RevenueCard />
      </div>

      <div className="dash-duo">
        <HealthCard />
        <ExpiryCard />
      </div>

      <div className="glass-card" style={{ marginTop: 20 }}>
        <div className="table-header" style={{ padding: '16px 20px' }}>
          <h3 style={{ margin: 0, fontSize: 16 }}>Recent Activity</h3>
        </div>
        <div className="table-responsive">
          <table>
            <thead><tr><th>User</th><th>Action</th><th>Time</th><th>Status</th></tr></thead>
            <tbody>
              {activity === 'loading' && <tr><td colSpan={4} style={{ textAlign: 'center', color: 'var(--text-muted)', padding: 32 }}>Loading activity…</td></tr>}
              {activity === 'error' && <tr><td colSpan={4} style={{ textAlign: 'center', color: 'var(--danger)', padding: 32 }}>Failed to load activity</td></tr>}
              {Array.isArray(activity) && activity.length === 0 && <tr><td colSpan={4} style={{ textAlign: 'center', color: 'var(--text-muted)', padding: 32 }}>No recent activity</td></tr>}
              {Array.isArray(activity) && activity.map((t, i) => (
                <tr key={i}>
                  <td>{t.user_name || 'User'}</td>
                  <td>{(t.last_message || t.subject || 'Updated ticket').slice(0, 80)}</td>
                  <td>{parseTs(t.updated_at || t.created_at)?.toLocaleString() || '—'}</td>
                  <td><span style={{ color: statusColor(t.status), fontWeight: 700 }}>{String(t.status || '—').toUpperCase()}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}

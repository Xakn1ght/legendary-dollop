import React, { useCallback, useEffect, useState } from 'react';

import { apiJson, logout as apiLogout } from './api.js';
import { CommandPalette } from './components/CommandPalette.jsx';
import { Icons, NAV } from './icons.jsx';
import { AuditPage } from './pages/AuditPage.jsx';
import { CouponsPage } from './pages/CouponsPage.jsx';
import { DashboardPage } from './pages/DashboardPage.jsx';
import { DatabasePage } from './pages/DatabasePage.jsx';
import { LogsPage } from './pages/LogsPage.jsx';
import { NotificationsPage } from './pages/NotificationsPage.jsx';
import { ReceiptsPage } from './pages/ReceiptsPage.jsx';
import { ServersPage } from './pages/ServersPage.jsx';
import { SettingsPage } from './pages/SettingsPage.jsx';
import { SubscriptionsPage } from './pages/SubscriptionsPage.jsx';
import { UsersPage } from './pages/UsersPage.jsx';
import { VipPage } from './pages/VipPage.jsx';
import { ShellContext } from './ShellContext.js';
import { useReceipts } from './useReceipts.js';

const TITLES = {
  dashboard: ['Dashboard', 'System Overview'],
  receipts: ['Purchase Receipts', 'Pending Approvals'],
  users: ['User Database', 'Manage Users'],
  vip: ['VIP Management', 'Premium Users'],
  coupons: ['Coupons', 'Discount Campaigns'],
  subscriptions: ['VPN Subscriptions', 'Active Services'],
  servers: ['Server Status', 'Node Monitoring'],
  notifications: ['Broadcasts', 'Send Messages'],
  settings: ['System Settings', 'Configuration'],
  logs: ['System Logs', 'Activity Monitor'],
  audit: ['Audit Trail', 'Admin Action History'],
  database: ['Database', 'Explorer (Admin)'],
};

const VALID = new Set(Object.keys(TITLES));

function pageFromPath() {
  const p = String(window.location.pathname || '').replace('/admin/v3', '/admin');
  const seg = p.replace(/^\/admin\/?/, '').split('/')[0] || 'dashboard';
  if (seg === 'vip') return 'vip';
  return VALID.has(seg) ? seg : 'dashboard';
}

const PAGES = {
  dashboard: DashboardPage,
  receipts: ReceiptsPage,
  users: UsersPage,
  vip: VipPage,
  coupons: CouponsPage,
  subscriptions: SubscriptionsPage,
  servers: ServersPage,
  notifications: NotificationsPage,
  settings: SettingsPage,
  logs: LogsPage,
  audit: AuditPage,
  database: DatabasePage,
};

export function AdminShell({ user }) {
  const [page, setPage] = useState(pageFromPath());
  const [mobileOpen, setMobileOpen] = useState(false);
  const [supportUnread, setSupportUnread] = useState(0);
  const receipts = useReceipts();

  const navigate = useCallback((next, opts = {}) => {
    setMobileOpen(false);
    if (next === 'support') {
      window.location.href = '/admin/support';
      return;
    }
    if (!VALID.has(next)) next = 'dashboard';
    setPage(next);
    receipts.setActivePage(next);
    if (opts.pushState !== false) {
      const path = '/admin/' + next;
      if (window.location.pathname !== path) history.pushState({ page: next }, '', path);
    }
  }, [receipts]);

  useEffect(() => {
    const onPop = () => setPage(pageFromPath());
    window.addEventListener('popstate', onPop);
    return () => window.removeEventListener('popstate', onPop);
  }, []);

  // Support unread badge: 30s poll as fallback + instant recheck when the
  // receipts WS relays support activity (new ticket / new user message).
  useEffect(() => {
    let alive = true;
    let debounce = null;
    const check = async () => {
      try {
        const { data } = await apiJson('/api/admin/tickets');
        if (alive && data.ok && Array.isArray(data.tickets)) {
          setSupportUnread(data.tickets.reduce((s, t) => s + (t.unread_count || 0), 0));
        }
      } catch (_) { /* ignore */ }
    };
    const onActivity = () => {
      clearTimeout(debounce);
      debounce = setTimeout(check, 400); // burst of events → one refetch
    };
    check();
    const id = setInterval(check, 30000);
    window.addEventListener('admin-support-activity', onActivity);
    return () => {
      alive = false;
      clearInterval(id);
      clearTimeout(debounce);
      window.removeEventListener('admin-support-activity', onActivity);
    };
  }, []);

  async function doLogout() {
    await apiLogout();
    try { localStorage.removeItem('admin_session'); } catch (_) { /* ignore */ }
    location.reload();
  }

  const badges = { receipts: receipts.receipts.length, support: supportUnread };
  const [title, subtitle] = TITLES[page] || ['Admin', ''];
  const PageComp = PAGES[page] || DashboardPage;

  const ctx = { page, navigate, receipts };

  return (
    <ShellContext.Provider value={ctx}>
      <div className="app-container" id="adminPanel" style={{ display: 'flex' }}>
        <div className={'overlay' + (mobileOpen ? ' active' : '')} onClick={() => setMobileOpen(false)} />

        <aside className={'sidebar' + (mobileOpen ? ' open' : '')} id="sidebar">
          <div className="sidebar-header">
            <a href="#" className="logo" onClick={(e) => { e.preventDefault(); navigate('dashboard'); }}>
              <div className="logo-icon fx-rocket"><Icons.rocket width={20} height={20} /></div>
              <span>AstroByte</span>
            </a>
          </div>
          <div className="sidebar-content">
            {NAV.map((sec) => (
              <div className="menu-section" key={sec.section}>
                <div className="menu-title">{sec.section}</div>
                {sec.items.map((it) => {
                  const Icon = Icons[it.page];
                  const count = it.badge ? badges[it.badge] : 0;
                  return (
                    <div
                      key={it.page}
                      className={'nav-item' + (page === it.page ? ' active' : '')}
                      data-page={it.page}
                      onClick={() => navigate(it.page)}
                    >
                      {Icon && <Icon />}
                      <span>{it.label}</span>
                      {it.badge && count > 0 && (
                        <span style={{ marginLeft: 'auto', background: 'var(--brand)', color: '#fff', padding: '2px 6px', borderRadius: 6, fontSize: 10, fontWeight: 700 }}>
                          {count > 99 ? '99+' : count}
                        </span>
                      )}
                    </div>
                  );
                })}
              </div>
            ))}
          </div>
          <div className="sidebar-footer">
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 }}>
              <div id="adminAvatar" style={{ width: 40, height: 40, borderRadius: '50%', background: 'var(--bg-card)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 700, border: '1px solid var(--border-subtle)' }}>
                {((user && user.name) || 'A').charAt(0).toUpperCase()}
              </div>
              <div>
                <div style={{ fontSize: 14, fontWeight: 600 }}>{(user && user.name) || 'Admin'}</div>
                <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>Super Admin</div>
              </div>
            </div>
            <button onClick={doLogout} className="btn btn-secondary" style={{ width: '100%', justifyContent: 'flex-start' }}>
              <Icons.logout width={16} height={16} /> Log Out
            </button>
          </div>
        </aside>

        <main className="main-content">
          <header className="top-bar">
            <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
              <button className="mobile-toggle" onClick={() => setMobileOpen((v) => !v)}>
                <Icons.menu width={25} height={25} />
              </button>
              <div className="page-title">
                <h1 id="pageTitle">{title}</h1>
                <p id="pageSubtitle">{subtitle}</p>
              </div>
            </div>
          </header>
          <div className="content-scroll">
            <div className="page-content active rx-page" key={page}>
              <PageComp />
            </div>
          </div>
        </main>

        <CommandPalette navigate={navigate} />
      </div>
    </ShellContext.Provider>
  );
}

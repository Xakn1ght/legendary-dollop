import React, { lazy, Suspense, useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { goBack as backStackGo, hasBackTarget, initBackStack, markNavigatingAway, pushBack, useBackClose } from '../shared/backstack.js';
import { loadSnapshot, saveSnapshot } from '../shared/snapshot.js';
import { getWebApp, hapticImpact } from '../shared/telegram.js';

import { api, canUseSessionStorage, getUrlAuthToken, schedulePrefsSave, setAuthCallbacks, setNetCallbacks, setPrefsApplying } from './api.js';
import { AuthHelpOverlay, NotRegisteredOverlay } from './components/AuthOverlays.jsx';
import { BottomNav } from './components/BottomNav.jsx';
import { Header } from './components/Header.jsx';
import { NotificationsPanel } from './components/NotificationsPanel.jsx';
import { AddSubSheet, ConfirmRemoveSheet, ExportModal } from './components/ShellSheets.jsx';
import { fmtNum } from './format.js';
import { HomePage } from './home/HomePage.jsx';
import { ShellContext } from './ShellContext.js';
import { showToast } from './toast.js';
import { TOUR_STEPS } from './tourSteps.js';
import { localizeCountryDisplay, makeT } from './translations.js';

const LAST_PAGE_KEY = 'tma_last_dashboard_page';
const PAGES = new Set(['home', 'tasks', 'shop', 'profile']);

// Non-home tabs are code-split: Home paints sooner on slow devices and the
// other chunks load on first visit (then stay warm via the import cache).
const TasksPage = lazy(() => import('./pages/TasksPage.jsx').then((m) => ({ default: m.TasksPage })));
const ShopPage = lazy(() => import('./pages/ShopPage.jsx').then((m) => ({ default: m.ShopPage })));
const ProfilePage = lazy(() => import('./pages/ProfilePage.jsx').then((m) => ({ default: m.ProfilePage })));

const TabFallback = () => (
  <div style={{ display: 'flex', justifyContent: 'center', padding: '48px 0', color: 'var(--muted)' }}>
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" width="22" height="22" aria-hidden="true">
      <path d="M21 12a9 9 0 1 1-6.2-8.56">
        <animateTransform attributeName="transform" type="rotate" from="0 12 12" to="360 12 12" dur="0.9s" repeatCount="indefinite" />
      </path>
    </svg>
  </div>
);

function detectLanguage() {
  let saved = null;
  try { saved = localStorage.getItem('lang'); } catch (_) { /* ignore */ }
  if (saved === 'fa' || saved === 'en') return saved;
  try {
    const lc = getWebApp()?.initDataUnsafe?.user?.language_code;
    if (lc && /^fa/i.test(lc)) return 'fa';
  } catch (_) { /* ignore */ }
  return 'en';
}

function setPlatformAttr() {
  try {
    const tg = getWebApp();
    const p = (tg && tg.platform ? String(tg.platform).toLowerCase() : '');
    const ua = navigator.userAgent || '';
    const isMobile = /android|iphone|ipad|ipod/i.test(ua);
    const isDesktopPlatform = /tdesktop|macos|linux|web|windows/i.test(p);
    document.documentElement.setAttribute('data-platform', (isDesktopPlatform || !isMobile) ? 'desktop' : 'mobile');
  } catch (_) { /* ignore */ }
}

function goFullscreen(opts = {}) {
  const request = !!(opts && opts.request);
  try {
    if (window.AstroUI && typeof window.AstroUI.goFullscreen === 'function') {
      window.AstroUI.goFullscreen({ request });
      return;
    }
  } catch (_) { /* ignore */ }
  if (window.__astroTgReadyOnce) window.__astroTgReadyOnce();
  if (window.__astroTgExpandOnce) window.__astroTgExpandOnce();
  if (request && !window.__ASTRO_DESKTOP_MODE) {
    const tg = getWebApp();
    if (!tg) return;
    try { if (typeof tg.requestFullscreen === 'function') tg.requestFullscreen(); } catch (_) { /* ignore */ }
    try { if (tg.viewport && typeof tg.viewport.requestFullscreen === 'function') tg.viewport.requestFullscreen(); } catch (_) { /* ignore */ }
  }
}

const ACCENT_ALLOWED = ['red', 'cyan', 'emerald', 'violet', 'amber', 'champion', 'legend'];

export function ShellApp() {
  const [lang, setLang] = useState(() => detectLanguage());
  const [theme, setThemeState] = useState(() => {
    try { return localStorage.getItem('theme') || document.documentElement.getAttribute('data-theme') || 'dark'; } catch (_) { return 'dark'; }
  });
  const [page, setPage] = useState('home');
  // Cold paint: hydrate last-known data instantly (network refresh replaces
  // it moments later; "Updated" timestamp shows the snapshot's real age).
  const bootSnapRef = useRef({
    subs: loadSnapshot('subs'),
    overview: loadSnapshot('overview'),
  });
  const [cachedSubs, setCachedSubs] = useState(() => bootSnapRef.current.subs?.data || []);
  const [subsLoaded, setSubsLoaded] = useState(false);
  const [currentSubId, setCurrentSubId] = useState(null);
  const [overview, setOverviewState] = useState(() => bootSnapRef.current.overview?.data || null);
  const [overviewUpdatedAt, setOverviewUpdatedAt] = useState(() => bootSnapRef.current.overview?.ts || null);
  const [netDown, setNetDown] = useState(false);
  const [geo, setGeo] = useState({ country: null, countryCode: null, pending: true });
  const [notifications, setNotifications] = useState([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [panelOpen, setPanelOpen] = useState(false);
  const [addSheetOpen, setAddSheetOpen] = useState(false);
  const [removeTarget, setRemoveTarget] = useState(null); // { label, id }
  const [exportState, setExportState] = useState(null);   // { link, showQRFirst }
  const [authHelp, setAuthHelp] = useState(false);
  const [notRegistered, setNotRegistered] = useState(false);
  const [dataLoading, setDataLoading] = useState(false);

  // Terminal auth failure: the overlay is the ONLY thing allowed on screen.
  const authBlocked = authHelp || notRegistered;
  const authBlockedRef = useRef(false);
  authBlockedRef.current = authBlocked;

  const t = useMemo(() => makeT(lang), [lang]);

  const langRef = useRef(lang);
  const pageRef = useRef(page);
  const currentSubIdRef = useRef(null);
  const overviewCacheRef = useRef(new Map());
  const overviewAbortRef = useRef(null);
  const lastOverviewUpdateRef = useRef(null);
  const notifPollRef = useRef(null);
  const notifDelayRef = useRef(5000);
  const notifSigRef = useRef('');
  const notifStopRef = useRef(false);
  const notifHiddenRef = useRef(typeof document !== 'undefined' && document.hidden);
  const notifBoostRef = useRef(null);
  langRef.current = lang;
  pageRef.current = page;
  currentSubIdRef.current = currentSubId;

  // ── Overview ──────────────────────────────────────────────────────
  const setOverview = useCallback((o, forceUpdate = false) => {
    if (!o) return;
    if (!forceUpdate) {
      const cached = overviewCacheRef.current.get(String(o.id || ''));
      if (cached && lastOverviewUpdateRef.current) {
        const minor = Math.abs((cached.used_traffic || 0) - (o.used_traffic || 0)) < 0.1
          && (cached.status || '') === (o.status || '')
          && (cached.username || '') === (o.username || '')
          && Date.now() - lastOverviewUpdateRef.current < 2000;
        if (minor) {
          overviewCacheRef.current.set(String(o.id), o);
          return;
        }
      }
    }
    lastOverviewUpdateRef.current = Date.now();
    if (o.id) overviewCacheRef.current.set(String(o.id), o);
    setOverviewState(o);
  }, []);

  const applyClientGeo = useCallback((payload) => {
    const g = payload && payload.client_geo;
    if (!g) return false;
    const name = g.country || g.label;
    if (!name) return false;
    setGeo({ country: String(name).trim(), countryCode: g.country_code ? String(g.country_code).trim() : null, pending: false });
    return true;
  }, []);

  const endDataLoading = useCallback(() => {
    setDataLoading(false);
    try { if (window.AstroSkeleton) window.AstroSkeleton.ready(); } catch (_) { /* ignore */ }
  }, []);

  const fetchOverview = useCallback(async (opts = {}) => {
    const { instant, skipLoading, skipCache, forceUpdate } = opts;
    if (instant && !skipCache) {
      const fromCache = (currentSubIdRef.current && overviewCacheRef.current.get(String(currentSubIdRef.current))) || null;
      if (fromCache) setOverview(fromCache, forceUpdate);
    }
    if (!skipLoading) setDataLoading(true);
    try {
      if (overviewAbortRef.current) { try { overviewAbortRef.current.abort(); } catch (_) { /* ignore */ } }
      overviewAbortRef.current = new AbortController();
      const j = await api('/api/dashboard/overview', { signal: overviewAbortRef.current.signal });
      if (j.ok && j.subscription) {
        applyClientGeo(j);
        setOverview(j.subscription, forceUpdate);
        setOverviewUpdatedAt(Date.now());
        saveSnapshot('overview', j.subscription);
        goFullscreen({ request: false });
        if (j.subscription.id) {
          currentSubIdRef.current = String(j.subscription.id);
          setCurrentSubId(String(j.subscription.id));
        }
      }
    } catch (e) { /* ignore */ } finally { if (!skipLoading) endDataLoading(); }
  }, [setOverview, applyClientGeo, endDataLoading]);

  const fetchOverviewById = useCallback(async (subId, opts = {}) => {
    const { instant, skipLoading, skipCache, forceUpdate } = opts;
    if (instant && !skipCache) {
      const cached = overviewCacheRef.current.get(String(subId || '')) || null;
      if (cached) setOverview(cached, forceUpdate);
    }
    if (!skipLoading) setDataLoading(true);
    try {
      if (overviewAbortRef.current) { try { overviewAbortRef.current.abort(); } catch (_) { /* ignore */ } }
      overviewAbortRef.current = new AbortController();
      const j = await api('/api/dashboard/overview?sub_id=' + encodeURIComponent(subId), { signal: overviewAbortRef.current.signal });
      if (j.ok) {
        applyClientGeo(j);
        setOverview(j.subscription, forceUpdate);
        setOverviewUpdatedAt(Date.now());
        saveSnapshot('overview', j.subscription);
        goFullscreen({ request: false });
        currentSubIdRef.current = String(subId);
        setCurrentSubId(String(subId));
      }
    } catch (e) { /* ignore */ } finally { if (!skipLoading) endDataLoading(); }
  }, [setOverview, applyClientGeo, endDataLoading]);

  // ── Subscriptions ─────────────────────────────────────────────────
  const loadSubscriptions = useCallback(async (selectId) => {
    try {
      const data = await api('/api/dashboard/subscriptions');
      if (!data.ok) return;
      const subs = data.subscriptions || [];
      setCachedSubs(subs);
      setSubsLoaded(true);
      saveSnapshot('subs', subs);
      if (subs.length > 0) {
        const has = (id) => subs.some((s) => String(s.id) === String(id));
        let savedDefault = null;
        try { savedDefault = localStorage.getItem('defaultSubId') || null; } catch (_) { /* ignore */ }
        let idToSelect = null;
        if (selectId && has(selectId)) idToSelect = selectId;
        else if (savedDefault && has(savedDefault)) idToSelect = savedDefault;
        else if (currentSubIdRef.current && has(currentSubIdRef.current)) idToSelect = currentSubIdRef.current;
        else idToSelect = subs[0].id;
        currentSubIdRef.current = String(idToSelect);
        setCurrentSubId(String(idToSelect));
        try { localStorage.setItem('currentSubId', String(idToSelect)); } catch (_) { /* ignore */ }
        schedulePrefsSave({ current_sub_id: String(idToSelect) });
        fetchOverviewById(idToSelect);
      } else {
        endDataLoading();
      }
    } catch (e) {
      console.error('[DASHBOARD] Error loading subscriptions:', e);
      setSubsLoaded(true);
      endDataLoading();
    }
  }, [fetchOverviewById, endDataLoading]);

  const selectSub = useCallback((id) => {
    currentSubIdRef.current = String(id);
    setCurrentSubId(String(id));
    try { localStorage.setItem('currentSubId', String(id)); } catch (_) { /* ignore */ }
    schedulePrefsSave({ current_sub_id: String(id) });
    fetchOverviewById(id);
  }, [fetchOverviewById]);

  const setDefaultSub = useCallback((id) => {
    try { localStorage.setItem('defaultSubId', String(id || '')); } catch (_) { /* ignore */ }
    schedulePrefsSave({ default_sub_id: String(id || '') });
    showToast(makeT(langRef.current)('defaultSet'), 'success');
    // re-render star fill
    setCachedSubs((cur) => [...cur]);
  }, []);

  // ── Theme / accent / language ─────────────────────────────────────
  const syncTelegramChromeToTheme = useCallback((themeName) => {
    try {
      const tg = getWebApp();
      if (!tg) return;
      const isLight = themeName === 'light';
      const bg = isLight ? '#f1ede5' : '#0a141b';
      const headerBg = isLight ? '#f1ede5' : '#10202a';
      try { if (typeof tg.setBackgroundColor === 'function') tg.setBackgroundColor(bg); } catch (_) { /* ignore */ }
      try { if (typeof tg.setHeaderColor === 'function') tg.setHeaderColor(headerBg); } catch (_) { /* ignore */ }
      try { if (typeof tg.setBottomBarColor === 'function') tg.setBottomBarColor(bg); } catch (_) { /* ignore */ }
    } catch (_) { /* ignore */ }
  }, []);

  const themeRafRef = useRef(0);
  const themeDesiredRef = useRef(null);
  const setTheme = useCallback((next0, { save = true } = {}) => {
    const next = next0 === 'light' ? 'light' : 'dark';
    themeDesiredRef.current = next;
    try { localStorage.setItem('theme', next); } catch (_) { /* ignore */ }
    setThemeState(next);
    if (themeRafRef.current) return;
    themeRafRef.current = requestAnimationFrame(() => {
      themeRafRef.current = 0;
      const target = themeDesiredRef.current;
      const prev = document.documentElement.getAttribute('data-theme') || '';
      if (prev === target) { syncTelegramChromeToTheme(target); return; }
      const apply = () => {
        document.documentElement.setAttribute('data-theme', target);
        if (save) schedulePrefsSave({ theme: target });
        requestAnimationFrame(() => syncTelegramChromeToTheme(target));
      };
      if (prev) {
        // Freeze transitions + decorative animation during the swap (heat fix).
        document.documentElement.setAttribute('data-no-trans', '1');
        apply();
        requestAnimationFrame(() => requestAnimationFrame(() => {
          document.documentElement.removeAttribute('data-no-trans');
        }));
      } else apply();
    });
  }, [syncTelegramChromeToTheme]);

  const setAccent = useCallback((accent, opts = {}) => {
    const next = ACCENT_ALLOWED.indexOf(accent) >= 0 ? accent : 'red';
    const prev = document.documentElement.getAttribute('data-accent') || 'red';
    if (prev !== next) document.documentElement.setAttribute('data-accent', next);
    try { localStorage.setItem('accent', next); } catch (_) { /* ignore */ }
    if (!opts.silent) schedulePrefsSave({ accent: next });
    if (prev !== next) {
      try { window.dispatchEvent(new CustomEvent('astro:accent-changed', { detail: { accent: next } })); } catch (_) { /* ignore */ }
    }
  }, []);

  const setLanguage = useCallback((next0, { save = true } = {}) => {
    const next = next0 === 'fa' ? 'fa' : 'en';
    setLang(next);
    try {
      localStorage.setItem('lang', next);
      localStorage.setItem('tma_lang', next);
    } catch (_) { /* ignore */ }
    document.documentElement.setAttribute('dir', next === 'fa' ? 'rtl' : 'ltr');
    document.documentElement.setAttribute('lang', next);
    try { window.dispatchEvent(new CustomEvent('tma:lang', { detail: { lang: next } })); } catch (_) { /* ignore */ }
    if (save && next !== langRef.current) {
      schedulePrefsSave({ lang: next });
      // Re-fetch with new language (server localizes some strings).
      setTimeout(() => {
        if (currentSubIdRef.current) fetchOverviewById(currentSubIdRef.current, { skipCache: true, forceUpdate: true });
        else fetchOverview({ skipCache: true, forceUpdate: true });
      }, 100);
    }
  }, [fetchOverview, fetchOverviewById]);

  // ── Navigation ────────────────────────────────────────────────────
  const openExternal = useCallback((path, extraParams = {}) => {
    try {
      const authToken = getUrlAuthToken();
      const mustPropagate = !canUseSessionStorage();
      let url = path;
      const params = [];
      if (authToken && mustPropagate) params.push('auth=' + encodeURIComponent(authToken));
      Object.entries(extraParams).forEach(([k, v]) => { if (v != null && v !== '') params.push(k + '=' + encodeURIComponent(v)); });
      params.push('v=' + Date.now());
      url += (url.includes('?') ? '&' : '?') + params.join('&');
      hapticImpact('light');
      markNavigatingAway();
      window.location.href = url;
    } catch (_) { markNavigatingAway(); window.location.href = path; }
  }, []);

  // Tab navigation owns ONE back-stack entry while off home: Telegram back,
  // hardware back, and edge swipe all return to home from any tab.
  const tabBackDisposeRef = useRef(null);
  const navigate = useCallback((next) => {
    if (next === 'arcade') {
      try {
        const authToken = getUrlAuthToken();
        const mustPropagate = !canUseSessionStorage();
        let url = '/webapp/arcade';
        if (authToken && mustPropagate) url += '?auth=' + encodeURIComponent(authToken);
        window.location.href = url;
      } catch (_) { window.location.href = '/webapp/arcade'; }
      return;
    }
    if (!PAGES.has(next)) return;
    setPage(next);
    pageRef.current = next;
    try { document.body.setAttribute('data-page', next); } catch (_) { /* ignore */ }
    try { sessionStorage.setItem(LAST_PAGE_KEY, next); } catch (_) { /* ignore */ }
    window.scrollTo(0, 0);
    if (next === 'home') {
      if (tabBackDisposeRef.current) { tabBackDisposeRef.current(); tabBackDisposeRef.current = null; }
    } else if (!tabBackDisposeRef.current) {
      tabBackDisposeRef.current = pushBack(() => {
        tabBackDisposeRef.current = null;
        hapticImpact('light');
        navigateRef.current('home');
      });
    }
  }, []);
  const navigateRef = useRef(navigate);
  navigateRef.current = navigate;

  const openPurchasePage = useCallback(() => openExternal('/webapp/dashboard/purchase.html'), [openExternal]);
  const openChargePage = useCallback(() => openExternal('/webapp/dashboard/charge.html', { sub_id: currentSubIdRef.current || '' }), [openExternal]);
  const openSupportPage = useCallback((subId = null) => {
    try {
      const authToken = getUrlAuthToken();
      const mustPropagate = !canUseSessionStorage();
      let url = '/webapp/dashboard/support.html';
      const params = [];
      if (authToken && mustPropagate) params.push('auth=' + encodeURIComponent(authToken));
      if (subId) params.push('sub_id=' + encodeURIComponent(subId));
      if (params.length) url += '?' + params.join('&');
      markNavigatingAway();
      window.location.href = url;
    } catch (_) { markNavigatingAway(); window.location.href = '/webapp/dashboard/support.html'; }
  }, []);

  const startInteractiveTour = useCallback(() => {
    try {
      if (authBlockedRef.current) return; // auth failed: error screen only
      if (!(window.AstroTour && typeof window.AstroTour.start === 'function')) return;
      // Completion (finish OR skip) is the only thing that marks the tour as
      // seen — locally AND in server prefs, so the flag survives webview
      // localStorage eviction and follows the USER, not the device.
      const onComplete = () => {
        try { localStorage.setItem('hasSeenWelcome', 'true'); } catch (_) { /* ignore */ }
        schedulePrefsSave({ welcome_shown: true });
      };
      const doStart = () => { try { window.AstroTour.start(TOUR_STEPS, { onComplete }); } catch (_) { /* ignore */ } };
      if (pageRef.current !== 'home') {
        navigateRef.current('home');
        setTimeout(doStart, 400);
      } else doStart();
    } catch (e) { console.error('[TUTORIAL] startInteractiveTour error:', e); }
  }, []);

  const openTutorial = useCallback(() => {
    try {
      hapticImpact('light');
      if (window.AstroTour) window.AstroTour.reset();
      startInteractiveTour();
    } catch (_) { /* ignore */ }
  }, [startInteractiveTour]);

  // ── Notifications ─────────────────────────────────────────────────
  const fetchNotifications = useCallback(async () => {
    try {
      const data = await api('/api/dashboard/notifications');
      if (data.ok) {
        const list = data.notifications || [];
        setNotifications(list);
        setUnreadCount(data.unread_count || 0);
        // Adaptive cadence: reset to fast on any change, otherwise ease the
        // interval up so an idle app stops polling every 5s (battery/data).
        const sig = `${data.unread_count || 0}|${list.map((n) => `${n.id}:${n.read ? 1 : 0}`).join(',')}`;
        if (sig !== notifSigRef.current) {
          notifSigRef.current = sig;
          notifDelayRef.current = 5000;
        } else {
          notifDelayRef.current = Math.min(Math.round(notifDelayRef.current * 1.6), 30000);
        }
      }
    } catch (e) {
      if (e && e.message === 'HTTP 404') {
        notifStopRef.current = true;
        if (notifPollRef.current) { clearTimeout(notifPollRef.current); notifPollRef.current = null; }
      }
    }
  }, []);

  const markNotificationAsRead = useCallback(async (notificationId = null) => {
    try {
      await api('/api/dashboard/notifications/mark-read', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ notification_id: notificationId }),
      });
      await fetchNotifications();
    } catch (e) { console.error('[NOTIFICATION] Error marking notification as read:', e); }
  }, [fetchNotifications]);

  const clearNotificationHistory = useCallback(async () => {
    try {
      await api('/api/dashboard/notifications/clear-history', { method: 'POST', headers: { 'Content-Type': 'application/json' } });
      await fetchNotifications();
    } catch (e) { console.error('[NOTIFICATION] Error clearing history:', e); }
  }, [fetchNotifications]);

  const handleNotificationClick = useCallback(async (n) => {
    await markNotificationAsRead(parseInt(n.id) || 0);
    setPanelOpen(false);
    loadSubscriptions();
    const ticketId = parseInt(n.ticket_id) || 0;
    if (ticketId) {
      try {
        const url = new URL('/webapp/dashboard/support.html', window.location.origin);
        url.searchParams.set('ticket_id', String(ticketId));
        const auth = getUrlAuthToken();
        if (auth && !canUseSessionStorage()) url.searchParams.set('auth', auth);
        window.location.href = url.pathname + '?' + url.searchParams.toString();
      } catch (_) {
        window.location.href = `/webapp/dashboard/support.html?ticket_id=${ticketId}`;
      }
    }
  }, [markNotificationAsRead, loadSubscriptions]);

  // ── Sheets ────────────────────────────────────────────────────────
  const submitAddSubscription = useCallback(async (raw) => {
    const tt = makeT(langRef.current);
    try {
      const r = await api('/api/dashboard/subscriptions/add', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ url: raw }) });
      if (r && r.ok) {
        setAddSheetOpen(false);
        showToast(tt('addedSuccess'), 'success');
        await loadSubscriptions(r.subscription_id || null);
      } else {
        showToast((r && (r.message || r.error)) ? String(r.message || r.error) : tt('addFailed'), 'error');
      }
    } catch (e) {
      showToast(tt('addFailed'), 'error');
    }
  }, [loadSubscriptions]);

  const confirmRemoveSubscription = useCallback(async () => {
    const tt = makeT(langRef.current);
    const subId = removeTarget?.id;
    if (!subId) { showToast(tt('noSubscriptionSelected'), 'error'); return; }
    try {
      const r = await api('/api/dashboard/subscriptions/' + encodeURIComponent(subId), { method: 'DELETE' });
      if (r && r.ok) {
        setRemoveTarget(null);
        await loadSubscriptions();
        if (r.remaining === 0) fetchOverview();
        showToast(tt('removedSuccess'), 'success');
      } else {
        showToast(tt('serverRejectedDeletion'), 'error');
      }
    } catch (e) {
      showToast(tt('removeFailed'), 'error');
    }
  }, [removeTarget, loadSubscriptions, fetchOverview]);

  const openExportModal = useCallback((showQRFirst = false) => {
    const tt = makeT(langRef.current);
    const ov = overviewCacheRef.current.get(String(currentSubIdRef.current || '')) || null;
    const link = ov && ov.subscription_url ? ov.subscription_url : '';
    if (!link) { showToast(tt('noSubOpen'), 'error'); return; }
    setExportState({ link, showQRFirst });
  }, []);

  // ── Update detection ──────────────────────────────────────────────
  // Deploys change the hashed bundle name inside the (no-store) shell HTML.
  // Compare it against the script this session is running; offer a reload
  // instead of letting users ride a stale bundle until the next cold open.
  const [updateReady, setUpdateReady] = useState(false);
  useEffect(() => {
    let stop = false;
    const runningSrc = (() => {
      try {
        const s = document.querySelector('script[src*="/react/assets/index-"]');
        return s ? s.src.split('/').pop() : '';
      } catch (_) { return ''; }
    })();
    if (!runningSrc) return undefined;
    const check = async () => {
      try {
        const r = await fetch('/webapp/dashboard/', { cache: 'no-store', credentials: 'include' });
        if (!r.ok) return;
        const html = await r.text();
        const m = html.match(/\/react\/assets\/(index-[^"']+\.js)/);
        if (!stop && m && m[1] && m[1] !== runningSrc) setUpdateReady(true);
      } catch (_) { /* offline — the net banner handles that story */ }
    };
    const iv = setInterval(check, 5 * 60 * 1000);
    const onVis = () => { if (document.visibilityState === 'visible') check(); };
    document.addEventListener('visibilitychange', onVis);
    return () => { stop = true; clearInterval(iv); document.removeEventListener('visibilitychange', onVis); };
  }, []);

  // ── Offline banner + auto-retry ───────────────────────────────────
  const netDownRef = useRef(false);
  const netRetryRef = useRef(null);
  const retryNow = useCallback(() => {
    // Re-run the boot fetches; any success flips the banner off via netUp.
    loadSubscriptions();
    fetchNotifications();
  }, [loadSubscriptions, fetchNotifications]);
  useEffect(() => {
    setNetCallbacks({
      netDown: () => {
        if (netDownRef.current) return;
        netDownRef.current = true;
        setNetDown(true);
        // Poll every 10s while down (light request; any api() success clears).
        if (!netRetryRef.current) {
          netRetryRef.current = setInterval(() => { retryNow(); }, 10000);
        }
      },
      netUp: () => {
        if (!netDownRef.current) return;
        netDownRef.current = false;
        setNetDown(false);
        if (netRetryRef.current) { clearInterval(netRetryRef.current); netRetryRef.current = null; }
      },
    });
    const onOnline = () => retryNow();
    window.addEventListener('online', onOnline);
    return () => {
      window.removeEventListener('online', onOnline);
      if (netRetryRef.current) clearInterval(netRetryRef.current);
    };
  }, [retryNow]);

  // ── Boot ──────────────────────────────────────────────────────────
  useEffect(() => {
    let cancelled = false;
    setAuthCallbacks({ authHelp: () => setAuthHelp(true), notRegistered: () => setNotRegistered(true) });

    if (window.__astroTgReadyOnce) window.__astroTgReadyOnce();
    setPlatformAttr();
    goFullscreen({ request: true });

    // Apply saved theme/accent/lang immediately (head-boot already set attrs pre-paint).
    setTheme(theme, { save: false });
    try {
      const savedAccent = localStorage.getItem('accent');
      setAccent(ACCENT_ALLOWED.indexOf(savedAccent) >= 0 ? savedAccent : 'red', { silent: true });
    } catch (_) { setAccent('red', { silent: true }); }
    setLanguage(lang, { save: false });

    // First-launch truth comes from server prefs (welcome_shown). Resolved by
    // boot() below: true = seen, false = fresh user, null = couldn't reach API.
    let _welcomeResolve;
    const welcomeShownPromise = new Promise((res) => { _welcomeResolve = res; });

    async function boot() {
      // Server prefs (cross-device theme/lang/accent/sub selection).
      let bootPrefs = null;
      try {
        const r = await api('/api/dashboard/preferences');
        if (r && r.ok && r.prefs) bootPrefs = r.prefs;
      } catch (_) { /* ignore */ }
      _welcomeResolve(bootPrefs ? bootPrefs.welcome_shown === true : null);
      if (cancelled) return;
      if (bootPrefs) {
        setPrefsApplying(true);
        try {
          if (bootPrefs.theme === 'light' || bootPrefs.theme === 'dark') setTheme(bootPrefs.theme, { save: false });
          if (bootPrefs.lang === 'fa' || bootPrefs.lang === 'en') setLanguage(bootPrefs.lang, { save: false });
          if (bootPrefs.current_sub_id) {
            currentSubIdRef.current = String(bootPrefs.current_sub_id);
            setCurrentSubId(String(bootPrefs.current_sub_id));
            try { localStorage.setItem('currentSubId', String(bootPrefs.current_sub_id)); } catch (_) { /* ignore */ }
          }
          if (bootPrefs.default_sub_id) {
            try { localStorage.setItem('defaultSubId', String(bootPrefs.default_sub_id)); } catch (_) { /* ignore */ }
          }
          if (typeof bootPrefs.accent === 'string' && ACCENT_ALLOWED.indexOf(bootPrefs.accent) >= 0) {
            setAccent(bootPrefs.accent, { silent: true });
          }
        } finally { setPrefsApplying(false); }
      }

      // Geo, overview, subs.
      try {
        const result = await api('/api/dashboard/detect-country');
        if (!cancelled && result && result.ok) {
          const name = result.country || result.label;
          if (name) setGeo({ country: String(name).trim(), countryCode: result.country_code ? String(result.country_code).trim() : null, pending: false });
          else setGeo((g) => ({ ...g, pending: false }));
        } else if (!cancelled) setGeo((g) => ({ ...g, pending: false }));
      } catch (e) {
        if (!cancelled) setGeo((g) => ({ ...g, pending: false }));
      }
      if (cancelled) return;
      fetchOverview();
      let defaultId = null, currentId = null;
      try { defaultId = localStorage.getItem('defaultSubId') || null; } catch (_) { /* ignore */ }
      try { currentId = localStorage.getItem('currentSubId') || null; } catch (_) { /* ignore */ }
      loadSubscriptions(defaultId || currentId || undefined);
    }
    boot();

    // Splash hide + first-launch tour.
    //
    // Decision order (server is the source of truth — device storage in
    // Telegram webviews is unreliable AND survives DB resets):
    //   1. #tour=1 deep link            → always replay.
    //   2. server welcome_shown true    → never auto-show (sync local flags).
    //   3. server welcome_shown false   → SHOW, even if this device saw it
    //      before (fresh user / fresh DB — device memory is stale).
    //   4. server unreachable (null)    → fall back to local flags only.
    const checkFirstLaunch = async () => {
      try {
        const hashP = new URLSearchParams(String(location.hash || '').replace(/^#/, ''));
        if (hashP.get('tour') === '1') {
          try { history.replaceState(null, '', location.pathname + location.search); } catch (_) { /* ignore */ }
          if (window.AstroTour) window.AstroTour.reset();
          setTimeout(() => startInteractiveTour(), 500);
          return;
        }
        let serverShown = null;
        try {
          serverShown = await Promise.race([
            welcomeShownPromise,
            new Promise((res) => setTimeout(() => res(null), 7000)),
          ]);
        } catch (_) { /* ignore */ }
        if (cancelled) return;

        let localSeen = false;
        try {
          localSeen = localStorage.getItem('hasSeenWelcome') === 'true'
            || !!(window.AstroTour && window.AstroTour.isCompleted());
        } catch (_) { /* ignore */ }

        let shouldShow;
        if (serverShown === true) {
          shouldShow = false;
          // Backfill device flags so the offline fallback stays consistent.
          try { localStorage.setItem('hasSeenWelcome', 'true'); } catch (_) { /* ignore */ }
        } else if (serverShown === false) {
          shouldShow = true;
          if (window.AstroTour) window.AstroTour.reset(); // clear stale device flag
        } else {
          shouldShow = !localSeen;
        }
        if (shouldShow) setTimeout(() => startInteractiveTour(), 600);
      } catch (_) { /* ignore */ }
    };
    const hideSplash = () => {
      const splash = document.getElementById('bootSplash');
      if (!splash) return;
      splash.classList.add('hide');
      setTimeout(() => { try { splash.remove(); } catch (_) { /* ignore */ } }, 260);
    };
    let splashDone = false;
    const splashOnce = () => { if (!splashDone) { splashDone = true; hideSplash(); checkFirstLaunch(); } };
    try {
      if (window.AstroUI && typeof window.AstroUI.waitForViewportStable === 'function') {
        const waitStable = window.AstroUI.waitForViewportStable(2400);
        const waitExpanded = typeof window.AstroUI.waitForExpanded === 'function' ? window.AstroUI.waitForExpanded(2400) : Promise.resolve(true);
        const waitFs = typeof window.AstroUI.waitForFullscreen === 'function' ? window.AstroUI.waitForFullscreen(3200) : Promise.resolve(true);
        Promise.all([waitStable, waitExpanded, waitFs]).then(splashOnce);
        setTimeout(splashOnce, 4200);
      } else {
        setTimeout(splashOnce, 1200);
      }
    } catch (_) { setTimeout(splashOnce, 1200); }

    // Adaptive notification polling: fast (5s) right after a change or when the
    // user re-engages, easing to 30s while idle, and fully paused while the
    // WebApp is hidden (astro-visibility). Beats a flat 5s poll on battery/data.
    // A generation token makes restarts race-free: an in-flight poll whose gen
    // was superseded by a boost/restart quietly stops instead of double-chaining.
    let pollGen = 0;
    const runNotifPoll = async (gen) => {
      await fetchNotifications();
      if (gen !== pollGen || notifStopRef.current || notifHiddenRef.current || cancelled) return;
      notifPollRef.current = setTimeout(() => runNotifPoll(gen), notifDelayRef.current);
    };
    const startNotifPoll = () => {
      if (notifPollRef.current) { clearTimeout(notifPollRef.current); notifPollRef.current = null; }
      if (notifStopRef.current || notifHiddenRef.current || cancelled) return;
      pollGen += 1;
      runNotifPoll(pollGen);
    };
    const boostNotifPoll = () => {
      // Snap back to the fast cadence and poll now (user is engaged again).
      notifDelayRef.current = 5000;
      startNotifPoll();
    };
    notifBoostRef.current = boostNotifPoll;
    startNotifPoll();
    const onAstroVisibility = (e) => {
      try {
        if (e.detail && e.detail.hidden) {
          notifHiddenRef.current = true;
          pollGen += 1; // supersede any in-flight poll so it won't reschedule
          if (notifPollRef.current) { clearTimeout(notifPollRef.current); notifPollRef.current = null; }
        } else {
          notifHiddenRef.current = false;
          boostNotifPoll();
        }
      } catch (_) { /* ignore */ }
    };
    window.addEventListener('astro-visibility', onAstroVisibility);

    // Restore last visited tab (session only) or #page= hash.
    try {
      const hash = new URLSearchParams(String(location.hash || '').replace(/^#/, ''));
      const hashPage = hash.get('page');
      const sessionPage = sessionStorage.getItem(LAST_PAGE_KEY) || '';
      const target = (hashPage && PAGES.has(hashPage)) ? hashPage : (PAGES.has(sessionPage) ? sessionPage : null);
      if (target && target !== 'home') setTimeout(() => navigateRef.current(target), 40);
    } catch (_) { /* ignore */ }

    // Unified back: Telegram BackButton + hardware/gesture back + edge swipe
    // all pop the same stack (open overlays close first, then tab → home).
    initBackStack();

    let destroySwipe = () => {};
    const swipeTimer = setTimeout(() => {
      try {
        if (window.AstroUI && window.AstroUI.swipeBack) {
          window.AstroUI.swipeBack.setup({
            edgeZone: 16,
            threshold: 80,
            onBack: () => { hapticImpact('light'); backStackGo(); },
            canSwipe: () => hasBackTarget(),
            target: () => document.querySelector('.content'),
          });
          destroySwipe = () => { try { window.AstroUI.swipeBack.destroy(); } catch (_) { /* ignore */ } };
        }
      } catch (_) { /* ignore */ }
    }, 0);

    // Closing confirmation keep-alive on mobile.
    const tg = getWebApp();
    const platform = (tg && tg.platform ? String(tg.platform).toLowerCase() : '');
    const ua = (navigator.userAgent || '').toLowerCase();
    const isMobile = /android|iphone|ipad|ipod/i.test(ua) && !/tdesktop|macos|linux|web|windows|desktop/i.test(platform);
    let closingTimer = null;
    if (isMobile && tg) {
      closingTimer = setInterval(() => {
        if (tg.enableClosingConfirmation && !tg.isClosingConfirmationEnabled) tg.enableClosingConfirmation();
      }, 5000);
    }

    // Legacy globals kept for tour.js / any residual integrations.
    window.openSupport = (subId = null) => openSupportPage(subId);
    window.openTutorialPage = openTutorial;
    window.startInteractiveTour = startInteractiveTour;
    window.startAppTutorial = openTutorial;
    window.syncTelegramChromeToTheme = syncTelegramChromeToTheme;
    window.setAccent = setAccent;
    window.getAccent = () => document.documentElement.getAttribute('data-accent') || 'red';

    return () => {
      cancelled = true;
      if (notifPollRef.current) clearTimeout(notifPollRef.current);
      notifBoostRef.current = null;
      if (closingTimer) clearInterval(closingTimer);
      window.removeEventListener('astro-visibility', onAstroVisibility);
      clearTimeout(swipeTimer);
      destroySwipe();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- mount-only boot sequence
  }, []);

  // Auth failed for good: tear down anything that could show or run behind
  // the error screen (active tour, notification polling).
  useEffect(() => {
    if (!authBlocked) return;
    try { if (window.AstroTour && window.AstroTour.active) window.AstroTour.stop(true); } catch (_) { /* ignore */ }
    notifStopRef.current = true;
    if (notifPollRef.current) { clearTimeout(notifPollRef.current); notifPollRef.current = null; }
  }, [authBlocked]);

  const fmt = useCallback((n, d = 1) => fmtNum(n, lang, d), [lang]);

  // Back closes open shell overlays before navigating.
  useBackClose(panelOpen, () => setPanelOpen(false));
  useBackClose(addSheetOpen, () => setAddSheetOpen(false));
  useBackClose(!!removeTarget, () => setRemoveTarget(null));
  useBackClose(!!exportState, () => setExportState(null));

  const ctx = useMemo(() => ({
    t, lang, setLanguage, page, navigate,
    currentSubId, cachedSubs, subsLoaded, selectSub, setDefaultSub, loadSubscriptions,
    overview, overviewUpdatedAt, fetchOverview, fetchOverviewById, dataLoading,
    geo,
    localizeCountry: (label, code) => localizeCountryDisplay(label, code, lang),
    openAddSheet: () => setAddSheetOpen(true),
    openExportModal,
    openRemoveConfirm: (label, id) => setRemoveTarget({ label, id }),
    openPurchasePage, openChargePage, openSupportPage, openTutorial,
    setAccent,
  }), [t, lang, setLanguage, page, navigate, currentSubId, cachedSubs, subsLoaded, selectSub, setDefaultSub, loadSubscriptions, overview, overviewUpdatedAt, fetchOverview, fetchOverviewById, dataLoading, geo, openExportModal, openPurchasePage, openChargePage, openSupportPage, openTutorial, setAccent]);

  // Terminal auth failure: render ONLY the error screen (no header, content,
  // nav, sheets — nothing else). Toasts stay so the Copy button gives feedback.
  if (authBlocked) {
    return (
      <>
        <div id="toastContainer" className="toasts" aria-live="polite" aria-atomic="true" />
        {notRegistered ? <NotRegisteredOverlay initialLang={lang} /> : <AuthHelpOverlay lang={lang} />}
      </>
    );
  }

  return (
    <ShellContext.Provider value={ctx}>
      <div className="wrap">
        <Header
          theme={theme}
          onThemeChange={(next) => setTheme(next)}
          lang={lang}
          onLangToggle={() => setLanguage(lang === 'en' ? 'fa' : 'en')}
          unreadCount={unreadCount}
          onBellClick={() => { setPanelOpen(true); notifBoostRef.current?.(); }}
          fmt={fmt}
        />

        {updateReady && !netDown && (
          <div className="net-banner update-banner" role="status">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" width="14" height="14" aria-hidden="true">
              <path d="M21 12a9 9 0 1 1-2.64-6.36" /><path d="M21 3v6h-6" />
            </svg>
            <span>{t('updateReady')}</span>
            <button type="button" onClick={() => { try { window.location.reload(); } catch (_) { /* ignore */ } }}>
              {t('updateReload')}
            </button>
          </div>
        )}

        {netDown && (
          <div className="net-banner" role="status">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" width="14" height="14" aria-hidden="true">
              <path d="M1 1l22 22" /><path d="M16.72 11.06A10.94 10.94 0 0 1 19 12.55" /><path d="M5 12.55a10.94 10.94 0 0 1 5.17-2.39" /><path d="M10.71 5.05A16 16 0 0 1 22.58 9" /><path d="M1.42 9a15.91 15.91 0 0 1 4.7-2.88" /><path d="M8.53 16.11a6 6 0 0 1 6.95 0" /><line x1="12" y1="20" x2="12.01" y2="20" />
            </svg>
            <span>{t('netOffline')}</span>
            <button type="button" onClick={retryNow}>{t('netRetry')}</button>
          </div>
        )}

        <div className={`content${dataLoading ? ' loading' : ''}`}>
          {page === 'home' && <HomePage />}
          <Suspense fallback={<TabFallback />}>
            {page === 'tasks' && <TasksPage />}
            {page === 'shop' && <ShopPage />}
            {page === 'profile' && <ProfilePage />}
          </Suspense>
        </div>

        <footer id="appFooter">© <span id="footerYear">{new Date().getFullYear()}</span> AstroBytech Team</footer>
      </div>

      <div id="toastContainer" className="toasts" aria-live="polite" aria-atomic="true" />

      <AddSubSheet t={t} open={addSheetOpen} onClose={() => setAddSheetOpen(false)} onSubmit={submitAddSubscription} />
      <ConfirmRemoveSheet
        t={t}
        open={!!removeTarget}
        label={removeTarget?.label}
        onClose={() => setRemoveTarget(null)}
        onConfirm={confirmRemoveSubscription}
      />
      <ExportModal
        t={t}
        open={!!exportState}
        link={exportState?.link}
        showQRFirst={exportState?.showQRFirst}
        onClose={() => setExportState(null)}
      />
      <NotificationsPanel
        t={t}
        lang={lang}
        open={panelOpen}
        notifications={notifications}
        onClose={() => setPanelOpen(false)}
        onMarkAllRead={() => markNotificationAsRead(null)}
        onClearHistory={clearNotificationHistory}
        onItemClick={handleNotificationClick}
      />

      <BottomNav t={t} activePage={page} onNavigate={navigate} />

      <div className="page-transition-layer" id="pageTransitionLayer" aria-hidden="true" />
    </ShellContext.Provider>
  );
}

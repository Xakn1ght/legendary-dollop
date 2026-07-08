import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { useBackClose } from '../../shared/backstack.js';
import { getWebApp, hapticImpact } from '../../shared/telegram.js';
import { api } from '../api.js';
import { faDigits, fmtDays, fmtGB, fmtNum, formatDate, getLocale } from '../format.js';
import { useShell } from '../ShellContext.js';
import { showToast } from '../toast.js';

import { Flag, FLAG_PIN } from './flags.jsx';
import { useSpeedTest } from './useSpeedTest.js';

// Status → power button / badge / ring styling (legacy setPowerState config).
const STATUS_CONFIG = {
  active: { btnActive: true, bg: 'rgba(34, 197, 94, 0.45)', border: 'rgba(74, 222, 128, 0.85)', textColor: 'rgba(236, 253, 245, 1)', btnGradient: 'linear-gradient(135deg, #22c55e, #4ade80)', btnShadow: '0 12px 32px rgba(34, 197, 94, 0.4), inset 0 3px 10px rgba(255, 255, 255, 0.22)', iconColor: '#ffffff', badgeShadow: '0 6px 16px rgba(34, 197, 94, 0.4)', accent: '#22c55e' },
  disabled: { btnActive: false, bg: 'rgba(82, 91, 104, 0.45)', border: 'rgba(156, 163, 175, 0.75)', textColor: 'rgba(229, 231, 235, 0.95)', btnGradient: 'linear-gradient(135deg, #4b5563, #6b7280)', btnShadow: '0 10px 28px rgba(75, 85, 99, 0.35), inset 0 2px 8px rgba(255, 255, 255, 0.12)', iconColor: '#e5e7eb', badgeShadow: '0 5px 14px rgba(75, 85, 99, 0.35)', accent: '#6b7280' },
  limited: { btnActive: false, bg: 'rgba(234, 179, 8, 0.45)', border: 'rgba(251, 191, 36, 0.85)', textColor: 'rgba(255, 247, 210, 1)', btnGradient: 'linear-gradient(135deg, #d97706, #facc15)', btnShadow: '0 12px 30px rgba(217, 119, 6, 0.4), inset 0 3px 10px rgba(255, 255, 255, 0.2)', iconColor: '#fff7d4', badgeShadow: '0 6px 16px rgba(234, 179, 8, 0.4)', accent: '#f59e0b' },
  expired: { btnActive: false, bg: 'rgba(239, 68, 68, 0.78)', border: 'rgba(254, 202, 202, 0.95)', textColor: '#fff', btnGradient: 'linear-gradient(135deg, #b91c1c, #ef4444)', btnShadow: '0 14px 34px rgba(185, 28, 28, 0.58), inset 0 4px 12px rgba(255, 255, 255, 0.22)', iconColor: '#fff7f7', badgeShadow: '0 8px 18px rgba(239, 68, 68, 0.55)', accent: '#ef4444' },
  on_hold: { btnActive: false, bg: 'rgba(96, 165, 250, 0.45)', border: 'rgba(147, 197, 253, 0.85)', textColor: 'rgba(219, 234, 254, 1)', btnGradient: 'linear-gradient(135deg, #2563eb, #60a5fa)', btnShadow: '0 12px 32px rgba(59, 130, 246, 0.45), inset 0 3px 10px rgba(255, 255, 255, 0.2)', iconColor: '#f8fafc', badgeShadow: '0 6px 16px rgba(96, 165, 250, 0.4)', accent: '#60a5fa' },
  pending: { btnActive: false, bg: 'rgba(196, 181, 253, 0.45)', border: 'rgba(196, 181, 253, 0.85)', textColor: 'rgba(237, 233, 254, 1)', btnGradient: 'linear-gradient(135deg, #7c3aed, #a855f7)', btnShadow: '0 12px 32px rgba(124, 58, 237, 0.45), inset 0 3px 10px rgba(255, 255, 255, 0.2)', iconColor: '#f5f3ff', badgeShadow: '0 6px 16px rgba(167, 139, 250, 0.45)', accent: '#a855f7' },
};
const RING_COLORS = { active: '#22c55e', disabled: '#6b7280', inactive: '#6b7280', limited: '#f59e0b', expired: '#ef4444', on_hold: '#60a5fa', pending: '#a855f7' };

// Usage-based ring color for active subs: green while healthy, warms up as data runs out.
function usageRingColor(usedRatio) {
  if (usedRatio >= 0.9) return '#ef4444';
  if (usedRatio >= 0.75) return '#f97316';
  if (usedRatio >= 0.5) return '#eab308';
  return '#22c55e';
}

const REFRESH_COOLDOWN_S = 300;
const REFRESH_TS_KEY = 'astro_last_manual_refresh';

function computeUsageRatio(sub) {
  const used = Number(sub.used_traffic || 0);
  const limit = Number(sub.data_limit || 0);
  if (!limit || limit <= 0) return 0;
  return Math.max(0, Math.min(1, used / limit));
}
function computeDaysLeft(sub) {
  const expire = Number(sub.expire || 0);
  if (!expire || expire <= 0) return 9999;
  const now = Math.floor(Date.now() / 1000);
  return Math.floor(Math.max(0, expire - now) / 86400);
}

export function HomePage() {
  const shell = useShell();
  const {
    t, lang, overview, geo, currentSubId, cachedSubs, subsLoaded,
    fetchOverview, fetchOverviewById, loadSubscriptions, selectSub,
    setDefaultSub, overviewUpdatedAt, dataLoading,
    openAddSheet, openExportModal, openRemoveConfirm,
    openPurchasePage, openChargePage, openSupportPage, openTutorial,
  } = shell;

  const tg = getWebApp();
  const fmt = useCallback((n, d = 1) => fmtNum(n, lang, d), [lang]);

  const [actionsOpen, setActionsOpen] = useState(false);
  const [ddOpen, setDdOpen] = useState(false);
  const [ddQuery, setDdQuery] = useState('');
  const [statusRefreshing, setStatusRefreshing] = useState(false);
  const [speedOpen, setSpeedOpen] = useState(() => {
    try { return localStorage.getItem('astro_speed_open') === '1'; } catch (_) { return false; }
  });
  const [cooldownLeft, setCooldownLeft] = useState(0);
  const { stats: speedStats, canvasRef } = useSpeedTest(speedOpen);

  const actionsRef = useRef(null);
  const ddRef = useRef(null);

  // Back closes the actions menu / subs dropdown before navigating.
  useBackClose(actionsOpen, () => setActionsOpen(false));
  useBackClose(ddOpen, () => setDdOpen(false));

  // Close actions menu / dropdown on outside click + Escape (legacy parity).
  useEffect(() => {
    const onDocClick = (e) => {
      if (actionsRef.current && !actionsRef.current.contains(e.target)) setActionsOpen(false);
      if (ddRef.current && !ddRef.current.contains(e.target) && !(e.target.closest && e.target.closest('#subsOpenBtn'))) setDdOpen(false);
    };
    const onKey = (e) => { if (e.key === 'Escape') { setActionsOpen(false); setDdOpen(false); } };
    document.addEventListener('click', onDocClick, true);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('click', onDocClick, true);
      document.removeEventListener('keydown', onKey);
    };
  }, []);

  // Manual refresh cooldown ticker — only ticks while a cooldown is running
  // (a permanent 1Hz interval kept the CPU/radio warm for a idle counter).
  const cooldownTimerRef = useRef(null);
  const startCooldownTicker = useCallback(() => {
    const left = () => {
      let last = 0;
      try { last = Number(localStorage.getItem(REFRESH_TS_KEY) || 0); } catch (_) { /* ignore */ }
      return Math.max(0, REFRESH_COOLDOWN_S - Math.floor((Date.now() - last) / 1000));
    };
    setCooldownLeft(left());
    if (cooldownTimerRef.current) clearInterval(cooldownTimerRef.current);
    if (left() <= 0) return;
    cooldownTimerRef.current = setInterval(() => {
      const l = left();
      setCooldownLeft(l);
      if (l <= 0 && cooldownTimerRef.current) {
        clearInterval(cooldownTimerRef.current);
        cooldownTimerRef.current = null;
      }
    }, 1000);
  }, []);
  useEffect(() => {
    startCooldownTicker();
    return () => { if (cooldownTimerRef.current) clearInterval(cooldownTimerRef.current); };
  }, [startCooldownTicker]);

  const fmtCooldown = (secs) => faDigits(Math.floor(secs / 60) + ':' + String(secs % 60).padStart(2, '0'), lang);

  // The status badge and the usage-card refresh button are the SAME action
  // (both re-fetch the current sub, cache-busted) and share ONE cooldown —
  // they only differ in feedback: the badge spins its icon in place, the
  // button goes through the page loading state (Pasha, 2026-07-09).
  const doRefresh = async (silent) => {
    if (statusRefreshing) return;
    if (cooldownLeft > 0) {
      showToast(t('nextRefreshIn').replace('{time}', fmtCooldown(cooldownLeft)), 'info', 1800);
      return;
    }
    try { localStorage.setItem(REFRESH_TS_KEY, String(Date.now())); } catch (_) { /* ignore */ }
    hapticImpact('light');
    setStatusRefreshing(true);
    startCooldownTicker();
    const opts = silent
      ? { skipCache: true, forceUpdate: true, skipLoading: true }
      : { skipCache: true, forceUpdate: true };
    try {
      if (currentSubId) await fetchOverviewById(currentSubId, opts);
      else await fetchOverview(opts);
    } finally {
      setStatusRefreshing(false);
    }
  };
  const manualRefresh = () => doRefresh(false);
  const refreshStatus = () => doRefresh(true);

  const setSpeed = (next) => {
    setSpeedOpen(next);
    try { localStorage.setItem('astro_speed_open', next ? '1' : '0'); } catch (_) { /* ignore */ }
  };

  // "Add to Orbit" chip removed 2026-07-08 (Pasha) — the ring button's app
  // launcher already leads with Orbit, the extra chip was redundant.

  const copyLink = async () => {
    const link = overview?.subscription_url || '';
    if (!link) { showToast(t('noSubOpen'), 'error'); return; }
    try {
      await navigator.clipboard.writeText(link);
      showToast(t('linkCopied'), 'success');
    } catch (_) { showToast(t('copyFailed'), 'error'); }
  };

  const importFromClipboard = async () => {
    try {
      const txt = await navigator.clipboard.readText();
      if (!txt || txt.length < 4) { showToast(t('clipboardEmpty'), 'error'); return; }
      const r = await api('/api/dashboard/subscriptions/add', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ url: txt }) });
      if (r && r.ok) {
        showToast(t('addedSuccess'), 'success');
        await loadSubscriptions(r.subscription_id || null);
      } else {
        showToast((r && (r.message || r.error)) ? String(r.message || r.error) : t('addFailed'), 'error');
      }
    } catch (_) { showToast(t('addFailed'), 'error'); }
  };

  const status = (overview?.status || 'disabled').toLowerCase();
  const cfg = STATUS_CONFIG[status] || STATUS_CONFIG.disabled;
  const used = overview?.used_traffic || 0;
  const limit = overview?.data_limit || 0;
  const usedRatio = limit > 0 ? Math.max(0, Math.min(1, used / limit)) : 0;
  const ringColor = status === 'active' && limit > 0
    ? usageRingColor(usedRatio)
    : (RING_COLORS[status] || RING_COLORS.disabled);
  const circumference = 2 * Math.PI * 56;
  const dleft = overview ? fmtDays(overview.expire) : null;
  const usagePct = limit > 0 ? Math.min(100, Math.round((used / limit) * 100)) : null;

  const locShown = useMemo(() => {
    if (geo.pending) return '—';
    const raw = geo.country || overview?.location_guess || null;
    return raw ? shell.localizeCountry(raw, geo.countryCode) : t('locationUnknown');
  }, [geo, overview, shell, t]);

  const noSubs = subsLoaded && cachedSubs.length === 0;
  const defaultSubId = (() => { try { return localStorage.getItem('defaultSubId') || ''; } catch (_) { return ''; } })();

  const ddRows = useMemo(() => {
    let rows = (cachedSubs || []).slice();
    const q = ddQuery.trim().toLowerCase();
    if (q) {
      rows = rows.filter((s) => {
        const name = s.name || s.marzban_username || s.username || '';
        return String(name).toLowerCase().includes(q) || String(s.id).includes(q);
      });
    }
    return rows;
  }, [cachedSubs, ddQuery]);

  const useDesignedPicker = !!(window.Telegram && window.Telegram.WebApp) && window.innerWidth <= 768;
  const currentSubLabel = useMemo(() => {
    const s = cachedSubs.find((x) => String(x.id) === String(currentSubId));
    return s ? (s.name || s.marzban_username || s.username || ('ID ' + s.id)) : t('selectSubscription');
  }, [cachedSubs, currentSubId, t]);

  const cooldownLabel = cooldownLeft > 0 ? fmtCooldown(cooldownLeft) : t('refreshNow');

  return (
    <>
      {noSubs && (
        <div id="emptyState" className="empty-state-container" style={{ display: 'block' }}>
          <div className="empty-state-art" aria-hidden="true">
            <div className="es-ring es-ring-1" />
            <div className="es-ring es-ring-2" />
            <div className="es-ring es-ring-3" />
            <div className="es-icon">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                <path d="M12 2L2 7l10 5 10-5-10-5z" />
                <path d="M2 17l10 5 10-5" />
                <path d="M2 12l10 5 10-5" />
              </svg>
            </div>
          </div>
          <h2 className="es-title">{t('emptyStateTitle')}</h2>
          <p className="es-desc">{t('emptyStateDesc')}</p>
          <div className="es-actions">
            <button className="es-btn-primary" onClick={openAddSheet}>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" width="18" height="18"><path d="M12 5v14M5 12h14" /></svg>
              <span>{t('addSubscriptionTitle')}</span>
            </button>
            <button className="es-btn-secondary" onClick={openPurchasePage}>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" width="17" height="17"><path d="M6 2L3 6v14a2 2 0 002 2h14a2 2 0 002-2V6l-3-4z" /><line x1="3" y1="6" x2="21" y2="6" /><path d="M16 10a4 4 0 01-8 0" /></svg>
              <span>{t('purchase')}</span>
            </button>
          </div>
        </div>
      )}

      {!noSubs && (
        <div className="sub-controls" style={{ display: 'flex' }}>
          <div className="sub-select-wrapper">
            {!useDesignedPicker ? (
              <select
                id="subSelect"
                className="native-select"
                value={currentSubId || ''}
                onChange={(e) => { if (e.target.value) selectSub(e.target.value); }}
              >
                {cachedSubs.length === 0 && <option value="">{t('selectSubscription')}</option>}
                {cachedSubs.map((s) => (
                  <option key={s.id} value={s.id}>{s.name || s.marzban_username || s.username || ('ID ' + s.id)}</option>
                ))}
              </select>
            ) : (
              <button
                id="subsOpenBtn"
                type="button"
                className="fake-select-btn"
                aria-haspopup="listbox"
                aria-expanded={ddOpen}
                style={{ display: 'flex' }}
                onClick={(e) => { e.preventDefault(); setDdOpen(!ddOpen); }}
              >
                <span id="subsOpenBtnText">{currentSubLabel}</span>
                <svg viewBox="0 0 24 24" width="16" height="16" xmlns="http://www.w3.org/2000/svg"><path d="M6 9l6 6 6-6" fill="none" stroke="currentColor" strokeWidth="2" /></svg>
              </button>
            )}
          </div>
          {cachedSubs.length > 0 && (
            <button id="removeSubBtn" className="btn btn-icon btn-remove" title={t('removeSubscription')} style={{ display: 'flex' }} onClick={() => {
              if (!currentSubId) { showToast(t('noSubscriptionSelected'), 'error'); return; }
              openRemoveConfirm(currentSubLabel, currentSubId);
            }}>
              <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" style={{ width: 20, height: 20, display: 'block', flex: 'none' }}>
                <path d="M10 12V17" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
                <path d="M14 12V17" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
                <path d="M4 7H20" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
                <path d="M6 10V18C6 19.6569 7.34315 21 9 21H15C16.6569 21 18 19.6569 18 18V10" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
                <path d="M9 5C9 3.89543 9.89543 3 11 3H13C14.1046 3 15 3.89543 15 5V7H9V5Z" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </button>
          )}
          <div ref={actionsRef} style={{ display: 'contents' }}>
            <button id="addSubBtn" className="btn btn-icon" title={t('actions')} aria-expanded={actionsOpen} onClick={(e) => { e.preventDefault(); hapticImpact('light'); setActionsOpen(!actionsOpen); }}>
              <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" style={{ width: 20, height: 20, display: 'block', flex: 'none' }}>
                <path d="M7 12L12 12M12 12L17 12M12 12V7M12 12L12 17" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
                <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </button>
            <div id="subActionsMenu" className={`sub-actions-menu${actionsOpen ? ' open' : ''}`} role="menu" aria-hidden={!actionsOpen}>
              <div className="menu-head">
                <div className="menu-title">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" width="14" height="14" aria-hidden="true">
                    <path d="M13 2 3 14h9l-1 8 10-12h-9l1-8z" />
                  </svg>
                  <span>{t('actions')}</span>
                </div>
                <button className="mini-btn" type="button" onClick={() => setActionsOpen(false)}>×</button>
              </div>
              <div className="menu-list">
                {[
                  { action: 'add', title: t('addSubscriptionTitle'), hint: t('pasteLinkHint'), cls: '', icon: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" width="18" height="18"><circle cx="12" cy="12" r="9" /><path d="M12 8v8M8 12h8" /></svg>, onClick: openAddSheet },
                  { action: 'buy', title: t('buyService'), hint: t('buyHint'), cls: '', icon: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" width="18" height="18"><path d="M6 2 3 6v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6l-3-4z" /><path d="M3 6h18" /><path d="M16 10a4 4 0 0 1-8 0" /></svg>, onClick: openPurchasePage },
                  { action: 'charge', title: t('chargeService'), hint: t('chargeHint'), cls: 'secondary', icon: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" width="18" height="18"><path d="M13 2 3 14h9l-1 8 10-12h-9l1-8z" /></svg>, onClick: openChargePage },
                  { action: 'support', title: t('support'), hint: t('supportHint'), cls: 'blue', icon: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" width="18" height="18"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" /></svg>, onClick: openSupportPage },
                  { action: 'tutorial', title: t('tutorial'), hint: t('tutorialHint'), cls: 'gray', icon: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" width="18" height="18"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" /><path d="M4 4.5A2.5 2.5 0 0 1 6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15Z" /><path d="M8 7h8" /><path d="M8 11h5" /></svg>, onClick: openTutorial },
                ].map((mi) => (
                  <button key={mi.action} className="menu-item" type="button" data-action={mi.action} onClick={() => { setActionsOpen(false); mi.onClick(); }}>
                    <span className={`mi-ic${mi.cls ? ' ' + mi.cls : ''}`} aria-hidden="true">{mi.icon}</span>
                    <span className="mi-text">
                      <span className="title">{mi.title}</span>
                      <span className="sub">{mi.hint}</span>
                    </span>
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {!noSubs && useDesignedPicker && (
        <div id="subsDropdown" ref={ddRef} className={`subs-dd${ddOpen ? ' visible' : ''}`}>
          <div className="panel">
            <div className="row">
              <input id="subsSearch" type="text" maxLength={64} placeholder={t('search')} value={ddQuery} onChange={(e) => setDdQuery(e.target.value)} />
            </div>
            <div id="subsList" className="list">
              {ddRows.map((s) => {
                const days = computeDaysLeft(s);
                const usage = Math.round(computeUsageRatio(s) * 100);
                const isDefault = String(s.id) === defaultSubId;
                return (
                  <div
                    key={s.id}
                    className="item"
                    onClick={(ev) => {
                      if (ev.target.closest && (ev.target.closest('.star') || ev.target.closest('.support-btn'))) return;
                      setDdOpen(false);
                      selectSub(String(s.id));
                    }}
                  >
                    <div className="meta">
                      <div className="name">{s.name || s.marzban_username || s.username || ('ID ' + s.id)}</div>
                      <div className="badge">{fmt(usage, 0)}% · {days === 9999 ? '∞' : fmt(days, 0)} {t('days')}</div>
                    </div>
                    <div style={{ display: 'flex', gap: 8 }}>
                      <button
                        className="support-btn"
                        aria-label="Get Support"
                        style={{ padding: '6px 10px', background: 'rgba(139, 92, 246, 0.15)', border: '1px solid rgba(139, 92, 246, 0.3)', borderRadius: 6, color: 'var(--brand, #8b5cf6)', fontSize: 12, fontWeight: 600, cursor: 'pointer', transition: 'all 0.2s' }}
                        onClick={() => { setDdOpen(false); openSupportPage(String(s.id)); }}
                      >
                        <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2" style={{ verticalAlign: 'middle', marginInlineEnd: 4 }}>
                          <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
                        </svg>
                        {t('support')}
                      </button>
                      <button
                        className={`star${isDefault ? ' active' : ''}`}
                        aria-label="Set default"
                        aria-pressed={isDefault}
                        title={t('setDefault') || 'Set as default'}
                        onClick={(e) => { e.stopPropagation(); setDefaultSub(String(s.id)); }}
                      >
                        <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg" fill={isDefault ? 'currentColor' : 'none'} stroke="currentColor" strokeWidth="2" strokeLinejoin="round"><path d="M12 17.27 18.18 21l-1.64-7.03L22 9.24l-7.19-.61L12 2 9.19 8.63 2 9.24l5.46 4.73L5.82 21z" /></svg>
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
            <div className="footer">
              <button className="btn" onClick={() => { setDdOpen(false); openExportModal(false); }}>{t('exportCurrent')}</button>
              <button className="btn" onClick={() => { setDdOpen(false); openExportModal(true); }}>{t('qr')}</button>
              <button className="btn" onClick={() => { setDdOpen(false); importFromClipboard(); }}>{t('importFromClipboard')}</button>
            </div>
          </div>
        </div>
      )}

      {!noSubs && (
        <div className="card vpn-card">
          <div className="vpn-lava" aria-hidden="true">
            <div className="vpn-blob vpn-blob-1" />
            <div className="vpn-blob vpn-blob-2" />
            <div className="vpn-blob vpn-blob-3" />
            <div className="vpn-blob vpn-blob-4" />
          </div>

          <div className="vpn-card-top">
            <div className="date-badge" id="currentDate">{formatDate(lang)}</div>
            <div className="vpn-card-icon">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" width="22" height="22">
                <circle cx="12" cy="12" r="2" />
                <path d="M16.24 7.76a6 6 0 0 1 0 8.49" />
                <path d="M7.76 16.24a6 6 0 0 1 0-8.49" />
                <path d="M19.07 4.93a10 10 0 0 1 0 14.14" />
                <path d="M4.93 19.07a10 10 0 0 1 0-14.14" />
              </svg>
            </div>
          </div>

          <div className="vpn-card-body">
            <div className="vpn-balance-row">
              <span className="vpn-balance" id="balance">{overview ? fmtGB(limit ? limit - used : null, lang, t) : '—'}</span>
              <span className="vpn-balance-unit" id="balanceUnit">GB</span>
            </div>
            <div className="vpn-username" id="username">{overview ? (overview.username || '—') : t('loading')}</div>
          </div>

          {usagePct !== null && (
            <div className="vpn-usage-track" id="vpnUsageTrack" style={{ display: 'flex' }}>
              <div
                className="vpn-usage-fill"
                id="vpnUsageFill"
                style={{
                  width: usagePct + '%',
                  background: usagePct >= 85 ? 'rgba(248,113,113,0.85)' : usagePct >= 60 ? 'rgba(251,191,36,0.75)' : 'rgba(255,255,255,0.65)',
                }}
              />
              <span className="vpn-usage-pct" id="vpnUsagePct">{usagePct}%</span>
            </div>
          )}

          <div className="vpn-card-footer">
            <div className="vpn-card-actions">
              <button id="cardCopyBtn" className="vpn-action-btn" title={t('copyLink')} onClick={copyLink}>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" width="17" height="17"><rect x="9" y="9" width="13" height="13" rx="2" /><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" /></svg>
              </button>
              <button id="cardQRBtn" className="vpn-action-btn" title="QR Code" onClick={() => openExportModal(true)}>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="17" height="17"><rect x="3" y="3" width="7" height="7" rx="1" /><rect x="14" y="3" width="7" height="7" rx="1" /><rect x="3" y="14" width="7" height="7" rx="1" /><rect x="14" y="14" width="3" height="3" rx="0.5" /><rect x="18" y="14" width="3" height="3" rx="0.5" /><rect x="14" y="18" width="3" height="3" rx="0.5" /><rect x="18" y="18" width="3" height="3" rx="0.5" /></svg>
              </button>
            </div>
            {/* Badge doubles as the refresh trigger (replaced the separate
                refresh button — both re-check the same status). */}
            <button
              type="button"
              className={`status-badge ${status}${statusRefreshing ? ' refreshing' : ''}${cooldownLeft > 0 ? ' cooldown' : ''}`}
              id="statusBadge"
              title={t('refresh')}
              aria-label={`${t(status) || status} — ${t('refresh')}`}
              onClick={refreshStatus}
            >
              {t(status) || status}
              <svg className="badge-refresh-ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M21 12a9 9 0 1 1-2.64-6.36" /><path d="M21 3v6h-6" /></svg>
            </button>
          </div>
        </div>
      )}

      {!noSubs && (
        <div className="card center" id="connectionCard">
          <div className="power-wrap">
            <svg className="usage-ring-svg" id="usageRingSvg" viewBox="0 0 130 130" xmlns="http://www.w3.org/2000/svg" aria-hidden="true" style={{ opacity: limit > 0 ? 1 : 0.5 }}>
              <defs>
                <linearGradient id="usageGrad" x1="0%" y1="0%" x2="100%" y2="0%">
                  <stop offset="0%" stopColor="var(--brand)" />
                  <stop offset="100%" stopColor="var(--brandDark)" />
                </linearGradient>
              </defs>
              <circle className="track" cx="65" cy="65" r="56" fill="none" strokeWidth="8" />
              <circle
                className="progress"
                id="usageRing"
                cx="65" cy="65" r="56" fill="none"
                stroke={ringColor}
                strokeWidth="8"
                strokeLinecap="round"
                strokeDasharray={`${circumference} ${circumference}`}
                strokeDashoffset={limit > 0 ? circumference * (1 - usedRatio) : circumference}
              />
            </svg>
            {/* The big ring button = "connect me": opens the app chooser
                (Orbit first, then the per-platform VPN apps) on every OS. */}
            <button
              id="powerBtn"
              className={`power-btn${cfg.btnActive ? '' : ' inactive'} orbit-enabled`}
              style={{ background: cfg.btnGradient, boxShadow: cfg.btnShadow }}
              aria-label={t('appLaunchTitle')}
              onClick={() => { hapticImpact('light'); shell.openAppLauncher(); }}
            >
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" aria-hidden="true" style={{ fill: cfg.iconColor }}>
                <path d="M18,8.5A2.5,2.5,0,1,1,15.5,6,2.5,2.5,0,0,1,18,8.5Zm-1.341,9.213a11.038,11.038,0,0,1-.828,2.222A7.634,7.634,0,0,1,9,24H8V19.143A3.214,3.214,0,0,0,4.857,16H0V15A7.634,7.634,0,0,1,4.065,8.169a11.038,11.038,0,0,1,2.222-.828C9.96,2.38,14.221.178,20.458,0H20.5A3.489,3.489,0,0,1,24,3.551C23.82,9.877,21.686,14,16.659,17.713ZM21,3.508A.5.5,0,0,0,20.515,3c-5.461.162-8.839,1.966-12.038,6.431a28.441,28.441,0,0,0-2.206,3.737,6.287,6.287,0,0,1,4.561,4.561,28.376,28.376,0,0,0,3.737-2.206C19.042,12.317,20.846,8.949,21,3.508ZM1.631,18.728C.857,19.5.38,21.831.211,22.8L0,24l1.2-.212c.961-.17,3.278-.649,4.052-1.425a2.58,2.58,0,0,0,0-3.635A2.613,2.613,0,0,0,1.631,18.728Z" />
              </svg>
            </button>
            <div className={`usage-badge${status === 'active' ? ' ok' : status === 'limited' ? ' warn' : status === 'expired' ? ' bad' : ''}`} id="usageBadge" aria-live="polite">
              {limit > 0 ? fmt(Math.round(usedRatio * 100), 0) + '%' : '∞'}
            </div>
          </div>
          <div className="location">
            <span className="flag" id="flag">
              {geo.country || overview?.location_guess
                ? <Flag countryName={geo.country || overview?.location_guess} countryCode={geo.countryCode} />
                : FLAG_PIN}
            </span>
            <span className="name" id="locName">{locShown}</span>
          </div>
          <div className="usage-meta">
            <div className="updated">
              <span id="overviewUpdatedLabel">{t('lastUpdated')}</span>{' '}
              <strong id="overviewUpdated">
                {overviewUpdatedAt ? new Date(overviewUpdatedAt).toLocaleTimeString(getLocale(lang), { hour: '2-digit', minute: '2-digit' }) : '—'}
              </strong>
            </div>
            <button id="autoRefreshBtn" className={`mini-btn${cooldownLeft > 0 ? ' cooldown' : ''}`} type="button" disabled={cooldownLeft > 0} onClick={manualRefresh}>
              {cooldownLabel}
            </button>
          </div>

          <div className="stats-grid" style={{ width: '100%', marginTop: 12 }}>
            <div className="stat-item">
              <div className="stat-label" id="labelAvailable">{t('available')}</div>
              <div className="stat-value" id="balance2">{overview ? fmtGB(limit ? limit - used : null, lang, t) : '—'}</div>
            </div>
            <div className="stat-item">
              <div className="stat-label" id="labelUsed">{t('used')}</div>
              <div className="stat-value" id="usedVal">{overview ? fmtGB(used, lang, t) : '—'}</div>
            </div>
            <div className="stat-item">
              <div className="stat-label" id="labelExpires">{t('expiresIn')}</div>
              <div className="stat-value" id="expireVal">{dleft == null ? '—' : (dleft === '∞' ? '∞' : fmt(Number(dleft) || 0, 0))}</div>
              <div className="stat-sub" id="daysLabel">{(String(dleft) === '1' && lang === 'en') ? t('day') : t('days')}</div>
            </div>
          </div>

          <div className="usage-extra" style={{ width: '100%' }}>
            <div className="info-row">
              <div className="label" id="labelTotalLimit">{t('totalLimit')}</div>
              <div className="value" id="limitVal">{overview ? (limit ? fmtGB(limit, lang, t) : '∞') : '—'}</div>
            </div>
            <div className="info-row">
              <div className="label" id="labelLocation">{t('location')}</div>
              <div className="value" id="locName2">{locShown}</div>
            </div>
          </div>
        </div>
      )}

      {!noSubs && (
        <div className="card" id="speedCard">
          <div className="card-head">
            <div className="card-title" id="speedTitle">{t('speedTest')}</div>
            <button
              id="speedToggleBtn"
              className="mini-btn"
              type="button"
              aria-expanded={speedOpen}
              onClick={() => { hapticImpact('light'); setSpeed(!speedOpen); }}
            >
              {speedOpen ? t('hide') : t('show')}
            </button>
          </div>
          <div id="speedPanel" className="speed-panel" hidden={!speedOpen}>
            <div className="speed-chips">
              <div className="speed-chip">
                <div className="label" id="labelDownload">{t('download')}</div>
                <div className="value" id="downv">
                  {speedStats.down == null ? '—' : <>{fmt(speedStats.down, 1)} <span style={{ fontSize: '0.75em', opacity: 0.8 }}>{t('mbps')}</span></>}
                </div>
              </div>
              <div className="speed-chip">
                <div className="label" id="labelUpload">{t('upload')}</div>
                <div className="value" id="upv">
                  {speedStats.up == null ? '—' : <>{fmt(speedStats.up, 1)} <span style={{ fontSize: '0.75em', opacity: 0.8 }}>{t('mbps')}</span></>}
                </div>
              </div>
              <div className="speed-chip">
                <div className="label" id="labelPing">{t('ping')}</div>
                <div className="value" id="pingv">{speedStats.ping == null ? '—' : fmt(speedStats.ping, 0) + ' ms'}</div>
              </div>
            </div>
            <canvas id="chart" ref={canvasRef} />
            <div className="chart-meta" id="speedUpdated">
              {speedStats.updatedAt
                ? t('lastUpdated') + ': ' + new Date(speedStats.updatedAt).toLocaleTimeString(getLocale(lang), { hour: '2-digit', minute: '2-digit', second: '2-digit' })
                : '—'}
            </div>
          </div>
        </div>
      )}
    </>
  );
}

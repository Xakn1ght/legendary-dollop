import React, { useCallback, useEffect, useMemo, useState } from 'react';

import { useBackClose } from '../../shared/backstack.js';
import { getTelegramPhotoUrl, getWebApp, hapticSelection } from '../../shared/telegram.js';
import { api, getUrlAuthToken } from '../api.js';
import { useShell } from '../ShellContext.js';
import { showToast } from '../toast.js';

import { i18nProfile, vipI18n } from './profileI18n.js';

const ACCENTS = [
  { key: 'red', swatch: '#ec5652' },
  { key: 'cyan', swatch: '#22d3ee' },
  { key: 'emerald', swatch: '#34d399' },
  { key: 'violet', swatch: '#a78bfa' },
  { key: 'amber', swatch: '#fbbf24' },
  { key: 'champion', swatch: '#e8a300', locked: true },
  { key: 'legend', swatch: '#c026d3', locked: true },
];

const ACHIEVEMENTS = [
  { key: 'firstLaunch', unlocked: () => true },
  { key: 'starCollector', unlocked: (u) => (u.stars || 0) > 0 },
  { key: 'champion', unlocked: (u) => (u.stars || 0) >= 5 },
  { key: 'vipMember', unlocked: (u) => !!u.is_vip },
  { key: 'taskMaster', unlocked: (u) => (u.referral_count || 0) >= 1 },
  { key: 'superStar', unlocked: (u) => (u.stars || 0) >= 10 },
  { key: 'royalty', unlocked: (u) => (u.stars || 0) >= 20 },
  { key: 'onFire', unlocked: (u) => (u.referral_count || 0) >= 5 },
];

function perfStoredMode() {
  try {
    const v = localStorage.getItem('astro_perf');
    if (v === 'lite' || v === 'full') return v;
  } catch (_) { /* ignore */ }
  return 'auto';
}

function SettingsRow({ onClick, icon, title, desc, right }) {
  return (
    <div
      className="settings-item"
      onClick={onClick}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => { if (e.key === 'Enter') onClick?.(); }}
    >
      <div className="settings-item-left">
        <div className="settings-item-icon" aria-hidden="true">{icon}</div>
        <div className="settings-item-text">
          <div className="settings-item-title">{title}</div>
          <div className="settings-item-desc">{desc}</div>
        </div>
      </div>
      <div className="settings-item-right">{right}</div>
    </div>
  );
}

const Arrow = () => (
  <svg className="settings-arrow" viewBox="0 0 24 24"><path d="M8.59 16.59L13.17 12 8.59 7.41 10 6l6 6-6 6-1.41-1.41z" /></svg>
);

export function ProfilePage() {
  const { lang, setLanguage, setAccent, openSupportPage, openTutorial } = useShell();
  const tt = useCallback((key) => (i18nProfile[lang] || i18nProfile.en)[key] || i18nProfile.en[key] || key, [lang]);
  const vt = useCallback((key) => (vipI18n[lang] || vipI18n.en)[key] || vipI18n.en[key] || key, [lang]);
  const getLocale = () => (lang === 'fa' ? 'fa-IR-u-nu-arabext' : 'en-US-u-nu-latn');
  const fmt = useCallback((n, digits = 0) => {
    try {
      return new Intl.NumberFormat(getLocale(), { minimumFractionDigits: digits, maximumFractionDigits: digits }).format(n);
    } catch (_) { return String(n); }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lang]);

  const [user, setUser] = useState(null);
  const [subsCount, setSubsCount] = useState(null);
  const [referrals, setReferrals] = useState(null);
  const [copied, setCopied] = useState(null); // 'chatId' | 'referralCode' | 'link'
  const [accent, setAccentState] = useState(() => document.documentElement.getAttribute('data-accent') || 'red');
  const [unlockedThemes, setUnlockedThemes] = useState([]);
  const [packBadge, setPackBadge] = useState('');
  const [notifOn, setNotifOn] = useState(() => {
    try { return localStorage.getItem('notifications') !== 'off'; } catch (_) { return true; }
  });
  const [perfMode, setPerfMode] = useState(perfStoredMode());
  const [autoClaim, setAutoClaim] = useState({ open: false, enabled: false, subId: '', subs: [], pickerOpen: false });
  const [vip, setVip] = useState(null); // { step, plans, cardNumber, selectedPlanId, orderId, amount, receiptData, receiptName }
  // Telegram home-screen shortcut (Bot API 8.0). Only shown when the client
  // supports it and the icon isn't already installed.
  const [canAddHome, setCanAddHome] = useState(false);

  // Back unwinds overlays innermost-first: voucher picker → auto-claim modal;
  // in the VIP modal it steps payment→plans before closing.
  useBackClose(autoClaim.open && !autoClaim.pickerOpen, () => setAutoClaim((c) => ({ ...c, open: false })));
  useBackClose(autoClaim.open && autoClaim.pickerOpen, () => setAutoClaim((c) => ({ ...c, pickerOpen: false })));
  useBackClose(!!vip && vip.step !== 2, () => setVip(null));
  useBackClose(!!vip && vip.step === 2, () => setVip((cur) => (cur ? { ...cur, step: 1 } : cur)));

  const isVip = !!user?.is_vip;

  const loadProfile = useCallback(async () => {
    try {
      const data = await api('/api/dashboard/overview');
      if (data.ok && data.user) setUser(data.user);
    } catch (_) { /* ignore */ }
    try {
      const subs = await api('/api/dashboard/subscriptions');
      if (subs.ok) setSubsCount((subs.subscriptions || []).length);
    } catch (_) { /* ignore */ }
    try {
      const refs = await api('/api/dashboard/referrals');
      if (refs.ok) setReferrals(refs);
    } catch (_) { /* ignore */ }
    // Accent unlocks: permanent prefs + owned season pack coupons.
    try {
      const themes = new Set();
      let badge = '';
      const prefsRes = await api('/api/dashboard/preferences');
      const prefs = (prefsRes && prefsRes.ok && prefsRes.prefs) ? prefsRes.prefs : {};
      (Array.isArray(prefs.unlocked_themes) ? prefs.unlocked_themes : []).forEach((th) => themes.add(th));
      if (prefs.badge) badge = prefs.badge;
      try {
        const season = await api('/api/dashboard/season');
        const coupons = (season && season.ok && Array.isArray(season.coupons)) ? season.coupons : [];
        coupons.forEach((c) => {
          if (c.coupon_type !== 'vip_pack' && c.coupon_type !== 'legend_pack') return;
          const p = c.payload || {};
          if (p.theme) themes.add(p.theme);
          if (p.badge && (c.coupon_type === 'legend_pack' || !badge)) badge = p.badge;
        });
      } catch (_) { /* ignore */ }
      setUnlockedThemes([...themes]);
      setPackBadge(badge);
    } catch (_) { /* ignore */ }
  }, []);

  useEffect(() => { loadProfile(); }, [loadProfile]);

  useEffect(() => {
    const onAccent = (e) => { if (e.detail?.accent) setAccentState(e.detail.accent); };
    window.addEventListener('astro:accent-changed', onAccent);
    return () => window.removeEventListener('astro:accent-changed', onAccent);
  }, []);

  const copyValue = async (type, value, toastMsg) => {
    try {
      await navigator.clipboard.writeText(String(value || ''));
      setCopied(type);
      setTimeout(() => setCopied(null), 2000);
      showToast(toastMsg, 'success', 2500);
    } catch (_) { /* ignore */ }
  };

  const referralLink = referrals?.referral_link
    || (user?.referral_code ? `https://t.me/AstroByteBot?start=${user.referral_code}` : '');

  const cyclePerf = () => {
    const order = ['auto', 'lite', 'full'];
    const next = order[(order.indexOf(perfStoredMode()) + 1) % order.length];
    try {
      if (next === 'auto') { localStorage.removeItem('astro_perf'); localStorage.removeItem('astro_perf_auto'); }
      else localStorage.setItem('astro_perf', next);
    } catch (_) { /* ignore */ }
    try { document.documentElement.setAttribute('data-perf', next === 'lite' ? 'lite' : 'full'); } catch (_) { /* ignore */ }
    setPerfMode(next);
    hapticSelection();
  };
  const perfLabel = () => {
    if (perfMode === 'lite') return tt('perfLite');
    if (perfMode === 'full') return tt('perfFull');
    const resolved = document.documentElement.getAttribute('data-perf') === 'lite' ? tt('perfLite') : tt('perfFull');
    return `${tt('perfAuto')} (${resolved})`;
  };

  // ── Auto-claimer ──────────────────────────────────────────────────
  const openAutoClaim = async () => {
    let enabled = false, subId = '', subs = [];
    try {
      const r = await api('/api/dashboard/preferences');
      if (r && r.ok && r.prefs) {
        enabled = !!r.prefs.auto_claim;
        subId = r.prefs.voucher_auto_sub_id ? String(r.prefs.voucher_auto_sub_id) : '';
      }
    } catch (_) { /* ignore */ }
    try {
      const r = await api('/api/dashboard/subscriptions');
      subs = (r.ok && r.subscriptions ? r.subscriptions : [])
        .filter((s) => String(s.status || '').toLowerCase() === 'active' && (s.marzban_username || s.username));
    } catch (_) { /* ignore */ }
    setAutoClaim({ open: true, enabled, subId, subs, pickerOpen: false });
  };

  const saveAutoClaim = async () => {
    if (!isVip) { showToast(tt('vipRequired'), 'error'); return; }
    try {
      const r = await api('/api/dashboard/preferences', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ auto_claim: autoClaim.enabled, voucher_auto_sub_id: autoClaim.subId || null }),
      });
      if (r && r.ok) {
        showToast(tt('save'), 'success');
        setAutoClaim((c) => ({ ...c, open: false }));
      } else {
        showToast(r?.error === 'vip_required' ? tt('vipRequired') : tt('failedToLoad'), 'error');
      }
    } catch (_) { showToast(tt('failedToLoad'), 'error'); }
  };

  const autoClaimSubLabel = autoClaim.subId
    ? (autoClaim.subs.find((s) => String(s.id) === autoClaim.subId)?.name
      || autoClaim.subs.find((s) => String(s.id) === autoClaim.subId)?.marzban_username
      || '#' + autoClaim.subId)
    : tt('noActiveSubscription');

  // ── VIP flow ──────────────────────────────────────────────────────
  const authQS = () => {
    const token = getUrlAuthToken();
    return token ? '?auth=' + encodeURIComponent(token) : '';
  };

  const openVipPurchase = async () => {
    setVip({ step: 1, plans: null, cardNumber: '', selectedPlanId: null });
    try {
      const r = await api('/api/dashboard/vip/plans' + authQS());
      if (r && r.ok) {
        setVip((cur) => (cur ? { ...cur, plans: r.plans || [], cardNumber: r.card_number || '' } : cur));
      } else {
        setVip((cur) => (cur ? { ...cur, plans: [] } : cur));
      }
    } catch (_) { setVip((cur) => (cur ? { ...cur, plans: [] } : cur)); }
  };

  const continueVip = async () => {
    if (!vip?.selectedPlanId) return;
    try {
      const r = await api('/api/dashboard/vip/purchase' + authQS(), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ plan_id: vip.selectedPlanId }),
      });
      if (r && r.ok) {
        const plan = vip.plans.find((p) => p.id === vip.selectedPlanId);
        setVip((cur) => ({ ...cur, step: 2, orderId: r.order_id, amount: plan?.price || 0, cardNumber: r.card_number || cur.cardNumber }));
      } else {
        showToast(String(r?.error || tt('failedToLoad')), 'error');
      }
    } catch (e) { showToast(String(e?.message || tt('failedToLoad')), 'error'); }
  };

  const onVipReceipt = (e) => {
    const file = e.target.files && e.target.files[0];
    e.target.value = '';
    if (!file) return;
    const allowed = ['image/jpeg', 'image/png', 'image/jpg'];
    if (!allowed.includes(file.type) && !/\.(jpg|jpeg|png)$/i.test(file.name)) {
      showToast('فقط فایل‌های JPG و PNG مجاز است', 'error');
      return;
    }
    const reader = new FileReader();
    reader.onload = () => setVip((cur) => (cur ? { ...cur, receiptData: reader.result, receiptName: file.name } : cur));
    reader.readAsDataURL(file);
  };

  const submitVip = async () => {
    if (!vip?.orderId || !vip?.receiptData) return;
    try {
      const r = await api('/api/dashboard/vip/receipt' + authQS(), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ order_id: vip.orderId, receipt_image: vip.receiptData }),
      });
      if (r && r.ok) setVip((cur) => ({ ...cur, step: 3 }));
      else showToast(String(r?.error || tt('failedToLoad')), 'error');
    } catch (e) { showToast(String(e?.message || tt('failedToLoad')), 'error'); }
  };

  const copyVipCard = async () => {
    try {
      await navigator.clipboard.writeText((vip?.cardNumber || '').replace(/[\s-]/g, ''));
      showToast(vt('copied'), 'success');
    } catch (_) { /* ignore */ }
  };

  // Install the Mini App as a home-screen shortcut (opens straight back into
  // Telegram, so auth keeps working — a plain PWA can't, the dashboard is
  // Telegram-only). Re-checks status after the prompt to hide the row on add.
  const addToHomeScreen = () => {
    const tg = getWebApp();
    if (!tg || typeof tg.addToHomeScreen !== 'function') return;
    hapticSelection();
    try { tg.addToHomeScreen(); } catch (_) { /* ignore */ }
    try {
      tg.checkHomeScreenStatus?.((status) => {
        if (status === 'added' || status === 'unsupported') setCanAddHome(false);
      });
    } catch (_) { /* ignore */ }
  };

  useEffect(() => {
    const tg = getWebApp();
    if (!tg || typeof tg.checkHomeScreenStatus !== 'function') return;
    try {
      tg.checkHomeScreenStatus((status) => { setCanAddHome(status === 'missed'); });
    } catch (_) { /* ignore */ }
  }, []);

  // VIP promo copy (hardcoded fa/en, legacy parity)
  const vipPromo = useMemo(() => {
    const fa = lang === 'fa';
    if (isVip) {
      const until = user?.vip_until ? new Date(user.vip_until) : null;
      if (!until) {
        return { cls: ' is-vip', title: fa ? 'VIP مادام‌العمر' : 'Lifetime VIP', desc: fa ? 'از ۲۰٪ تخفیف لذت ببرید' : 'Enjoy 20% off everything', btn: '✓', disabled: true };
      }
      const daysLeft = Math.max(0, Math.ceil((until.getTime() - Date.now()) / 86400000));
      return {
        cls: ' is-vip',
        title: fa ? 'عضویت VIP فعال' : 'VIP Active',
        desc: fa ? `${fmt(daysLeft)} روز باقی‌مانده` : `${fmt(daysLeft)} days remaining`,
        btn: fa ? 'تمدید' : 'Renew',
      };
    }
    return {
      cls: '',
      title: fa ? 'ارتقا به VIP' : 'Upgrade to VIP',
      desc: fa ? '۲۰٪ تخفیف روی همه خریدها + پلن‌های اختصاصی' : '20% discount on all purchases + exclusive plans',
      btn: fa ? 'خرید VIP' : 'Get VIP',
    };
  }, [isVip, user, lang, fmt]);

  const categoryBadge = useMemo(() => {
    const fa = lang === 'fa';
    if (isVip) {
      const until = user?.vip_until ? new Date(user.vip_until) : null;
      if (until) {
        const daysLeft = Math.ceil((until.getTime() - Date.now()) / 86400000);
        if (daysLeft > 0 && daysLeft <= 30) return { cls: ' vip', text: `VIP (${fmt(daysLeft)}${fa ? 'ر' : 'd'})` };
      }
      return { cls: ' vip', text: 'VIP' };
    }
    if (user?.category === 'premium') return { cls: ' premium', text: tt('premium') };
    return { cls: '', text: tt('free') };
  }, [isVip, user, lang, fmt, tt]);

  const joinDate = user?.created_at
    ? new Date(user.created_at).toLocaleDateString(getLocale(), { year: 'numeric', month: 'long', day: 'numeric' })
    : '—';

  // Avatar: Telegram only exposes photo_url to attachment-menu apps, so the
  // backend fetches it via the Bot API — load it as an authed blob.
  const [fetchedAvatar, setFetchedAvatar] = useState(null);
  useEffect(() => {
    let cancelled = false;
    let objUrl = null;
    (async () => {
      try {
        const r = await api('/api/dashboard/profile-photo', { raw: true });
        const blob = await r.blob();
        if (blob && blob.size > 100 && !cancelled) {
          objUrl = URL.createObjectURL(blob);
          setFetchedAvatar(objUrl);
        }
      } catch (_) { /* no photo / offline — initial letter stays */ }
    })();
    return () => { cancelled = true; if (objUrl) URL.revokeObjectURL(objUrl); };
  }, []);

  const avatarUrl = user?.photo_url || fetchedAvatar || getTelegramPhotoUrl();

  return (
    <>
      <section className="profile-hero">
        <div className="profile-header">
          <div className="profile-avatar-wrapper">
            <div className="profile-avatar-orbit">
              <span className="orbit-icon" aria-hidden="true">
                <svg viewBox="0 0 24 24" fill="currentColor" width="12" height="12"><path d="M12 2l1.8 6.2L20 10l-6.2 1.8L12 18l-1.8-6.2L4 10l6.2-1.8L12 2z" /></svg>
              </span>
            </div>
            <div className={`profile-avatar${avatarUrl ? ' has-photo' : ''}`} id="userAvatar">
              {avatarUrl
                ? <img src={avatarUrl} alt="" onError={(e) => { e.target.parentElement.classList.remove('has-photo'); e.target.replaceWith((user?.full_name?.[0] || '?').toUpperCase()); }} />
                : (user?.full_name?.[0] || '?').toUpperCase()}
            </div>
          </div>
          <div className="profile-info">
            <div className="profile-name" id="userName">{user ? (user.full_name || tt('astronaut')) : '...'}</div>
            <div className="profile-username" id="userUsername">{user?.username ? '@' + user.username : ''}</div>
            <div className="profile-badges" id="userBadges">
              <span className={`profile-badge${categoryBadge.cls}`} id="userCategory">
                <span className="svg-icon">
                  <svg viewBox="0 0 24 24" fill="currentColor" width="12" height="12"><path d="M12 2l2.4 7.4H22l-6.2 4.5 2.4 7.3-6.2-4.5-6.2 4.5 2.4-7.3L2 9.4h7.6z" /></svg>
                </span>
                <span id="userCategoryText">{categoryBadge.text}</span>
              </span>
              {packBadge && (
                <span className="profile-badge" id="userPackBadge" style={{ background: 'rgba(var(--brandRgb),0.18)' }}>
                  <span className="svg-icon">
                    <svg viewBox="0 0 24 24" fill="currentColor" width="12" height="12"><path d="M20 7h-3.3l1.1-3.1-1.9-.7L14.6 7H9.4L8.1 3.2l-1.9.7L7.3 7H4a1 1 0 0 0-1 1v2a3 3 0 0 0 3 3h.3l.8 7.1a1 1 0 0 0 1 .9h7.8a1 1 0 0 0 1-.9l.8-7.1h.3a3 3 0 0 0 3-3V8a1 1 0 0 0-1-1z" /></svg>
                  </span>
                  <span id="userPackBadgeText">{packBadge}</span>
                </span>
              )}
            </div>
          </div>
        </div>
        <div className="profile-stats-grid">
          <div className="profile-stat-item">
            <div className="profile-stat-icon" aria-hidden="true">
              <svg viewBox="0 0 24 24" fill="currentColor" width="16" height="16"><path d="M21 18v1a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v1h-9a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h9zm-9-2h10V8H12v8zm4-2.5a1.5 1.5 0 1 1 0-3 1.5 1.5 0 0 1 0 3z" /></svg>
            </div>
            <div className="profile-stat-value" id="statCredit">{fmt(user?.credit || 0)}</div>
            <div className="profile-stat-label">{tt('credit')}</div>
          </div>
          <div className="profile-stat-item">
            <div className="profile-stat-icon" aria-hidden="true">
              <svg viewBox="0 0 24 24" fill="currentColor" width="16" height="16"><path d="M12 17.27 18.18 21l-1.64-7.03L22 9.24l-7.19-.61L12 2 9.19 8.63 2 9.24l5.46 4.73L5.82 21z" /></svg>
            </div>
            <div className="profile-stat-value" id="statStars">{fmt(user?.stars || 0)}</div>
            <div className="profile-stat-label">{tt('stars')}</div>
          </div>
          <div className="profile-stat-item">
            <div className="profile-stat-icon" aria-hidden="true">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="16" height="16"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" /><circle cx="9" cy="7" r="4" /><path d="M23 21v-2a4 4 0 0 0-3-3.87" /><path d="M16 3.13a4 4 0 0 1 0 7.75" /></svg>
            </div>
            <div className="profile-stat-value" id="statReferrals">{fmt(referrals?.total ?? user?.referral_count ?? 0)}</div>
            <div className="profile-stat-label">{tt('referrals')}</div>
          </div>
        </div>
        <div className={`vip-promo-section${vipPromo.cls}`} id="vipPromoSection">
          <div className="vip-promo-content">
            <div className="vip-promo-icon">
              <svg viewBox="0 0 24 24" fill="currentColor" width="22" height="22"><path d="M5 16 3 5l5.5 5L12 4l3.5 6L21 5l-2 11H5zm14 3H5v-2h14v2z" /></svg>
            </div>
            <div className="vip-promo-text">
              <div className="vip-promo-title" id="vipPromoTitle">{vipPromo.title}</div>
              <div className="vip-promo-desc" id="vipPromoDesc">{vipPromo.desc}</div>
            </div>
          </div>
          <button
            className="vip-promo-btn"
            id="vipPromoBtn"
            style={vipPromo.disabled ? { pointerEvents: 'none' } : undefined}
            onClick={openVipPurchase}
          >
            <span id="vipBtnText">{vipPromo.btn}</span>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" width="14" height="14"><path d="M5 12h14M12 5l7 7-7 7" /></svg>
          </button>
        </div>
      </section>

      <section className="profile-section">
        <div className="profile-section-title">
          <div className="icon-box">
            <svg viewBox="0 0 24 24" fill="currentColor" width="15" height="15"><path d="M13 2 3 14h9l-1 8 10-12h-9l1-8z" /></svg>
          </div>
          <span>{tt('progressRewards')}</span>
        </div>
        <div className="profile-info-row">
          <span className="profile-info-label">{tt('activeSubscriptions')}</span>
          <span className="profile-info-value" id="infoSubs">{subsCount == null ? '—' : fmt(subsCount)}</span>
        </div>
      </section>

      <section className="profile-section">
        <div className="profile-section-title">
          <div className="icon-box">
            <svg viewBox="0 0 24 24" fill="currentColor" width="15" height="15"><path d="M12 17.27 18.18 21l-1.64-7.03L22 9.24l-7.19-.61L12 2 9.19 8.63 2 9.24l5.46 4.73L5.82 21z" /></svg>
          </div>
          <span>{tt('achievements')}</span>
        </div>
        <div className="achievements-grid" id="achievementsGrid">
          {ACHIEVEMENTS.map((a) => {
            const unlocked = user ? a.unlocked(user) : a.key === 'firstLaunch';
            return (
              <div key={a.key} className={`achievement-item${unlocked ? '' : ' locked'}`}>
                <div className="achievement-icon">
                  <svg viewBox="0 0 24 24" fill="currentColor" width="20" height="20"><path d="M12 17.27 18.18 21l-1.64-7.03L22 9.24l-7.19-.61L12 2 9.19 8.63 2 9.24l5.46 4.73L5.82 21z" /></svg>
                </div>
                <div className="achievement-name">{tt(a.key)}</div>
              </div>
            );
          })}
        </div>
      </section>

      <section className="profile-section">
        <div className="profile-section-title">
          <div className="icon-box" style={{ background: 'linear-gradient(135deg, #34d399, #059669)' }}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="15" height="15"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" /><circle cx="9" cy="7" r="4" /></svg>
          </div>
          <span>{tt('referralProgram')}</span>
        </div>
        <div className="referral-card">
          <div className="referral-header">
            <span className="referral-title">
              <span className="svg-icon">
                <svg viewBox="0 0 24 24" fill="currentColor" width="14" height="14"><path d="M20 12v10H4V12M2 7h20v5H2zM12 22V7M12 7H7.5a2.5 2.5 0 1 1 0-5C11 2 12 7 12 7zM12 7h4.5a2.5 2.5 0 1 0 0-5C13 2 12 7 12 7z" /></svg>
              </span>
              <span>{tt('inviteFriends')}</span>
            </span>
            <span className="referral-count" id="referralCountBadge">{fmt(referrals?.total || 0)} {tt('invited')}</span>
          </div>
          <div className="referral-link-box">
            <div className="referral-link" id="referralLinkDisplay">{referralLink || '—'}</div>
            <button
              className="referral-copy-btn"
              onClick={() => copyValue('link', referralLink, tt('linkCopied'))}
              style={copied === 'link' ? { background: '#34d399' } : undefined}
            >
              {copied === 'link' ? '✓' : tt('copyLink')}
            </button>
          </div>
          <div className="referral-stats">
            <div className="referral-stat">
              <div className="referral-stat-value" id="refStatTotal">{fmt(referrals?.total || 0)}</div>
              <div className="referral-stat-label">{tt('totalInvites')}</div>
            </div>
            <div className="referral-stat">
              <div className="referral-stat-value" id="refStatActive">{fmt(referrals?.active || 0)}</div>
              <div className="referral-stat-label">{tt('activeUsers')}</div>
            </div>
            <div className="referral-stat">
              <div className="referral-stat-value" id="refStatEarned">{fmt(referrals?.earned || 0)}</div>
              <div className="referral-stat-label">{tt('creditsEarned')}</div>
            </div>
          </div>
        </div>
      </section>

      <section className="profile-section">
        <div className="profile-section-title">
          <div className="icon-box">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="15" height="15"><circle cx="12" cy="12" r="10" /><path d="M12 8v4l3 3" /></svg>
          </div>
          <span>{tt('accountInformation')}</span>
        </div>
        <div className="profile-info-row">
          <span className="profile-info-label">{tt('userId')}</span>
          <span className="profile-info-value" id="infoUserId">{user?.id ?? '—'}</span>
        </div>
        <div className="profile-info-row">
          <span className="profile-info-label">{tt('chatId')}</span>
          <span className="profile-info-value">
            <span id="infoChatId">{user?.chat_id ?? '—'}</span>{' '}
            <button
              className="profile-copy-btn"
              onClick={() => copyValue('chatId', user?.chat_id, tt('copied'))}
              style={copied === 'chatId' ? { background: '#34d399' } : undefined}
            >
              {copied === 'chatId' ? '✓' : tt('copy')}
            </button>
          </span>
        </div>
        <div className="profile-info-row">
          <span className="profile-info-label">{tt('referralCode')}</span>
          <span className="profile-info-value">
            <span id="infoReferralCode">{user?.referral_code ?? '—'}</span>{' '}
            <button
              className="profile-copy-btn"
              onClick={() => copyValue('referralCode', user?.referral_code, tt('copied'))}
              style={copied === 'referralCode' ? { background: '#34d399' } : undefined}
            >
              {copied === 'referralCode' ? '✓' : tt('copy')}
            </button>
          </span>
        </div>
        <div className="profile-info-row">
          <span className="profile-info-label">{tt('memberSince')}</span>
          <span className="profile-info-value" id="infoJoinDate">{joinDate}</span>
        </div>
      </section>

      <section className="profile-section">
        <div className="profile-section-title">
          <div className="icon-box" style={{ background: 'linear-gradient(135deg, #60a5fa, #2563eb)' }}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="15" height="15"><circle cx="12" cy="12" r="10" /><path d="M12 6v6l4 2" /></svg>
          </div>
          <span>{tt('recentActivity')}</span>
        </div>
        <div className="activity-timeline" id="activityTimeline">
          <div className="activity-item success">
            <div className="activity-icon">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" width="14" height="14"><path d="M20 6L9 17l-5-5" /></svg>
            </div>
            <div className="activity-content">
              <div className="activity-title">{tt('accountCreated')}</div>
              <div className="activity-time" id="activityJoinDate">{joinDate}</div>
            </div>
          </div>
        </div>
      </section>

      <section className="profile-section">
        <div className="profile-section-title">
          <div className="icon-box" style={{ background: 'linear-gradient(135deg, #a78bfa, #7c3aed)' }}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="15" height="15"><circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" /></svg>
          </div>
          <span>{tt('settings')}</span>
        </div>
        <div className="settings-list">
          <SettingsRow
            onClick={() => {
              const next = !notifOn;
              setNotifOn(next);
              try { localStorage.setItem('notifications', next ? 'on' : 'off'); } catch (_) { /* ignore */ }
              showToast(next ? 'Notifications enabled' : 'Notifications disabled', 'success');
            }}
            icon={<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="18" height="18"><path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 7h18s-3 0-3-7" /><path d="M13.7 21a2 2 0 0 1-3.4 0" /></svg>}
            title={tt('notifications')}
            desc={tt('notificationsDesc')}
            right={<div className={`toggle-switch${notifOn ? ' active' : ''}`} id="notifToggle" />}
          />
          <SettingsRow
            onClick={() => setLanguage(lang === 'en' ? 'fa' : 'en')}
            icon={<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="18" height="18"><path d="M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20z" /><path d="M2 12h20" /><path d="M12 2a15 15 0 0 1 0 20" /><path d="M12 2a15 15 0 0 0 0 20" /></svg>}
            title={tt('language')}
            desc={tt('languageDesc')}
            right={<><span className="settings-item-value" id="currentLangLabel">{lang === 'fa' ? tt('persian') : tt('english')}</span><Arrow /></>}
          />
          <div className="settings-item settings-item--accent">
            <div className="settings-item-left">
              <div className="settings-item-icon" aria-hidden="true">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" width="18" height="18"><circle cx="13.5" cy="6.5" r="2.5" /><circle cx="19" cy="12" r="2.5" /><circle cx="17" cy="18.5" r="2.5" /><circle cx="8" cy="19" r="2.5" /><path d="M12 2a10 10 0 1 0 0 20c1.1 0 1.5-1.4.7-2.2-.8-.8-.8-2 0-2.8a2 2 0 0 1 1.4-.6h2.4a3.5 3.5 0 0 0 3.5-3.5C20 8 16.4 4 12 2z" /></svg>
              </div>
              <div className="settings-item-text">
                <div className="settings-item-title">{tt('accentColor')}</div>
                <div className="settings-item-desc">{tt('accentColorDesc')}</div>
              </div>
            </div>
            <div className="settings-item-right">
              <div className="accent-swatches" role="radiogroup" aria-label="Accent color">
                {ACCENTS.filter((a) => !a.locked || unlockedThemes.includes(a.key)).map((a) => (
                  <button
                    key={a.key}
                    type="button"
                    className={`accent-swatch${accent === a.key ? ' is-active' : ''}`}
                    data-accent-key={a.key}
                    role="radio"
                    aria-checked={accent === a.key}
                    aria-label={a.key}
                    tabIndex={accent === a.key ? 0 : -1}
                    style={{ '--swatch': a.swatch }}
                    onClick={() => { setAccent(a.key); setAccentState(a.key); }}
                  />
                ))}
              </div>
            </div>
          </div>
          <SettingsRow
            onClick={cyclePerf}
            icon={<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="18" height="18"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z" /></svg>}
            title={tt('perfMode')}
            desc={tt('perfModeDesc')}
            right={<><span className="settings-item-value" id="perfModeValue">{perfLabel()}</span><Arrow /></>}
          />
          <SettingsRow
            onClick={openAutoClaim}
            icon={<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="18" height="18"><path d="M12 2l1.8 6.2L20 10l-6.2 1.8L12 18l-1.8-6.2L4 10l6.2-1.8L12 2z" /><path d="M19 13l.9 3.1L23 17l-3.1.9L19 21l-.9-3.1L15 17l3.1-.9L19 13z" /></svg>}
            title={tt('autoClaimer')}
            desc={tt('autoClaimerDesc')}
            right={<><span className="settings-item-value" id="autoClaimerValue">{autoClaim.enabled ? tt('enabled') : tt('disabled')}</span><Arrow /></>}
          />
          <SettingsRow
            onClick={() => showToast('Privacy settings coming soon', 'info')}
            icon={<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="18" height="18"><path d="M19 11H5a2 2 0 0 0-2 2v7a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7a2 2 0 0 0-2-2z" /><path d="M7 11V7a5 5 0 0 1 10 0v4" /></svg>}
            title={tt('privacySecurity')}
            desc={tt('privacyDesc')}
            right={<Arrow />}
          />
          <SettingsRow
            onClick={() => openSupportPage()}
            icon={<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="18" height="18"><path d="M12 18h.01" /><path d="M9.1 9a3 3 0 1 1 5.8 1c0 2-3 2-3 4" /><circle cx="12" cy="12" r="10" /></svg>}
            title={tt('helpCenter')}
            desc={tt('helpDesc')}
            right={<Arrow />}
          />
          <SettingsRow
            onClick={openTutorial}
            icon={<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="18" height="18"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" /><path d="M4 4.5A2.5 2.5 0 0 1 6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15Z" /></svg>}
            title={tt('appTutorial')}
            desc={tt('appTutorialDesc')}
            right={<Arrow />}
          />
          {canAddHome && (
            <SettingsRow
              onClick={addToHomeScreen}
              icon={<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="18" height="18"><rect x="5" y="2" width="14" height="20" rx="3" /><path d="M12 7v6M9 10h6" /></svg>}
              title={tt('addToHome')}
              desc={tt('addToHomeDesc')}
              right={<Arrow />}
            />
          )}
        </div>
      </section>

      {/* ── Auto-claimer modal ── */}
      {autoClaim.open && (
        <div
          id="autoClaimModalOverlay"
          className="visible"
          onClick={(e) => { if (e.target.id === 'autoClaimModalOverlay') setAutoClaim((c) => ({ ...c, open: false })); }}
        >
          <div id="autoClaimModal" role="dialog" aria-modal="true" aria-labelledby="autoClaimModalTitle">
            <div id="autoClaimModalHeader">
              <div id="autoClaimModalTitle">{tt('autoClaimer')}</div>
              <button id="autoClaimModalClose" onClick={() => setAutoClaim((c) => ({ ...c, open: false }))}>{tt('close')}</button>
            </div>
            <div id="autoClaimModalBody">
              <div className="auto-claim-row">
                <div className="auto-claim-text">
                  <div className="auto-claim-title">{tt('autoClaimerToggle')}</div>
                  <div className="auto-claim-sub">{tt('autoClaimerToggleDesc')}</div>
                </div>
                <div className="auto-claim-actions">
                  <div
                    className={`toggle-switch${autoClaim.enabled ? ' active' : ''}`}
                    id="autoClaimToggle"
                    role="switch"
                    aria-checked={autoClaim.enabled}
                    tabIndex={0}
                    onClick={() => {
                      if (!isVip) { showToast(tt('vipRequired'), 'error'); openVipPurchase(); return; }
                      setAutoClaim((c) => ({ ...c, enabled: !c.enabled }));
                    }}
                  />
                </div>
              </div>
              <div className="auto-claim-row">
                <div className="auto-claim-text">
                  <div className="auto-claim-title">{tt('voucherAutoTarget')}</div>
                  <div className="auto-claim-sub">{tt('voucherAutoTargetDesc')}</div>
                </div>
              </div>
              <div
                className={`auto-picker-trigger${autoClaim.pickerOpen ? ' open' : ''}`}
                id="voucherPickerTrigger"
                role="button"
                tabIndex={0}
                style={!isVip ? { opacity: 0.7 } : undefined}
                onClick={() => {
                  if (!isVip) { showToast(tt('vipRequired'), 'error'); openVipPurchase(); return; }
                  setAutoClaim((c) => ({ ...c, pickerOpen: !c.pickerOpen }));
                }}
                onKeyDown={(e) => { if (e.key === 'Enter') setAutoClaim((c) => ({ ...c, pickerOpen: !c.pickerOpen })); }}
              >
                <div className="auto-picker-left">
                  <div className="auto-picker-label">{tt('selectSubscription')}</div>
                  <div className="auto-picker-value" id="voucherPickerValue">{autoClaimSubLabel}</div>
                </div>
                <svg className="auto-picker-caret" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="16" height="16"><path d="M6 9l6 6 6-6" /></svg>
              </div>
              {autoClaim.pickerOpen && (
                <div id="voucherPickerList" style={{ marginTop: 8 }}>
                  {autoClaim.subs.length === 0 && <div className="voucher-pick-item" style={{ cursor: 'default' }}><div className="voucher-pick-title">{tt('noActiveSubscription')}</div></div>}
                  {autoClaim.subs.map((s) => (
                    <div
                      key={s.id}
                      className={`voucher-pick-item${autoClaim.subId === String(s.id) ? ' selected' : ''}`}
                      role="button"
                      tabIndex={0}
                      onClick={() => setAutoClaim((c) => ({ ...c, subId: String(s.id), pickerOpen: false }))}
                      onKeyDown={(e) => { if (e.key === 'Enter') setAutoClaim((c) => ({ ...c, subId: String(s.id), pickerOpen: false })); }}
                    >
                      <div className="voucher-pick-title">{s.name || s.marzban_username || s.username || ('#' + s.id)}</div>
                      <div className="voucher-pick-sub">{[s.plan_name, String(s.status || '').toUpperCase()].filter(Boolean).join(' · ')}</div>
                    </div>
                  ))}
                </div>
              )}
              <div className="auto-claim-row">
                <button className="auto-claim-btn" onClick={() => setAutoClaim((c) => ({ ...c, open: false }))}>{tt('cancel')}</button>
                <button className="auto-claim-btn primary" onClick={saveAutoClaim}>{tt('save')}</button>
              </div>
              {!isVip && (
                <div className="auto-claim-sub" id="autoClaimVipHint" style={{ display: 'block' }}>{tt('vipRequiredDesc')}</div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ── VIP modal ── */}
      {vip && (
        <div className="vip-modal-overlay active" id="vipModalOverlay">
          <div className="vip-modal">
            <div className="vip-modal-header">
              <div className="vip-modal-title">
                <span className="svg-icon">
                  <svg viewBox="0 0 24 24" fill="currentColor" width="18" height="18"><path d="M5 16 3 5l5.5 5L12 4l3.5 6L21 5l-2 11H5zm14 3H5v-2h14v2z" /></svg>
                </span>
                <span id="vipModalTitle">{vt('modalTitle')}</span>
              </div>
              <button className="vip-modal-close" onClick={() => setVip(null)}>×</button>
            </div>
            <div className="vip-modal-body">
              {vip.step === 1 && (
                <div className="vip-step" id="vipStep1">
                  <div className="vip-benefits">
                    {['benefitDiscount', 'benefitPlans', 'benefitSupport', 'benefitBadge'].map((k) => (
                      <div className="vip-benefit-item" key={k}>
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" width="14" height="14"><path d="M20 6L9 17l-5-5" /></svg>
                        <span className="vip-benefit-text">{vt(k)}</span>
                      </div>
                    ))}
                  </div>
                  <div className="vip-plans-title" id="selectPlanTitle">{vt('selectPlan')}</div>
                  <div className="vip-plans-grid" id="vipPlansGrid">
                    {vip.plans === null && <div style={{ padding: 12 }}>{tt('loading')}</div>}
                    {vip.plans !== null && vip.plans.map((p) => (
                      <div
                        key={p.id}
                        className={`vip-plan-card${p.id === '3_months' ? ' popular' : ''}${vip.selectedPlanId === p.id ? ' selected' : ''}`}
                        role="button"
                        tabIndex={0}
                        onClick={() => setVip((cur) => ({ ...cur, selectedPlanId: p.id }))}
                        onKeyDown={(e) => { if (e.key === 'Enter') setVip((cur) => ({ ...cur, selectedPlanId: p.id })); }}
                      >
                        <div className="vip-plan-info">
                          <div className="vip-plan-duration">{lang === 'fa' ? (p.label_fa || p.label_en) : (p.label_en || p.label_fa)}</div>
                          <div className="vip-plan-price">{fmt(p.price)} {vt('toman')}</div>
                        </div>
                        {p.id === '3_months' && <div className="vip-plan-badge">{vt('popular')}</div>}
                        {p.is_lifetime && <div className="vip-plan-badge">{vt('bestValue')}</div>}
                      </div>
                    ))}
                  </div>
                </div>
              )}
              {vip.step === 2 && (
                <div className="vip-step vip-payment-step active" id="vipStep2">
                  <div className="vip-card-info">
                    <div className="vip-card-label" id="cardLabel">{vt('cardLabel')}</div>
                    <div className="vip-card-number" id="vipCardNumber" onClick={copyVipCard} role="button" tabIndex={0} onKeyDown={(e) => { if (e.key === 'Enter') copyVipCard(); }}>
                      {vip.cardNumber || '—'}
                    </div>
                    <div id="tapToCopy">{vt('tapToCopy')}</div>
                  </div>
                  <div className="vip-amount-display">
                    <div id="amountLabel">{vt('amountLabel')}</div>
                    <div id="vipPayAmount">{fmt(vip.amount || 0)} {vt('toman')}</div>
                  </div>
                  <div
                    className={`vip-receipt-upload${vip.receiptData ? ' has-image' : ''}`}
                    id="vipReceiptUpload"
                    role="button"
                    tabIndex={0}
                    onClick={() => document.getElementById('vipReceiptInput')?.click()}
                    onKeyDown={(e) => { if (e.key === 'Enter') document.getElementById('vipReceiptInput')?.click(); }}
                  >
                    <input id="vipReceiptInput" type="file" accept="image/jpeg,image/png,.jpg,.jpeg,.png" hidden onChange={onVipReceipt} />
                    {!vip.receiptData && <div id="vipReceiptPlaceholder">{vt('uploadReceipt')}</div>}
                    {vip.receiptData && <img id="vipReceiptPreview" className="vip-receipt-preview" src={vip.receiptData} alt="" />}
                  </div>
                  <button className="vip-submit-btn" id="vipSubmitBtn" disabled={!vip.receiptData} onClick={submitVip}>{vt('submit')}</button>
                  <button className="vip-back-btn" id="backBtn" onClick={() => setVip((cur) => ({ ...cur, step: 1 }))}>{vt('back')}</button>
                </div>
              )}
              {vip.step === 3 && (
                <div className="vip-step vip-payment-step active" id="vipStep3">
                  <div id="successTitle">{vt('successTitle')}</div>
                  <div id="successDesc">{vt('successDesc')}</div>
                  <button className="vip-purchase-btn" onClick={() => setVip(null)}>{vt('close')}</button>
                </div>
              )}
            </div>
            {vip.step === 1 && (
              <div className="vip-modal-footer" id="vipModalFooter">
                <button className="vip-purchase-btn" id="vipContinueBtn" disabled={!vip.selectedPlanId} onClick={continueVip}>{vt('continue')}</button>
              </div>
            )}
          </div>
        </div>
      )}
    </>
  );
}

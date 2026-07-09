import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { createPortal } from 'react-dom';

import { useBackClose } from '../../shared/backstack.js';
import { useScrollLock } from '../../shared/scrollLock.js';
import { BOT_USERNAME, getTelegramPhotoUrl, getWebApp, hapticSelection } from '../../shared/telegram.js';
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
  { key: 'vip', swatch: '#c9d6e8', locked: true },
  // Earned accents render as metal-gradient chips (premium finish, 2026-07-09)
  { key: 'champion', swatch: 'linear-gradient(135deg, #f8cc57, #e8a300 55%, #8a5c00)', locked: true },
  { key: 'legend', swatch: 'linear-gradient(135deg, #e766f2, #c026d3 55%, #6d0b8f)', locked: true },
];

// Server-driven mission achievements (GET /api/dashboard/achievements).
// key → i18n key + icon; conditions/progress/claims all live server-side.
const ACH_META = {
  launch: { i18n: 'achLaunch', icon: <path d="M4.5 16.5c-1.5 1.26-2 5-2 5s3.74-.5 5-2c.71-.84.7-2.13-.09-2.91a2.18 2.18 0 0 0-2.91-.09zM12 15l-3-3a22 22 0 0 1 2-3.95A12.88 12.88 0 0 1 22 2c0 2.72-.78 7.5-6 11a22.35 22.35 0 0 1-4 2zM9 12H4s.55-3.03 2-4c1.62-1.08 5 0 5 0M12 15v5s3.03-.55 4-2c1.08-1.62 0-5 0-5" /> },
  refuel: { i18n: 'achRefuel', icon: <path d="M12 2.69l5.66 5.66a8 8 0 1 1-11.31 0z" /> },
  starHunter: { i18n: 'achStarHunter', icon: <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01z" /> },
  orbiter: { i18n: 'achOrbiter', icon: <><circle cx="12" cy="12" r="3" /><path d="M20.2 20.2c2.04-2.03.02-7.36-4.5-11.9-4.54-4.52-9.87-6.54-11.9-4.5-2.04 2.03-.02 7.36 4.5 11.9 4.54 4.52 9.87 6.54 11.9 4.5z" /></> },
  supernova: { i18n: 'achSupernova', icon: <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83" /> },
  envoy: { i18n: 'achEnvoy', icon: <><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" /><circle cx="9" cy="7" r="4" /><path d="M23 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75" /></> },
  fleetCommander: { i18n: 'achFleetCommander', icon: <path d="M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1zM4 22v-7" /> },
  crew: { i18n: 'achCrew', img: '/webapp/static/badges/vip.png', icon: <path d="M2 4l3 12h14l3-12-6 7-4-7-4 7-6-7zm3 16h14" /> },
  arcadePilot: { i18n: 'achArcadePilot', icon: <><line x1="6" y1="11" x2="10" y2="11" /><line x1="8" y1="9" x2="8" y2="13" /><line x1="15" y1="12" x2="15.01" y2="12" /><line x1="18" y1="10" x2="18.01" y2="10" /><path d="M17.32 5H6.68a4 4 0 0 0-3.978 3.59c-.006.052-.01.101-.017.152C2.604 9.416 2 14.456 2 16a3 3 0 0 0 3 3c1 0 1.5-.5 2-1l1.414-1.414A2 2 0 0 1 9.828 16h4.344a2 2 0 0 1 1.414.586L17 18c.5.5 1 1 2 1a3 3 0 0 0 3-3c0-1.545-.604-6.584-.685-7.258-.007-.05-.011-.1-.017-.151A4 4 0 0 0 17.32 5z" /></> },
  inOrbit: { i18n: 'achInOrbit', icon: <><circle cx="12" cy="12" r="10" /><polyline points="12 6 12 12 16 14" /></> },
};

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

// `open` points the chevron DOWN for expandable rows (FAQ). Inline style
// wins over the CSS rules that flip it in RTL / nudge it on hover — down
// is down in both directions, so a plain 90° works everywhere.
const Arrow = ({ open = false }) => (
  <svg
    className="settings-arrow"
    viewBox="0 0 24 24"
    style={open ? { transform: 'rotate(90deg)' } : undefined}
  >
    <path d="M8.59 16.59L13.17 12 8.59 7.41 10 6l6 6-6 6-1.41-1.41z" />
  </svg>
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
  const [achData, setAchData] = useState(null); // { paying_customer, achievements[] }
  const [achClaiming, setAchClaiming] = useState(null); // key being claimed
  const [copied, setCopied] = useState(null); // 'chatId' | 'referralCode' | 'link'
  const [accent, setAccentState] = useState(() => document.documentElement.getAttribute('data-accent') || 'red');
  const [unlockedThemes, setUnlockedThemes] = useState([]);
  const [packBadge, setPackBadge] = useState('');
  const [notifOn, setNotifOn] = useState(() => {
    try { return localStorage.getItem('notifications') !== 'off'; } catch (_) { return true; }
  });
  const [perfMode, setPerfMode] = useState(perfStoredMode());
  const [vip, setVip] = useState(null); // { step, plans, cardNumber, selectedPlanId, orderId, amount, receiptData, receiptName }
  // Telegram home-screen shortcut (Bot API 8.0). Only shown when the client
  // supports it and the icon isn't already installed.
  const [canAddHome, setCanAddHome] = useState(false);
  const [faqOpen, setFaqOpen] = useState(false);

  // Back unwinds overlays innermost-first: voucher picker → auto-claim modal;
  // in the VIP modal it steps payment→plans before closing.
  useBackClose(!!vip && vip.step !== 2, () => setVip(null));
  useBackClose(!!vip && vip.step === 2, () => setVip((cur) => (cur ? { ...cur, step: 1 } : cur)));
  // Page behind the VIP modal must not scroll (same guard as Sheet).
  useScrollLock(!!vip);

  const isVip = !!user?.is_vip;

  const loadProfile = useCallback(async () => {
    let vipActive = false;
    try {
      const data = await api('/api/dashboard/overview');
      if (data.ok && data.user) {
        setUser(data.user);
        vipActive = !!data.user.is_vip;
      }
    } catch (_) { /* ignore */ }
    try {
      const subs = await api('/api/dashboard/subscriptions');
      if (subs.ok) setSubsCount((subs.subscriptions || []).length);
    } catch (_) { /* ignore */ }
    try {
      const refs = await api('/api/dashboard/referrals');
      if (refs.ok) setReferrals(refs);
    } catch (_) { /* ignore */ }
    try {
      const a = await api('/api/dashboard/achievements');
      if (a.ok) setAchData(a);
    } catch (_) { /* section renders a quiet skeleton — never break the page */ }
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
      if (vipActive) themes.add('vip'); // active VIP unlocks the platinum accent
      setUnlockedThemes([...themes]);
      setPackBadge(badge);
    } catch (_) { /* ignore */ }
  }, []);

  useEffect(() => { loadProfile(); }, [loadProfile]);

  const claimAchievement = async (key) => {
    if (achClaiming) return;
    setAchClaiming(key);
    try {
      const r = await api('/api/dashboard/achievements/claim', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ key }),
      });
      if (r && r.ok) {
        setAchData((cur) => (cur ? {
          ...cur,
          achievements: cur.achievements.map((a) => (a.key === key ? { ...a, claimed: true, claimable: false } : a)),
        } : cur));
        showToast(tt('achClaimSuccess'), 'success');
        hapticSelection();
      } else {
        showToast(tt(r?.error === 'requires_purchase' ? 'achLockedNote' : 'achClaimFailed'), 'error');
      }
    } catch (_) { showToast(tt('achClaimFailed'), 'error'); }
    setAchClaiming(null);
  };

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
    || (user?.referral_code ? `https://t.me/${BOT_USERNAME}?start=${user.referral_code}` : '');

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

  // ── VIP flow ──────────────────────────────────────────────────────
  const authQS = () => {
    const token = getUrlAuthToken();
    return token ? '?auth=' + encodeURIComponent(token) : '';
  };

  const openVipPurchase = async () => {
    setVip({ step: 1, plans: null, cardNumber: '', selectedPlanId: null, isVip: false, vipUntil: null });
    try {
      const r = await api('/api/dashboard/vip/plans' + authQS());
      if (r && r.ok) {
        setVip((cur) => (cur ? {
          ...cur,
          plans: r.plans || [],
          cardNumber: r.card_number || '',
          isVip: !!r.is_vip,
          vipUntil: r.vip_until || null,
        } : cur));
      } else {
        setVip((cur) => (cur ? { ...cur, plans: [] } : cur));
      }
    } catch (_) { setVip((cur) => (cur ? { ...cur, plans: [] } : cur)); }
  };

  const continueVip = async () => {
    if (!vip?.selectedPlanId || vip.busy) return;
    setVip((cur) => (cur ? { ...cur, busy: true } : cur));
    try {
      const r = await api('/api/dashboard/vip/purchase' + authQS(), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ plan_id: vip.selectedPlanId }),
      });
      if (r && r.ok) {
        const plan = vip.plans.find((p) => p.id === vip.selectedPlanId);
        setVip((cur) => ({ ...cur, busy: false, step: 2, orderId: r.order_id, amount: plan?.price || 0, cardNumber: r.card_number || cur.cardNumber }));
      } else if (r && r.error === 'pending_exists') {
        setVip((cur) => (cur ? { ...cur, busy: false } : cur));
        showToast(lang === 'fa'
          ? 'یک سفارش VIP در انتظار تایید دارید — منتظر بررسی ادمین بمانید'
          : 'You already have a VIP order awaiting review', 'error');
      } else {
        setVip((cur) => (cur ? { ...cur, busy: false } : cur));
        showToast(String(r?.error || tt('failedToLoad')), 'error');
      }
    } catch (e) {
      setVip((cur) => (cur ? { ...cur, busy: false } : cur));
      showToast(String(e?.message || tt('failedToLoad')), 'error');
    }
  };

  const onVipReceipt = (e) => {
    const file = e.target.files && e.target.files[0];
    e.target.value = '';
    if (!file) return;
    const looksImage = (file.type || '').startsWith('image/') || /\.(jpg|jpeg|png|webp|heic|heif)$/i.test(file.name);
    if (!looksImage) {
      showToast('فقط فایل تصویر مجاز است', 'error');
      return;
    }
    const reader = new FileReader();
    reader.onload = () => setVip((cur) => (cur ? { ...cur, receiptData: reader.result, receiptName: file.name } : cur));
    reader.readAsDataURL(file);
  };

  const submitVip = async () => {
    if (!vip?.orderId || !vip?.receiptData || vip.busy) return;
    // Instant feedback: the receipt is a base64 image inside JSON, which can
    // take several seconds to upload — the button locks and shows progress so
    // nobody spam-taps it (which used to pile up orders + admin DMs).
    setVip((cur) => (cur ? { ...cur, busy: true } : cur));
    try {
      const r = await api('/api/dashboard/vip/receipt' + authQS(), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ order_id: vip.orderId, receipt_image: vip.receiptData }),
      });
      if (r && r.ok) setVip((cur) => ({ ...cur, busy: false, step: 3 }));
      else {
        setVip((cur) => (cur ? { ...cur, busy: false } : cur));
        showToast(String(r?.error || tt('failedToLoad')), 'error');
      }
    } catch (e) {
      setVip((cur) => (cur ? { ...cur, busy: false } : cur));
      showToast(String(e?.message || tt('failedToLoad')), 'error');
    }
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

  // VIP promo copy (hardcoded fa/en, legacy parity). `meter` = % of the
  // V4 footer bar (days remaining against a 30-day window, capped).
  const vipPromo = useMemo(() => {
    const fa = lang === 'fa';
    if (isVip) {
      const until = user?.vip_until ? new Date(user.vip_until) : null;
      // Active members get an INFO button (see the perks; renewal still lives
      // inside the modal) — a "Renew" CTA nagged people who just bought it.
      if (!until) {
        return { cls: ' is-vip', title: fa ? 'VIP مادام‌العمر' : 'Lifetime VIP', desc: fa ? 'از ۲۰٪ تخفیف لذت ببرید' : 'Enjoy 20% off everything', info: true, meter: 100 };
      }
      const daysLeft = Math.max(0, Math.ceil((until.getTime() - Date.now()) / 86400000));
      return {
        cls: ' is-vip',
        title: fa ? 'عضویت VIP فعال' : 'VIP Active',
        desc: fa ? `${fmt(daysLeft)} روز باقی‌مانده` : `${fmt(daysLeft)} days remaining`,
        info: true,
        meter: Math.max(3, Math.min(100, Math.round((daysLeft / 30) * 100))),
      };
    }
    return {
      cls: '',
      title: fa ? 'ارتقا به VIP' : 'Upgrade to VIP',
      desc: fa ? '۲۰٪ تخفیف + پلن‌های اختصاصی' : '20% off + exclusive plans',
      btn: fa ? 'خرید VIP' : 'Get VIP',
      meter: null,
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
  const [avatarBroken, setAvatarBroken] = useState(false);
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
          setAvatarBroken(false);
        }
      } catch (_) { /* no photo / offline — initial letter stays */ }
    })();
    return () => { cancelled = true; if (objUrl) URL.revokeObjectURL(objUrl); };
  }, []);

  // Server-proxied blob FIRST: t.me photo_url hotlinks are blocked inside some
  // mobile webviews (loaded fine on desktop), which used to lock the avatar
  // into the "?" fallback even after the blob arrived.
  const avatarUrl = fetchedAvatar
    || (!avatarBroken ? (user?.photo_url || getTelegramPhotoUrl()) : null);

  return (
    <>
      {/* V4 "Split Panel" (Pasha's pick, 2026-07-09): identity | stat
          column grid, VIP footer with a days-remaining meter. */}
      <section className="profile-hero ph4">
        <div className="ph4-body">
          <div className="ph4-id">
            <div className={`profile-avatar${avatarUrl ? ' has-photo' : ''}`} id="userAvatar">
              {avatarUrl
                ? <img src={avatarUrl} alt="" onError={() => setAvatarBroken(true)} />
                : (user?.full_name?.[0] || '?').toUpperCase()}
            </div>
            <div className="ph4-idt">
              <div className="profile-name" id="userName">{user ? (user.full_name || tt('astronaut')) : '...'}</div>
              <div className="profile-username" id="userUsername">{user?.username ? '@' + user.username : ''}</div>
            </div>
            <div className="profile-badges" id="userBadges">
              <span className={`profile-badge${categoryBadge.cls}`} id="userCategory">
                {isVip
                  ? (
                    <img
                      src="/webapp/static/badges/vip.png"
                      alt=""
                      style={{ width: 15, height: 15, objectFit: 'contain' }}
                      onError={(e) => { e.target.style.display = 'none'; }}
                    />
                  )
                  : (
                    <span className="svg-icon">
                      <svg viewBox="0 0 24 24" fill="currentColor" width="12" height="12"><path d="M12 2l2.4 7.4H22l-6.2 4.5 2.4 7.3-6.2-4.5-6.2 4.5 2.4-7.3L2 9.4h7.6z" /></svg>
                    </span>
                  )}
                <span id="userCategoryText">{categoryBadge.text}</span>
              </span>
              {packBadge && (
                <span className="profile-badge" id="userPackBadge" style={{ background: 'rgba(var(--brandRgb),0.18)' }}>
                  <img
                    src={`/webapp/static/badges/${String(packBadge).toLowerCase() === 'legend' ? 'legend' : 'champion'}.png`}
                    alt=""
                    style={{ width: 16, height: 16, objectFit: 'contain' }}
                    onError={(e) => { e.target.style.display = 'none'; }}
                  />
                  <span id="userPackBadgeText">{packBadge}</span>
                </span>
              )}
            </div>
          </div>
          <div className="ph4-col">
            <div className="ph4-st">
              <div className="ph4-n" id="statCredit">{fmt(user?.credit || 0)}</div>
              <div className="ph4-l">{tt('credit')}</div>
            </div>
            <div className="ph4-st">
              <div className="ph4-n" id="statStars">{fmt(user?.stars || 0)}</div>
              <div className="ph4-l">{tt('stars')}</div>
            </div>
            <div className="ph4-st">
              <div className="ph4-n" id="statReferrals">{fmt(referrals?.total ?? user?.referral_count ?? 0)}</div>
              <div className="ph4-l">{tt('referrals')}</div>
            </div>
          </div>
        </div>
        <button
          type="button"
          className={`ph4-vip${vipPromo.cls}`}
          id="vipPromoSection"
          aria-label={vipPromo.info ? (lang === 'fa' ? 'مشاهده مزایای VIP' : 'View VIP perks') : undefined}
          onClick={openVipPurchase}
        >
          <div className="ph4-vip-row">
            <svg viewBox="0 0 24 24" fill="currentColor" width="17" height="17" aria-hidden="true"><path d="M5 16 3 5l5.5 5L12 4l3.5 6L21 5l-2 11H5zm14 3H5v-2h14v2z" /></svg>
            <div className="ph4-vip-t" id="vipPromoTitle">{vipPromo.title}</div>
            <div className="ph4-vip-d" id="vipPromoDesc">{vipPromo.desc}</div>
            {vipPromo.info
              ? (
                <svg className="ph4-vip-go" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" width="15" height="15" aria-hidden="true">
                  <circle cx="12" cy="12" r="10" /><path d="M12 16v-4" /><path d="M12 8h.01" />
                </svg>
              )
              : (
                <svg className="ph4-vip-go flip-rtl" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" width="15" height="15" aria-hidden="true"><path d="M5 12h14M12 5l7 7-7 7" /></svg>
              )}
          </div>
          {vipPromo.meter != null && (
            <div className="ph4-meter" aria-hidden="true"><i style={{ width: vipPromo.meter + '%' }} /></div>
          )}
        </button>
      </section>

      {/* «پیشرفت و جوایز» section removed 2026-07-09 (Pasha): it only ever
          held the active-subs count — a one-row section reading as broken.
          The row lives in Account information now; real progress content
          is the achievements section below. */}
      <section className="profile-section">
        <div className="profile-section-title">
          <div className="icon-box">
            <svg viewBox="0 0 24 24" fill="currentColor" width="15" height="15"><path d="M12 17.27 18.18 21l-1.64-7.03L22 9.24l-7.19-.61L12 2 9.19 8.63 2 9.24l5.46 4.73L5.82 21z" /></svg>
          </div>
          <span>{tt('achievements')}</span>
        </div>
        <div className="ach-grid" id="achievementsGrid">
          {(achData?.achievements || Object.keys(ACH_META).map((key) => ({ key, progress: 0, target: 1, done: false, claimed: false, claimable: false }))).map((a) => {
            const meta = ACH_META[a.key];
            if (!meta) return null;
            const pct = Math.min(100, Math.round((a.progress / a.target) * 100));
            const showBar = !a.done && a.target > 1;
            return (
              <div key={a.key} className={`ach-item${a.done ? ' done' : ''}${a.claimed ? ' claimed' : ''}`}>
                <div className="ach-item-top">
                  <div className="ach-icon">
                    {meta.img && a.done
                      ? <img src={meta.img} alt="" style={{ width: 24, height: 24, objectFit: 'contain' }} onError={(e) => { e.target.style.display = 'none'; }} />
                      : <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" width="18" height="18">{meta.icon}</svg>}
                  </div>
                  <div className="ach-text">
                    <div className="ach-name">{tt(meta.i18n)}</div>
                    {showBar && (
                      <div className="ach-progress-nums">{fmt(a.progress)} / {fmt(a.target)}</div>
                    )}
                  </div>
                </div>
                {showBar && (
                  <div className="ach-bar"><div className="ach-bar-fill" style={{ width: pct + '%' }} /></div>
                )}
                {a.claimable && (
                  <button
                    className={`ach-claim${achClaiming === a.key ? ' busy' : ''}`}
                    type="button"
                    disabled={!!achClaiming}
                    onClick={() => claimAchievement(a.key)}
                  >
                    {tt('achClaim')}
                  </button>
                )}
                {a.claimed && (
                  <div className="ach-claimed-tag">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" width="11" height="11"><polyline points="20 6 9 17 4 12" /></svg>
                    {tt('achClaimed')}
                  </div>
                )}
              </div>
            );
          })}
        </div>
        {achData && achData.paying_customer === false && (
          <div className="ach-locked-note">{tt('achLockedNote')}</div>
        )}
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
          <span className="profile-info-label">{tt('activeSubscriptions')}</span>
          <span className="profile-info-value" id="infoSubs">{subsCount == null ? '—' : fmt(subsCount)}</span>
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

      {/* «فعالیت اخیر» section removed 2026-07-09 (Pasha) — it only ever
          showed the account-creation date, already in Account Information. */}

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
            onClick={() => setFaqOpen((v) => !v)}
            icon={<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="18" height="18"><circle cx="12" cy="12" r="10" /><path d="M9.1 9a3 3 0 1 1 5.8 1c0 2-3 2-3 4" /><path d="M12 18h.01" /></svg>}
            title={tt('faqTitle')}
            desc={tt('faqDesc')}
            right={<Arrow open={faqOpen} />}
          />
          {faqOpen && (
            <div className="faq-list" style={{ padding: '4px 14px 12px' }}>
              {[1, 2, 3, 4, 5, 6, 7, 8, 9].map((n, i, arr) => (
                <details key={n} className="faq-item" style={{ padding: '8px 0', borderBottom: i < arr.length - 1 ? '1px solid var(--line, rgba(255,255,255,0.08))' : 'none' }}>
                  <summary style={{ cursor: 'pointer', fontWeight: 700, fontSize: 13.5, listStyle: 'none' }}>{tt('faqQ' + n)}</summary>
                  <p style={{ margin: '8px 0 0', fontSize: 12.5, lineHeight: 1.7, color: 'var(--muted)' }}>{tt('faqA' + n)}</p>
                  {n === 9 && (
                    <button
                      id="faqSupportBtn"
                      type="button"
                      onClick={() => openSupportPage()}
                      style={{
                        marginTop: 10,
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: 7,
                        padding: '9px 14px',
                        borderRadius: 11,
                        border: '1px solid rgba(var(--brandRgb), 0.35)',
                        background: 'rgba(var(--brandRgb), 0.14)',
                        color: 'var(--brand)',
                        fontFamily: 'inherit',
                        fontSize: 12.5,
                        fontWeight: 800,
                        cursor: 'pointer',
                      }}
                    >
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" width="15" height="15" aria-hidden="true">
                        <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
                      </svg>
                      {tt('faqAskSupport')}
                    </button>
                  )}
                </details>
              ))}
            </div>
          )}
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

      {/* ── VIP modal — portaled to <body>: page sections create stacking
          contexts (transforms/filters) that trapped it under the app header
          and bottom nav on phones. ── */}
      {vip && createPortal(
        <div className="vip-modal-overlay active" id="vipModalOverlay">
          <div className="vip-modal">
            <div className="vip-modal-header">
              <div className="vip-modal-title">
                <span className="svg-icon vip-crown">
                  <svg viewBox="0 0 24 24" fill="currentColor" width="18" height="18"><path d="M5 16 3 5l5.5 5L12 4l3.5 6L21 5l-2 11H5zm14 3H5v-2h14v2z" /></svg>
                </span>
                <span id="vipModalTitle">{vt('modalTitle')}</span>
              </div>
              <button className="vip-modal-close" onClick={() => setVip(null)}>×</button>
            </div>
            <div className="vip-modal-body">
              {vip.step === 1 && (
                <div className="vip-step" id="vipStep1">
                  {vip.isVip && (
                    <div className="vip-status-card">
                      <div className="vip-status-title">
                        <svg viewBox="0 0 24 24" fill="currentColor" width="16" height="16"><path d="M5 16 3 5l5.5 5L12 4l3.5 6L21 5l-2 11H5zm14 3H5v-2h14v2z" /></svg>
                        {vt('statusActive')}
                      </div>
                      <div className="vip-status-sub">
                        {vip.vipUntil
                          ? `${vt('statusUntil')} ${new Date(vip.vipUntil).toLocaleDateString(getLocale(lang), { year: 'numeric', month: 'long', day: 'numeric' })}`
                          : vt('statusLifetime')}
                      </div>
                    </div>
                  )}
                  <div className="vip-hero">
                    <img className="vip-hero-medal" src="/webapp/static/badges/vip.png" alt="" onError={(e) => { e.target.style.display = 'none'; }} />
                    <div className="vip-hero-copy">
                      <div className="vip-hero-tag">{vt('heroTag')}</div>
                      <div className="vip-hero-line">{vt('heroLine')}</div>
                    </div>
                  </div>
                  <div className="vip-benefits">
                    {[
                      ['benefitDiscount', 'M12 8v8m-4-4h8', true],
                      ['benefitPlans', 'M20 7H4m16 5H4m16 5H4', false],
                      ['benefitSupport', 'M9.1 9a3 3 0 1 1 5.8 1c0 2-3 2-3 4m.1 4h.01', false],
                      ['benefitTheme', 'M12 3a9 9 0 1 0 9 9c0-1-1-2-2-2h-2a2 2 0 0 1-2-2V6c0-1.5-1.5-3-3-3z', false],
                    ].map(([k, path]) => (
                      <div className="vip-benefit-item" key={k}>
                        <span className="vip-benefit-icon">
                          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="15" height="15" strokeLinecap="round" strokeLinejoin="round"><path d={path} /></svg>
                        </span>
                        <span className="vip-benefit-col">
                          <span className="vip-benefit-text">{vt(k)}</span>
                          <span className="vip-benefit-sub">{vt(k + 'Sub')}</span>
                        </span>
                      </div>
                    ))}
                  </div>
                  <div className="vip-plans-title" id="selectPlanTitle">{vip.isVip ? vt('renew') : vt('selectPlan')}</div>
                  <div className="vip-plans-grid" id="vipPlansGrid">
                    {vip.plans === null && <div style={{ padding: 12 }}>{tt('loading')}</div>}
                    {vip.plans !== null && vip.plans.map((p) => {
                      // Per-month + savings vs the 1-month rate, computed from data.
                      const base = (vip.plans.find((x) => x.id === '1_month') || {}).price || 0;
                      const months = p.days ? Math.round(p.days / 30) : 0;
                      const perMonth = months > 1 ? Math.round(p.price / months / 1000) * 1000 : 0;
                      const savePct = base && months > 1 ? Math.max(0, Math.round((1 - p.price / (base * months)) * 100)) : 0;
                      return (
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
                            {perMonth > 0 && <div className="vip-plan-permonth">≈ {fmt(perMonth)} {vt('toman')}{vt('perMonth')}</div>}
                          </div>
                          {savePct > 4 && <div className="vip-plan-save">{vt('save')} {fmt(savePct)}٪</div>}
                          {p.id === '3_months' && <div className="vip-plan-badge">{vt('popular')}</div>}
                          {p.is_lifetime && <div className="vip-plan-badge">{vt('bestValue')}</div>}
                        </div>
                      );
                    })}
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
                    <input id="vipReceiptInput" type="file" accept="image/*" hidden onChange={onVipReceipt} />
                    {!vip.receiptData && <div id="vipReceiptPlaceholder">{vt('uploadReceipt')}</div>}
                    {vip.receiptData && <img id="vipReceiptPreview" className="vip-receipt-preview" src={vip.receiptData} alt="" />}
                    {vip.receiptData && (
                      <button
                        type="button"
                        className="receipt-remove-btn"
                        aria-label="Remove"
                        onClick={(e) => {
                          e.stopPropagation();
                          const inp = document.getElementById('vipReceiptInput');
                          if (inp) inp.value = '';
                          setVip((cur) => (cur ? { ...cur, receiptData: null, receiptName: '' } : cur));
                        }}
                      >
                        <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round"><path d="M18 6 6 18M6 6l12 12" /></svg>
                      </button>
                    )}
                  </div>
                  <button className="vip-submit-btn" id="vipSubmitBtn" disabled={!vip.receiptData || vip.busy} onClick={submitVip}>
                    {vip.busy ? (lang === 'fa' ? 'در حال ارسال…' : 'Sending…') : vt('submit')}
                  </button>
                  <button className="vip-back-btn" id="backBtn" disabled={vip.busy} onClick={() => setVip((cur) => ({ ...cur, step: 1 }))}>{vt('back')}</button>
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
                <button className="vip-purchase-btn" id="vipContinueBtn" disabled={!vip.selectedPlanId || vip.busy} onClick={continueVip}>{vt('continue')}</button>
              </div>
            )}
          </div>
        </div>,
        document.body,
      )}
    </>
  );
}

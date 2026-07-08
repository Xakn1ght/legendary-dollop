import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { useBackClose } from '../../shared/backstack.js';
import { AlertTriangleIcon, GiftIcon, Spinner, StarIcon, TicketIcon } from '../../shared/icons.jsx';
import { getWebApp, hapticImpact, hapticNotify } from '../../shared/telegram.js';
import { astroConfirm } from '../../shared/ui.js';
import { api } from '../api.js';
import { Sheet } from '../components/Sheet.jsx';
import { useShell } from '../ShellContext.js';
import { showToast } from '../toast.js';

import { couponLabel, faNum, i18nTasks } from './tasksI18n.js';

const ShareIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" width="16" height="16" aria-hidden="true">
    <circle cx="18" cy="5" r="3" /><circle cx="6" cy="12" r="3" /><circle cx="18" cy="19" r="3" />
    <line x1="8.59" y1="13.51" x2="15.42" y2="17.49" /><line x1="15.41" y1="6.51" x2="8.59" y2="10.49" />
  </svg>
);
const CopyIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" width="16" height="16" aria-hidden="true">
    <rect x="9" y="9" width="13" height="13" rx="2" ry="2" /><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
  </svg>
);
const CheckIcon = ({ size = 12 }) => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" width={size} height={size} aria-hidden="true">
    <polyline points="20 6 9 17 4 12" />
  </svg>
);

// Milestone reward → short label for rail caption + full couponLabel reuse.
function milestoneLabel(m, tt, lang) {
  let label = couponLabel(m, tt, lang);
  (m.extra_coupons || []).forEach((ex) => { label += ' + ' + couponLabel(ex, tt, lang); });
  if (m.badge) {
    label += lang === 'fa'
      ? ` + نشان ${m.badge === 'Champion' ? 'قهرمان' : 'افسانه'}`
      : ` + ${m.badge} badge`;
  }
  return label;
}

export function TasksPage() {
  const { lang, openPurchasePage } = useShell();
  const tt = useCallback((key) => (i18nTasks[lang] || i18nTasks.en)[key] || i18nTasks.en[key] || key, [lang]);
  const fmt = useCallback((n) => Number(n || 0).toLocaleString(lang === 'fa' ? 'fa-IR' : 'en-US'), [lang]);

  const [referralData, setReferralData] = useState(null);
  const [seasonData, setSeasonData] = useState(null);
  const [vouchers, setVouchers] = useState(null); // null = loading
  const [voucherError, setVoucherError] = useState('');
  const [railSel, setRailSel] = useState(null); // manually tapped milestone (stars)
  const [copied, setCopied] = useState(false);
  const [redeem, setRedeem] = useState(null); // { reward, options, selectedType, selectedSubId, subs }
  const [addToken, setAddToken] = useState('');
  const [earnings, setEarnings] = useState(null); // null = loading/hidden
  const [cardSheet, setCardSheet] = useState(false);
  const [cardInput, setCardInput] = useState('');
  const [cardBusy, setCardBusy] = useState(false);
  const [withdrawBusy, setWithdrawBusy] = useState(false);
  const retryCountRef = useRef(0);
  const railRef = useRef(null);

  // Back closes the redeem sheet before leaving the tab.
  useBackClose(!!redeem, () => setRedeem(null));
  useBackClose(cardSheet, () => setCardSheet(false));

  const fetchReferrals = useCallback(async () => {
    try {
      const r = await api('/api/dashboard/referrals');
      setReferralData(r);
    } catch (_) { setReferralData({ ok: false }); }
  }, []);

  const fetchEarnings = useCallback(async () => {
    try {
      const r = await api('/api/dashboard/earnings');
      if (r && r.ok) setEarnings(r);
    } catch (_) { /* card stays hidden — never break the page */ }
  }, []);

  const fetchSeason = useCallback(async () => {
    try {
      const r = await api('/api/dashboard/season');
      if (r && r.ok) setSeasonData(r);
    } catch (_) { /* ignore */ }
  }, []);

  const fetchVouchers = useCallback(async () => {
    try {
      const r = await api('/api/dashboard/referral-rewards');
      if (r && r.ok) {
        setVouchers(r.rewards || []);
        setVoucherError('');
        retryCountRef.current = 0;
        return;
      }
      throw new Error(r?.error || 'failed');
    } catch (e) {
      const msg = String(e?.message || e);
      // Auth may not be ready right after boot: auto-retry up to 5 times.
      if (/401|403/.test(msg) && retryCountRef.current < 5) {
        retryCountRef.current++;
        setVouchers(null);
        setVoucherError('');
        setTimeout(fetchVouchers, Math.min(500 + retryCountRef.current * 400, 3000));
        return;
      }
      setVouchers([]);
      setVoucherError(msg.slice(0, 100));
    }
  }, []);

  useEffect(() => {
    const t1 = setTimeout(() => {
      fetchReferrals();
      fetchSeason();
      fetchVouchers();
      fetchEarnings();
    }, 100);
    const t2 = setTimeout(() => fetchVouchers(), 900);
    return () => { clearTimeout(t1); clearTimeout(t2); };
  }, [fetchReferrals, fetchSeason, fetchVouchers, fetchEarnings]);

  // ── Season derived values ───────────────────────────────────────
  const season = useMemo(() => {
    const stars = Number(seasonData?.season_stars || 0);
    const ladder = seasonData?.ladder || [];
    const next = seasonData?.next_milestone || null;
    const nextStars = next ? Number(next.stars) : null;
    const prevStars = (() => {
      const reached = ladder.filter((m) => m.reached).map((m) => Number(m.stars));
      return reached.length ? Math.max(...reached) : 0;
    })();
    let pct = 100;
    if (nextStars != null && nextStars > prevStars) {
      pct = Math.max(0, Math.min(100, Math.round(((stars - prevStars) / (nextStars - prevStars)) * 100)));
    }
    const nextMilestoneEntry = nextStars != null ? ladder.find((m) => Number(m.stars) === nextStars) : null;
    return { stars, ladder, next, nextStars, pct, nextMilestoneEntry, daysLeft: seasonData?.season?.days_left };
  }, [seasonData]);

  const coupons = seasonData?.coupons || [];

  // Rail selection: tapped node wins, else the next milestone, else the last rung.
  const selectedMilestone = useMemo(() => {
    if (!season.ladder.length) return null;
    if (railSel != null) {
      const m = season.ladder.find((x) => Number(x.stars) === railSel);
      if (m) return m;
    }
    if (season.nextMilestoneEntry) return season.nextMilestoneEntry;
    return season.ladder[season.ladder.length - 1];
  }, [season, railSel]);

  // Keep the highlighted milestone centered in the rail. Scroll ONLY the rail:
  // scrollIntoView also scrolls ancestors, and on RTL it shoved the whole PAGE
  // sideways (overflow:hidden containers still scroll programmatically).
  useEffect(() => {
    if (!selectedMilestone || !railRef.current) return undefined;
    const center = () => {
      try {
        const rail = railRef.current;
        if (!rail) return false;
        const el = rail.querySelector(`[data-stars="${selectedMilestone.stars}"]`);
        if (!el) return false;
        const rRect = rail.getBoundingClientRect();
        if (rRect.width < 10) return false; // not laid out yet — retry
        const eRect = el.getBoundingClientRect();
        const delta = (eRect.left + eRect.width / 2) - (rRect.left + rRect.width / 2);
        if (Math.abs(delta) >= 2) {
          if (typeof rail.scrollBy === 'function') {
            rail.scrollBy({ left: delta, behavior: railSel == null ? 'auto' : 'smooth' });
          } else {
            rail.scrollLeft += delta;
          }
        }
        return true;
      } catch (_) { return true; }
    };
    // First paint can race layout (fonts/tab mount) — retry briefly until
    // the rail has real geometry.
    if (center()) return undefined;
    const t1 = setTimeout(center, 150);
    const t2 = setTimeout(center, 600);
    return () => { clearTimeout(t1); clearTimeout(t2); };
  }, [selectedMilestone, railSel]);

  // ── Referral actions ────────────────────────────────────────────
  const refLink = referralData?.referral_link || referralData?.referral_code || '';
  const copyRefLink = async () => {
    try {
      await navigator.clipboard.writeText(refLink);
      setCopied(true);
      setTimeout(() => setCopied(false), 1600);
      hapticNotify('success');
    } catch (_) {
      showToast(lang === 'fa' ? 'کپی نشد' : 'Copy failed', 'error', 1800);
    }
  };
  const shareRefLink = () => {
    const tg = getWebApp();
    if (tg?.openTelegramLink && referralData?.referral_link) {
      tg.openTelegramLink('https://t.me/share/url?url=' + encodeURIComponent(referralData.referral_link));
    } else copyRefLink();
  };

  // ── Enter a friend's invite code ────────────────────────────────
  const [friendCode, setFriendCode] = useState('');
  const [friendMsg, setFriendMsg] = useState(null); // { type:'error'|'ok', text }
  const [friendBusy, setFriendBusy] = useState(false);
  const submitFriendCode = async () => {
    const code = friendCode.trim().toUpperCase();
    if (!/^[A-Z0-9]{6}$/.test(code)) {
      setFriendMsg({ type: 'error', text: tt('friendCodeErrFormat') });
      return;
    }
    setFriendBusy(true);
    setFriendMsg(null);
    try {
      const res = await api('/api/dashboard/referrals/enter', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ referral_code: code }),
      });
      if (res && res.ok) {
        setFriendMsg({ type: 'ok', text: tt('friendCodeApplied') });
        setFriendCode('');
        hapticNotify('success');
        fetchReferrals();
      } else {
        const map = { invalid_format: 'friendCodeErrFormat', invalid_code: 'friendCodeErrInvalid', own_code: 'friendCodeErrOwn', already_used: 'friendCodeErrUsed' };
        setFriendMsg({ type: 'error', text: tt(map[res && res.error] || 'friendCodeErrServer') });
        hapticNotify('error');
      }
    } catch (_) {
      setFriendMsg({ type: 'error', text: tt('friendCodeErrServer') });
    }
    setFriendBusy(false);
  };

  // ── Earnings (cash-out) actions ─────────────────────────────────
  const saveCard = async () => {
    const digits = cardInput.replace(/\D/g, '');
    if (digits.length !== 16) { showToast(tt('cardInvalid'), 'error'); return; }
    setCardBusy(true);
    try {
      const r = await api('/api/dashboard/earnings/card', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ card: digits }),
      });
      if (r && r.ok) {
        setEarnings((cur) => (cur ? { ...cur, card_masked: r.card_masked } : cur));
        setCardSheet(false);
        setCardInput('');
        showToast(tt('cardSaved'), 'success');
        hapticNotify('success');
      } else {
        showToast(tt(r?.error === 'invalid_card' ? 'cardInvalid' : 'withdrawFailed'), 'error');
      }
    } catch (_) { showToast(tt('withdrawFailed'), 'error'); }
    setCardBusy(false);
  };

  const requestWithdraw = async () => {
    if (!earnings || withdrawBusy) return;
    if (!earnings.card_masked) { setCardSheet(true); showToast(tt('needCardFirst'), 'error'); return; }
    const ok = await astroConfirm({
      title: tt('withdraw'),
      message: tt('withdrawConfirm'),
      okText: tt('withdraw'),
      cancelText: tt('close'),
    });
    if (!ok) return;
    setWithdrawBusy(true);
    try {
      const r = await api('/api/dashboard/wallet/cashout', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ amount: earnings.credit_toman }),
      });
      if (r && r.ok) {
        showToast(tt('withdrawSuccess'), 'success');
        hapticNotify('success');
        fetchEarnings();
      } else {
        const key = r?.error === 'requires_active_paid_subscription' ? 'withdrawNeedsPaidSub'
          : r?.error === 'amount_below_minimum' ? 'minCashoutHint'
            : 'withdrawFailed';
        showToast(tt(key).replace('{amount}', fmt(earnings.min_cashout_toman)), 'error');
        hapticNotify('error');
      }
    } catch (_) { showToast(tt('withdrawFailed'), 'error'); }
    setWithdrawBusy(false);
  };

  // ── Redeem sheet ────────────────────────────────────────────────
  const voucherOptions = (reward) => {
    const opts = [];
    const gb = Math.round((reward.traffic_bytes || 0) / (1024 ** 3));
    if (gb >= 1) opts.push({ type: 'traffic', label: `${tt('rewardTraffic')} +${faNum(gb, lang)}GB` });
    if (reward.extra_days > 0) opts.push({ type: 'days', label: `${tt('rewardDays')} +${faNum(reward.extra_days, lang)}` });
    if (reward.credit_amount > 0) opts.push({ type: 'credit', label: `${tt('rewardCredit')} +${fmt(reward.credit_amount)}` });
    if (reward.star_increment > 0) opts.push({ type: 'stars', label: `${tt('rewardStars')} +${faNum(reward.star_increment, lang)}` });
    return opts;
  };

  const needsSub = (type) => type === 'traffic' || type === 'days';

  const openRedeemSheet = async (reward) => {
    const opts = voucherOptions(reward);
    const selectedType = opts.length === 1 ? opts[0].type : null;
    setRedeem({ reward, options: opts, selectedType, selectedSubId: null, subs: null });
    setAddToken('');
    try {
      const r = await api('/api/dashboard/subscriptions');
      const subs = (r.ok && r.subscriptions) ? r.subscriptions : [];
      const sorted = [...subs].sort((a, b) => {
        const aa = String(a.status || '').toLowerCase() === 'active' ? 0 : 1;
        const bb = String(b.status || '').toLowerCase() === 'active' ? 0 : 1;
        return aa - bb;
      });
      const firstActive = sorted.find((s) => String(s.status || '').toLowerCase() === 'active');
      setRedeem((cur) => (cur ? { ...cur, subs: sorted, selectedSubId: firstActive ? String(firstActive.id) : null } : cur));
    } catch (_) {
      setRedeem((cur) => (cur ? { ...cur, subs: [] } : cur));
    }
  };

  // 50★ Legend prize: activate VIP straight from the wallet (never at checkout).
  const activateVipCoupon = async (c) => {
    const days = Number(c.payload?.days || 30);
    const ok = await astroConfirm({
      title: lang === 'fa' ? 'فعال‌سازی VIP' : 'Activate VIP',
      message: lang === 'fa'
        ? `${faNum(days, lang)} روز عضویت VIP همین حالا فعال شود؟`
        : `Activate ${days} days of VIP membership now?`,
      okText: lang === 'fa' ? 'فعال کن' : 'Activate',
      cancelText: lang === 'fa' ? 'بعداً' : 'Later',
    });
    if (!ok) return;
    try {
      const r = await api(`/api/dashboard/coupons/${c.id}/redeem-vip`, { method: 'POST' });
      if (r && r.ok) {
        showToast(lang === 'fa' ? '🎖 VIP فعال شد!' : '🎖 VIP activated!', 'success', 2600);
        hapticNotify('success');
        fetchSeason();
      } else {
        showToast(String(r?.error || tt('failedToLoad')), 'error', 2600);
      }
    } catch (e) {
      showToast(String(e?.message || tt('failedToLoad')), 'error', 2600);
    }
  };

  const confirmRedeem = async () => {
    if (!redeem) return;
    if (redeem.options.length > 1 && !redeem.selectedType) {
      await astroConfirm({ title: 'Error', message: tt('rewardChoiceRequired'), okText: tt('close'), cancelText: ' ' });
      return;
    }
    const payload = {};
    if (redeem.selectedType) payload.reward_type = redeem.selectedType;
    if (needsSub(redeem.selectedType) && redeem.selectedSubId) payload.subscription_id = Number(redeem.selectedSubId);
    try {
      const r = await api(`/api/dashboard/referral-rewards/${redeem.reward.id}/redeem`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (r && r.ok) {
        showToast(tt('redeemed'), 'success', 2200);
        hapticNotify('success');
        setRedeem(null);
        fetchVouchers();
        fetchSeason();
      } else {
        showToast(String(r?.error || tt('failedToLoad')), 'error', 2600);
      }
    } catch (e) {
      showToast(String(e?.message || tt('failedToLoad')), 'error', 2600);
    }
  };

  const submitToken = async () => {
    const token = addToken.trim().slice(0, 256);
    if (!token) return;
    try {
      const r = await api('/api/dashboard/subscriptions/add', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token }),
      });
      if (r && r.ok) {
        setAddToken('');
        // refresh sub list in sheet
        const rr = await api('/api/dashboard/subscriptions');
        const subs = (rr.ok && rr.subscriptions) ? rr.subscriptions : [];
        setRedeem((cur) => (cur ? { ...cur, subs } : cur));
      }
    } catch (_) { /* legacy swallows errors here */ }
  };

  const vouchersShown = (vouchers || []).slice(0, 8);
  const redeemNeedsSubSection = redeem && redeem.selectedType && needsSub(redeem.selectedType);
  const redeemConfirmDisabled = redeem
    ? (redeem.options.length > 1 && !redeem.selectedType) || (redeemNeedsSubSection && !redeem.selectedSubId)
    : true;

  const selReached = !!(selectedMilestone && selectedMilestone.reached);
  const selIsNext = !!(selectedMilestone && season.nextStars != null && Number(selectedMilestone.stars) === season.nextStars);

  return (
    <div id="rewardsSection" className="rw">

      {/* ── Season hero ── */}
      <section className="rw-card rw-hero" id="seasonCard">
        <div className="rw-hero-top">
          <div className="rw-hero-heading">
            <h2 className="rw-title">{tt('seasonTitle')}</h2>
            <div className="rw-sub">{tt('seasonSubtitle')}</div>
          </div>
          {season.daysLeft != null && (
            <span className="rw-days-chip">
              {lang === 'fa' ? `${faNum(season.daysLeft, lang)} روز مانده` : `${season.daysLeft}d left`}
            </span>
          )}
        </div>

        <div className="rw-hero-mid">
          <div className="rw-count">
            <div className="rw-count-num">
              <span>{faNum(season.stars, lang)}</span>
              <StarIcon size={22} />
            </div>
            <div className="rw-count-label">{tt('seasonStarsLabel')}</div>
          </div>
          <div className="rw-next">
            <div className="rw-next-label">{tt('seasonNextLabel')}</div>
            {season.nextStars != null ? (
              <>
                <div className="rw-next-reward">
                  {season.nextMilestoneEntry ? couponLabel(season.nextMilestoneEntry, tt, lang) : '—'}
                </div>
                <div className="rw-next-togo">
                  <StarIcon size={11} />
                  {lang === 'fa'
                    ? `${faNum(Math.max(0, season.nextStars - season.stars), lang)} ستاره مانده`
                    : `${Math.max(0, season.nextStars - season.stars)} to go`}
                </div>
              </>
            ) : (
              <div className="rw-next-reward">{tt('seasonAllUnlocked')}</div>
            )}
          </div>
        </div>

        <div className="rw-progress" role="progressbar" aria-valuenow={season.pct} aria-valuemin={0} aria-valuemax={100}>
          <div className="rw-progress-fill" style={{ width: season.pct + '%' }} />
        </div>
        <div className="rw-progress-nums">
          {season.nextStars != null
            ? (lang === 'fa'
              ? `${faNum(season.stars, lang)} از ${faNum(season.nextStars, lang)}`
              : `${season.stars} of ${season.nextStars}`)
            : ''}
        </div>

        {/* Milestone rail (replaces the old hidden vertical ladder) */}
        {season.ladder.length > 0 && (
          <>
            <div className="rw-rail" ref={railRef}>
              {season.ladder.map((m, i) => {
                const reached = !!m.reached;
                const isNext = season.nextStars != null && Number(m.stars) === season.nextStars;
                const isSel = selectedMilestone && Number(m.stars) === Number(selectedMilestone.stars);
                return (
                  <React.Fragment key={m.stars}>
                    {i > 0 && <span className={`rw-rail-link${reached ? ' reached' : ''}`} aria-hidden="true" />}
                    <button
                      type="button"
                      data-stars={m.stars}
                      className={`rw-node${reached ? ' reached' : ''}${isNext ? ' next' : ''}${isSel ? ' sel' : ''}`}
                      onClick={() => { setRailSel(Number(m.stars)); hapticImpact('light'); }}
                      aria-label={`${m.stars}★ — ${milestoneLabel(m, tt, lang)}`}
                    >
                      {m.badge
                        ? <img src={`/webapp/static/badges/${String(m.theme || m.badge).toLowerCase()}.png`} alt="" />
                        : <span className="rw-node-num">{faNum(m.stars, lang)}</span>}
                    </button>
                  </React.Fragment>
                );
              })}
            </div>
            {selectedMilestone && (
              <div className="rw-rail-caption" key={selectedMilestone.stars}>
                <span className={`rw-rail-tag${selReached ? ' ok' : selIsNext ? ' next' : ''}`}>
                  {selReached
                    ? <><CheckIcon size={11} /> {tt('railUnlocked')}</>
                    : <>{faNum(selectedMilestone.stars, lang)} <StarIcon size={10} /></>}
                </span>
                <span className="rw-rail-caption-text">{milestoneLabel(selectedMilestone, tt, lang)}</span>
              </div>
            )}
          </>
        )}
      </section>

      {/* ── Invite friends (the earn action) ── */}
      {referralData?.ok !== false && (
        <section className="rw-card" id="referralCard">
          <div className="rw-card-head">
            <div>
              <h3 className="rw-title">{tt('referralsTitle')}</h3>
              <div className="rw-sub">{tt('referralsSubtitle')}</div>
            </div>
          </div>

          <div className="rw-code-row">
            <div className="rw-code" dir="ltr">{referralData?.referral_code || '—'}</div>
            <button className={`rw-icon-btn${copied ? ' ok' : ''}`} type="button" onClick={copyRefLink} aria-label={tt('copy')}>
              {copied ? <CheckIcon size={16} /> : <CopyIcon />}
            </button>
          </div>
          <button className="rw-btn primary rw-share-btn" id="referralShareBtn" type="button" onClick={shareRefLink}>
            <ShareIcon />
            {tt('shareInvite')}
          </button>

          {referralData?.has_referrer === false && (
            <div className="friend-code-box">
              <div className="friend-code-label">{tt('friendCodeTitle')}</div>
              <div className="friend-code-row">
                <input
                  className={`friend-code-input${friendMsg?.type === 'error' ? ' is-error' : ''}`}
                  type="text"
                  inputMode="text"
                  maxLength={6}
                  autoComplete="off"
                  autoCorrect="off"
                  spellCheck={false}
                  placeholder={tt('friendCodePlaceholder')}
                  value={friendCode}
                  onChange={(e) => { setFriendCode(e.target.value.toUpperCase().replace(/[^A-Z0-9]/g, '')); setFriendMsg(null); }}
                  onKeyDown={(e) => { if (e.key === 'Enter') submitFriendCode(); }}
                />
                <button className="friend-code-btn" type="button" disabled={friendBusy || friendCode.length !== 6} onClick={submitFriendCode} aria-label={tt('add')}>
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" width="18" height="18"><path d="M5 12h14M12 5l7 7-7 7" /></svg>
                </button>
              </div>
              {friendMsg && <div className={`friend-code-msg is-${friendMsg.type}`}>{friendMsg.text}</div>}
            </div>
          )}

          <div className="rw-stats">
            <div className="rw-stat">
              <div className="rw-stat-num">{fmt(referralData?.total || 0)}</div>
              <div className="rw-stat-label">{tt('total')}</div>
            </div>
            <div className="rw-stat">
              <div className="rw-stat-num">{fmt(referralData?.active || 0)}</div>
              <div className="rw-stat-label">{tt('active')}</div>
            </div>
            <div className="rw-stat">
              <div className="rw-stat-num">{fmt(referralData?.earned || 0)}</div>
              <div className="rw-stat-label">{tt('earned')}</div>
            </div>
          </div>

          {(referralData?.referrals || []).length > 0 && (
            <div className="rw-list">
              <div className="rw-list-title">{tt('recent')}</div>
              {(referralData.referrals || []).slice(0, 5).map((r, i) => (
                <div key={i} className="rw-row">
                  <div className="rw-row-main">{r.full_name || r.username || '—'}</div>
                  <div className={`rw-row-meta${r.is_active ? ' ok' : ''}`}>{r.is_active ? tt('active') : tt('joined')}</div>
                </div>
              ))}
            </div>
          )}
        </section>
      )}

      {/* ── Earnings: invite → earn → get paid ── */}
      {earnings?.ok && (
        <section className="rw-card" id="earningsCard">
          <div className="rw-card-head">
            <div>
              <h3 className="rw-title">{tt('earningsTitle')}</h3>
              <div className="rw-sub">{tt('earningsSubtitle')}</div>
            </div>
            {earnings.unlocked && <span className="rw-head-chip ok"><CheckIcon size={11} /></span>}
          </div>

          {!earnings.unlocked && (
            <>
              <div className="rw-earn-progress-row">
                <div className="rw-progress">
                  <div
                    className="rw-progress-fill"
                    style={{ width: Math.min(100, Math.round((earnings.active_referrals / earnings.gate) * 100)) + '%' }}
                  />
                </div>
                <div className="rw-progress-nums">
                  {faNum(earnings.active_referrals, lang)} / {faNum(earnings.gate, lang)} {tt('earningsProgressLabel')}
                </div>
              </div>
              <div className="rw-earn-stat">
                <span className="rw-earn-stat-label">{tt('earnedSoFar')}</span>
                <span className="rw-earn-stat-num">{fmt(earnings.earned_total_toman)} {tt('toman')}</span>
              </div>
              <div className="rw-earn-hint">{tt('earningsGoalHint')}</div>
            </>
          )}

          {earnings.unlocked && (
            <>
              <div className="rw-earn-balance">
                <div className="rw-earn-balance-label">{tt('withdrawableBalance')}</div>
                <div className="rw-earn-balance-num">{fmt(earnings.credit_toman)} <span>{tt('toman')}</span></div>
              </div>
              <button
                className={`rw-btn primary rw-earn-withdraw${withdrawBusy ? ' loading' : ''}`}
                type="button"
                disabled={withdrawBusy || earnings.credit_toman < earnings.min_cashout_toman}
                onClick={requestWithdraw}
              >
                {earnings.credit_toman >= earnings.min_cashout_toman
                  ? tt('withdraw')
                  : tt('minCashoutHint').replace('{amount}', fmt(earnings.min_cashout_toman))}
              </button>
              <div className="rw-earn-card-row">
                <span className="rw-earn-card-label">{tt('savedCardLabel')}</span>
                <button className="rw-btn sm" type="button" onClick={() => { setCardInput(''); setCardSheet(true); }}>
                  {earnings.card_masked
                    ? <span dir="ltr" className="rw-earn-card-num">{earnings.card_masked}</span>
                    : tt('addCard')}
                </button>
              </div>
              {(earnings.recent_payouts || []).length > 0 && (
                <div className="rw-list">
                  <div className="rw-list-title">{tt('recentPayouts')}</div>
                  {earnings.recent_payouts.map((p) => (
                    <div key={p.id} className="rw-row">
                      <div className="rw-row-main">{fmt(p.amount_toman)} {tt('toman')}</div>
                      <div className={`rw-row-meta${p.status === 'paid' ? ' ok' : ''}${p.status === 'denied' ? ' bad' : ''}`}>
                        {tt(p.status === 'paid' ? 'payoutPaid' : p.status === 'denied' ? 'payoutDenied' : 'payoutPending')}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </>
          )}
        </section>
      )}

      {/* ── Referral vouchers ── */}
      <section className="rw-card" id="voucherCard">
        <div className="rw-card-head">
          <div>
            <h3 className="rw-title">{tt('referralRewardsTitle')}</h3>
            <div className="rw-sub">{tt('referralRewardsSubtitle')}</div>
          </div>
          {vouchers !== null && !voucherError && vouchers.length > 0 && (
            <span className="rw-head-chip">{faNum(vouchers.length, lang)}</span>
          )}
        </div>

        {vouchers === null && (
          <div className="rw-empty">
            <Spinner size={15} />
            <span>{tt('fetchingVouchers')}…</span>
          </div>
        )}
        {vouchers !== null && voucherError && (
          <div className="rw-empty">
            <span className="rw-empty-warn"><AlertTriangleIcon size={15} /></span>
            <span>{tt('failedToLoad')}</span>
            <button className="rw-btn sm" type="button" onClick={() => { retryCountRef.current = 0; setVouchers(null); setVoucherError(''); fetchVouchers(); }}>
              {tt('retry')}
            </button>
          </div>
        )}
        {vouchers !== null && !voucherError && vouchers.length === 0 && (
          <div className="rw-empty">
            <GiftIcon size={16} />
            <span>{tt('noVouchers')} — {tt('noVouchersHint')}</span>
          </div>
        )}
        {vouchers !== null && !voucherError && vouchersShown.map((rw) => {
          const gb = (rw.traffic_bytes || 0) / (1024 ** 3);
          return (
            <div key={rw.id} className="rw-row rw-voucher">
              <div className="rw-row-main">
                <div className="rw-chips">
                  {gb >= 0.5 && <span className="rw-chip">+{faNum(Math.round(gb), lang)}GB</span>}
                  {rw.extra_days > 0 && <span className="rw-chip">+{faNum(rw.extra_days, lang)} {lang === 'fa' ? 'روز' : 'd'}</span>}
                  {rw.credit_amount > 0 && <span className="rw-chip">+{fmt(rw.credit_amount)}</span>}
                  {rw.star_increment > 0 && <span className="rw-chip star">+{faNum(rw.star_increment, lang)} <StarIcon size={10} /></span>}
                </div>
                <div className="rw-row-sub">#{faNum(rw.id, lang)}</div>
              </div>
              <button className="rw-btn primary sm" type="button" onClick={() => openRedeemSheet(rw)}>{tt('redeem')}</button>
            </div>
          );
        })}
      </section>

      {/* ── My coupons ── */}
      <section className="rw-card" id="couponsCard">
        <div className="rw-card-head">
          <div>
            <h3 className="rw-title">{tt('couponsTitle')}</h3>
            <div className="rw-sub">{tt('couponsSubtitle')}</div>
          </div>
          {coupons.length > 0 && <span className="rw-head-chip">{faNum(coupons.length, lang)}</span>}
        </div>

        {coupons.length === 0 ? (
          <div className="rw-empty">
            <TicketIcon size={16} />
            <span>{tt('couponsEmpty')}</span>
          </div>
        ) : coupons.map((c, i) => {
          const dleft = Number(c.days_left);
          return (
            <div key={i} className="rw-ticket">
              <div className="rw-ticket-stub"><TicketIcon size={18} /></div>
              <div className="rw-ticket-body">
                <div className="rw-ticket-label">{couponLabel(c, tt, lang)}</div>
                {Number.isFinite(dleft) && (
                  <div className={`rw-ticket-exp${dleft <= 7 ? ' soon' : ''}`}>
                    {tt('couponExpires')} {faNum(dleft, lang)} {lang === 'fa' ? 'روز' : 'days'}
                  </div>
                )}
              </div>
              {c.coupon_type === 'vip_days' && (
                <button className="rw-btn primary sm" type="button" onClick={() => activateVipCoupon(c)}>
                  {lang === 'fa' ? 'فعال‌سازی' : 'Activate'}
                </button>
              )}
            </div>
          );
        })}
      </section>

      {/* ── Redeem bottom sheet ── */}
      <Sheet open={!!redeem} onClose={() => setRedeem(null)} panelId="redeemPanel" backdropId="redeemBackdrop" labelledBy="redeemTitle">
        <div className="sheet-title-row">
          <h3 className="sheet-title" id="redeemTitle">{tt('redeemTitle')}</h3>
          <button className="sheet-close" onClick={() => setRedeem(null)}>{tt('close')}</button>
        </div>
        <p className="sheet-subtitle">{tt('redeemSubtitle')}</p>
        {redeem && (
          <>
            <div className="rw-row rw-sheet-meta">
              <div className="rw-chips">
                {(redeem.reward.traffic_bytes || 0) / (1024 ** 3) >= 0.5 && (
                  <span className="rw-chip">+{faNum(Math.round(redeem.reward.traffic_bytes / (1024 ** 3)), lang)}GB</span>
                )}
                {redeem.reward.extra_days > 0 && <span className="rw-chip">+{faNum(redeem.reward.extra_days, lang)} {lang === 'fa' ? 'روز' : 'd'}</span>}
                {redeem.reward.credit_amount > 0 && <span className="rw-chip">+{fmt(redeem.reward.credit_amount)}</span>}
                {redeem.reward.star_increment > 0 && <span className="rw-chip star">+{faNum(redeem.reward.star_increment, lang)} <StarIcon size={10} /></span>}
              </div>
              <div className="rw-row-meta">#{faNum(redeem.reward.id, lang)}</div>
            </div>

            {redeem.options.length > 1 && (
              <div id="redeemChoiceSection">
                <div className="rw-list-title">{tt('redeemChoiceLabel')}</div>
                <div className="sheet-list" id="redeemChoiceList">
                  {redeem.options.map((o) => (
                    <div
                      key={o.type}
                      className={`sheet-item${redeem.selectedType === o.type ? ' selected' : ''}`}
                      role="button"
                      tabIndex={0}
                      onClick={() => setRedeem((cur) => ({ ...cur, selectedType: o.type }))}
                      onKeyDown={(e) => { if (e.key === 'Enter') setRedeem((cur) => ({ ...cur, selectedType: o.type })); }}
                    >
                      <div className="sheet-item-main"><div className="sheet-item-title">{o.label}</div></div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {redeemNeedsSubSection && (
              <div id="redeemSubsSection">
                <div className="rw-list-title">{tt('selectSubscription')}</div>
                {redeem.subs === null && <p className="sheet-subtitle">{tt('loading')}…</p>}
                {redeem.subs !== null && redeem.subs.length === 0 && (
                  <>
                    <p className="sheet-subtitle">{tt('noSubscriptions')}</p>
                    <div className="rw-sheet-add">
                      <input
                        className="sheet-input"
                        type="text"
                        placeholder={tt('addTokenPlaceholder')}
                        inputMode="text"
                        autoCapitalize="none"
                        autoComplete="off"
                        spellCheck={false}
                        maxLength={2000}
                        value={addToken}
                        onChange={(e) => setAddToken(e.target.value)}
                      />
                      <div className="rw-sheet-add-btns">
                        <button className="rw-btn" type="button" onClick={submitToken}>{tt('add')}</button>
                        <button className="rw-btn" type="button" onClick={openPurchasePage}>{tt('buyNew')}</button>
                      </div>
                    </div>
                  </>
                )}
                {redeem.subs !== null && redeem.subs.length > 0 && (
                  <div className="sheet-list" id="redeemSubsList">
                    {redeem.subs.map((s) => (
                      <div
                        key={s.id}
                        className={`sheet-item${String(redeem.selectedSubId) === String(s.id) ? ' selected' : ''}`}
                        role="button"
                        tabIndex={0}
                        onClick={() => setRedeem((cur) => ({ ...cur, selectedSubId: String(s.id) }))}
                        onKeyDown={(e) => { if (e.key === 'Enter') setRedeem((cur) => ({ ...cur, selectedSubId: String(s.id) })); }}
                      >
                        <div className="sheet-item-main">
                          <div className="sheet-item-title">{s.name || s.marzban_username || s.username || ('#' + s.id)}</div>
                          <div className="sheet-item-sub">{[s.plan_name, String(s.status || '').toUpperCase()].filter(Boolean).join(' · ')}</div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            <div className="rw-sheet-actions">
              <button
                className="rw-btn primary wide"
                type="button"
                disabled={redeemConfirmDisabled}
                onClick={confirmRedeem}
              >
                {tt('redeem')}
              </button>
            </div>
          </>
        )}
      </Sheet>

      {/* ── Payout card sheet ── */}
      <Sheet open={cardSheet} onClose={() => setCardSheet(false)} panelId="payoutCardSheet" backdropId="payoutCardBackdrop" labelledBy="payoutCardTitle">
        <h2 id="payoutCardTitle">{tt('cardSheetTitle')}</h2>
        <p className="sheet-subtitle">{tt('cardSheetSubtitle')}</p>
        <div className="sheet-field">
          <input
            className="sheet-input"
            type="text"
            dir="ltr"
            inputMode="numeric"
            autoComplete="off"
            spellCheck={false}
            maxLength={19}
            placeholder={tt('cardPlaceholder')}
            value={cardInput}
            onChange={(e) => {
              // digits only, grouped 4-4-4-4 for readability
              const d = e.target.value.replace(/\D/g, '').slice(0, 16);
              setCardInput(d.replace(/(.{4})/g, '$1 ').trim());
            }}
            onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); saveCard(); } }}
          />
        </div>
        <div className="rw-sheet-actions">
          <button className="rw-btn" type="button" onClick={() => setCardSheet(false)}>{tt('close')}</button>
          <button
            className={`rw-btn primary${cardBusy ? ' loading' : ''}`}
            type="button"
            disabled={cardBusy || cardInput.replace(/\D/g, '').length !== 16}
            onClick={saveCard}
          >
            {tt('saveCard')}
          </button>
        </div>
      </Sheet>
    </div>
  );
}

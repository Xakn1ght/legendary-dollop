import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { useBackClose } from '../../shared/backstack.js';
import { AlertTriangleIcon, CheckCircleIcon, ClockIcon, GiftIcon, LockIcon, Spinner, StarIcon, TicketIcon } from '../../shared/icons.jsx';
import { getWebApp, hapticImpact, hapticNotify } from '../../shared/telegram.js';
import { astroConfirm } from '../../shared/ui.js';
import { api } from '../api.js';
import { Sheet } from '../components/Sheet.jsx';
import { useShell } from '../ShellContext.js';
import { showToast } from '../toast.js';

import { couponLabel, faNum, i18nTasks } from './tasksI18n.js';

const Chevron = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="18" height="18">
    <polyline points="6 9 12 15 18 9" />
  </svg>
);

// Collapsible reward card with per-card persistence (legacy parity).
function RewardCard({ id, extraClass = '', title, subtitle, children }) {
  const [collapsed, setCollapsed] = useState(() => {
    try { return localStorage.getItem(`reward_card_${id}_collapsed`) === '1'; } catch (_) { return false; }
  });
  const toggle = () => {
    const next = !collapsed;
    setCollapsed(next);
    try { localStorage.setItem(`reward_card_${id}_collapsed`, next ? '1' : '0'); } catch (_) { /* ignore */ }
    hapticImpact('light');
  };
  return (
    <div className={`referral-card ${extraClass}${collapsed ? ' collapsed' : ''}`} id={id} data-collapsible="true">
      <div
        className="referral-header"
        role="button"
        tabIndex={0}
        style={{ cursor: 'pointer' }}
        onClick={(e) => { if (e.target.closest('button, a, input, label')) return; toggle(); }}
        onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); toggle(); } }}
      >
        <div>
          <div className="referral-title">{title}</div>
          <div className="referral-subtitle">{subtitle}</div>
        </div>
        <div className="referral-actions">
          <button
            className="reward-toggle"
            type="button"
            data-toggle="collapse"
            aria-expanded={!collapsed}
            aria-label={collapsed ? 'Expand section' : 'Collapse section'}
            onClick={toggle}
          >
            <Chevron />
          </button>
        </div>
      </div>
      <div className="reward-body">{children}</div>
    </div>
  );
}

export function TasksPage() {
  const { lang } = useShell();
  const tt = useCallback((key) => (i18nTasks[lang] || i18nTasks.en)[key] || i18nTasks.en[key] || key, [lang]);
  const fmt = useCallback((n) => Number(n || 0).toLocaleString(lang === 'fa' ? 'fa-IR' : 'en-US'), [lang]);

  const [referralData, setReferralData] = useState(null);
  const [seasonData, setSeasonData] = useState(null);
  const [vouchers, setVouchers] = useState(null); // null = loading
  const [voucherError, setVoucherError] = useState('');
  const [ladderOpen, setLadderOpen] = useState(false);
  const [redeem, setRedeem] = useState(null); // { reward, selectedType, selectedSubId, subs, subsLoading }
  const [addToken, setAddToken] = useState('');
  const retryCountRef = useRef(0);

  // Back closes the redeem sheet before leaving the tab.
  useBackClose(!!redeem, () => setRedeem(null));

  const fetchReferrals = useCallback(async () => {
    try {
      const r = await api('/api/dashboard/referrals');
      setReferralData(r);
    } catch (_) { setReferralData({ ok: false }); }
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
    }, 100);
    const t2 = setTimeout(() => fetchVouchers(), 900);
    return () => { clearTimeout(t1); clearTimeout(t2); };
  }, [fetchReferrals, fetchSeason, fetchVouchers]);

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

  // ── Referral actions ────────────────────────────────────────────
  const refLink = referralData?.referral_link || referralData?.referral_code || '';
  const copyRefLink = async () => {
    try {
      await navigator.clipboard.writeText(refLink);
      showToast('Copied!', 'success', 1800);
      hapticNotify('success');
    } catch (_) {
      showToast('Copy failed', 'error', 1800);
    }
  };
  const shareRefLink = () => {
    const tg = getWebApp();
    if (tg?.openTelegramLink && referralData?.referral_link) {
      tg.openTelegramLink('https://t.me/share/url?url=' + encodeURIComponent(referralData.referral_link));
    } else copyRefLink();
  };

  // ── Enter a friend's invite code (moved off the old first-launch screen) ──
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

  return (
    <div id="rewardsSection">
      {/* ── Star Season ── */}
      <RewardCard id="seasonCard" extraClass="season-hero" title={tt('seasonTitle')} subtitle={tt('seasonSubtitle')}>
        <div className="season-count">
          <span className="season-count-num" id="seasonStars">{fmt(season.stars)}</span>
          <span className="season-count-label">{tt('seasonStarsLabel')}</span>
        </div>
        <div className="season-next-block">
          <div className="season-next-row">
            <span className="season-next-label">{tt('seasonNextLabel')}</span>
            <span className="season-togo" id="seasonToGo">
              {season.nextStars != null
                ? (
                  <>
                    {faNum(Math.max(0, season.nextStars - season.stars), lang)}
                    <StarIcon size={11} />{' '}
                    {lang === 'fa' ? 'مانده' : 'to go'}
                  </>
                )
                : tt('seasonAllUnlocked')}
            </span>
          </div>
          <div className="season-progress">
            <div className="season-progress-fill" id="seasonProgressFill" style={{ width: season.pct + '%' }} />
          </div>
          <div className="season-progress-nums" id="seasonProgressNums">
            {season.nextStars != null
              ? (
                <>
                  <StarIcon size={11} />{' '}
                  {lang === 'fa'
                    ? `${faNum(season.stars, lang)} از ${faNum(season.nextStars, lang)}`
                    : `${season.stars} of ${season.nextStars}`}
                </>
              )
              : '—'}
          </div>
          <div className="season-next-reward" id="seasonNextReward">
            {season.nextMilestoneEntry ? couponLabel(season.nextMilestoneEntry, tt, lang) : '—'}
          </div>
        </div>
        <div className="season-ends" id="seasonEnds">
          {season.daysLeft != null
            ? (lang === 'fa' ? `پایان فصل تا ${faNum(season.daysLeft, lang)} روز` : `Season ends in ${season.daysLeft} days`)
            : ''}
        </div>
        <button
          className={`season-ladder-toggle${ladderOpen ? ' open' : ''}`}
          type="button"
          aria-expanded={ladderOpen}
          onClick={() => { setLadderOpen(!ladderOpen); hapticImpact('light'); }}
        >
          <span>{tt('seasonLadderLabel')}</span>
          <Chevron />
        </button>
        <div className="season-ladder" id="seasonLadderWrap" style={{ display: ladderOpen ? 'block' : 'none' }}>
          <div id="seasonLadderList">
            {season.ladder.map((m) => {
              const isNext = season.nextStars != null && Number(m.stars) === season.nextStars;
              return (
                <div key={m.stars} className={`season-rung${m.reached ? ' reached' : ''}${isNext ? ' next' : ''}`}>
                  <div className="season-rung-node">{m.reached ? <StarIcon size={12} /> : faNum(m.stars, lang)}</div>
                  <div className="season-rung-body">
                    <div className="season-rung-reward">{couponLabel(m, tt, lang)}</div>
                    <div className="season-rung-stars">{faNum(m.stars, lang)} <StarIcon size={10} /></div>
                  </div>
                  <div className="season-rung-state">
                    {m.reached
                      ? <span style={{ color: 'var(--ok, #34d399)' }}><CheckCircleIcon size={16} /></span>
                      : isNext
                        ? <span style={{ color: 'var(--brand)' }}><ClockIcon size={16} /></span>
                        : <span style={{ opacity: 0.55 }}><LockIcon size={16} /></span>}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </RewardCard>

      {/* ── Referral Rewards (vouchers) ── */}
      <RewardCard id="voucherCard" title={tt('referralRewardsTitle')} subtitle={tt('referralRewardsSubtitle')}>
        <div className="referral-list" id="voucherListWrap" style={{ display: 'block' }}>
          <div className="referral-list-title">{tt('available')}</div>
          <div id="voucherList">
            {vouchers === null && (
              <div className="referral-item" style={{ alignItems: 'center', padding: 24, textAlign: 'center' }}>
                <div className="referral-item-name" style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
                  <Spinner size={15} /> {tt('fetchingVouchers')}…
                </div>
              </div>
            )}
            {vouchers !== null && voucherError && (
              <div className="referral-item" style={{ alignItems: 'flex-start', padding: 20 }}>
                <div className="referral-item-name" style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
                  <span style={{ color: '#fbbf24' }}><AlertTriangleIcon size={15} /></span>
                  {tt('failedToLoad')}: {voucherError}
                </div>
                <button className="ref-btn" onClick={() => { retryCountRef.current = 0; setVouchers(null); setVoucherError(''); fetchVouchers(); }}>{tt('retry')}</button>
              </div>
            )}
            {vouchers !== null && !voucherError && vouchers.length === 0 && (
              <div className="referral-item" style={{ alignItems: 'center', padding: 24, textAlign: 'center' }}>
                <div className="referral-item-name" style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
                  <GiftIcon size={16} /> {tt('noVouchers')}
                </div>
                <div className="referral-item-meta">{tt('noVouchersHint')}</div>
              </div>
            )}
            {vouchers !== null && !voucherError && vouchersShown.map((rw, i) => {
              const gb = (rw.traffic_bytes || 0) / (1024 ** 3);
              return (
                <div key={rw.id} className="referral-item voucher-item" style={{ marginBottom: i === vouchersShown.length - 1 ? 0 : 8 }}>
                  <div>
                    <div className="referral-item-name" style={{ fontSize: 14, fontWeight: 700 }}>#{rw.id}</div>
                    <div className="voucher-chips">
                      {gb >= 0.5 && <span className="voucher-chip vc-gb">+{faNum(Math.round(gb), lang)}GB</span>}
                      {rw.extra_days > 0 && <span className="voucher-chip vc-days">+{faNum(rw.extra_days, lang)}d</span>}
                      {rw.credit_amount > 0 && <span className="voucher-chip vc-credit">+{fmt(rw.credit_amount)}</span>}
                      {rw.star_increment > 0 && <span className="voucher-chip vc-star">+{faNum(rw.star_increment, lang)} <StarIcon size={10} /></span>}
                    </div>
                  </div>
                  <button className="ref-btn primary" onClick={() => openRedeemSheet(rw)}>{tt('redeem')}</button>
                </div>
              );
            })}
          </div>
        </div>
      </RewardCard>

      {/* ── My Coupons ── */}
      <RewardCard id="couponsCard" title={tt('couponsTitle')} subtitle={tt('couponsSubtitle')}>
        <div className="coupon-list" id="couponList">
          {coupons.length === 0 ? (
            <div className="coupon-empty">
              <div className="coupon-empty-icon"><GiftIcon size={26} /></div>
              <div className="coupon-empty-text">{tt('couponsEmpty')}</div>
            </div>
          ) : coupons.map((c, i) => {
            const dleft = Number(c.days_left);
            return (
              <div key={i} className="coupon-ticket">
                <div className="coupon-ticket-stub"><TicketIcon size={20} /></div>
                <div className="coupon-ticket-body">
                  <div className="coupon-ticket-label">{couponLabel(c, tt, lang)}</div>
                  {Number.isFinite(dleft) && (
                    <div className={`coupon-ticket-exp${dleft <= 7 ? ' soon' : ''}`}>
                      {tt('couponExpires')} {faNum(dleft, lang)} {lang === 'fa' ? 'روز' : 'days'}
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </RewardCard>

      {/* ── Referrals ── */}
      {referralData?.ok !== false && (
        <RewardCard id="referralCard" title={tt('referralsTitle')} subtitle={tt('referralsSubtitle')}>
          <div className="card-actions grid-2" id="referralActions">
            <button className="ref-btn primary" id="referralShareBtn" type="button" onClick={shareRefLink}>{tt('share')}</button>
            <button className="ref-btn" id="referralCopyBtn" type="button" onClick={copyRefLink}>{tt('copy')}</button>
          </div>
          <div className="referral-code-row">
            <div className="referral-code" id="referralCode">{referralData?.referral_code || '—'}</div>
          </div>

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
                <button className="friend-code-btn" type="button" disabled={friendBusy || friendCode.length !== 6} onClick={submitFriendCode}>
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" width="18" height="18"><path d="M5 12h14M12 5l7 7-7 7" /></svg>
                </button>
              </div>
              {friendMsg && <div className={`friend-code-msg is-${friendMsg.type}`}>{friendMsg.text}</div>}
            </div>
          )}

          <div className="referral-stats">
            <div className="ref-stat">
              <div id="refTotal">{fmt(referralData?.total || 0)}</div>
              <div id="refTotalLabel">{tt('total')}</div>
            </div>
            <div className="ref-stat">
              <div id="refActive">{fmt(referralData?.active || 0)}</div>
              <div id="refActiveLabel">{tt('active')}</div>
            </div>
            <div className="ref-stat">
              <div id="refEarned">{fmt(referralData?.earned || 0)}</div>
              <div id="refEarnedLabel">{tt('earned')}</div>
            </div>
          </div>
          {(referralData?.referrals || []).length > 0 && (
            <div className="referral-list" id="referralListWrap" style={{ display: 'block' }}>
              <div className="referral-list-title">{tt('recent')}</div>
              <div id="referralList">
                {(referralData.referrals || []).slice(0, 5).map((r, i) => (
                  <div key={i} className="referral-item">
                    <div className="referral-item-name">{r.full_name || r.username || '—'}</div>
                    <div className="referral-item-meta">{r.is_active ? tt('active') : tt('joined')}</div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </RewardCard>
      )}

      {/* ── Redeem bottom sheet ── */}
      <Sheet open={!!redeem} onClose={() => setRedeem(null)} panelId="redeemPanel" backdropId="redeemBackdrop" labelledBy="redeemTitle">
        <div className="sheet-title-row">
          <h3 className="sheet-title" id="redeemTitle">{tt('redeemTitle')}</h3>
          <button className="sheet-close" onClick={() => setRedeem(null)}>{tt('close')}</button>
        </div>
        <p className="sheet-subtitle">{tt('redeemSubtitle')}</p>
        {redeem && (
          <>
            <div className="referral-item" id="redeemVoucherMeta" style={{ display: 'flex' }}>
              <div className="referral-item-name" id="redeemVoucherMetaText">
                #{redeem.reward.id}
                {(redeem.reward.traffic_bytes || 0) / (1024 ** 3) >= 0.5 && ` +${Math.round(redeem.reward.traffic_bytes / (1024 ** 3))}GB`}
                {redeem.reward.extra_days > 0 && ` +${redeem.reward.extra_days}D`}
                {redeem.reward.credit_amount > 0 && ` +${fmt(redeem.reward.credit_amount)}`}
                {redeem.reward.star_increment > 0 && <> +{redeem.reward.star_increment} <StarIcon size={11} /></>}
              </div>
              <div className="referral-item-meta"><TicketIcon size={18} /></div>
            </div>

            {redeem.options.length > 1 && (
              <div id="redeemChoiceSection">
                <div className="referral-list-title">{tt('redeemChoiceLabel')}</div>
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
                <div className="referral-list-title">{tt('selectSubscription')}</div>
                {redeem.subs === null && <p className="sheet-subtitle">{tt('loading')}…</p>}
                {redeem.subs !== null && redeem.subs.length === 0 && (
                  <div id="redeemNoSubs" style={{ display: 'block' }}>
                    <p className="sheet-subtitle">{tt('noSubscriptions')}</p>
                  </div>
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

            <div className="sheet-actions">
              <input
                className="sheet-input"
                id="redeemAddTokenInput"
                type="text"
                placeholder={tt('addTokenPlaceholder')}
                inputMode="text"
                autoCapitalize="none"
                autoComplete="off"
                spellCheck={false}
                value={addToken}
                onChange={(e) => setAddToken(e.target.value)}
              />
              <button className="ref-btn" type="button" onClick={submitToken}>{tt('add')}</button>
              <button className="ref-btn" type="button" onClick={() => { window.location.href = '/webapp/dashboard/purchase.html'; }}>{tt('buyNew')}</button>
              <button
                className="ref-btn primary"
                type="button"
                style={redeemConfirmDisabled ? { opacity: 0.55 } : undefined}
                disabled={redeemConfirmDisabled}
                onClick={confirmRedeem}
              >
                {tt('redeem')}
              </button>
            </div>
          </>
        )}
      </Sheet>
    </div>
  );
}

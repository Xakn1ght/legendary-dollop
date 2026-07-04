import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { PackageIcon } from '../../shared/icons.jsx';
import { getWebApp, hapticImpact, hapticSelection } from '../../shared/telegram.js';
import { api, canUseSessionStorage, getUrlAuthToken } from '../api.js';
import { useShell } from '../ShellContext.js';

import { i18nShop } from './shopI18n.js';

const clampDiscountPct = (pct) => Math.max(0, Math.min(90, Number(pct || 0) || 0));

function openUrl(path, extra = {}) {
  const params = [];
  const authToken = getUrlAuthToken();
  if (authToken && !canUseSessionStorage()) params.push('auth=' + encodeURIComponent(authToken));
  Object.entries(extra).forEach(([k, v]) => {
    if (v != null && v !== '') params.push(k + '=' + encodeURIComponent(v));
  });
  params.push('v=' + Date.now());
  hapticImpact('light');
  window.location.href = path + (path.includes('?') ? '&' : '?') + params.join('&');
}

const Chevron = () => (
  <svg className="shop-plan-chevron" viewBox="0 0 24 24" fill="none" aria-hidden="true">
    <path d="M9 18l6-6-6-6" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

function PriceBlock({ price, finalPrice, discounted, fmt, tt }) {
  return (
    <div className="shop-plan-price">
      {discounted
        ? <><span className="old">{fmt(price)}</span><span className="new">{fmt(finalPrice)} {tt('currency')}</span></>
        : <span className="new">{fmt(price)} {tt('currency')}</span>}
    </div>
  );
}

export function ShopPage() {
  const { lang, openSupportPage } = useShell();
  const tt = useCallback((key) => (i18nShop[lang] || i18nShop.en)[key] || i18nShop.en[key] || key, [lang]);
  const fmt = useCallback((num) => {
    try { return new Intl.NumberFormat(lang === 'fa' ? 'fa-IR' : 'en-US').format(Number(num || 0)); } catch (_) { return String(num ?? ''); }
  }, [lang]);

  const [activeTab, setActiveTab] = useState('purchase');
  const [allPlans, setAllPlans] = useState([]);
  const [plansStatus, setPlansStatus] = useState('loading'); // loading | ready | error
  const [userInfo, setUserInfo] = useState(null);
  const [chargePackages, setChargePackages] = useState([]);
  const [chargeStatus, setChargeStatus] = useState('loading');
  const [chargeVipPct, setChargeVipPct] = useState(0);
  const [subs, setSubs] = useState(null); // null = not loaded yet
  const [selectedSubId, setSelectedSubId] = useState('');
  const [subHighlight, setSubHighlight] = useState(false);
  const [sizeOrder, setSizeOrder] = useState('asc'); // 'asc' small→big | 'desc' big→small
  const [spinPlans, setSpinPlans] = useState(false);
  const [spinCharge, setSpinCharge] = useState(false);
  const subSelectRef = useRef(null);
  const subsLoadedRef = useRef(false);

  const autoDiscounts = userInfo?.auto_discounts || [];
  const autoDiscountPercent = autoDiscounts.reduce((s, d) => s + (Number(d?.percent || 0) || 0), 0);

  const loadShopData = useCallback(async () => {
    try {
      const [plansRes, infoRes] = await Promise.all([
        api('/api/dashboard/purchase/plans').catch(() => null),
        api('/api/dashboard/purchase/user-info').catch(() => null),
      ]);
      if (plansRes && plansRes.ok && plansRes.plans && plansRes.plans.length) {
        setAllPlans(plansRes.plans);
        setPlansStatus('ready');
      } else {
        setAllPlans([]);
        setPlansStatus('error');
      }
      if (infoRes && infoRes.ok) setUserInfo(infoRes.info);
    } catch (_) {
      setPlansStatus('error');
    }
  }, []);

  const loadChargeData = useCallback(async () => {
    try {
      const res = await api('/api/dashboard/charge/packages');
      if (res && res.ok && res.packages && res.packages.length) {
        setChargePackages(res.packages);
        setChargeVipPct(Number(res.vip_discount_percent || 0) || 0);
        setChargeStatus('ready');
      } else {
        setChargePackages([]);
        setChargeStatus('error');
      }
    } catch (_) { setChargeStatus('error'); }
  }, []);

  const loadSubscriptions = useCallback(async () => {
    try {
      const res = await api('/api/dashboard/subscriptions');
      const actives = (res.ok && res.subscriptions ? res.subscriptions : [])
        .filter((s) => String(s.status || '').toLowerCase() === 'active');
      setSubs(actives);
    } catch (_) { setSubs([]); }
  }, []);

  useEffect(() => {
    loadShopData();
    loadChargeData();
  }, [loadShopData, loadChargeData]);

  const switchTab = (tab) => {
    setActiveTab(tab);
    if (tab === 'charge' && !subsLoadedRef.current) {
      subsLoadedRef.current = true;
      loadSubscriptions();
    }
  };

  // Single size-order control (few plans — heavier filters were removed).
  const sortedPlans = useMemo(() => {
    const dir = sizeOrder === 'desc' ? -1 : 1;
    return [...allPlans].sort((a, b) => dir * (a.gb - b.gb) || a.price - b.price);
  }, [allPlans, sizeOrder]);

  const getPlanDisplayName = (p) => (lang === 'en' && p.name_en ? p.name_en : p.name);
  const getDiscountLabel = (d) => {
    if (d.type === 'vip') return 'VIP';
    return lang === 'fa' ? (d.label_fa || d.label_en || tt('discounts')) : (d.label_en || d.label_fa || tt('discounts'));
  };

  const spinThen = (setSpin, fn) => {
    setSpin(true);
    setTimeout(() => setSpin(false), 550);
    fn();
  };

  const chooseCharge = (pkgName) => {
    if (!selectedSubId) {
      try { getWebApp()?.HapticFeedback?.notificationOccurred('warning'); } catch (_) { /* ignore */ }
      subSelectRef.current?.focus();
      setSubHighlight(true);
      setTimeout(() => setSubHighlight(false), 1500);
      return;
    }
    openUrl('/webapp/dashboard/charge.html', { sub_id: selectedSubId, package: pkgName, step: 2 });
  };

  const discountPct = clampDiscountPct(autoDiscountPercent);
  const creditVisible = userInfo && Number(userInfo.credit || 0) > 0;
  const discountChipVisible = autoDiscounts.length > 0 && autoDiscountPercent > 0;

  return (
    <>
      <div className="card shop-hero">
        <div className="shop-row">
          <div className="shop-badge">{tt('badge')}</div>
          <div className="shop-mini">{tt('mini')}</div>
        </div>
        <h1 id="shopHeroTitle">{tt('heroTitle')}</h1>
        <p id="shopHeroSub">{tt('heroSub')}</p>
        <div className="shop-tabs" id="shopTabs">
          <button className={`shop-tab${activeTab === 'purchase' ? ' active' : ''}`} data-tab="purchase" onClick={() => switchTab('purchase')}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="15" height="15"><path d="M6 2L3 6v14a2 2 0 002 2h14a2 2 0 002-2V6l-3-4z" /><line x1="3" y1="6" x2="21" y2="6" /><path d="M16 10a4 4 0 01-8 0" /></svg>
            <span>{tt('tabPurchase')}</span>
          </button>
          <button className={`shop-tab${activeTab === 'charge' ? ' active' : ''}`} data-tab="charge" onClick={() => switchTab('charge')}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="15" height="15"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z" /></svg>
            <span>{tt('tabCharge')}</span>
          </button>
        </div>
        {(creditVisible || discountChipVisible) && (
          <div className="shop-meta" id="shopMeta">
            {creditVisible && (
              <div className="shop-chip" id="shopCreditChip">{tt('walletCredit')}: {fmt(userInfo.credit)} {tt('currency')}</div>
            )}
            {discountChipVisible && (
              <div className="shop-chip" id="shopDiscountChip">
                {tt('discounts')}: {autoDiscounts.filter((d) => Number(d?.percent || 0) > 0).map((d) => `${getDiscountLabel(d)} -${fmt(d.percent)}%`).join(' + ')}
              </div>
            )}
          </div>
        )}
        <div className="shop-tip" id="shopTip">{activeTab === 'charge' ? tt('chargeTip') : tt('tip')}</div>
      </div>

      <div className={`shop-tab-content${activeTab === 'purchase' ? ' active' : ''}`} data-tab="purchase">
        <div className="card shop-plans-card">
          <div className="shop-section-head">
            <div>
              <div className="shop-section-title">{tt('plansTitle')}</div>
              <div className="shop-section-sub">{tt('plansSub')}</div>
            </div>
            <button
              className={`shop-icon-btn${spinPlans ? ' spinning' : ''}`}
              title={tt('refresh')}
              aria-label={tt('refresh')}
              onClick={() => spinThen(setSpinPlans, loadShopData)}
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" width="16" height="16"><path d="M21 12a9 9 0 1 1-2.64-6.36" /><path d="M21 3v6h-6" /></svg>
            </button>
          </div>
          <div className="shop-sort-pills shop-size-order" id="shopSizeOrder" role="radiogroup" aria-label="Sort by size">
            {[['asc', 'sortSmallToBig'], ['desc', 'sortBigToSmall']].map(([key, label]) => (
              <button
                key={key}
                className={`shop-sort-pill${sizeOrder === key ? ' active' : ''}`}
                role="radio"
                aria-checked={sizeOrder === key}
                onClick={() => { setSizeOrder(key); hapticSelection(); }}
              >
                {tt(label)}
              </button>
            ))}
          </div>
          <div className="shop-plans-grid" id="shopPlansGrid" aria-live="polite">
            {plansStatus === 'loading' && [0, 1, 2, 3, 4].map((i) => (
              <div key={i} className="shop-plan-card shop-skeleton" style={{ height: 78 }} />
            ))}
            {plansStatus === 'ready' && sortedPlans.map((plan) => {
              const discountAmount = discountPct > 0 ? Math.floor(plan.price * (discountPct / 100)) : 0;
              const finalPrice = Math.max(0, plan.price - discountAmount);
              const perGb = plan.gb > 0 ? Math.round(finalPrice / plan.gb) : null;
              return (
                <div
                  key={plan.name}
                  className="shop-plan-card"
                  role="button"
                  tabIndex={0}
                  onClick={() => openUrl('/webapp/dashboard/purchase.html', { plan: plan.name, step: 2 })}
                  onKeyDown={(e) => { if (e.key === 'Enter') openUrl('/webapp/dashboard/purchase.html', { plan: plan.name, step: 2 }); }}
                >
                  <div className="shop-plan-top-row">
                    <div className="shop-plan-title">{getPlanDisplayName(plan)}</div>
                    <Chevron />
                  </div>
                  <div className="shop-plan-bottom-row">
                    <div className="shop-plan-badges">
                      <span className="shop-plan-pill gb">{fmt(plan.gb)} {tt('gb')}</span>
                      {discountAmount > 0 && <span className="shop-plan-pill off">-{fmt(discountPct)}%</span>}
                    </div>
                    <div className="shop-plan-price-col">
                      <PriceBlock price={plan.price} finalPrice={finalPrice} discounted={discountAmount > 0} fmt={fmt} tt={tt} />
                      {perGb != null && (
                        <div className="shop-plan-pergb">≈ {fmt(perGb)} {tt('currency')} / {tt('gb')}</div>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
            {plansStatus === 'ready' && (
              <div
                className="shop-plan-card shop-plan-custom"
                role="button"
                tabIndex={0}
                onClick={() => openUrl('/webapp/dashboard/purchase.html', { plan: 'custom' })}
                onKeyDown={(e) => { if (e.key === 'Enter') openUrl('/webapp/dashboard/purchase.html', { plan: 'custom' }); }}
              >
                <div className="shop-plan-top-row">
                  <div className="shop-plan-title" style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                    <PackageIcon size={16} /> {tt('customPlanTitle')}
                  </div>
                  <Chevron />
                </div>
                <div className="shop-plan-bottom-row">
                  <div className="shop-plan-badges">
                    <span className="shop-plan-pill gb">{tt('customPlanPill')}</span>
                  </div>
                  <div className="shop-plan-price"><span className="new">{tt('customPlanPrice')}</span></div>
                </div>
              </div>
            )}
          </div>
          {plansStatus === 'error' && <div className="shop-empty" id="shopPlansEmpty">{tt('loadingFailed')}</div>}
        </div>
      </div>

      <div className={`shop-tab-content${activeTab === 'charge' ? ' active' : ''}`} data-tab="charge">
        <div className="shop-charge-section">
          <div className="shop-sub-picker" id="shopSubPicker">
            <div className="shop-sub-picker-label">{tt('selectSub')}</div>
            <select
              ref={subSelectRef}
              className="shop-sub-select"
              id="shopSubSelect"
              aria-label="Select subscription"
              value={selectedSubId}
              style={subHighlight ? { borderColor: 'rgba(var(--brandRgb),0.5)' } : undefined}
              onChange={(e) => setSelectedSubId(String(e.target.value || ''))}
            >
              {subs === null && <option value="">{tt('loadingSubs')}</option>}
              {subs !== null && subs.length === 0 && <option value="">{tt('noActiveSubs')}</option>}
              {subs !== null && subs.length > 0 && (
                <>
                  <option value="">{tt('selectSubPlaceholder')}</option>
                  {subs.map((s) => (
                    <option key={s.id} value={s.id}>{s.name || s.username || s.marzban_username || ('#' + s.id)}</option>
                  ))}
                </>
              )}
            </select>
            <div className="shop-sub-hint">{tt('subHint')}</div>
          </div>
          <div className="shop-section-head">
            <div>
              <div className="shop-section-title">{tt('chargeTitle')}</div>
              <div className="shop-section-sub">{tt('chargeSub')}</div>
            </div>
            <button
              className={`shop-icon-btn${spinCharge ? ' spinning' : ''}`}
              title={tt('refresh')}
              aria-label={tt('refresh')}
              onClick={() => spinThen(setSpinCharge, loadChargeData)}
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" width="16" height="16"><path d="M21 12a9 9 0 1 1-2.64-6.36" /><path d="M21 3v6h-6" /></svg>
            </button>
          </div>
          <div className="shop-plans-grid" id="shopChargeGrid" aria-live="polite">
            {chargeStatus === 'loading' && [0, 1, 2].map((i) => (
              <div key={i} className="shop-plan-card shop-charge-card shop-skeleton" style={{ height: 78 }} />
            ))}
            {chargeStatus === 'ready' && chargePackages.map((pkg) => {
              const totalPct = Math.min(90, (Number(pkg.discount_percent || 0) || 0) + chargeVipPct);
              const discountAmount = totalPct > 0 ? Math.floor(pkg.price * (totalPct / 100)) : 0;
              const finalPrice = Math.max(0, pkg.price - discountAmount);
              return (
                <div
                  key={pkg.name}
                  className="shop-plan-card shop-charge-card"
                  role="button"
                  tabIndex={0}
                  onClick={() => chooseCharge(pkg.name)}
                  onKeyDown={(e) => { if (e.key === 'Enter') chooseCharge(pkg.name); }}
                >
                  <div className="shop-plan-top-row">
                    <div className="shop-plan-title">{pkg.name}</div>
                    <Chevron />
                  </div>
                  <div className="shop-plan-bottom-row">
                    <div className="shop-plan-badges">
                      <span className="shop-plan-pill gb">{fmt(pkg.gb)} {tt('gb')}</span>
                      {pkg.days > 0 && <span className="shop-plan-pill days">{tt('plusDays').replace('{n}', fmt(pkg.days))}</span>}
                      {totalPct > 0 && <span className="shop-plan-pill off">-{fmt(totalPct)}%</span>}
                      {pkg.badge_label && <span className={`shop-plan-pill ${pkg.badge_type || 'event'}`}>{pkg.badge_label}</span>}
                    </div>
                    <PriceBlock price={pkg.price} finalPrice={finalPrice} discounted={discountAmount > 0} fmt={fmt} tt={tt} />
                  </div>
                </div>
              );
            })}
          </div>
          {chargeStatus === 'error' && <div className="shop-empty" id="shopChargeEmpty">{tt('chargeFailed')}</div>}
          {chargeStatus === 'ready' && chargePackages.length === 0 && <div className="shop-empty" id="shopChargeEmpty">{tt('chargeEmpty')}</div>}
        </div>
      </div>

      <div className="card shop-help">
        <div className="shop-help-left">
          <div className="shop-help-icon" aria-hidden="true">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="18" height="18"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" /></svg>
          </div>
          <div className="shop-help-text">
            <div className="shop-help-title">{tt('helpTitle')}</div>
            <div className="shop-help-sub">{tt('helpSub')}</div>
          </div>
        </div>
        <button className="btn" id="shopSupportBtn" type="button" onClick={() => openSupportPage()}>{tt('support')}</button>
      </div>
    </>
  );
}

import React, { useEffect, useRef, useState } from 'react';

import { api } from '../../shared/auth.js';
import { PackageIcon } from '../../shared/icons.jsx';
import { isAndroidLike } from '../../shared/keyboard.js';
import { hapticSelection } from '../../shared/telegram.js';

// Aggregate auto-discount badges shown on plan cards (VIP + event promos).
// The VIP % does NOT apply to VIP-exclusive plans (offer removed 2026-07-09 —
// list price is the price; flows/pricing.py enforces the same exemption).
function applicableDiscounts(autoDiscounts, vipOnly = false) {
  return (autoDiscounts || []).filter((d) => !(vipOnly && String(d?.type) === 'vip'));
}
function discountPctFor(autoDiscounts, vipOnly = false) {
  const sum = applicableDiscounts(autoDiscounts, vipOnly)
    .reduce((s, d) => s + (Number(d?.percent || 0) || 0), 0);
  return Math.max(0, Math.min(90, sum));
}
function AutoBadges({ autoDiscounts, fmt, t, lang, vipOnly }) {
  const badges = applicableDiscounts(autoDiscounts, vipOnly).map((d, i) => {
    const type = d?.type ? String(d.type) : 'event';
    const pct = Number(d?.percent || 0) || 0;
    if (pct <= 0) return null;
    if (type === 'vip') return <div key={i} className="plan-badge vip">-{fmt(pct)}%</div>;
    const label = lang === 'fa' ? (d.label_fa || d.label_en || t('discount')) : (d.label_en || d.label_fa || t('discount'));
    return <div key={i} className="plan-badge event">{label} -{fmt(pct)}%</div>;
  }).filter(Boolean);
  // VIP-exclusive cards carry a members-only tag in front of the discounts.
  if (vipOnly) badges.unshift(<div key="viptag" className="plan-badge vip-tag">VIP</div>);
  if (!badges.length) return null;
  return <div className="plan-badges">{badges}</div>;
}

// ── multi-month variants (2026-07-09) ────────────────────────────────────
// months prop: 1/2/3 = the duration tab (plans below their min_months are
// hidden; custom card only on 1-month). months=null = "auto" (renewal grid):
// every plan renders at its own minimum — base plans monthly, VIP plans as
// their 2-month package. Checkout names carry "@<n>m" when scaled; the
// server re-resolves and re-prices authoritatively (flows/pricing.py).
export function planFactor(plan, months) {
  const min = Math.max(1, Number(plan.min_months || 1));
  if (months == null) return min;
  return Math.max(min, months);
}
export function scaledPlanSelection(plan, months) {
  const factor = planFactor(plan, months);
  return {
    ...plan,
    base_name: plan.name,
    name: factor > 1 ? `${plan.name}@${factor}m` : plan.name,
    price: Number(plan.price || 0) * factor,
    gb: Number(plan.gb || 0) * factor,
    days: Number(plan.days || 35) * factor,
    months: factor,
  };
}
export function monthsLabel(n, t, fmt) {
  return t('monthsN').replace('{n}', fmt(n));
}

// "Build your own" card + slider/number pop. Quote comes from the server;
// a successful quote auto-selects the virtual custom plan (parity with legacy).
// autoDiscounts: custom plans are NOT vip_only, so the VIP % applies — show
// the discounted price here exactly like the fixed cards (Pasha bug report:
// "the VIP offer isn't applied on the custom").
function CustomPlanCard({ t, fmt, selected, onSelect, autoOpen, autoDiscounts, route }) {
  const isPro = route === 'pro';
  const planPrefix = isPro ? 'pro:' : 'custom:';
  const quoteUrl = isPro
    ? '/api/dashboard/purchase/custom-quote?route=pro'
    : '/api/dashboard/purchase/custom-quote';
  const mine = (sel) => (isPro ? sel?.route === 'pro' : (sel?.custom && sel?.route !== 'pro'));
  const customPct = discountPctFor(autoDiscounts);
  const discounted = (price) => (customPct > 0 ? price - Math.floor(price * (customPct / 100)) : price);
  const [open, setOpen] = useState(autoOpen || mine(selected) || false);
  const [gb, setGb] = useState(mine(selected) ? selected.gb : 50);
  const [maxGb, setMaxGb] = useState(300); // VIP-aware ceiling from the server (300 / 500)
  const [priceLabel, setPriceLabel] = useState(null); // null=tap hint, 'loading', number=price
  // Android Telegram overlays the keyboard without resizing the page; while
  // the GB field is being edited, float the whole editor to the top of the
  // screen where no keyboard can cover it. iOS resizes properly — untouched.
  const [kbFloat, setKbFloat] = useState(false);
  const timerRef = useRef(null);
  const cardRef = useRef(null);
  const numRef = useRef(null);
  const gbRef = useRef(gb);
  gbRef.current = gb;
  // Server price table (index 0 = 1GB) fetched once on first open → every
  // slider tick prices instantly with the EXACT server curve, no round-trips.
  const tableRef = useRef(null);
  const tableLoadRef = useRef(null);

  const loadTable = () => {
    if (tableRef.current || tableLoadRef.current) return tableLoadRef.current;
    tableLoadRef.current = api(`${quoteUrl}${quoteUrl.includes('?') ? '&' : '?'}gb=all`)
      .then((d) => {
        if (d && d.ok && Array.isArray(d.prices)) {
          tableRef.current = { min: d.min || 1, prices: d.prices };
          if (d.max) setMaxGb(d.max);
        }
        return tableRef.current;
      })
      .catch(() => null)
      .finally(() => { tableLoadRef.current = null; });
    return tableLoadRef.current;
  };

  const applyPrice = (value, price) => {
    setPriceLabel(price);
    onSelect({ name: `${planPrefix}${value}`, gb: value, price, custom: true, route: route || 'normal' });
  };

  const quote = (value) => {
    clearTimeout(timerRef.current);
    if (!value || value < 1 || value > maxGb) { setPriceLabel(null); return; }
    const tab = tableRef.current;
    if (tab) {
      const price = tab.prices[value - tab.min];
      if (typeof price === 'number') { applyPrice(value, price); return; }
    }
    // Table not ready yet — load it, then price this value (fallback: single quote).
    setPriceLabel('loading');
    loadTable().then((loaded) => {
      if (gbRef.current !== value) return; // user moved on
      if (loaded) {
        const price = loaded.prices[value - loaded.min];
        if (typeof price === 'number') { applyPrice(value, price); hapticSelection(); return; }
      }
      timerRef.current = setTimeout(async () => {
        try {
          const data = await api(`${quoteUrl}${quoteUrl.includes('?') ? '&' : '?'}gb=${value}`);
          if (!(data && data.ok)) { setPriceLabel(null); return; }
          if (gbRef.current !== data.gb) return; // stale response
          applyPrice(data.gb, data.price);
          hapticSelection();
        } catch (_) { setPriceLabel(null); }
      }, 150);
    });
  };

  // A fixed plan was picked while the builder was open → close the slider
  // (owner bug report: "I have 40 selected and it still shows the bar").
  useEffect(() => {
    if (selected && !mine(selected) && open) { setOpen(false); setPriceLabel(null); }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selected]);

  // autoOpen arrives async (after plans + URL params load), so react to the
  // prop instead of only reading it at mount: open the builder, fetch a
  // quote (which auto-selects the plan) and bring the card into view.
  useEffect(() => {
    if (!autoOpen) return;
    setOpen(true);
    quote(parseInt(gbRef.current, 10) || 50);
    setTimeout(() => {
      try { cardRef.current?.scrollIntoView({ block: 'center', behavior: 'smooth' }); } catch (_) { /* ignore */ }
    }, 120);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- quote is stable per render
  }, [autoOpen]);

  useEffect(() => () => clearTimeout(timerRef.current), []);

  const setGbClamped = (raw) => {
    let v = parseInt(raw, 10);
    if (Number.isFinite(v)) v = Math.max(1, Math.min(maxGb, v));
    setGb(Number.isFinite(v) ? v : raw);
    quote(Number.isFinite(v) ? v : 0);
  };

  const onCardClick = () => {
    if (!open) {
      setOpen(true);
      quote(parseInt(gb, 10));
    } else if (!mine(selected)) {
      setOpen(false);
    }
  };

  const isSelected = !!mine(selected);
  // Hint reflects the live VIP-aware ceiling (maxGb = 300 / 500 from the
  // server) instead of a hardcoded "1-300".
  const customHint = t('customPlanHint').replace('{max}', fmt(maxGb));
  return (
    <>
      <div
        ref={cardRef}
        className={`plan-card plan-card-custom${isSelected ? ' selected' : ''}`}
        data-plan={isPro ? 'pro' : 'custom'}
        role="button"
        tabIndex={0}
        onClick={onCardClick}
        onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onCardClick(); } }}
      >
        <AutoBadges autoDiscounts={autoDiscounts} fmt={fmt} t={t} lang="fa" vipOnly={false} />
        <div className="plan-gb" style={{ fontSize: 26, display: 'flex', justifyContent: 'center' }}><PackageIcon size={26} /></div>
        <div className="plan-gb-label">{isPro ? t('proPlan') : t('customPlan')}</div>
        <div className="plan-price">
          {customPct > 0 && typeof (priceLabel === 'number' ? priceLabel : (isSelected ? selected.price : null)) === 'number' && (
            <div className="old">
              {fmt(typeof priceLabel === 'number' ? priceLabel : selected.price)} <span>{t('currency')}</span>
            </div>
          )}
          <div className="new custom-price-label">
            {priceLabel === 'loading' ? '…'
              : typeof priceLabel === 'number' ? <>{fmt(discounted(priceLabel))} <span>{t('currency')}</span></>
                : isSelected ? <>{fmt(discounted(selected.price))} <span>{t('currency')}</span></>
                  : t('customPlanTap')}
          </div>
        </div>
      </div>
      {kbFloat && (
        <div
          className="kb-float-backdrop"
          onClick={() => { try { document.activeElement?.blur(); } catch (_) { /* ignore */ } setKbFloat(false); }}
        />
      )}
      <div
        className={`custom-plan-pop${kbFloat ? ' kb-float' : ''}`}
        style={{ display: open ? 'block' : 'none' }}
        onBlur={(e) => {
          // Keep floating while focus stays inside (e.g. dragging the slider);
          // collapse only when focus truly leaves the editor.
          if (e.currentTarget.contains(e.relatedTarget)) return;
          setKbFloat(false);
        }}
      >
        <div className="custom-plan-row">
          <input
            type="range" min="1" max={maxGb} step="1" dir="ltr"
            className="custom-gb-range"
            value={Number.isFinite(parseInt(gb, 10)) ? gb : 50}
            onChange={(e) => setGbClamped(e.target.value)}
            aria-label={customHint}
          />
          <input
            ref={numRef}
            type="number" inputMode="numeric" min="1" max={maxGb} dir="ltr"
            className="custom-gb-num"
            value={gb}
            onChange={(e) => setGbClamped(e.target.value)}
            onFocus={() => { if (isAndroidLike()) setKbFloat(true); }}
            onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); e.target.blur(); } }}
            aria-label={customHint}
          />
          <span className="custom-gb-unit">{t('GB')}</span>
        </div>
        <div className="custom-plan-hint">{customHint}</div>
      </div>
    </>
  );
}

export function PlanGrid({ id, t, fmt, lang, plans, autoDiscounts, selectedPlan, onSelect, autoOpenCustom, months = 1, pro }) {
  // months=1: base plans + custom builder + VIP plans (shown at their 2-month
  //           minimum — they must never be hidden from VIP users).
  // months=2/3: everything scaled ×months, no custom builder.
  // months=null (renewal grid): all plans, each at its own minimum duration.
  // Custom builder shows on the 1-month tab AND the renewal/auto-renew grid
  // (months==null). Custom plans are GB-only/1-month by design, and the
  // server accepts "custom:<gb>" as a renewal_template — so auto-renew must
  // offer it too (2026-07-14, Pasha: "auto renew still doesn't have custom
  // gb plans"). It's hidden on the 2/3-month tabs (custom isn't multi-month).
  const showCustom = months === 1 || months == null;
  // months==null = renewal/booking grid → every plan at its own minimum.
  // Numeric tabs (1/2/3) govern for ALL plans incl. VIP bundles: a
  // min_months=2 VIP plan must NOT appear on the 1-month tab (2026-07-14,
  // Pasha). The API already hides vip_only from non-VIP entirely.
  const visiblePlans = plans.filter(
    (p) => months == null || months >= Math.max(1, Number(p.min_months || 1)),
  );
  return (
    <div className="plans-grid" id={id}>
      {visiblePlans.map((plan) => {
        const vipOnly = !!plan.vip_only;
        const factor = planFactor(plan, months);
        const pct = discountPctFor(autoDiscounts, vipOnly);
        const totalPrice = Number(plan.price || 0) * factor;
        const discountAmount = pct > 0 ? Math.floor(totalPrice * (pct / 100)) : 0;
        const finalPrice = totalPrice - discountAmount;
        const scaledName = factor > 1 ? `${plan.name}@${factor}m` : plan.name;
        const isSelected = !!selectedPlan && !selectedPlan.custom
          && (selectedPlan.name === scaledName || selectedPlan.base_name === plan.name);
        return (
          <div
            key={plan.name}
            className={`plan-card${isSelected ? ' selected' : ''}`}
            data-plan={scaledName}
            role="button"
            tabIndex={0}
            onClick={() => { onSelect(scaledPlanSelection(plan, months)); hapticSelection(); }}
            onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onSelect(scaledPlanSelection(plan, months)); hapticSelection(); } }}
          >
            <AutoBadges autoDiscounts={autoDiscounts} fmt={fmt} t={t} lang={lang} vipOnly={vipOnly} />
            <div className="plan-gb">{fmt(Number(plan.gb || 0) * factor)}</div>
            <div className="plan-gb-label">{t('GB')}</div>
            {factor > 1 && <div className="plan-months-tag">{monthsLabel(factor, t, fmt)}</div>}
            <div className="plan-price">
              {discountAmount > 0 && <div className="old">{fmt(totalPrice)} <span>{t('currency')}</span></div>}
              <div className="new">{fmt(finalPrice)} <span>{t('currency')}</span></div>
            </div>
          </div>
        );
      })}
      {showCustom && (
        <CustomPlanCard t={t} fmt={fmt} selected={selectedPlan} onSelect={onSelect} autoOpen={autoOpenCustom} autoDiscounts={autoDiscounts} />
      )}
      {pro?.available && months === 1 && (
        <CustomPlanCard t={t} fmt={fmt} selected={selectedPlan} onSelect={onSelect} autoDiscounts={autoDiscounts} route="pro" />
      )}
    </div>
  );
}

// Segmented duration control for the plan step.
export function MonthsTabs({ t, fmt, months, onChange }) {
  return (
    <div className="months-tabs" role="tablist" aria-label={t('durationLabel')}>
      {[1, 2, 3].map((n) => (
        <button
          key={n}
          type="button"
          role="tab"
          aria-selected={months === n}
          className={`months-tab${months === n ? ' active' : ''}`}
          onClick={() => { if (months !== n) { onChange(n); hapticSelection(); } }}
        >
          {monthsLabel(n, t, fmt)}
        </button>
      ))}
    </div>
  );
}

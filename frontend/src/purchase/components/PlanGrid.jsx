import React, { useEffect, useRef, useState } from 'react';

import { api } from '../../shared/auth.js';
import { PackageIcon } from '../../shared/icons.jsx';
import { isAndroidLike } from '../../shared/keyboard.js';
import { hapticSelection } from '../../shared/telegram.js';

// Aggregate auto-discount badges shown on every plan card (VIP + event promos).
// VIP-exclusive plans never show/get the VIP % — they already carry the best
// per-GB price and the server refuses to stack (flows/pricing.py).
function applicableDiscounts(autoDiscounts, vipOnly) {
  return (autoDiscounts || []).filter((d) => !(vipOnly && String(d?.type) === 'vip'));
}
function discountPctFor(autoDiscounts, vipOnly) {
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
  if (!badges.length) return null;
  return <div className="plan-badges">{badges}</div>;
}

// "Build your own" card + slider/number pop. Quote comes from the server;
// a successful quote auto-selects the virtual custom plan (parity with legacy).
// autoDiscounts: custom plans are NOT vip_only, so the VIP % applies — show
// the discounted price here exactly like the fixed cards (Pasha bug report:
// "the VIP offer isn't applied on the custom").
function CustomPlanCard({ t, fmt, selected, onSelect, autoOpen, autoDiscounts }) {
  const customPct = discountPctFor(autoDiscounts, false);
  const discounted = (price) => (customPct > 0 ? price - Math.floor(price * (customPct / 100)) : price);
  const [open, setOpen] = useState(autoOpen || (selected?.custom ?? false));
  const [gb, setGb] = useState(selected?.custom ? selected.gb : 50);
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
    tableLoadRef.current = api('/api/dashboard/purchase/custom-quote?gb=all')
      .then((d) => {
        if (d && d.ok && Array.isArray(d.prices)) tableRef.current = { min: d.min || 1, prices: d.prices };
        return tableRef.current;
      })
      .catch(() => null)
      .finally(() => { tableLoadRef.current = null; });
    return tableLoadRef.current;
  };

  const applyPrice = (value, price) => {
    setPriceLabel(price);
    onSelect({ name: `custom:${value}`, gb: value, price, custom: true });
  };

  const quote = (value) => {
    clearTimeout(timerRef.current);
    if (!value || value < 1 || value > 300) { setPriceLabel(null); return; }
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
          const data = await api(`/api/dashboard/purchase/custom-quote?gb=${value}`);
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
    if (selected && !selected.custom && open) { setOpen(false); setPriceLabel(null); }
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
    if (Number.isFinite(v)) v = Math.max(1, Math.min(300, v));
    setGb(Number.isFinite(v) ? v : raw);
    quote(Number.isFinite(v) ? v : 0);
  };

  const onCardClick = () => {
    if (!open) {
      setOpen(true);
      quote(parseInt(gb, 10));
    } else if (!selected?.custom) {
      setOpen(false);
    }
  };

  const isSelected = !!selected?.custom;
  return (
    <>
      <div
        ref={cardRef}
        className={`plan-card plan-card-custom${isSelected ? ' selected' : ''}`}
        data-plan="custom"
        role="button"
        tabIndex={0}
        onClick={onCardClick}
        onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onCardClick(); } }}
      >
        <AutoBadges autoDiscounts={autoDiscounts} fmt={fmt} t={t} lang="fa" vipOnly={false} />
        <div className="plan-gb" style={{ fontSize: 26, display: 'flex', justifyContent: 'center' }}><PackageIcon size={26} /></div>
        <div className="plan-gb-label">{t('customPlan')}</div>
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
            type="range" min="1" max="300" step="1" dir="ltr"
            className="custom-gb-range"
            value={Number.isFinite(parseInt(gb, 10)) ? gb : 50}
            onChange={(e) => setGbClamped(e.target.value)}
            aria-label={t('customPlanHint')}
          />
          <input
            ref={numRef}
            type="number" inputMode="numeric" min="1" max="300" dir="ltr"
            className="custom-gb-num"
            value={gb}
            onChange={(e) => setGbClamped(e.target.value)}
            onFocus={() => { if (isAndroidLike()) setKbFloat(true); }}
            onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); e.target.blur(); } }}
            aria-label={t('customPlanHint')}
          />
          <span className="custom-gb-unit">{t('GB')}</span>
        </div>
        <div className="custom-plan-hint">{t('customPlanHint')}</div>
      </div>
    </>
  );
}

export function PlanGrid({ id, t, fmt, lang, plans, autoDiscounts, selectedPlan, onSelect, autoOpenCustom }) {
  return (
    <div className="plans-grid" id={id}>
      {plans.map((plan) => {
        const vipOnly = !!plan.vip_only;
        const pct = discountPctFor(autoDiscounts, vipOnly);
        const totalPrice = Number(plan.price || 0);
        const discountAmount = pct > 0 ? Math.floor(totalPrice * (pct / 100)) : 0;
        const finalPrice = totalPrice - discountAmount;
        const isSelected = !!selectedPlan && !selectedPlan.custom && selectedPlan.name === plan.name;
        return (
          <div
            key={plan.name}
            className={`plan-card${isSelected ? ' selected' : ''}`}
            data-plan={plan.name}
            role="button"
            tabIndex={0}
            onClick={() => { onSelect(plan); hapticSelection(); }}
            onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onSelect(plan); hapticSelection(); } }}
          >
            <AutoBadges autoDiscounts={autoDiscounts} fmt={fmt} t={t} lang={lang} vipOnly={vipOnly} />
            <div className="plan-gb">{fmt(plan.gb)}</div>
            <div className="plan-gb-label">{t('GB')}</div>
            <div className="plan-price">
              {discountAmount > 0 && <div className="old">{fmt(totalPrice)} <span>{t('currency')}</span></div>}
              <div className="new">{fmt(finalPrice)} <span>{t('currency')}</span></div>
            </div>
          </div>
        );
      })}
      <CustomPlanCard t={t} fmt={fmt} selected={selectedPlan} onSelect={onSelect} autoOpen={autoOpenCustom} autoDiscounts={autoDiscounts} />
    </div>
  );
}

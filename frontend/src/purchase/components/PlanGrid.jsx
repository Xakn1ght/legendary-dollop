import React, { useEffect, useRef, useState } from 'react';

import { api } from '../../shared/auth.js';
import { PackageIcon } from '../../shared/icons.jsx';
import { isAndroidLike } from '../../shared/keyboard.js';
import { hapticSelection } from '../../shared/telegram.js';

// Aggregate auto-discount badges shown on every plan card (VIP + event promos).
function AutoBadges({ autoDiscounts, fmt, t, lang }) {
  const badges = (autoDiscounts || []).map((d, i) => {
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
function CustomPlanCard({ t, fmt, selected, onSelect, autoOpen }) {
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

  const quote = (value) => {
    clearTimeout(timerRef.current);
    if (!value || value < 1 || value > 300) { setPriceLabel(null); return; }
    setPriceLabel('loading');
    timerRef.current = setTimeout(async () => {
      try {
        const data = await api(`/api/dashboard/purchase/custom-quote?gb=${value}`);
        if (!(data && data.ok)) { setPriceLabel(null); return; }
        if (gbRef.current !== data.gb) return; // stale response
        setPriceLabel(data.price);
        onSelect({ name: data.plan_name, gb: data.gb, price: data.price, custom: true });
        hapticSelection();
      } catch (_) { setPriceLabel(null); }
    }, 300);
  };

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
        <div className="plan-gb" style={{ fontSize: 26, display: 'flex', justifyContent: 'center' }}><PackageIcon size={26} /></div>
        <div className="plan-gb-label">{t('customPlan')}</div>
        <div className="plan-price">
          <div className="new custom-price-label">
            {priceLabel === 'loading' ? '…'
              : typeof priceLabel === 'number' ? <>{fmt(priceLabel)} <span>{t('currency')}</span></>
                : isSelected ? <>{fmt(selected.price)} <span>{t('currency')}</span></>
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
  const autoDiscountPercent = (autoDiscounts || []).reduce((sum, d) => sum + (Number(d?.percent || 0) || 0), 0);
  const discountPct = Math.max(0, Math.min(90, autoDiscountPercent));

  return (
    <div className="plans-grid" id={id}>
      {plans.map((plan) => {
        const totalPrice = Number(plan.price || 0);
        const discountAmount = discountPct > 0 ? Math.floor(totalPrice * (discountPct / 100)) : 0;
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
            <AutoBadges autoDiscounts={autoDiscounts} fmt={fmt} t={t} lang={lang} />
            <div className="plan-gb">{fmt(plan.gb)}</div>
            <div className="plan-gb-label">{t('GB')}</div>
            <div className="plan-price">
              {discountAmount > 0 && <div className="old">{fmt(totalPrice)} <span>{t('currency')}</span></div>}
              <div className="new">{fmt(finalPrice)} <span>{t('currency')}</span></div>
            </div>
          </div>
        );
      })}
      <CustomPlanCard t={t} fmt={fmt} selected={selectedPlan} onSelect={onSelect} autoOpen={autoOpenCustom} />
    </div>
  );
}

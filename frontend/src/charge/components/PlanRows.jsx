import React, { useEffect, useRef, useState } from 'react';

import { api } from '../../shared/auth.js';
import { PackageIcon } from '../../shared/icons.jsx';
import { hapticSelection } from '../../shared/telegram.js';

import s from './PlanRows.module.css';

// PlanRows (2026-07-18, Pasha: "the ui is kinda horrible and i want the same
// exact plans for charge that we have for purchase") — THE plan picker for
// the charge app (top-up packages, booking, auto-renew template). Shop-row
// anatomy (title / pills / price / per-GB) instead of the old number-block
// grid, radio-select semantics instead of navigation.
//
// Selection objects mirror PlanGrid.scaledPlanSelection: name carries "@Nm"
// when scaled, "custom:<gb>" for the builder; price/gb/days arrive scaled.
// flows/charge.py re-resolves and re-prices authoritatively server-side.

function discountPctFor(autoDiscounts, vipOnly = false) {
  const sum = (autoDiscounts || [])
    .filter((d) => !(vipOnly && String(d?.type) === 'vip'))
    .reduce((acc, d) => acc + (Number(d?.percent || 0) || 0), 0);
  return Math.max(0, Math.min(90, sum));
}

export function planFactor(plan, months) {
  const min = Math.max(1, Number(plan.min_months || 1));
  if (months == null) return min;
  return Math.max(min, months);
}

// Title rule (2026-07-15, "fix the display names"): scaled variants rebuild
// from the SCALED TOTAL GB so the title never contradicts the GB pill —
// mirrors server plan_display_name and the shop.
export function planRowTitle(plan, factor, lang, t, fmt) {
  const baseName = lang === 'en' && plan.name_en ? plan.name_en : plan.name;
  if (factor <= 1) return baseName;
  const gbTotal = Number(plan.gb || 0) * factor;
  const unit = lang === 'en' ? 'GB' : 'گیگ';
  const vip = plan.vip_only ? ' VIP' : '';
  return `${fmt(gbTotal)} ${unit}${vip} | ${t('monthsTag').replace('{n}', fmt(factor))}`;
}

export function scaledSelection(plan, months, lang, t, fmt) {
  const factor = planFactor(plan, months);
  return {
    ...plan,
    base_name: plan.name,
    name: factor > 1 ? `${plan.name}@${factor}m` : plan.name,
    display_name: planRowTitle(plan, factor, lang, t, fmt),
    price: Number(plan.price || 0) * factor,
    gb: Number(plan.gb || 0) * factor,
    days: Number(plan.days || 35) * factor,
    months: factor,
  };
}

const CheckDot = () => (
  <span className={s.check} aria-hidden="true">
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3.4" strokeLinecap="round" strokeLinejoin="round" width="11" height="11"><polyline points="20 6 9 17 4 12" /></svg>
  </span>
);

function PriceCol({ price, finalPrice, perGb, t, fmt }) {
  const discounted = finalPrice < price;
  return (
    <div className={s.priceCol}>
      <div className={s.price}>
        {discounted && <span className={s.old}>{fmt(price)}</span>}
        <span className={s.new}>{fmt(finalPrice)} {t('currency')}</span>
      </div>
      {perGb != null && <div className={s.perGb}>≈ {fmt(perGb)} {t('currency')} / {t('perGbUnit')}</div>}
    </div>
  );
}

// Build-your-own row: inline slider editor, priced by the server curve
// (/purchase/custom-quote table = the EXACT prices flows/charge.py bills).
function CustomRow({ t, fmt, lang, autoDiscounts, selected, onSelect, customDays = 35 }) {
  const [open, setOpen] = useState(!!selected?.custom);
  const [gb, setGb] = useState(selected?.custom ? selected.gb : 50);
  const [maxGb, setMaxGb] = useState(300); // VIP-aware ceiling from the server (300 / 500)
  const [price, setPrice] = useState(selected?.custom ? selected.price : null); // null | 'loading' | number
  const rowRef = useRef(null);
  const gbRef = useRef(gb);
  gbRef.current = gb;
  const tableRef = useRef(null);
  const tableLoadRef = useRef(null);

  const pct = discountPctFor(autoDiscounts, false);
  const discounted = (p) => (pct > 0 ? p - Math.floor(p * (pct / 100)) : p);

  const loadTable = () => {
    if (tableRef.current) return Promise.resolve(tableRef.current);
    if (tableLoadRef.current) return tableLoadRef.current;
    tableLoadRef.current = api('/api/dashboard/purchase/custom-quote?gb=all')
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

  const quote = (value) => {
    if (!value || value < 1 || value > maxGb) { setPrice(null); onSelect(null); return; }
    const apply = (p) => {
      setPrice(p);
      onSelect({
        name: `custom:${value}`,
        display_name: `${t('customPlan')} — ${fmt(value)} ${t('GB')}`,
        gb: value,
        price: p,
        days: customDays,
        months: 1,
        custom: true,
      });
    };
    const tab = tableRef.current;
    if (tab && typeof tab.prices[value - tab.min] === 'number') { apply(tab.prices[value - tab.min]); return; }
    setPrice('loading');
    loadTable().then((loaded) => {
      if (gbRef.current !== value) return;
      const p = loaded && loaded.prices[value - loaded.min];
      if (typeof p === 'number') apply(p); else setPrice(null);
    });
  };

  // Picking a fixed row while the builder is open closes it.
  useEffect(() => {
    if (selected && !selected.custom && open) { setOpen(false); setPrice(null); }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selected]);

  const setGbClamped = (raw) => {
    let v = parseInt(raw, 10);
    if (Number.isFinite(v)) v = Math.max(1, Math.min(maxGb, v));
    setGb(Number.isFinite(v) ? v : raw);
    quote(Number.isFinite(v) ? v : 0);
  };

  const isSelected = !!selected?.custom;
  const shown = typeof price === 'number' ? discounted(price) : null;
  const openEditor = () => {
    if (open) return;
    setOpen(true);
    loadTable();
    quote(parseInt(gb, 10));
    hapticSelection();
    // The editor expands below the fold behind the sticky footer buttons —
    // bring the whole row into view once it has rendered.
    setTimeout(() => {
      try { rowRef.current?.scrollIntoView({ block: 'center', behavior: 'smooth' }); } catch (_) { /* ignore */ }
    }, 120);
  };

  return (
    <div
      ref={rowRef}
      className={`${s.row}${isSelected ? ` ${s.selected}` : ''}`}
      role="radio"
      aria-checked={isSelected}
      tabIndex={0}
      onClick={openEditor}
      onKeyDown={(e) => { if ((e.key === 'Enter' || e.key === ' ') && !open) { e.preventDefault(); openEditor(); } }}
    >
      <div className={s.topRow}>
        <CheckDot />
        <div className={`${s.title} ${s.customTitle}`}>
          <PackageIcon size={15} /> {t('customPlan')}
        </div>
      </div>
      <div className={s.bottomRow}>
        <div className={s.pills}>
          <span className={`${s.pill} ${s.gb}`}>{t('customRangePill').replace('{max}', fmt(maxGb))}</span>
          <span className={`${s.pill} ${s.days}`}>{t('plusDays').replace('{n}', fmt(customDays))}</span>
          {pct > 0 && <span className={`${s.pill} ${s.off}`}>-{fmt(pct)}%</span>}
        </div>
        {!open && <div className={s.price}><span className={s.new}>{t('customPriceByGb')}</span></div>}
        {open && (
          <div className={s.price}>
            {price === 'loading' && <span className={s.new}>…</span>}
            {typeof price === 'number' && pct > 0 && <span className={s.old}>{fmt(price)}</span>}
            {typeof price === 'number' && <span className={s.new}>{fmt(shown)} {t('currency')}</span>}
          </div>
        )}
      </div>
      {open && (
        <div className={s.editor} onClick={(e) => e.stopPropagation()}>
          <div className={s.sliderRow}>
            <input
              type="range" min="1" max={maxGb} step="1" dir="ltr"
              className={s.range}
              value={Number.isFinite(parseInt(gb, 10)) ? gb : 50}
              onChange={(e) => setGbClamped(e.target.value)}
              aria-label={t('customPlan')}
            />
            <input
              type="number" inputMode="numeric" min="1" max={maxGb} dir="ltr"
              className={s.num}
              value={gb}
              onChange={(e) => setGbClamped(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); e.target.blur(); } }}
              aria-label={t('customPlan')}
            />
            <span className={s.unit}>{t('GB')}</span>
          </div>
        </div>
      )}
    </div>
  );
}

export function PlanRows({
  t, fmt, lang, plans, autoDiscounts,
  months = 1, selected, onSelect, showCustom = true, customDays = 35, idPrefix = 'planrow',
}) {
  // Month tab governs for everyone: plans below their min_months are hidden
  // (a min_months=2 VIP bundle never sits on the 1-month tab, 2026-07-14).
  const visible = (plans || []).filter(
    (p) => months == null || months >= Math.max(1, Number(p.min_months || 1)),
  );
  const customVisible = showCustom && (months === 1 || months == null);
  return (
    <div className={s.list} role="radiogroup" aria-label={t('selectPackage')}>
      {visible.map((plan) => {
        const factor = planFactor(plan, months);
        const vipOnly = !!plan.vip_only;
        const pct = discountPctFor(autoDiscounts, vipOnly);
        const scaledPrice = Number(plan.price || 0) * factor;
        const scaledGb = Number(plan.gb || 0) * factor;
        const scaledDays = Number(plan.days || 35) * factor;
        const discountAmount = pct > 0 ? Math.floor(scaledPrice * (pct / 100)) : 0;
        const finalPrice = scaledPrice - discountAmount;
        const perGb = scaledGb > 0 && finalPrice > 0 ? Math.round(finalPrice / scaledGb) : null;
        const scaledName = factor > 1 ? `${plan.name}@${factor}m` : plan.name;
        const isSelected = !!selected && !selected.custom
          && (selected.name === scaledName || selected.base_name === plan.name);
        const pick = () => { onSelect(scaledSelection(plan, months, lang, t, fmt)); hapticSelection(); };
        return (
          <div
            key={plan.name}
            id={`${idPrefix}-${plan.name}`}
            className={`${s.row}${isSelected ? ` ${s.selected}` : ''}`}
            data-plan={scaledName}
            role="radio"
            aria-checked={isSelected}
            tabIndex={0}
            onClick={pick}
            onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); pick(); } }}
          >
            <div className={s.topRow}>
              <CheckDot />
              <div className={s.title}>{planRowTitle(plan, factor, lang, t, fmt)}</div>
            </div>
            <div className={s.bottomRow}>
              <div className={s.pills}>
                <span className={`${s.pill} ${s.gb}`}>{fmt(scaledGb)} {t('GB')}</span>
                {scaledDays > 0 && <span className={`${s.pill} ${s.days}`}>{t('plusDays').replace('{n}', fmt(scaledDays))}</span>}
                {pct > 0 && <span className={`${s.pill} ${s.off}`}>-{fmt(pct)}%</span>}
                {vipOnly && <span className={`${s.pill} ${s.vip}`}>VIP</span>}
              </div>
              <PriceCol price={scaledPrice} finalPrice={finalPrice} perGb={perGb} t={t} fmt={fmt} />
            </div>
          </div>
        );
      })}
      {customVisible && (
        <CustomRow
          t={t}
          fmt={fmt}
          lang={lang}
          autoDiscounts={autoDiscounts}
          selected={selected}
          onSelect={onSelect}
          customDays={customDays}
        />
      )}
    </div>
  );
}

import React, { useEffect, useRef, useState } from 'react';

import { api } from '../../shared/auth.js';

// Build-your-own top-up (2026-07-09, Pasha: "add custom plans too") — same
// slider anatomy as the purchase page's custom card. Prices come from the
// shared server curve via /purchase/custom-quote (identical math to what
// /charge/start will charge for "custom:<gb>").
function CustomChargeCard({ t, fmt, selected, isVip, vipDiscountPercent, onSelectCustom }) {
  const [open, setOpen] = useState(false);
  const [gb, setGb] = useState(50);
  const [price, setPrice] = useState(null); // null | 'loading' | number
  const gbRef = useRef(gb);
  gbRef.current = gb;
  const tableRef = useRef(null);
  const tableLoadRef = useRef(null);

  const loadTable = () => {
    if (tableRef.current) return Promise.resolve(tableRef.current);
    if (tableLoadRef.current) return tableLoadRef.current;
    tableLoadRef.current = api('/api/dashboard/purchase/custom-quote?gb=all')
      .then((d) => {
        if (d && d.ok && Array.isArray(d.prices)) tableRef.current = { min: d.min || 1, prices: d.prices };
        return tableRef.current;
      })
      .catch(() => null)
      .finally(() => { tableLoadRef.current = null; });
    return tableLoadRef.current;
  };

  const quote = (value) => {
    if (!value || value < 1 || value > 300) { setPrice(null); onSelectCustom(null); return; }
    const apply = (p) => {
      setPrice(p);
      onSelectCustom({ name: `custom:${value}`, gb: value, price: p, days: 35, custom: true });
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

  // Picking a fixed package while the builder is open closes it.
  useEffect(() => {
    if (selected && !selected.startsWith('custom:') && open) { setOpen(false); setPrice(null); }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selected]);

  const setGbClamped = (raw) => {
    let v = parseInt(raw, 10);
    if (Number.isFinite(v)) v = Math.max(1, Math.min(300, v));
    setGb(Number.isFinite(v) ? v : raw);
    quote(Number.isFinite(v) ? v : 0);
  };

  const isSelected = !!(selected && selected.startsWith('custom:'));
  const vipPct = isVip ? (Number(vipDiscountPercent || 0) || 0) : 0;
  const shown = typeof price === 'number' && vipPct > 0 ? price - Math.floor(price * (vipPct / 100)) : price;

  return (
    <div
      className={`plan-card plan-card-custom${isSelected ? ' selected' : ''}`}
      data-package="custom"
      role="button"
      tabIndex={0}
      onClick={() => { if (!open) { setOpen(true); quote(parseInt(gb, 10)); } }}
      onKeyDown={(e) => { if ((e.key === 'Enter' || e.key === ' ') && !open) { e.preventDefault(); setOpen(true); quote(parseInt(gb, 10)); } }}
    >
      <div className="plan-gb custom-mark" aria-hidden="true">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" width="26" height="26"><path d="M12 20h9" /><path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4Z" /></svg>
      </div>
      <div className="plan-gb-label">{t('customCharge')}</div>
      {!open && <div className="plan-days custom-hint">{t('customChargeHint')}</div>}
      {open && (
        <div className="custom-editor" onClick={(e) => e.stopPropagation()}>
          <div className="custom-row">
            <input
              type="range" min="1" max="300" value={Number.isFinite(parseInt(gb, 10)) ? gb : 50}
              onChange={(e) => setGbClamped(e.target.value)}
              aria-label={t('customCharge')}
            />
            <input
              className="custom-num" type="number" inputMode="numeric" min="1" max="300" value={gb}
              onChange={(e) => setGbClamped(e.target.value)}
            />
            <span className="custom-unit">{t('GB')}</span>
          </div>
          <div className="plan-days">+{fmt(35)} {t('days')}</div>
          <div className="plan-price">
            <div className="new">
              {price === 'loading' ? '…'
                : typeof shown === 'number' ? <>{fmt(shown)} <span>{t('currency')}</span></>
                : '—'}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export function PackageSection({ t, fmt, packages, packagesStatus, selectedPackageName, isVip, vipDiscountPercent, onSelect, onSelectCustom, onBack, onContinue }) {
  return (
    <div className="section active" id="section-package">
      <div className="card">
        <div className="card-title">
          <div className="icon">
            <svg viewBox="0 0 24 24"><path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z" /></svg>
          </div>
          <span>{t('selectPackage')}</span>
        </div>

        <div className="plans-grid" id="packagesGrid">
          {packagesStatus !== 'ready' && (
            <div className="no-plans" id="noPackagesMsg">
              <svg viewBox="0 0 24 24"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z" /></svg>
              <div>
                {packagesStatus === 'loading' ? t('loadingPackages')
                  : packagesStatus === 'empty' ? t('noPackagesAvailable')
                    : t('errorOccurred')}
              </div>
            </div>
          )}
          {packagesStatus === 'ready' && packages.map((pkg) => {
            const totalPrice = Number(pkg.price || 0);
            const pkgDiscount = Number(pkg.discount_percent || 0) || 0;
            const vipDiscount = isVip ? (Number(vipDiscountPercent || 0) || 0) : 0;
            const totalDiscountPercent = Math.max(0, Math.min(90, pkgDiscount + vipDiscount));
            const discountAmount = totalDiscountPercent > 0 ? Math.floor(totalPrice * (totalDiscountPercent / 100)) : 0;
            const finalPrice = totalPrice - discountAmount;
            const badges = [];
            if (isVip && vipDiscountPercent > 0) badges.push({ cls: 'vip', label: `-${fmt(vipDiscountPercent)}%` });
            if (pkg.discount_percent > 0) badges.push({ cls: 'event', label: `${pkg.discount_percent}% OFF` });
            if (pkg.badge_label) badges.push({ cls: pkg.badge_type || 'event', label: pkg.badge_label });
            return (
              <div
                key={pkg.name}
                className={`plan-card${pkg.name === selectedPackageName ? ' selected' : ''}`}
                data-package={pkg.name}
                role="button"
                tabIndex={0}
                onClick={() => onSelect(pkg.name)}
                onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onSelect(pkg.name); } }}
              >
                {badges.length > 0 && (
                  <div className="plan-badges">
                    {badges.map((b, i) => <div key={i} className={`plan-badge ${b.cls}`}>{b.label}</div>)}
                  </div>
                )}
                <div className="plan-gb">{fmt(pkg.gb)}</div>
                <div className="plan-gb-label">{t('GB')}</div>
                {pkg.days ? <div className="plan-days">+{fmt(pkg.days)} {t('days')}</div> : null}
                <div className="plan-price">
                  {discountAmount > 0 && <div className="old">{fmt(totalPrice)} <span>{t('currency')}</span></div>}
                  <div className="new">{fmt(finalPrice)} <span>{t('currency')}</span></div>
                </div>
              </div>
            );
          })}
          {packagesStatus === 'ready' && (
            <CustomChargeCard
              t={t}
              fmt={fmt}
              selected={selectedPackageName}
              isVip={isVip}
              vipDiscountPercent={vipDiscountPercent}
              onSelectCustom={onSelectCustom}
            />
          )}
        </div>
      </div>

      <div className="btn-container">
        <button className="btn btn-secondary" onClick={onBack}>
          <span>{t('back')}</span>
        </button>
        <button className="btn btn-primary" id="btnSelectPackage" disabled={!selectedPackageName} onClick={onContinue}>
          <span>{t('continue')}</span>
        </button>
      </div>
    </div>
  );
}

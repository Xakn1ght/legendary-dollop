import React, { useEffect, useRef, useState } from 'react';

import { couponDescription, couponLabel } from '../coupons.js';

// Custom coupon listbox (2026-07-09 — replaces the unstyled native <select>):
// each option carries a one-line explainer, incl. the discount cap that used
// to make "50% off" look broken on big plans.
function CouponPicker({ t, lang, plans, shownCoupons, selectedCouponId, onSelectCoupon }) {
  const [open, setOpen] = useState(false);
  const wrapRef = useRef(null);

  useEffect(() => {
    if (!open) return undefined;
    const onDoc = (e) => { if (wrapRef.current && !wrapRef.current.contains(e.target)) setOpen(false); };
    document.addEventListener('pointerdown', onDoc);
    return () => document.removeEventListener('pointerdown', onDoc);
  }, [open]);

  const current = shownCoupons.find((c) => c.id === selectedCouponId) || null;

  const pick = (id) => { onSelectCoupon(id); setOpen(false); };

  const Row = ({ id, label, desc, on }) => (
    <button type="button" className={'cpk-row' + (on ? ' on' : '')} role="option" aria-selected={on} onClick={() => pick(id)}>
      <span className={'cpk-dot' + (on ? ' on' : '')} aria-hidden="true" />
      <span className="cpk-txt">
        <span className="cpk-label">{label}</span>
        {desc && <span className="cpk-desc">{desc}</span>}
      </span>
    </button>
  );

  return (
    <div className={'cpk' + (open ? ' open' : '')} ref={wrapRef}>
      <button
        type="button"
        className="form-input cpk-trigger"
        aria-haspopup="listbox"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
      >
        <span className="cpk-trigger-txt">{current ? couponLabel(current, lang) : t('couponNone')}</span>
        <svg className="cpk-chev" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" width="15" height="15" aria-hidden="true"><path d="m6 9 6 6 6-6" /></svg>
      </button>
      {open && (
        <div className="cpk-list" role="listbox">
          <Row id={null} label={t('couponNone')} desc={t('couponNoneDesc')} on={selectedCouponId === null} />
          {shownCoupons.map((c) => (
            <Row
              key={c.id}
              id={c.id}
              label={couponLabel(c, lang)}
              desc={couponDescription(c, lang, plans)}
              on={selectedCouponId === c.id}
            />
          ))}
        </div>
      )}
    </div>
  );
}

export function PaymentSection({
  t, fmt, fmtPrice, lang, userInfo, plans,
  useCredit, onUseCreditChange,
  selectedDiscountIds, onToggleDiscount,
  shownCoupons, selectedCouponId, onSelectCoupon,
  summary,
  onBack, onConfirm,
}) {
  return (
    <div className="section active" id="section-payment">
      <div className="card">
        <div className="card-title">
          <div className="icon">
            <svg viewBox="0 0 24 24"><path d="M20 4H4c-1.11 0-1.99.89-1.99 2L2 18c0 1.11.89 2 2 2h16c1.11 0 2-.89 2-2V6c0-1.11-.89-2-2-2zm0 14H4v-6h16v6zm0-10H4V6h16v2z" /></svg>
          </div>
          <span>{t('paymentInfo')}</span>
        </div>

        {userInfo?.credit > 0 && (
          <div id="creditInfo" style={{ marginBottom: 20 }}>
            {/* Label + toggle share the first row; the credit chip sits below. */}
            <div className="toggle-row" style={{ border: 'none', padding: 0, marginBottom: 10 }}>
              <span className="toggle-label">{t('useCredit')}</span>
              <label className="toggle-switch">
                <input
                  type="checkbox"
                  id="useCredit"
                  aria-label={t('useCredit')}
                  checked={useCredit}
                  onChange={(e) => onUseCreditChange(e.target.checked)}
                />
                <span className="toggle-slider" />
              </label>
            </div>
            <div className="credit-badge">
              <svg viewBox="0 0 24 24"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1.41 16.09V20h-2.67v-1.93c-1.71-.36-3.16-1.46-3.27-3.4h1.96c.1 1.05.82 1.87 2.65 1.87 1.96 0 2.4-.98 2.4-1.59 0-.83-.44-1.61-2.67-2.14-2.48-.6-4.18-1.62-4.18-3.67 0-1.72 1.39-2.84 3.11-3.21V4h2.67v1.95c1.86.45 2.79 1.86 2.85 3.39H14.3c-.05-1.11-.64-1.87-2.22-1.87-1.5 0-2.4.68-2.4 1.64 0 .84.65 1.39 2.67 1.91s4.18 1.39 4.18 3.91c-.01 1.83-1.38 2.83-3.12 3.16z" /></svg>
              <span id="creditAmount">{fmt(userInfo.credit)}</span> <span>{t('currency')}</span>
            </div>
          </div>
        )}

        {userInfo?.discounts?.length > 0 && (
          <div id="discountsInfo" style={{ marginBottom: 20 }}>
            <label className="form-label">{t('activeDiscounts')}</label>
            <div id="discountsList" style={{ marginTop: 10, display: 'flex', flexWrap: 'wrap', gap: 8 }}>
              {userInfo.discounts.map((d) => {
                const on = selectedDiscountIds.includes(d.id);
                return (
                  <label key={d.id} className="discount-tag" style={{ cursor: 'pointer', opacity: on ? 1 : 0.55 }}>
                    <input
                      type="checkbox"
                      style={{ display: 'none' }}
                      checked={on}
                      onChange={() => onToggleDiscount(d.id)}
                      data-discount-id={d.id}
                    />
                    <span
                      aria-hidden="true"
                      style={{
                        width: 16, height: 16, borderRadius: 5, display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                        border: '1.5px solid rgba(52, 211, 153, 0.7)', background: on ? 'rgba(52, 211, 153, 0.9)' : 'transparent',
                        color: '#052e22', transition: 'all .15s', flexShrink: 0,
                      }}
                    >
                      {on && (
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3.2" strokeLinecap="round" strokeLinejoin="round" width="10" height="10"><path d="M20 6 9 17l-5-5" /></svg>
                      )}
                    </span>
                    {d.percent}% ({d.source})
                  </label>
                );
              })}
            </div>
          </div>
        )}

        {shownCoupons.length > 0 && (
          <div id="couponInfo" style={{ marginBottom: 20 }}>
            <label className="form-label">{t('rewardCoupon')}</label>
            <CouponPicker
              t={t}
              lang={lang}
              plans={plans}
              shownCoupons={shownCoupons}
              selectedCouponId={selectedCouponId}
              onSelectCoupon={onSelectCoupon}
            />
          </div>
        )}

        <div className="summary" id="orderSummary" style={{ marginTop: 4 }}>
          <div className="summary-row">
            <span className="label">{t('selectedPlan')}</span>
            <span className="value" id="summaryPlan">{summary.planLabel}</span>
          </div>
          {summary.renewalLabel && (
            <div className="summary-row" id="summaryRenewalRow">
              <span className="label">{t('autoRenewal')}</span>
              <span className="value" id="summaryRenewal">{summary.renewalLabel}</span>
            </div>
          )}
          <div className="summary-row">
            <span className="label">{t('totalPrice')}</span>
            <span className="value" id="summaryTotalPrice">{fmtPrice(summary.totalPrice)}</span>
          </div>
          {summary.discountAmount > 0 && (
            <div className="summary-row discount" id="summaryDiscountRow">
              <span className="label">{t('discount')}</span>
              <span className="value" id="summaryDiscount">-{fmtPrice(summary.discountAmount)}</span>
            </div>
          )}
          {summary.couponCapApplied && (
            <div className="summary-cap-note" id="summaryCapNote">
              {t('couponCapNote').replace('{cap}', fmtPrice(summary.couponCapBase))}
            </div>
          )}
          {summary.creditUsed > 0 && (
            <div className="summary-row discount" id="summaryCreditRow">
              <span className="label">{t('credit')}</span>
              <span className="value" id="summaryCredit">-{fmtPrice(summary.creditUsed)}</span>
            </div>
          )}
          <div className="summary-row total">
            <span className="label">{t('amountDue')}</span>
            <span className="value" id="summaryFinal">{fmtPrice(summary.finalPrice)}</span>
          </div>
        </div>
      </div>

      <div className="btn-container">
        <button className="btn btn-secondary" onClick={onBack}>
          <span>{t('back')}</span>
        </button>
        <button className="btn btn-primary" onClick={onConfirm}>
          <span>{t('confirmPay')}</span>
        </button>
      </div>
    </div>
  );
}

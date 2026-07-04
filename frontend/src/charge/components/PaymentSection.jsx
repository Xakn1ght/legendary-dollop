import React from 'react';

function getPlanDisplayName(plan, lang) {
  if (!plan) return '';
  const en = String(plan.name_en || '').trim();
  const fa = String(plan.name || '').trim();
  if (lang === 'en' && en) return en;
  return fa;
}

export function PaymentSection({
  t, fmt, fmtPrice, lang, userInfo,
  useCredit, onUseCreditChange,
  autoRenewal, onAutoRenewalChange,
  plans, selectedRenewalPlan, onSelectRenewalPlan,
  selectedSubscription, selectedPackage, pricing,
  onBack, onConfirm,
}) {
  const subLabel = selectedSubscription
    ? (selectedSubscription.name || selectedSubscription.marzban_username || `#${selectedSubscription.id}`)
    : '-';
  const pkgLabel = selectedPackage ? `${selectedPackage.name} (${fmt(selectedPackage.gb)} ${t('GB')})` : '-';

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

        <div className="toggle-row" style={{ marginBottom: 16 }}>
          <span className="toggle-label">{t('autoRenewal')}</span>
          <label className="toggle-switch">
            <input
              type="checkbox"
              id="autoRenewal"
              aria-label={t('autoRenewal')}
              checked={autoRenewal}
              onChange={(e) => onAutoRenewalChange(e.target.checked)}
            />
            <span className="toggle-slider" />
          </label>
        </div>

        {autoRenewal && (
          <div id="renewalPlanGroup" style={{ marginBottom: 16 }}>
            <label className="form-label">{t('renewalPlan')}</label>
            <div id="renewalPlansGrid" className="plans-grid" style={{ marginTop: 12 }}>
              {plans.map((plan) => (
                <div
                  key={plan.name}
                  className={`plan-card${selectedRenewalPlan === plan.name ? ' selected' : ''}`}
                  data-plan={plan.name}
                  role="button"
                  tabIndex={0}
                  onClick={() => onSelectRenewalPlan(plan.name)}
                  onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onSelectRenewalPlan(plan.name); } }}
                >
                  <div className="plan-name">{getPlanDisplayName(plan, lang) || plan.name}</div>
                  <div className="plan-details">
                    <span>{fmt(plan.gb)} {t('GB')}</span>
                  </div>
                  <div className="plan-price">{fmtPrice(plan.price)}</div>
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="summary" id="orderSummary">
          <div className="summary-row">
            <span className="label">{t('subscription')}</span>
            <span className="value" id="summarySubscription">{subLabel}</span>
          </div>
          <div className="summary-row">
            <span className="label">{t('selectedPackage')}</span>
            <span className="value" id="summaryPackage">{pkgLabel}</span>
          </div>
          <div className="summary-row">
            <span className="label">{t('totalPrice')}</span>
            <span className="value" id="summaryTotalPrice">{fmtPrice(pricing.totalPrice)}</span>
          </div>
          {pricing.discountAmount > 0 && (
            <div className="summary-row discount" id="summaryDiscountRow">
              <span className="label">{t('discount')}</span>
              <span className="value" id="summaryDiscount">-{fmtPrice(pricing.discountAmount)}</span>
            </div>
          )}
          {pricing.creditUsed > 0 && (
            <div className="summary-row discount" id="summaryCreditRow">
              <span className="label">{t('credit')}</span>
              <span className="value" id="summaryCredit">-{fmtPrice(pricing.creditUsed)}</span>
            </div>
          )}
          <div className="summary-row total">
            <span className="label">{t('amountDue')}</span>
            <span className="value" id="summaryFinal">{fmtPrice(pricing.finalPrice)}</span>
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

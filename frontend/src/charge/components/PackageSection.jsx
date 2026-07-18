import React from 'react';

import { PlanRows } from './PlanRows.jsx';

// Top-up package step. Since plan parity (2026-07-18, Pasha: "same exact
// plans for charge that we have for purchase") the packages API serves the
// purchase PLANS — this step renders them with the shop-row picker instead
// of the old number-block grid ("the ui is kinda horrible").
export function PackageSection({
  t, fmt, lang, packages, packagesStatus, autoDiscounts,
  selected, isVip, months = 1, onMonthsChange, onSelect, autoOpenCustom = false, onBack, onContinue,
}) {
  return (
    <div className="section active" id="section-package">
      <div className="card">
        <div className="card-title">
          <div className="icon">
            <svg viewBox="0 0 24 24"><path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z" /></svg>
          </div>
          <span>{t('selectPackage')}</span>
        </div>

        {/* Months selector: VIP-only perk (2026-07-14) — non-VIP charges
            1 month, no tabs; flows/charge.py rejects @Nm server-side too. */}
        {isVip && (
          <div className="months-tabs" role="tablist" aria-label={t('durationLabel')}>
            {[1, 2, 3].map((n) => (
              <button
                key={n}
                type="button"
                role="tab"
                aria-selected={months === n}
                className={`months-tab${months === n ? ' active' : ''}`}
                onClick={() => { if (months !== n && onMonthsChange) onMonthsChange(n); }}
              >
                {t(`months${n}`)}
              </button>
            ))}
          </div>
        )}

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
        {packagesStatus === 'ready' && (
          <PlanRows
            t={t}
            fmt={fmt}
            lang={lang}
            plans={packages}
            autoDiscounts={autoDiscounts}
            months={months}
            selected={selected}
            onSelect={onSelect}
            autoOpenCustom={autoOpenCustom}
            idPrefix="chargepkg"
          />
        )}
      </div>

      <div className="btn-container">
        <button className="btn btn-secondary" onClick={onBack}>
          <span>{t('back')}</span>
        </button>
        <button className="btn btn-primary" id="btnSelectPackage" disabled={!selected} onClick={onContinue}>
          <span>{t('continue')}</span>
        </button>
      </div>
    </div>
  );
}

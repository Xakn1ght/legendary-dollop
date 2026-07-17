import React from 'react';

// Book-next-plan step (2026-07-12, image-6 "add the book button"). Same
// shop-row picker as the top-up step since the charge UI rework (2026-07-18);
// selection carries the final template name ("plan", "plan@2m", "custom:52")
// that /charge/book posts verbatim.
import { PlanRows } from './PlanRows.jsx';

export function BookingPlanSection({
  t, fmt, lang, plans, autoDiscounts, isVip = false,
  selectedPlan, onSelect, months, onMonthsChange,
  onBack, onContinue,
}) {
  return (
    <div className="section active" id="section-book-plan">
      <div className="card">
        <div className="card-title">
          <div className="icon">
            <svg viewBox="0 0 24 24"><path d="M19 3h-1V1h-2v2H8V1H6v2H5c-1.11 0-1.99.9-1.99 2L3 19c0 1.1.89 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm0 16H5V8h14v11zM7 10h5v5H7z" /></svg>
          </div>
          <span>{t('bookPlanTitle')}</span>
        </div>
        <p className="book-plan-hint">{t('bookPlanHint')}</p>
        {/* Multi-month booking is a VIP perk (2026-07-14) — non-VIP books 1 month. */}
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
        <PlanRows
          t={t}
          fmt={fmt}
          lang={lang}
          plans={plans}
          autoDiscounts={autoDiscounts}
          months={months}
          selected={selectedPlan}
          onSelect={onSelect}
          idPrefix="bookplan"
        />
      </div>

      <div className="btn-container">
        <button className="btn btn-secondary" onClick={onBack}>
          <span>{t('back')}</span>
        </button>
        <button className="btn btn-primary" onClick={onContinue}>
          <span>{t('continue')}</span>
        </button>
      </div>
    </div>
  );
}

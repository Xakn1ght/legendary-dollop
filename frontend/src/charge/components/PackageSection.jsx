import React from 'react';

export function PackageSection({ t, fmt, packages, packagesStatus, selectedPackageName, isVip, vipDiscountPercent, onSelect, onBack, onContinue }) {
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

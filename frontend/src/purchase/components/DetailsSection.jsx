import React, { useEffect, useRef, useState } from 'react';

import { api } from '../../shared/auth.js';

import { PlanGrid } from './PlanGrid.jsx';

// Debounced availability check for the optional service name.
// Validity gates the Continue button (parity with legacy checkServiceName).
function useServiceNameCheck(t, lang, onValidity) {
  const [name, setName] = useState('');
  const [hint, setHint] = useState({ cls: 'form-hint', key: 'serviceNameHint', text: null });
  const timerRef = useRef(null);

  const onInput = (raw) => {
    const value = raw.replace(/\s+/g, '');
    setName(value);
    const trimmed = value.trim();
    clearTimeout(timerRef.current);

    if (!trimmed) {
      setHint({ cls: 'form-hint', key: 'serviceNameHint', text: null });
      onValidity(true);
      return;
    }
    if (!/^[A-Za-z0-9]+$/.test(trimmed)) {
      setHint({
        cls: 'form-error', key: null,
        text: lang === 'fa'
          ? 'نام نامعتبر! فقط حروف انگلیسی (A-Z, a-z) و اعداد (0-9) مجاز است'
          : 'Invalid name! Only English letters (A-Z, a-z) and numbers (0-9) allowed',
      });
      onValidity(false);
      return;
    }
    if (trimmed.length < 3) {
      setHint({
        cls: 'form-error', key: null,
        text: lang === 'fa' ? 'نام باید حداقل ۳ کاراکتر باشد' : 'Name must be at least 3 characters',
      });
      onValidity(false);
      return;
    }
    setHint({ cls: 'form-hint', key: 'checking', text: null });
    onValidity(false);
    timerRef.current = setTimeout(async () => {
      try {
        const data = await api(`/api/dashboard/purchase/check-name?name=${encodeURIComponent(trimmed)}`);
        if (data.ok) {
          if (data.available) {
            setHint({ cls: 'form-success', key: 'available', text: null });
            onValidity(true);
          } else {
            setHint({ cls: 'form-error', key: 'taken', text: null });
            onValidity(false);
          }
        }
      } catch (_e) {
        setHint({ cls: 'form-hint', key: 'serviceNameHint', text: null });
        onValidity(true); // on error, allow continue (server re-validates)
      }
    }, 500);
  };

  useEffect(() => () => clearTimeout(timerRef.current), []);
  return { name, onInput, hint };
}

function useReferralCheck(t) {
  const [code, setCode] = useState('');
  const [hint, setHint] = useState({ cls: 'form-hint', key: 'referralHint', text: null });
  const timerRef = useRef(null);

  const onInput = (raw) => {
    const value = raw.toUpperCase();
    setCode(value);
    const trimmed = value.trim();
    clearTimeout(timerRef.current);

    if (!trimmed) {
      setHint({ cls: 'form-hint', key: 'referralHint', text: null });
      return;
    }
    if (!/^[A-Z0-9]{6}$/.test(trimmed)) {
      setHint({ cls: 'form-error', key: 'invalidFormat', text: null });
      return;
    }
    setHint({ cls: 'form-hint', key: 'checking', text: null });
    timerRef.current = setTimeout(async () => {
      try {
        const data = await api(`/api/dashboard/purchase/validate-referral?code=${encodeURIComponent(trimmed)}`);
        if (data.ok) {
          if (data.valid) setHint({ cls: 'form-success', key: null, text: `${t('validCode')} - ${data.referrer_name}` });
          else setHint({ cls: 'form-error', key: data.reason === 'own_code' ? 'ownCode' : 'invalidCode', text: null });
        }
      } catch (_e) {
        setHint({ cls: 'form-hint', key: 'referralHint', text: null });
      }
    }, 500);
  };

  useEffect(() => () => clearTimeout(timerRef.current), []);
  return { code, onInput, hint };
}

export function DetailsSection({
  t, fmt, lang, plans, autoDiscounts, showReferral,
  autoRenewal, onAutoRenewalChange,
  selectedRenewalPlan, onSelectRenewalPlan,
  serviceNameState, referralState, nameValid,
  onBack, onContinue,
}) {
  const hintText = (h) => h.text ?? (h.key ? t(h.key) : '');

  return (
    <div className="section active" id="section-details">
      <div className="card">
        <div className="card-title">
          <div className="icon">
            <svg viewBox="0 0 24 24"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z" /></svg>
          </div>
          <span>{t('serviceSettings')}</span>
        </div>

        <div className="form-group">
          <label className="form-label" htmlFor="serviceName">{t('serviceName')}</label>
          <input
            type="text"
            className="form-input"
            id="serviceName"
            placeholder="e.g. myservice123"
            maxLength={20}
            value={serviceNameState.name}
            onChange={(e) => serviceNameState.onInput(e.target.value)}
          />
          <div className={serviceNameState.hint.cls} id="serviceNameHint">{hintText(serviceNameState.hint)}</div>
        </div>

        {showReferral && (
          <div className="form-group" id="referralGroup">
            <label className="form-label" htmlFor="referralCode">{t('referralCode')}</label>
            <input
              type="text"
              className="form-input"
              id="referralCode"
              placeholder="e.g. ABC123"
              maxLength={6}
              style={{ textTransform: 'uppercase' }}
              value={referralState.code}
              onChange={(e) => referralState.onInput(e.target.value)}
            />
            <div className={referralState.hint.cls} id="referralHint">{hintText(referralState.hint)}</div>
          </div>
        )}

        <div className="toggle-row">
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
          <div id="renewalPlanGroup" style={{ marginTop: 16 }}>
            <label className="form-label">{t('renewalPlan')}</label>
            <PlanGrid
              id="renewalPlansGrid"
              t={t} fmt={fmt} lang={lang}
              plans={plans}
              autoDiscounts={autoDiscounts}
              selectedPlan={selectedRenewalPlan}
              onSelect={onSelectRenewalPlan}
            />
          </div>
        )}
      </div>

      <div className="btn-container">
        <button className="btn btn-secondary" onClick={onBack}>
          <span>{t('back')}</span>
        </button>
        <button className="btn btn-primary" disabled={!nameValid} onClick={onContinue}>
          <span>{t('continue')}</span>
        </button>
      </div>
    </div>
  );
}

export { useReferralCheck, useServiceNameCheck };

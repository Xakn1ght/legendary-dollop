import React, { useState } from 'react';

import { hapticNotify } from '../../shared/telegram.js';
import { api } from '../api.js';

// First-time welcome overlay: shows own referral code + optional friend-code entry.
export function WelcomeScreen({ t, ownCode, hasUsedRef, onDismiss }) {
  const [refCode, setRefCode] = useState('');
  const [refMsg, setRefMsg] = useState(null); // { type, msg }
  const [refApplied, setRefApplied] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [copied, setCopied] = useState(false);
  const [leaving, setLeaving] = useState(false);

  const copyCode = async () => {
    try {
      await navigator.clipboard.writeText(ownCode);
    } catch (_) {
      try {
        const ta = document.createElement('textarea');
        ta.value = ownCode;
        document.body.appendChild(ta);
        ta.select();
        document.execCommand('copy');
        document.body.removeChild(ta);
      } catch (_2) { /* ignore */ }
    }
    setCopied(true);
    setTimeout(() => setCopied(false), 1800);
    hapticNotify('success');
  };

  const submitRef = async () => {
    const code = refCode.trim().toUpperCase();
    if (!code || code.length !== 6) {
      setRefMsg({ type: 'error', msg: t('welcomeErrInvalidFormat') });
      return;
    }
    setSubmitting(true);
    try {
      const res = await api('/api/dashboard/referrals/enter', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ referral_code: code }),
      });
      if (res && res.ok) {
        setRefApplied(true);
        hapticNotify('success');
      } else {
        const errMap = { invalid_format: 'welcomeErrInvalidFormat', invalid_code: 'welcomeErrInvalidCode', own_code: 'welcomeErrOwnCode', already_used: 'welcomeErrAlreadyUsed', server_error: 'welcomeErrServer' };
        setRefMsg({ type: 'error', msg: t(errMap[res && res.error] || 'welcomeErrServer') });
      }
    } catch (_) {
      setRefMsg({ type: 'error', msg: t('welcomeErrServer') });
    }
    setSubmitting(false);
  };

  const dismiss = async () => {
    setLeaving(true);
    try { localStorage.setItem('astro_welcome_shown', '1'); } catch (_) { /* ignore */ }
    setTimeout(onDismiss, 280);
    try {
      await api('/api/dashboard/preferences', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ welcome_shown: true }),
      });
    } catch (_) { /* ignore */ }
  };

  return (
    <div
      id="welcomeScreen"
      className="welcome-screen"
      aria-modal="true"
      role="dialog"
      style={{
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        ...(leaving ? { transition: 'opacity 260ms ease, transform 260ms ease', opacity: 0, transform: 'scale(0.97)' } : {}),
      }}
    >
      <div className="welcome-body">
        <div className="welcome-orb" aria-hidden="true">
          <div className="welcome-orb-ring r1" />
          <div className="welcome-orb-ring r2" />
          <div className="welcome-orb-ring r3" />
          <div className="welcome-orb-core">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="10" r="6" />
              <rect x="7" y="15" width="10" height="4" rx="2" fill="currentColor" stroke="none" />
              <circle cx="12" cy="10" r="3" fill="currentColor" stroke="none" />
            </svg>
          </div>
        </div>

        <h1 className="welcome-title">{t('welcomeTitle')}</h1>
        <p className="welcome-subtitle">{t('welcomeSubtitle')}</p>

        <div className="welcome-code-box">
          <span className="welcome-code-text">{ownCode}</span>
          <button className="welcome-copy-btn" type="button" aria-label="Copy code" onClick={copyCode}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" width="16" height="16"><rect x="9" y="9" width="13" height="13" rx="2" /><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" /></svg>
            <span>{copied ? t('welcomeCopied') : t('welcomeCopy')}</span>
          </button>
        </div>

        {!hasUsedRef && !refApplied && (
          <div className="welcome-enter-section" style={{ display: 'block' }}>
            <div className="welcome-divider"><span>{t('welcomeHaveFriendCode')}</span></div>
            <div className="welcome-input-row">
              <input
                className={`welcome-ref-input${refMsg?.type === 'error' ? ' is-error' : ''}`}
                type="text"
                maxLength={6}
                autoComplete="off"
                autoCorrect="off"
                spellCheck={false}
                placeholder={t('welcomeRefPlaceholder')}
                value={refCode}
                onChange={(e) => {
                  setRefCode(e.target.value.toUpperCase().replace(/[^A-Z0-9]/g, ''));
                  setRefMsg(null);
                }}
                onKeyDown={(e) => { if (e.key === 'Enter') submitRef(); }}
              />
              <button className="welcome-ref-submit" type="button" disabled={submitting} onClick={submitRef}>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" width="18" height="18"><path d="M5 12h14M12 5l7 7-7 7" /></svg>
              </button>
            </div>
            {refMsg && <p className={`welcome-ref-msg is-${refMsg.type}`} style={{ display: 'block' }}>{refMsg.msg}</p>}
          </div>
        )}

        {refApplied && (
          <div className="welcome-success-section" style={{ display: 'flex' }}>
            <div className="welcome-success-icon" aria-hidden="true">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M20 6L9 17l-5-5" /></svg>
            </div>
            <p className="welcome-success-msg">{t('welcomeSuccessMsg')}</p>
          </div>
        )}

        <button className="welcome-start-btn" type="button" onClick={dismiss}>
          <span>{t('welcomeStartLabel')}</span>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" width="18" height="18"><path d="M5 12h14M12 5l7 7-7 7" /></svg>
        </button>
      </div>
    </div>
  );
}

import React from 'react';

import { BulbIcon, LockIcon } from '../../shared/icons.jsx';

// Shown when /api/dashboard/login answers not_registered (bot requires a referral code).
export function NotRegisteredOverlay({ lang, onClose }) {
  const fa = lang === 'fa';
  const close = () => {
    try { window.Telegram?.WebApp?.close(); } catch (_) { /* ignore */ }
    onClose();
  };
  return (
    <div style={{ position: 'fixed', inset: 0, zIndex: 9999, background: 'rgba(0,0,0,.85)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16 }}>
      <div style={{ width: '100%', maxWidth: 420, background: 'var(--panel)', border: '1px solid var(--line)', borderRadius: 20, padding: 24, color: 'var(--lightText)', textAlign: 'center' }}>
        <div style={{ width: 64, height: 64, margin: '0 auto 16px', borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'rgba(var(--brandRgb),0.16)', color: 'var(--brand)' }}>
          <LockIcon size={30} />
        </div>
        <div style={{ fontWeight: 800, fontSize: 18, marginBottom: 12 }}>
          {fa ? 'کد دعوت نیاز است' : 'Referral Code Required'}
        </div>
        <div style={{ opacity: 0.85, fontSize: 14, lineHeight: 1.6, marginBottom: 20, whiteSpace: 'pre-line' }}>
          {fa
            ? 'شما هنوز ثبت‌نام نکرده‌اید.\n\nبرای استفاده از این ربات، نیاز به کد دعوت دارید.'
            : 'You are not registered yet.\n\nThis bot requires a referral code.'}
        </div>
        <div style={{ background: 'rgba(var(--brandRgb),0.15)', border: '1px solid rgba(var(--brandRgb),0.3)', padding: '14px 16px', borderRadius: 12, marginBottom: 20 }}>
          <div style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 6 }}>
            {fa ? 'در چت ربات ارسال کنید:' : 'Send in bot chat:'}
          </div>
          <div style={{ fontFamily: 'monospace', fontSize: 18, fontWeight: 700, color: 'var(--brand)' }}>/start</div>
        </div>
        <div style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 16, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6 }}>
          <BulbIcon size={14} />
          {fa ? 'کد دعوت را از دوستان خود بگیرید.' : 'Get a referral code from your friends.'}
        </div>
        <button onClick={close} className="btn btn-primary" style={{ minWidth: 140, background: 'var(--brand)', borderColor: 'var(--brand)', color: '#fff' }}>
          {fa ? 'بستن' : 'Close'}
        </button>
      </div>
    </div>
  );
}

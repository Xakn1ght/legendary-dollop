import React, { useState } from 'react';

import { getWebApp, openBotChatWithStart } from '../../shared/telegram.js';
import { showToast } from '../toast.js';

// "Login problem" overlay (repeated 401/403 with initData present).
export function AuthHelpOverlay({ lang }) {
  const fa = lang === 'fa';
  const msg = fa
    ? 'مشکل ورود. لطفاً از این صفحه خارج شوید و در چت ربات دستور /start را ارسال کنید، سپس دوباره داشبورد را باز کنید.'
    : 'Login problem. Please close this page, send /start to the bot, then open the dashboard again.';
  return (
    <div style={{ position: 'fixed', inset: 0, zIndex: 9999, background: 'rgba(12,9,26,.9)', backdropFilter: 'blur(16px) saturate(150%)', WebkitBackdropFilter: 'blur(16px) saturate(150%)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16 }}>
      <div style={{ width: '100%', maxWidth: 420, background: 'var(--panel)', border: '1px solid var(--line)', borderRadius: 16, padding: 14, color: 'var(--lightText)' }}>
        <div style={{ fontWeight: 800, marginBottom: 6 }}>{fa ? 'مشکل در ورود' : 'Login problem'}</div>
        <div style={{ opacity: 0.9, fontSize: 13, lineHeight: 1.5, marginBottom: 10 }}>{msg}</div>
        <div style={{ fontFamily: "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace", background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.08)', padding: '10px 12px', borderRadius: 12, marginBottom: 12 }}>/start</div>
        <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end', flexWrap: 'wrap' }}>
          <button
            className="btn"
            style={{ minWidth: 120 }}
            onClick={async () => {
              try {
                await navigator.clipboard.writeText('/start');
                showToast(fa ? 'کپی شد' : 'Copied', 'success', 1500);
              } catch (_e) {
                try { prompt('Copy this command:', '/start'); } catch (_2) { /* ignore */ }
              }
            }}
          >
            {fa ? 'کپی /start' : 'Copy /start'}
          </button>
          <button
            className="btn primary"
            style={{ minWidth: 140 }}
            onClick={() => { try { getWebApp()?.close(); } catch (_) { /* ignore */ } }}
          >
            {fa ? 'بستن' : 'Close'}
          </button>
        </div>
      </div>
    </div>
  );
}

const NR_STRINGS = {
  fa: {
    title: 'ثبت‌نام لازم است',
    subtitle: 'برای ورود به داشبورد، در چت ربات ثبت‌نام کنید',
    step1Title: 'روی «ارسال /start» بزنید',
    step1Desc: 'چت ربات باز می‌شود و دکمه شروع آماده است',
    step2Title: 'دستور را ارسال کنید',
    step2Desc: 'در چت ربات دکمه شروع را بزنید (یا این دستور را بفرستید)',
    step3Title: 'کد دعوت را وارد کنید',
    step3Desc: 'کد ۶ رقمی دوست خود را ارسال کنید',
    hint: 'کد دعوت از دوستی که قبلاً عضو است بگیرید',
    copy: 'کپی دستور',
    copied: '✓ کپی شد',
    goStart: 'ارسال /start',
    langToggle: 'EN',
  },
  en: {
    title: 'Registration Required',
    subtitle: 'Sign up via the bot chat to access your dashboard',
    step1Title: 'Tap "Send /start" below',
    step1Desc: 'The bot chat opens with the Start button ready',
    step2Title: 'Send the command',
    step2Desc: 'Hit Start in the bot chat (or type this command)',
    step3Title: 'Enter your referral code',
    step3Desc: 'Send the 6-character code from a friend',
    hint: 'Get a referral code from a friend who is already a member',
    copy: 'Copy command',
    copied: '✓ Copied',
    goStart: 'Send /start',
    langToggle: 'FA',
  },
};

// Referral-registration walkthrough (login answered not_registered).
// Styling reuses the legacy nr-* CSS (injected below once).
const NR_CSS = `
@keyframes nrFadeIn { from { opacity:0; } to { opacity:1; } }
@keyframes nrPopIn { 0% { opacity:0; transform:translateY(16px) scale(.96); } 100% { opacity:1; transform:none; } }
@keyframes nrLockPulse {
  0%,100% { box-shadow:0 0 0 0 rgba(139,92,246,.5), 0 10px 30px -8px rgba(139,92,246,.5); }
  50%     { box-shadow:0 0 0 14px rgba(139,92,246,0), 0 14px 40px -10px rgba(139,92,246,.7); }
}
@keyframes nrShimmer { 0% { transform:translateX(-100%); } 100% { transform:translateX(250%); } }
.nr-overlay { position:fixed; inset:0; z-index:9999; background:rgba(12,9,26,.82); backdrop-filter:blur(16px) saturate(150%); -webkit-backdrop-filter:blur(16px) saturate(150%); display:flex; align-items:center; justify-content:center; padding:16px; animation:nrFadeIn 200ms ease both; }
.nr-card { width:100%; max-width:400px; max-height:calc(100vh - 32px); overflow-y:auto; background:linear-gradient(175deg, rgba(255,255,255,.07) 0%, rgba(255,255,255,0) 55%), var(--panel, #1b1530); border:1px solid rgba(255,255,255,.08); border-radius:22px; padding:20px 18px 18px; color:var(--lightText,#fff); box-shadow:0 24px 50px -16px rgba(0,0,0,.65), 0 0 0 1px rgba(139,92,246,.1) inset; animation:nrPopIn 320ms cubic-bezier(.2,.9,.25,1.15) both; position:relative; scrollbar-width:none; }
.nr-card::-webkit-scrollbar { display:none; }
.nr-lang-btn { position:absolute; top:14px; width:36px; height:22px; border-radius:20px; border:1px solid rgba(167,139,250,.45); background:rgba(139,92,246,.15); color:#c4b5fd; font-size:10px; font-weight:800; letter-spacing:.5px; cursor:pointer; display:flex; align-items:center; justify-content:center; transition:background .15s; z-index:1; }
[dir="ltr"] .nr-lang-btn { right:14px; }
[dir="rtl"] .nr-lang-btn { left:14px; }
.nr-icon-wrap { width:60px; height:60px; margin:0 auto 12px; border-radius:50%; display:flex; align-items:center; justify-content:center; background:linear-gradient(135deg, #8b5cf6, #6d28d9); animation:nrLockPulse 2.4s ease-in-out infinite; }
.nr-icon-wrap svg { width:28px; height:28px; color:#fff; }
.nr-title { font-size:17px; font-weight:800; text-align:center; margin:0 0 4px; letter-spacing:-.01em; }
.nr-subtitle { font-size:12.5px; text-align:center; opacity:.65; margin:0 0 16px; line-height:1.5; padding:0 8px; }
.nr-steps { display:flex; flex-direction:column; gap:8px; margin-bottom:12px; }
.nr-step { display:flex; gap:10px; align-items:flex-start; padding:10px 12px; border-radius:12px; background:rgba(255,255,255,.03); border:1px solid rgba(255,255,255,.055); }
.nr-step-num { flex:0 0 24px; width:24px; height:24px; border-radius:50%; background:linear-gradient(135deg, #8b5cf6, #7c3aed); color:#fff; font-weight:800; font-size:12px; display:flex; align-items:center; justify-content:center; box-shadow:0 3px 10px -3px rgba(139,92,246,.6); }
.nr-step-body { flex:1; min-width:0; }
.nr-step-title { font-size:13px; font-weight:700; margin:0 0 2px; }
.nr-step-desc { font-size:11.5px; opacity:.65; margin:0; line-height:1.45; }
.nr-cmd-box { margin-top:8px; padding:8px 10px; border-radius:9px; background:rgba(139,92,246,.1); border:1px dashed rgba(139,92,246,.45); display:flex; align-items:center; justify-content:space-between; gap:8px; position:relative; overflow:hidden; }
.nr-cmd { font-family:ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,monospace; font-size:14px; font-weight:700; color:#c4b5fd; letter-spacing:.5px; direction:ltr; }
.nr-cmd-copy { background:transparent; border:0; cursor:pointer; color:#c4b5fd; display:flex; align-items:center; gap:5px; font-size:11px; font-weight:600; padding:3px 7px; border-radius:7px; transition:background .15s; white-space:nowrap; }
.nr-cmd-copy svg { width:12px; height:12px; flex-shrink:0; }
.nr-hint { display:flex; gap:7px; align-items:flex-start; padding:9px 11px; border-radius:10px; background:rgba(250,204,21,.06); border:1px solid rgba(250,204,21,.16); font-size:11.5px; line-height:1.45; opacity:.9; margin-bottom:14px; }
.nr-actions { display:flex; gap:8px; }
.nr-btn { flex:1; padding:11px 12px; border-radius:11px; font-weight:700; font-size:13px; cursor:pointer; border:1px solid transparent; display:flex; align-items:center; justify-content:center; gap:6px; min-width:0; }
.nr-btn-ghost { background:rgba(255,255,255,.05); border-color:rgba(255,255,255,.1); color:var(--lightText,#fff); }
.nr-btn-primary { background:linear-gradient(135deg,#8b5cf6,#7c3aed); color:#fff; box-shadow:0 8px 20px -7px rgba(139,92,246,.7); }
.nr-btn svg { width:14px; height:14px; flex-shrink:0; }
`;

export function NotRegisteredOverlay({ initialLang }) {
  const [nrLang, setNrLang] = useState(initialLang === 'fa' ? 'fa' : 'en');
  const [copied, setCopied] = useState(false);
  const T = NR_STRINGS[nrLang];

  const doCopy = async () => {
    try {
      await navigator.clipboard.writeText('/start');
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch (_) {
      try { prompt(T.copy + ':', '/start'); } catch (_2) { /* ignore */ }
    }
  };

  return (
    <>
      <style>{NR_CSS}</style>
      <div className="nr-overlay" role="dialog" aria-modal="true">
        <div className="nr-card" dir={nrLang === 'fa' ? 'rtl' : 'ltr'}>
          <button type="button" className="nr-lang-btn" aria-label="Switch language" onClick={() => setNrLang(nrLang === 'fa' ? 'en' : 'fa')}>
            {T.langToggle}
          </button>
          <div className="nr-icon-wrap" aria-hidden="true">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
              <rect x="4" y="10" width="16" height="11" rx="2.5" />
              <path d="M8 10V7a4 4 0 0 1 8 0v3" />
              <circle cx="12" cy="15.5" r="1.4" fill="currentColor" stroke="none" />
            </svg>
          </div>
          <h2 className="nr-title">{T.title}</h2>
          <p className="nr-subtitle">{T.subtitle}</p>
          <div className="nr-steps">
            {[
              { num: 1, title: T.step1Title, desc: T.step1Desc },
              { num: 2, title: T.step2Title, desc: T.step2Desc, cmd: true },
              { num: 3, title: T.step3Title, desc: T.step3Desc },
            ].map((s) => (
              <div className="nr-step" key={s.num}>
                <div className="nr-step-num">{s.num}</div>
                <div className="nr-step-body">
                  <p className="nr-step-title">{s.title}</p>
                  <p className="nr-step-desc">{s.desc}</p>
                  {s.cmd && (
                    <div className="nr-cmd-box">
                      <span className="nr-cmd">/start</span>
                      <button type="button" className="nr-cmd-copy" aria-label={T.copy} onClick={doCopy}>
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" /><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" /></svg>
                        <span>{copied ? T.copied : T.copy}</span>
                      </button>
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
          <div className="nr-hint">
            <span aria-hidden="true" style={{ display: 'inline-flex' }}>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" width="14" height="14"><path d="M9 18h6" /><path d="M10 22h4" /><path d="M12 2a7 7 0 0 0-4 12.7c.6.5 1 1.4 1 2.3h6c0-.9.4-1.8 1-2.3A7 7 0 0 0 12 2z" /></svg>
            </span>
            <span>{T.hint}</span>
          </div>
          <div className="nr-actions">
            <button type="button" className="nr-btn nr-btn-ghost" onClick={doCopy}>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" /><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" /></svg>
              <span>{copied ? T.copied : T.copy}</span>
            </button>
            <button type="button" className="nr-btn nr-btn-primary" onClick={() => openBotChatWithStart('register')}>
              <span>{T.goStart}</span>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round"><path d="M22 2 11 13M22 2l-7 20-4-9-9-4 20-7z" /></svg>
            </button>
          </div>
        </div>
      </div>
    </>
  );
}

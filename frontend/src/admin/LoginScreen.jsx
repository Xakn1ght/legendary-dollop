import React, { useEffect, useRef, useState } from 'react';

import { login, setBearer, setCsrf, verify2fa } from './api.js';
import { Icons } from './icons.jsx';

// Login + 2FA + lockout, ported from index-main.js. On success we hand the
// user object up to AdminApp (cookie already set server-side).
export function LoginScreen({ onAuthed }) {
  const [stage, setStage] = useState('login'); // login | twofa | lockout
  const [chatId, setChatId] = useState('');
  const [password, setPassword] = useState('');
  const [trusted, setTrusted] = useState(false);
  const [code, setCode] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [lockout, setLockout] = useState(0);
  const pendingChatId = useRef('');
  const lockoutTimer = useRef(null);

  // Attempt browser credential autofill (like the legacy panel).
  useEffect(() => {
    (async () => {
      if (window.PasswordCredential && navigator.credentials) {
        try {
          const cred = await navigator.credentials.get({ password: true, mediation: 'optional' });
          if (cred && cred.type === 'password') {
            setChatId(cred.id || '');
            setPassword(cred.password || '');
          }
        } catch (_) { /* ignore */ }
      }
    })();
    return () => { if (lockoutTimer.current) clearInterval(lockoutTimer.current); };
  }, []);

  function beginLockout(seconds) {
    setStage('lockout');
    setLockout(seconds);
    lockoutTimer.current = setInterval(() => {
      setLockout((s) => {
        if (s <= 1) { clearInterval(lockoutTimer.current); setStage('login'); return 0; }
        return s - 1;
      });
    }, 1000);
  }

  async function saveCredential(user) {
    if (trusted && window.PasswordCredential && navigator.credentials?.store && chatId && password) {
      try {
        await navigator.credentials.store(new PasswordCredential({
          id: chatId, password, name: (user && user.name) || 'Admin',
        }));
      } catch (_) { /* ignore */ }
    }
  }

  async function submitLogin(e) {
    e.preventDefault();
    if (!chatId || !password) { setError('Fill all fields'); return; }
    setError('');
    setBusy(true);
    try {
      const { data } = await login(chatId, password);
      if (data.ok && data.requires_2fa) {
        pendingChatId.current = chatId;
        setStage('twofa');
      } else if (data.ok) {
        if (data.token) setBearer(data.token);
        if (data.csrf_token) setCsrf(data.csrf_token);
        await saveCredential(data.user);
        onAuthed(data.user || { name: 'Admin' });
      } else if (data.lockout_seconds) {
        beginLockout(data.lockout_seconds);
      } else {
        setError(data.message || 'Login failed');
      }
    } catch (_) {
      setError('Connection error');
    } finally {
      setBusy(false);
    }
  }

  async function submit2fa(e) {
    e.preventDefault();
    setBusy(true);
    setError('');
    try {
      const { data } = await verify2fa(pendingChatId.current, code.trim());
      if (data.ok) {
        if (data.token) setBearer(data.token);
        if (data.csrf_token) setCsrf(data.csrf_token);
        await saveCredential(data.user);
        onAuthed(data.user || { name: 'Admin' });
      } else {
        setError(data.message || 'Invalid code');
      }
    } catch (_) {
      setError('Error');
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="login-wrapper" id="loginScreen">
      <div className="login-card fx-tilt">
        <div className="fx-rocket" style={{ width: 60, height: 60, background: 'linear-gradient(135deg, var(--brand), var(--brandDark))', borderRadius: 16, margin: '0 auto 24px', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#fff', boxShadow: '0 0 30px var(--primary-glow)' }}><Icons.rocket width={30} height={30} /></div>
        <h1 style={{ margin: '0 0 8px 0', fontSize: 24 }}>AstroByte Admin</h1>
        <p style={{ color: 'var(--text-muted)', margin: '0 0 32px 0' }}>Authentication Required</p>

        {error && (
          <div style={{ background: 'rgba(248,113,113,0.12)', color: 'var(--danger)', padding: 12, borderRadius: 8, marginBottom: 20, fontSize: 13 }}>{error}</div>
        )}

        {stage === 'login' && (
          <form onSubmit={submitLogin} autoComplete="on">
            <div style={{ marginBottom: 16, textAlign: 'left' }}>
              <label htmlFor="chatId" style={{ display: 'block', fontSize: 12, color: 'var(--text-muted)', marginBottom: 6, textTransform: 'uppercase', fontWeight: 600 }}>Chat ID</label>
              <input type="text" id="chatId" name="username" className="input-field" placeholder="Enter ID..." autoComplete="username" inputMode="text" value={chatId} onChange={(e) => setChatId(e.target.value)} />
            </div>
            <div style={{ marginBottom: 24, textAlign: 'left' }}>
              <label htmlFor="password" style={{ display: 'block', fontSize: 12, color: 'var(--text-muted)', marginBottom: 6, textTransform: 'uppercase', fontWeight: 600 }}>Password</label>
              <input type="password" id="password" name="password" className="input-field" placeholder="••••••••" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} />
            </div>
            <div style={{ marginBottom: 18, textAlign: 'left', display: 'flex', alignItems: 'center', gap: 10 }}>
              <input type="checkbox" id="trustedDevice" style={{ width: 16, height: 16 }} checked={trusted} onChange={(e) => setTrusted(e.target.checked)} />
              <label htmlFor="trustedDevice" style={{ fontSize: 13, color: 'var(--text-muted)', cursor: 'pointer' }}>Trusted device (save login on this browser)</label>
            </div>
            <button type="submit" className="btn btn-primary" style={{ width: '100%', padding: 14 }} disabled={busy}>{busy ? '...' : 'Initiate Sequence'}</button>
          </form>
        )}

        {stage === 'twofa' && (
          <form onSubmit={submit2fa} autoComplete="on">
            <p style={{ color: 'var(--text-muted)', marginBottom: 20 }}>Enter the 6-digit code sent to your device</p>
            <input type="text" id="twoFactorCode" name="otp" className="input-field" placeholder="000000" maxLength={6} autoComplete="one-time-code" inputMode="numeric" pattern="[0-9]*" style={{ textAlign: 'center', fontSize: 24, letterSpacing: 8, marginBottom: 24 }} value={code} onChange={(e) => setCode(e.target.value)} autoFocus />
            <button type="submit" className="btn btn-primary" style={{ width: '100%' }} disabled={busy}>Verify Access</button>
            <button type="button" onClick={() => { setStage('login'); setError(''); }} className="btn btn-secondary" style={{ width: '100%', marginTop: 12 }}>Cancel</button>
          </form>
        )}

        {stage === 'lockout' && (
          <div>
            <h3 style={{ color: 'var(--danger)' }}>Locked Out</h3>
            <p style={{ color: 'var(--text-muted)' }}>Try again in {lockout}s</p>
          </div>
        )}
      </div>
    </div>
  );
}

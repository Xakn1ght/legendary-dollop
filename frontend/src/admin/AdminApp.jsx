import React, { useEffect, useState } from 'react';

import { verifySession } from './api.js';
import { AdminShell } from './AdminShell.jsx';
import { ModalProvider } from './components/Modal.jsx';
import { ToastProvider } from './components/Toast.jsx';
import { LoginScreen } from './LoginScreen.jsx';

const SESSION_KEY = 'admin_session';

export function AdminApp() {
  const [phase, setPhase] = useState('checking'); // checking | login | ready
  const [user, setUser] = useState(null);

  useEffect(() => {
    (async () => {
      const valid = await verifySession();
      if (valid) {
        let u = { name: 'Admin' };
        try { u = JSON.parse(localStorage.getItem(SESSION_KEY) || '') || u; } catch (_) { /* ignore */ }
        setUser(u);
        setPhase('ready');
      } else {
        try { localStorage.removeItem(SESSION_KEY); } catch (_) { /* ignore */ }
        setPhase('login');
      }
    })();
  }, []);

  function handleAuthed(u) {
    const info = { ...(u || {}), loginTime: Date.now() };
    try { localStorage.setItem(SESSION_KEY, JSON.stringify(info)); } catch (_) { /* ignore */ }
    setUser(info);
    setPhase('ready');
  }

  return (
    <ToastProvider>
      <ModalProvider>
        {phase === 'checking' && (
          <div style={{ position: 'fixed', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-muted)', letterSpacing: 1 }}>
            LOADING MISSION CONTROL
          </div>
        )}
        {phase === 'login' && <LoginScreen onAuthed={handleAuthed} />}
        {phase === 'ready' && <AdminShell user={user} />}
      </ModalProvider>
    </ToastProvider>
  );
}

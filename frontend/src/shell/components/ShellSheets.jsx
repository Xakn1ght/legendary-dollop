import React, { useEffect, useRef, useState } from 'react';

import { getWebApp } from '../../shared/telegram.js';
import { api } from '../api.js';
import { showToast } from '../toast.js';

import { Sheet } from './Sheet.jsx';

// ---- one-tap app import -----------------------------------------------
// Launching a custom scheme via window.location navigates the Telegram
// webview to net::ERR_UNKNOWN_URL_SCHEME and KILLS the SPA (the mini app
// stays dead until Telegram is force-closed). A throwaway iframe fires the
// scheme without ever navigating the top frame: app installed → OS opens
// it; not installed → silent no-op and the dashboard stays alive.
function launchScheme(url) {
  try {
    const f = document.createElement('iframe');
    f.style.display = 'none';
    f.src = url;
    document.body.appendChild(f);
    setTimeout(() => { try { f.remove(); } catch (_) { /* ignore */ } }, 2500);
  } catch (_) { /* ignore */ }
}

const PLATFORM = /android/i.test(navigator.userAgent || '') ? 'android'
  : /iphone|ipad|ipod/i.test(navigator.userAgent || '') ? 'ios' : 'any';

// Per-client formats come from PasarGuard: {link}/{client_type}.
// Only apps that exist on the viewer's platform are shown (v2rayNG has no
// iOS build, Streisand/V2Box have no Android build).
const ALL_APPS = [
  { key: 'v2rayng', label: 'v2rayNG', os: ['android'], url: (l) => 'v2rayng://install-config?url=' + encodeURIComponent(l) },
  { key: 'karing', label: 'Karing', os: ['android', 'ios', 'any'], url: (l) => 'sing-box://import-remote-profile?url=' + encodeURIComponent(l + '/sing_box') + '#AstroByte' },
  { key: 'hiddify', label: 'Hiddify', os: ['android', 'ios', 'any'], url: (l) => 'hiddify://import/' + l },
  { key: 'streisand', label: 'Streisand', os: ['ios'], url: (l) => 'streisand://import/' + l },
  { key: 'v2box', label: 'V2Box', os: ['ios'], url: (l) => 'v2box://install-sub?url=' + encodeURIComponent(l) + '&name=AstroByte' },
  { key: 'clashmeta', label: 'Clash Meta', os: ['android'], url: (l) => 'clash://install-config?url=' + encodeURIComponent(l + '/clash_meta') + '&name=AstroByte' },
];
const appsForPlatform = () => ALL_APPS.filter((a) => PLATFORM === 'any' || a.os.includes(PLATFORM) || a.os.includes('any'));

// Choose-your-app sheet, opened from the big ring button on Home. Orbit
// (the house app) sits on top as the hero choice; its add-link is an https
// URL minted server-side, so it opens through Telegram's own openLink.
export function AppLaunchSheet({ t, open, link, currentSubId, onClose }) {
  const [orbitBusy, setOrbitBusy] = useState(false);

  const openOrbit = async () => {
    if (orbitBusy) return;
    setOrbitBusy(true);
    try {
      const body = currentSubId ? { subscription_id: Number(currentSubId) } : {};
      const r = await api('/api/dashboard/orbit/add-link', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
      });
      if (r && r.ok && r.add_url) {
        const tg = getWebApp();
        if (tg?.openLink) tg.openLink(r.add_url); else window.open(r.add_url, '_blank');
      } else {
        showToast(r?.error === 'no_subscription' ? t('noSubOpen') : t('orbitFailed'), 'error');
      }
    } catch (_) { showToast(t('orbitFailed'), 'error'); } finally { setOrbitBusy(false); }
  };

  const openApp = (app) => {
    if (!link) { showToast(t('noSubOpen'), 'error'); return; }
    launchScheme(app.url(link));
    showToast(t('appLaunchHint'), 'success');
  };

  return (
    <Sheet open={open} onClose={onClose} panelId="appLaunchSheet" backdropId="appLaunchBackdrop" labelledBy="appLaunchTitle">
      <h2 id="appLaunchTitle">{t('appLaunchTitle')}</h2>
      <p className="sheet-subtitle">{t('appLaunchSub')}</p>
      <button
        type="button"
        className="btn btn-primary"
        style={{ width: '100%', justifyContent: 'center', marginTop: 12, fontWeight: 800, fontSize: 15, padding: '13px 16px' }}
        disabled={orbitBusy}
        onClick={openOrbit}
      >
        {orbitBusy ? '…' : 'Orbit ' + t('appOrbitTag')}
      </button>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginTop: 10 }}>
        {appsForPlatform().map((app) => (
          <button key={app.key} type="button" className="btn" style={{ justifyContent: 'center', fontWeight: 700 }} onClick={() => openApp(app)}>
            {app.label}
          </button>
        ))}
      </div>
      <a className="btn" style={{ width: '100%', justifyContent: 'center', marginTop: 8, fontSize: 12.5 }} href="/webapp/dashboard/tutorial.html">
        {t('appGridHelp')}
      </a>
      <div className="sheet-actions" style={{ marginTop: 12, justifyContent: 'center' }}>
        <button className="btn" onClick={onClose}>{t('close')}</button>
      </div>
    </Sheet>
  );
}

export function AddSubSheet({ t, open, onClose, onSubmit }) {
  const [value, setValue] = useState('');
  const [busy, setBusy] = useState(false);
  const inputRef = useRef(null);

  useEffect(() => {
    if (open) {
      setValue('');
      setTimeout(() => { try { inputRef.current?.focus(); } catch (_) { /* ignore */ } }, 80);
    }
  }, [open]);

  const submit = async () => {
    const raw = value.trim();
    if (!raw) { showToast(t('invalidInput'), 'error'); return; }
    setBusy(true);
    try { await onSubmit(raw); } finally { setBusy(false); }
  };

  return (
    <Sheet open={open} onClose={onClose} panelId="addSubSheet" backdropId="addSubSheetBackdrop" labelledBy="addSubTitle">
      <h2 id="addSubTitle">{t('addSubscriptionTitle')}</h2>
      <p className="sheet-subtitle" id="addSubSubtitle">{t('promptAdd')}</p>
      <div className="sheet-field">
        <input
          id="addSubInput"
          ref={inputRef}
          type="text"
          placeholder={t('promptAdd')}
          inputMode="text"
          autoCapitalize="none"
          autoComplete="off"
          spellCheck={false}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); submit(); } }}
        />
      </div>
      <div className="sheet-actions">
        <button id="addSubCancel" className="btn" onClick={onClose}>{t('cancel')}</button>
        <button id="addSubConfirm" className={`btn btn-primary${busy ? ' loading' : ''}`} disabled={busy} onClick={submit}>{t('addNow')}</button>
      </div>
    </Sheet>
  );
}

export function ConfirmRemoveSheet({ t, open, label, onClose, onConfirm }) {
  const [busy, setBusy] = useState(false);
  return (
    <Sheet open={open} onClose={onClose} panelId="confirmSheet" backdropId="confirmSheetBackdrop" labelledBy="confirmRemoveTitle">
      <h2 id="confirmRemoveTitle">{t('removeSubscription')}</h2>
      <p className="sheet-subtitle" id="confirmRemoveText">
        <span>{t('removeSubscription')}</span>
        <strong style={{ margin: '0 6px' }} id="confirmRemoveName">{label || '—'}</strong>?
      </p>
      <div className="sheet-actions">
        <button id="confirmRemoveCancel" className="btn" onClick={onClose}>{t('cancel')}</button>
        <button
          id="confirmRemoveConfirm"
          className="btn btn-primary"
          disabled={busy}
          onClick={async () => { setBusy(true); try { await onConfirm(); } finally { setBusy(false); } }}
        >
          {t('removeSubscription')}
        </button>
      </div>
    </Sheet>
  );
}

export function ExportModal({ t, open, link, showQRFirst, onClose }) {
  const [qrVisible, setQrVisible] = useState(false);
  const [qrDataUrl, setQrDataUrl] = useState('');
  useEffect(() => { if (open) setQrVisible(!!showQRFirst); }, [open, showQRFirst]);

  // QR is generated locally (lazy chunk): no third-party service, so the
  // subscription link never leaves the device and CSP stays closed.
  useEffect(() => {
    if (!(qrVisible && link)) { setQrDataUrl(''); return undefined; }
    let cancelled = false;
    import('qrcode')
      .then((QR) => QR.toDataURL(link, { width: 600, margin: 1, errorCorrectionLevel: 'M' }))
      .then((url) => { if (!cancelled) setQrDataUrl(url); })
      .catch(() => { if (!cancelled) { setQrDataUrl(''); showToast(t('qrFailed') || 'QR failed', 'error'); } });
    return () => { cancelled = true; };
  }, [qrVisible, link, t]);

  const [appsVisible, setAppsVisible] = useState(false);
  useEffect(() => { if (!open) setAppsVisible(false); }, [open]);

  const openApp = (app) => {
    if (!link) { showToast(t('noSubOpen'), 'error'); return; }
    // iframe launch — never navigates the webview (see launchScheme above)
    launchScheme(app.url(link));
    showToast(t('appLaunchHint'), 'success');
  };

  return (
    <Sheet open={open} onClose={onClose} panelId="exportModal" backdropId="exportModalBackdrop" labelledBy="exportModalTitle">
      <h2 id="exportModalTitle">{t('exportTitle')}</h2>
      <p
        className="sheet-subtitle"
        id="exportLinkText"
        style={{ wordBreak: 'break-all', fontSize: 12, fontFamily: 'monospace', background: 'var(--chip)', padding: 10, borderRadius: 8, marginTop: 12, direction: 'ltr', textAlign: 'left' }}
      >
        {link || '—'}
      </p>
      {qrVisible && link && qrDataUrl && (
        <div id="exportQRContainer" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', marginTop: 16 }}>
          <img
            id="exportQRImg"
            src={qrDataUrl}
            alt="QR Code"
            style={{ width: 300, height: 300, borderRadius: 12, background: '#fff', padding: 10 }}
          />
        </div>
      )}
      {appsVisible && (
        <div id="exportAppGrid" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginTop: 14 }}>
          {appsForPlatform().map((app) => (
            <button
              key={app.key}
              className="btn"
              style={{ justifyContent: 'center', fontWeight: 700 }}
              onClick={() => openApp(app)}
            >
              {app.label}
            </button>
          ))}
          <a
            className="btn"
            style={{ gridColumn: '1 / -1', justifyContent: 'center', fontSize: 12.5, color: 'var(--muted, inherit)' }}
            href="/webapp/dashboard/tutorial.html"
          >
            {t('appGridHelp')}
          </a>
        </div>
      )}
      <div className="sheet-actions" style={{ marginTop: 16, justifyContent: 'center' }}>
        <button id="exportAddBtn" className="btn btn-primary" onClick={() => setAppsVisible((v) => !v)}>{t('addToApp')}</button>
        <button id="exportQRBtn" className="btn" onClick={() => setQrVisible(!qrVisible)}>{t('showQR')}</button>
        <button id="exportModalClose" className="btn" onClick={onClose}>{t('close')}</button>
      </div>
    </Sheet>
  );
}

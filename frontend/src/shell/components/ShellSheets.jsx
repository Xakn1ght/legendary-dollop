import React, { useEffect, useRef, useState } from 'react';

import { getWebApp } from '../../shared/telegram.js';
import { api } from '../api.js';
import { showToast } from '../toast.js';

// CSS Modules pilot (2026-07-18): the export modal's styles are co-located
// here instead of index.css — the convention for all new component styles.
import exp from './ExportModal.module.css';
import { Sheet } from './Sheet.jsx';

// ---- one-tap app import -----------------------------------------------
// Launching a custom scheme via window.location navigates the Telegram
// webview to net::ERR_UNKNOWN_URL_SCHEME and KILLS the SPA (the mini app
// stays dead until Telegram is force-closed) — never top-navigate.
//
// Ladder (2026-07-08, second revision — Pasha: iPhone opened NOTHING):
// 1. window.open on EVERY platform — Telegram hands the URL to the OS
//    (Android intent resolution / iOS UIApplication.open). This is the only
//    path that ever worked on Android, and iOS WKWebView silently blocks
//    custom-scheme loads in SUBFRAMES, so the old iframe-first iOS path was
//    a no-op.
// 2. Popup blocked → synthesized <a target=_blank> tap (still counts as the
//    same user gesture; goes through the same external-open policy).
// 3. iframe only as a last resort if anchor creation itself threw.
function launchScheme(url) {
  try {
    const w = window.open(url, '_blank');
    if (w) {
      // If the scheme resolved, the OS already switched apps; close the
      // stray about:blank so it doesn't linger behind the webview.
      setTimeout(() => { try { w.close(); } catch (_) { /* ignore */ } }, 1200);
      return;
    }
  } catch (_) { /* ignore */ }
  try {
    const a = document.createElement('a');
    a.href = url;
    a.target = '_blank';
    a.rel = 'noopener';
    document.body.appendChild(a);
    a.click();
    setTimeout(() => { try { a.remove(); } catch (_) { /* ignore */ } }, 0);
    return;
  } catch (_) { /* ignore */ }
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
//
// SCHEME RULE (2026-07-08, round 2 — Pasha: Clash Meta opened Hiddify):
// generic scheme names (clash://, clashmeta://, sing-box://) are registered
// by EVERY same-core client, so a plain scheme lets whichever app grabbed it
// answer — Hiddify squats clashmeta:// (their own devs acknowledge this).
// The only deterministic Android fix is an intent:// URL pinned to the app's
// package via `apkg`; the plain `url` stays for iOS + as the fallback.
// `dl` = official download page when the app turns out not to be installed:
// GitHub releases where the project officially distributes there (all four
// Android clients), App Store for iOS (sideloading isn't a thing — the store
// IS the official download page even when a repo exists).
const ALL_APPS = [
  { key: 'v2rayng', label: 'v2rayNG', os: ['android'], apkg: 'com.v2ray.ang', url: (l) => 'v2rayng://install-config?url=' + encodeURIComponent(l), dl: { android: 'https://github.com/2dust/v2rayNG/releases/latest' } },
  { key: 'karing', label: 'Karing', os: ['android', 'ios', 'any'], apkg: 'com.nebula.karing', url: (l) => 'karing://install-config?url=' + encodeURIComponent(l + '/sing_box') + '&name=AstroByte', dl: { android: 'https://github.com/KaringX/karing/releases/latest', ios: 'https://apps.apple.com/app/id6472431552', any: 'https://github.com/KaringX/karing/releases/latest' } },
  { key: 'hiddify', label: 'Hiddify', os: ['android', 'ios', 'any'], apkg: 'app.hiddify.com', url: (l) => 'hiddify://install-config?url=' + encodeURIComponent(l), dl: { android: 'https://github.com/hiddify/hiddify-app/releases/latest', ios: 'https://apps.apple.com/app/id6596777532', any: 'https://github.com/hiddify/hiddify-app/releases/latest' } },
  { key: 'streisand', label: 'Streisand', os: ['ios'], url: (l) => 'streisand://import/' + l, dl: { ios: 'https://apps.apple.com/app/id6450534064' } },
  { key: 'v2box', label: 'V2Box', os: ['ios'], url: (l) => 'v2box://install-sub?url=' + encodeURIComponent(l) + '&name=AstroByte', dl: { ios: 'https://apps.apple.com/app/id6446814690' } },
  { key: 'clashmeta', label: 'Clash Meta', os: ['android'], apkg: 'com.github.metacubex.clash.meta', url: (l) => 'clashmeta://install-config?url=' + encodeURIComponent(l + '/clash_meta') + '&name=AstroByte', dl: { android: 'https://github.com/MetaCubeX/ClashMetaForAndroid/releases/latest' } },
];
const appsForPlatform = () => ALL_APPS.filter((a) => PLATFORM === 'any' || a.os.includes(PLATFORM) || a.os.includes('any'));

export function appDownloadUrl(app) {
  return (app.dl && (app.dl[PLATFORM] || app.dl.any)) || null;
}

// Launch (round 6 — Pasha: the timed "not installed" popup opened BEHIND
// Telegram's own "Open link?" confirm, because while that native dialog is
// up the webview stays visible and un-blurred, so every visibility heuristic
// reads "launch failed"). A webview fundamentally cannot know whether a
// scheme resolved — every timer/visibility guess has a false-positive mode.
// New approach: NO detection, NO popups. Fire the launch (Android still gets
// the package-locked intent:// first with a plain-scheme follow-up — TG's
// Android webview can't parse intent://), and the SHEET shows a quiet inline
// "didn't open? get it from …" link for the tapped app. Deterministic on
// both OSes; nothing can appear behind native dialogs.
let _ladderToken = 0;
function launchApp(app, link) {
  const token = ++_ladderToken;
  const raw = app.url(link);
  const steps = [];
  if (PLATFORM === 'android' && app.apkg) {
    const m = /^([a-z0-9+.-]+):\/\/(.*)$/i.exec(raw);
    if (m) steps.push('intent://' + m[2] + '#Intent;scheme=' + m[1] + ';package=' + app.apkg + ';end');
  }
  steps.push(raw);
  launchScheme(steps[0]);
  if (steps.length > 1) {
    setTimeout(() => {
      // Skip the follow-up when we were clearly backgrounded (app opened).
      if (token !== _ladderToken || document.hidden) return;
      launchScheme(steps[1]);
    }, 1200);
  }
}

// Inline "didn't open? get it from …" row shown after a launch attempt —
// replaces the old timed popup (see launchApp above).
export function AppFallbackRow({ t, app }) {
  if (!app) return null;
  const dl = appDownloadUrl(app);
  if (!dl) return null;
  const openDl = () => {
    const tg = getWebApp();
    if (tg?.openLink) tg.openLink(dl); else window.open(dl, '_blank');
  };
  return (
    <button type="button" className="app-fallback" onClick={openDl}>
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" width="14" height="14" aria-hidden="true">
        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><polyline points="7 10 12 15 17 10" /><line x1="12" y1="15" x2="12" y2="3" />
      </svg>
      <span>{t('appDidntOpen').replace('{app}', '\u2068' + app.label + '\u2069')}</span>
    </button>
  );
}

// Choose-your-app sheet, opened from the big ring button on Home. Orbit
// (the house app) sits on top as the hero choice; its add-link is an https
// URL minted server-side, so it opens through Telegram's own openLink.
// Orbit is Android-only for now — hidden on iOS until the iOS build ships.
export function AppLaunchSheet({ t, open, link, currentSubId, onClose }) {
  const [orbitBusy, setOrbitBusy] = useState(false);
  const [lastTried, setLastTried] = useState(null);
  const showOrbit = PLATFORM !== 'ios';

  useEffect(() => { if (!open) setLastTried(null); }, [open]);

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
    // \u2068…\u2069 isolates the Latin app name inside the RTL sentence.
    showToast(t('appLaunchHint').replace('{app}', '\u2068' + app.label + '\u2069'), 'success');
    launchApp(app, link);
    setLastTried(app);
  };

  return (
    <Sheet open={open} onClose={onClose} panelId="appLaunchSheet" backdropId="appLaunchBackdrop" labelledBy="appLaunchTitle">
      <h2 id="appLaunchTitle">{t('appLaunchTitle')}</h2>
      <p className="sheet-subtitle">{t('appLaunchSub')}</p>
      {showOrbit && (
        <button
          type="button"
          className="btn btn-primary app-hero"
          disabled={orbitBusy}
          onClick={openOrbit}
        >
          {orbitBusy ? '…' : 'Orbit ' + t('appOrbitTag')}
        </button>
      )}
      <div className="app-grid">
        {appsForPlatform().map((app) => (
          <button key={app.key} type="button" className="btn app-tile" onClick={() => openApp(app)}>
            {app.label}
          </button>
        ))}
      </div>
      <AppFallbackRow t={t} app={lastTried} />
      <a className="btn app-help-link" href="/webapp/dashboard/apps.html">
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
          maxLength={2000}
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
          className="btn btn-danger"
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
  const [copied, setCopied] = useState(false);
  useEffect(() => { if (open) { setQrVisible(!!showQRFirst); setCopied(false); } }, [open, showQRFirst]);

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
  const [lastTried, setLastTried] = useState(null);
  useEffect(() => { if (!open) { setAppsVisible(false); setLastTried(null); } }, [open]);

  const openApp = (app) => {
    if (!link) { showToast(t('noSubOpen'), 'error'); return; }
    // window.open launches — never navigates the webview (see launchScheme above)
    showToast(t('appLaunchHint').replace('{app}', '\u2068' + app.label + '\u2069'), 'success');
    launchApp(app, link);
    setLastTried(app);
  };

  const copyLink = async () => {
    if (!link) { showToast(t('noSubOpen'), 'error'); return; }
    try {
      await navigator.clipboard.writeText(link);
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
      showToast(t('linkCopied'), 'success', 1800);
    } catch (_) { showToast(t('copyFailed'), 'error'); }
  };

  return (
    <Sheet open={open} onClose={onClose} panelId="exportModal" backdropId="exportModalBackdrop" labelledBy="exportModalTitle">
      <div className={exp.head}>
        <h2 id="exportModalTitle">{t('exportTitle')}</h2>
        <button id="exportModalClose" className={exp.close} type="button" aria-label={t('close')} onClick={onClose}>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" width="16" height="16" aria-hidden="true">
            <path d="M18 6 6 18M6 6l12 12" />
          </svg>
        </button>
      </div>

      <div className={exp.linkRow}>
        <div className={exp.link} id="exportLinkText" dir="ltr">{link || '—'}</div>
        <button className={`${exp.copy}${copied ? ` ${exp.ok}` : ''}`} type="button" aria-label={t('copyLink')} onClick={copyLink}>
          {copied
            ? <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" width="16" height="16" aria-hidden="true"><polyline points="20 6 9 17 4 12" /></svg>
            : <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" width="16" height="16" aria-hidden="true"><rect x="9" y="9" width="13" height="13" rx="2" ry="2" /><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" /></svg>}
        </button>
      </div>

      {qrVisible && link && (
        <div className={exp.qrWrap} id="exportQRContainer">
          {qrDataUrl
            ? <img id="exportQRImg" className={exp.qr} src={qrDataUrl} alt="QR Code" />
            : <div className={`${exp.qr} ${exp.qrLoading}`} aria-hidden="true" />}
        </div>
      )}

      {appsVisible && (
        <div id="exportAppGrid" className={exp.apps}>
          {appsForPlatform().map((app) => (
            <button key={app.key} className="btn app-tile" onClick={() => openApp(app)}>
              {app.label}
            </button>
          ))}
          <AppFallbackRow t={t} app={lastTried} />
          <a className={`btn ${exp.appsHelp}`} href="/webapp/dashboard/apps.html">
            {t('appGridHelp')}
          </a>
        </div>
      )}

      <div className={exp.actions}>
        <button id="exportAddBtn" className={`btn btn-primary ${exp.primary}`} onClick={() => setAppsVisible((v) => !v)}>
          {t('addToApp')}
        </button>
        <div className={exp.actionsRow}>
          <button id="exportCopyBtn" className="btn" onClick={copyLink}>{t('copyLink')}</button>
          <button id="exportQRBtn" className="btn" onClick={() => setQrVisible(!qrVisible)}>
            {qrVisible ? t('hideQR') : t('showQR')}
          </button>
        </div>
      </div>
    </Sheet>
  );
}

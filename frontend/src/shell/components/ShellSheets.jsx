import React, { useEffect, useRef, useState } from 'react';

import { getWebApp } from '../../shared/telegram.js';
import { showToast } from '../toast.js';

import { Sheet } from './Sheet.jsx';

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

  const addToApp = () => {
    if (!link) { showToast(t('noSubOpen'), 'error'); return; }
    const tg = getWebApp();
    const ua = navigator.userAgent || '';
    if (/android/i.test(ua)) {
      window.location.href = 'v2rayng://install-config?url=' + encodeURIComponent(link);
      showToast(t('addToApp'), 'success');
    } else {
      const tutorialUrl = '/webapp/dashboard/tutorial.html';
      if (tg?.openLink) tg.openLink(tutorialUrl); else window.location.href = tutorialUrl;
    }
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
      <div className="sheet-actions" style={{ marginTop: 16, justifyContent: 'center' }}>
        <button id="exportAddBtn" className="btn btn-primary" onClick={addToApp}>{t('addToApp')}</button>
        <button id="exportQRBtn" className="btn" onClick={() => setQrVisible(!qrVisible)}>{t('showQR')}</button>
        <button id="exportModalClose" className="btn" onClick={onClose}>{t('close')}</button>
      </div>
    </Sheet>
  );
}

import React, { useRef } from 'react';

import { hapticSelection } from '../telegram.js';

function formatCardNumber(cardNum) {
  if (!cardNum) return '6037-xxxx-xxxx-xxxx';
  const formatted = cardNum.replace(/[\s-]/g, '').replace(/(.{4})/g, '$1-').slice(0, -1);
  return formatted || '6037-xxxx-xxxx-xxxx';
}

export function ReceiptSection({ t, fmtPrice, paymentInfo, amount, previewSrc, hasFile, onCopyCard, onFileSelect, onClearFile, onCancel, onSubmit, uploadPct = null }) {
  const inputRef = useRef(null);
  const uploading = uploadPct != null;

  const openPicker = () => {
    try {
      inputRef.current?.click();
      hapticSelection();
    } catch (_) { /* ignore */ }
  };

  const clearFile = (e) => {
    e.stopPropagation();
    try { if (inputRef.current) inputRef.current.value = ''; } catch (_) { /* ignore */ }
    if (onClearFile) onClearFile();
    hapticSelection();
  };

  return (
    <div className="section active" id="section-receipt">
      <div className="card">
        <div className="card-title">
          <div className="icon">
            <svg viewBox="0 0 24 24"><path d="M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm-5 14H7v-2h7v2zm3-4H7v-2h10v2zm0-4H7V7h10v2z" /></svg>
          </div>
          <span>{t('uploadReceipt')}</span>
        </div>

        <div className="bank-info">
          <div className="bank-info-title">{t('cardNumber')}</div>
          <div className="card-number" id="bankCardNumber" onClick={onCopyCard}>
            {formatCardNumber(paymentInfo.card_number)}
          </div>
          <div className="card-number-tap-hint">{t('tapToCopy')}</div>
        </div>

        <div className="receipt-amount-box">
          <div className="receipt-amount-label">{t('amountToPay')}</div>
          <div className="receipt-amount-value" id="receiptAmount">{fmtPrice(amount)}</div>
        </div>

        <input
          ref={inputRef}
          type="file"
          className="file-input"
          id="receiptInput"
          accept="image/*"
          onChange={onFileSelect}
        />
        <div
          className={`receipt-upload${hasFile ? ' has-image' : ''}`}
          id="receiptUploadBox"
          tabIndex={0}
          role="button"
          aria-label="Upload receipt"
          onClick={openPicker}
          onKeyDown={(e) => {
            if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); openPicker(); }
          }}
        >
          {!hasFile && (
            <div className="upload-placeholder" id="receiptPlaceholder">
              <svg viewBox="0 0 24 24" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2h3l2-3h8l2 3h3a2 2 0 0 1 2 2z" /><path d="M12 17a4 4 0 1 0 0-8 4 4 0 0 0 0 8z" /></svg>
              <div className="upload-label">{t('selectReceipt')}</div>
            </div>
          )}
          {previewSrc && <img className="receipt-preview" id="receiptPreview" alt="Receipt preview" src={previewSrc} />}
          {hasFile && !uploading && (
            <button
              type="button"
              className="receipt-remove-btn"
              aria-label={t('removePhoto') || 'Remove photo'}
              onClick={clearFile}
            >
              <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round"><path d="M18 6 6 18M6 6l12 12" /></svg>
            </button>
          )}
        </div>
      </div>

      {uploading && (
        <div className="upload-progress" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={uploadPct}>
          <div className="upload-progress-track">
            <div className="upload-progress-fill" style={{ width: `${uploadPct}%` }} />
          </div>
          <div className="upload-progress-label">
            {uploadPct >= 100 ? (t('uploadProcessing') || '…') : `${t('uploading') || 'Uploading'} ${uploadPct}%`}
          </div>
        </div>
      )}

      <div className="btn-container">
        <button className="btn btn-secondary" onClick={onCancel} disabled={uploading}>
          <span>{t('cancel')}</span>
        </button>
        <button className="btn btn-primary" id="btnSubmitReceipt" disabled={!hasFile || uploading} onClick={onSubmit}>
          <span>{uploading ? `${uploadPct}%` : t('submitReceipt')}</span>
        </button>
      </div>
    </div>
  );
}

import React from 'react';

export function SuccessSection({ t, message, onDone }) {
  return (
    <div className="section active" id="section-success">
      <div className="success-screen">
        <div className="success-icon">
          <svg viewBox="0 0 24 24"><path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z" /></svg>
        </div>
        <h2 className="success-title">{t('receiptSent')}</h2>
        <p className="success-message">{message}</p>
      </div>

      <button className="btn btn-primary" onClick={onDone}>
        <span>{t('backToDashboard')}</span>
      </button>
    </div>
  );
}

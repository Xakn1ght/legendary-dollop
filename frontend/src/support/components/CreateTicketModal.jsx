import React, { useEffect, useState } from 'react';

import { useBackClose } from '../../shared/backstack.js';

const CATEGORIES = ['connection', 'money', 'other'];

// Telegram mobile gets the designed bottom-sheet picker instead of a web <select>.
function useDesignedPicker() {
  const [use, setUse] = useState(() => {
    try { return !!(window.Telegram && window.Telegram.WebApp) && window.innerWidth <= 768; } catch (_) { return false; }
  });
  useEffect(() => {
    let timer;
    const onResize = () => {
      clearTimeout(timer);
      timer = setTimeout(() => {
        try { setUse(!!(window.Telegram && window.Telegram.WebApp) && window.innerWidth <= 768); } catch (_) { /* ignore */ }
      }, 80);
    };
    window.addEventListener('resize', onResize);
    return () => { window.removeEventListener('resize', onResize); clearTimeout(timer); };
  }, []);
  return use;
}

function PickerSheet({ t, type, subs, current, onPick, onClose }) {
  const [query, setQuery] = useState('');
  useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape') onClose(); };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [onClose]);

  let items;
  if (type === 'category') {
    items = CATEGORIES.map((c) => ({ value: c, label: t(c) }));
  } else {
    const all = [{ value: '', label: t('none') }, ...subs.map((s) => ({ value: String(s.id), label: s.username || 'Sub #' + s.id }))];
    const q = query.toLowerCase();
    items = q ? all.filter((o) => o.label.toLowerCase().includes(q) || o.value.includes(q)) : all;
  }

  return (
    <>
      <div className="picker-backdrop active" onClick={onClose} />
      <div className="picker-panel active" role="dialog" aria-modal="true">
        <div className="picker-head">
          <div className="picker-title">{type === 'category' ? t('categoryLabel') : t('subscriptionLabel')}</div>
          <button className="picker-close" type="button" onClick={onClose} aria-label="Close">
            <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>
        {type === 'sub' && (
          <div className="picker-search">
            <input
              type="text"
              placeholder={t('search')}
              autoComplete="off"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              // eslint-disable-next-line jsx-a11y/no-autofocus
              autoFocus
            />
          </div>
        )}
        <div className="picker-list">
          {items.map((o) => (
            <div
              key={o.value || '__none'}
              className={`picker-item${o.value === current ? ' selected' : ''}`}
              onClick={() => { onPick(o.value); onClose(); }}
            >
              <div className="label">{o.label}</div>
              <svg className="check" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3">
                <path d="M20 6 9 17l-5-5" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </div>
          ))}
        </div>
      </div>
    </>
  );
}

export function CreateTicketModal({ t, active, subs, initialSubId, onSubmit, onClose }) {
  const [category, setCategory] = useState('');
  const [subId, setSubId] = useState(initialSubId || '');
  const [message, setMessage] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [picker, setPicker] = useState(null); // null | 'category' | 'sub'
  const designed = useDesignedPicker();

  // Back closes the picker sheet before the modal itself.
  useBackClose(active && !!picker, () => setPicker(null));

  useEffect(() => { if (initialSubId) setSubId(String(initialSubId)); }, [initialSubId]);

  const subLabel = subId ? (subs.find((s) => String(s.id) === String(subId))?.username || '#' + subId) : t('none');

  const submit = async (e) => {
    e.preventDefault();
    if (!category || !message.trim() || submitting) return;
    setSubmitting(true);
    try {
      const ok = await onSubmit({ category, subId, message: message.trim() });
      if (ok) { setCategory(''); setSubId(''); setMessage(''); }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className={`modal-overlay${active ? ' active' : ''}`} id="createTicketModal">
      <div className="modal">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
          <h3 className="modal-title" style={{ margin: 0 }}>{t('newTicket')}</h3>
          <button onClick={onClose} style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }} aria-label="Close">
            <svg viewBox="0 0 24 24" width="24" height="24" stroke="currentColor" fill="none" strokeWidth="2"><line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" /></svg>
          </button>
        </div>
        <form onSubmit={submit}>
          <div className="form-group">
            <label className="form-label">{t('categoryLabel')}</label>
            {designed ? (
              <button type="button" className="fake-select-btn" style={{ display: 'flex' }} onClick={() => setPicker('category')}>
                <span className={`value${category ? '' : ' muted'}`}>{category ? t(category) : t('selectCategory')}</span>
                <svg className="chev" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M6 9l6 6 6-6" strokeLinecap="round" strokeLinejoin="round" /></svg>
              </button>
            ) : (
              <select className="form-select" id="ticketCategory" required value={category} onChange={(e) => setCategory(e.target.value)}>
                <option value="" disabled>{t('selectCategory')}</option>
                {CATEGORIES.map((c) => <option key={c} value={c}>{t(c)}</option>)}
              </select>
            )}
          </div>
          <div className="form-group">
            <label className="form-label">{t('subscriptionLabel')}</label>
            {designed ? (
              <button type="button" className="fake-select-btn" style={{ display: 'flex' }} onClick={() => setPicker('sub')}>
                <span className="value">{subLabel}</span>
                <svg className="chev" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M6 9l6 6 6-6" strokeLinecap="round" strokeLinejoin="round" /></svg>
              </button>
            ) : (
              <select className="form-select" id="ticketSub" value={subId} onChange={(e) => setSubId(e.target.value)}>
                <option value="">{t('none')}</option>
                {subs.map((s) => <option key={s.id} value={s.id}>{s.username || 'Sub #' + s.id}</option>)}
              </select>
            )}
          </div>
          <div className="form-group">
            <label className="form-label">{t('messageLabel')}</label>
            <textarea
              className="form-textarea"
              id="ticketMessage"
              rows={4}
              placeholder={t('describeIssue')}
              required
              value={message}
              onChange={(e) => setMessage(e.target.value)}
            />
          </div>
          <button type="submit" className={`btn-block${submitting ? ' btn-loading' : ''}`}>{t('createTicketBtn')}</button>
        </form>
      </div>

      {picker && (
        <PickerSheet
          t={t}
          type={picker}
          subs={subs}
          current={picker === 'category' ? category : String(subId)}
          onPick={(v) => (picker === 'category' ? setCategory(v) : setSubId(v))}
          onClose={() => setPicker(null)}
        />
      )}
    </div>
  );
}

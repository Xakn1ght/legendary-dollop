import React, { createContext, useCallback, useContext, useState } from 'react';

// Themed confirm / alert / prompt modal, ported from admin_shared.js v3Modal.
// Exposed as a promise-based API via useModal(): confirm(), alert(), prompt().

const ModalCtx = createContext(null);
export function useModal() { return useContext(ModalCtx); }

export function ModalProvider({ children }) {
  const [state, setState] = useState(null); // {title, sub, message, kind, okText, cancelText, danger, defaultValue, resolve}
  const [inputVal, setInputVal] = useState('');

  const close = useCallback((result) => {
    setState((s) => {
      if (s && s.resolve) s.resolve(result);
      return null;
    });
  }, []);

  const open = useCallback((cfg) => new Promise((resolve) => {
    setInputVal(cfg.defaultValue || '');
    setState({ ...cfg, resolve });
  }), []);

  const api = {
    alert: (title, message, sub = '') => open({ kind: 'alert', title, message, sub }),
    confirm: (title, message, opts = {}) => open({
      kind: 'confirm', title, message,
      sub: opts.sub || '', okText: opts.okText || 'OK',
      cancelText: opts.cancelText || 'Cancel', danger: !!opts.danger,
    }),
    prompt: (title, message, defaultValue = '', opts = {}) => open({
      kind: 'prompt', title, message, defaultValue,
      okText: opts.okText || 'OK', cancelText: opts.cancelText || 'Cancel',
    }),
  };

  return (
    <ModalCtx.Provider value={api}>
      {children}
      {state && (
        <div
          className="v3-modal-backdrop open"
          onClick={(e) => { if (e.target === e.currentTarget) close(state.kind === 'prompt' ? null : false); }}
          onKeyDown={(e) => { if (e.key === 'Escape') close(state.kind === 'prompt' ? null : false); }}
        >
          <div className="v3-modal" role="dialog" aria-modal="true">
            <div className="v3-modal-head">
              <div>
                <div className="v3-modal-title">{state.title || 'Confirm'}</div>
                <div className="v3-modal-sub">{state.sub || ''}</div>
              </div>
              <button className="mini-close" type="button" aria-label="Close"
                onClick={() => close(state.kind === 'prompt' ? null : false)}>✕</button>
            </div>
            <div className="v3-modal-body">
              {state.message}
              {state.kind === 'prompt' && (
                <input
                  className="input-field" style={{ marginTop: 12 }} autoFocus
                  value={inputVal} onChange={(e) => setInputVal(e.target.value)}
                  onKeyDown={(e) => { if (e.key === 'Enter') close(inputVal); }}
                />
              )}
            </div>
            <div className="v3-modal-actions">
              {state.kind !== 'alert' && (
                <button className="btn btn-secondary" type="button"
                  onClick={() => close(state.kind === 'prompt' ? null : false)}>
                  {state.cancelText || 'Cancel'}
                </button>
              )}
              <button
                className={'btn btn-primary' + (state.danger ? ' btn-danger' : '')}
                type="button"
                onClick={() => close(state.kind === 'prompt' ? inputVal : true)}
              >
                {state.okText || 'OK'}
              </button>
            </div>
          </div>
        </div>
      )}
    </ModalCtx.Provider>
  );
}

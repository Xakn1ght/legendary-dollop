import React from 'react';

// Generic bottom sheet matching legacy .sheet-backdrop/.sheet-panel markup
// (glass.css + index.css style these by class).
export function Sheet({ open, onClose, labelledBy, children, panelId, backdropId }) {
  return (
    <>
      <div
        className={`sheet-backdrop${open ? ' visible' : ''}`}
        id={backdropId}
        aria-hidden={!open}
        onClick={onClose}
      />
      <div
        className={`sheet-panel${open ? ' open' : ''}`}
        id={panelId}
        role="dialog"
        aria-modal="true"
        aria-labelledby={labelledBy}
        aria-hidden={!open}
      >
        <div className="sheet-handle" />
        <div className="sheet-content">{children}</div>
      </div>
    </>
  );
}

import React, { useCallback, useEffect, useId, useImperativeHandle, useRef, useState } from 'react';

import { hapticSelection } from '../../shared/telegram.js';

import s from './SubDropdown.module.css';

// Themed subscription picker for the shop charge tab (2026-07-18, Pasha:
// "make dropdown to be built in match theme") — replaces the native <select>
// whose OS sheet clashed with the app. Button trigger + in-page listbox
// panel: tap-outside/Escape close, arrow-key navigation, RTL via logical
// properties, light theme via :global rules in the co-located module.
//
// Imperative contract kept from the old select: parent holds a ref and calls
// .focus() when the user taps a plan without picking a sub first — here that
// focuses the trigger AND opens the panel (the pulse ring is the `highlight`
// prop, driven by the same parent state as before).
export function SubDropdown({
  ref, subs, value, onChange, placeholder, loadingLabel, emptyLabel, ariaLabel, highlight = false,
}) {
  const [open, setOpen] = useState(false);
  const wrapRef = useRef(null);
  const triggerRef = useRef(null);
  const panelRef = useRef(null);
  const listboxId = useId();

  const loading = subs === null;
  const empty = !loading && subs.length === 0;
  const options = loading ? [] : subs;
  const subName = (sub) => sub.name || sub.username || sub.marzban_username || ('#' + sub.id);
  const selected = options.find((sub) => String(sub.id) === String(value)) || null;

  useImperativeHandle(ref, () => ({
    focus() {
      try { triggerRef.current?.focus(); } catch (_) { /* ignore */ }
      if (!loading && !empty) setOpen(true);
    },
  }), [loading, empty]);

  const close = useCallback((refocus = false) => {
    setOpen(false);
    if (refocus) { try { triggerRef.current?.focus(); } catch (_) { /* ignore */ } }
  }, []);

  // Tap-outside + Escape close while the panel is open.
  useEffect(() => {
    if (!open) return undefined;
    const onPointerDown = (e) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target)) setOpen(false);
    };
    const onKeyDown = (e) => {
      if (e.key === 'Escape') { e.stopPropagation(); close(true); }
    };
    document.addEventListener('pointerdown', onPointerDown, true);
    document.addEventListener('keydown', onKeyDown, true);
    return () => {
      document.removeEventListener('pointerdown', onPointerDown, true);
      document.removeEventListener('keydown', onKeyDown, true);
    };
  }, [open, close]);

  const focusOption = useCallback((idx) => {
    const nodes = panelRef.current?.querySelectorAll('[role="option"]');
    if (!nodes || !nodes.length) return;
    const i = Math.max(0, Math.min(nodes.length - 1, idx));
    try { nodes[i].focus(); } catch (_) { /* ignore */ }
  }, []);

  const toggle = () => {
    if (loading || empty) return;
    setOpen((was) => !was);
    hapticSelection();
  };

  const onTriggerKeyDown = (e) => {
    if (loading || empty) return;
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault();
      setOpen(true);
      const idx = e.key === 'ArrowDown' ? 0 : options.length - 1;
      requestAnimationFrame(() => focusOption(idx));
    }
  };

  const onOptionKeyDown = (e, idx) => {
    if (e.key === 'ArrowDown') { e.preventDefault(); focusOption(idx + 1); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); focusOption(idx - 1); }
    else if (e.key === 'Home') { e.preventDefault(); focusOption(0); }
    else if (e.key === 'End') { e.preventDefault(); focusOption(options.length - 1); }
    else if (e.key === 'Tab') { setOpen(false); }
  };

  const pick = (sub) => {
    onChange(String(sub.id));
    hapticSelection();
    close(true);
  };

  const triggerText = loading ? loadingLabel : empty ? emptyLabel : (selected ? subName(selected) : placeholder);

  return (
    <div ref={wrapRef} className={s.wrap}>
      <button
        ref={triggerRef}
        type="button"
        id="shopSubSelect"
        className={`${s.trigger}${highlight ? ` ${s.pulse}` : ''}`}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={open ? listboxId : undefined}
        aria-label={ariaLabel}
        aria-disabled={loading || empty || undefined}
        onClick={toggle}
        onKeyDown={onTriggerKeyDown}
      >
        {/* bdi: latin usernames keep their own direction inside the RTL row
            without being torn from the row's start edge */}
        <span className={`${s.value}${selected ? '' : ` ${s.placeholder}`}`}>
          {selected ? <bdi>{triggerText}</bdi> : triggerText}
        </span>
        <svg
          className={`${s.chev}${open ? ` ${s.chevOpen}` : ''}`}
          viewBox="0 0 24 24" fill="none" aria-hidden="true"
        >
          <path d="M6 9l6 6 6-6" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </button>
      {open && !loading && !empty && (
        <div ref={panelRef} id={listboxId} className={s.panel} role="listbox" aria-label={ariaLabel}>
          {options.map((sub, idx) => {
            const isSel = String(sub.id) === String(value);
            return (
              <button
                key={sub.id}
                type="button"
                role="option"
                aria-selected={isSel}
                className={s.option}
                onClick={() => pick(sub)}
                onKeyDown={(e) => onOptionKeyDown(e, idx)}
              >
                <span className={s.check} aria-hidden="true">
                  <svg viewBox="0 0 24 24" fill="none" width="15" height="15"><polyline points="20 6 9 17 4 12" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" /></svg>
                </span>
                <span className={s.optName}><bdi>{subName(sub)}</bdi></span>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

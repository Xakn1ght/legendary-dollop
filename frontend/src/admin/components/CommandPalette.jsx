import React, { useCallback, useEffect, useRef, useState } from 'react';

import { apiJson } from '../api.js';
import { Icons, NAV } from '../icons.jsx';

// Cmd+K / Ctrl+K — jump to any page, or search users live and jump to them.
export function CommandPalette({ navigate }) {
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState('');
  const [users, setUsers] = useState([]);
  const [sel, setSel] = useState(0);
  const inputRef = useRef(null);
  const timerRef = useRef(0);

  const pages = NAV.flatMap((s) => s.items).map((it) => ({
    kind: 'page', id: it.page, label: it.label,
  }));

  const close = useCallback(() => { setOpen(false); setQ(''); setUsers([]); setSel(0); }, []);

  useEffect(() => {
    const onKey = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        setOpen((v) => !v);
      } else if (e.key === 'Escape' && open) {
        close();
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, close]);

  useEffect(() => {
    if (open) setTimeout(() => inputRef.current && inputRef.current.focus(), 30);
  }, [open]);

  // live user search (debounced)
  useEffect(() => {
    clearTimeout(timerRef.current);
    if (!q.trim() || q.trim().length < 2) { setUsers([]); return undefined; }
    timerRef.current = setTimeout(async () => {
      try {
        const { data } = await apiJson(`/api/admin/users?search=${encodeURIComponent(q.trim())}&limit=6`);
        if (data.ok && Array.isArray(data.users)) setUsers(data.users.slice(0, 6));
      } catch (_) { /* ignore */ }
    }, 220);
    return () => clearTimeout(timerRef.current);
  }, [q]);

  if (!open) return null;

  const ql = q.trim().toLowerCase();
  const pageHits = ql
    ? pages.filter((p) => p.label.toLowerCase().includes(ql) || p.id.includes(ql))
    : pages;
  const items = [
    ...pageHits.map((p) => ({ ...p, key: 'p' + p.id })),
    ...users.map((u) => ({
      kind: 'user', key: 'u' + u.id, id: u.id,
      label: `${u.first_name || u.username || 'user'} · ${u.chat_id}`,
    })),
  ];
  const selIdx = Math.min(sel, Math.max(items.length - 1, 0));

  function run(item) {
    if (!item) return;
    if (item.kind === 'page') {
      navigate(item.id);
    } else {
      try { sessionStorage.setItem('admin_user_search', q.trim()); } catch (_) { /* ignore */ }
      navigate('users');
    }
    close();
  }

  function onKeyDown(e) {
    if (e.key === 'ArrowDown') { e.preventDefault(); setSel((s) => Math.min(s + 1, items.length - 1)); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); setSel((s) => Math.max(s - 1, 0)); }
    else if (e.key === 'Enter') { e.preventDefault(); run(items[selIdx]); }
  }

  return (
    <div className="cmdk-backdrop" onClick={close}>
      <div className="cmdk" onClick={(e) => e.stopPropagation()}>
        <div className="cmdk-input-row">
          <Icons.search width={16} height={16} />
          <input
            ref={inputRef}
            value={q}
            placeholder="Jump to page or search users…"
            onChange={(e) => { setQ(e.target.value); setSel(0); }}
            onKeyDown={onKeyDown}
          />
          <kbd>esc</kbd>
        </div>
        <div className="cmdk-list">
          {items.length === 0 && <div className="cmdk-empty">No matches</div>}
          {items.map((it, i) => {
            const Icon = it.kind === 'page' ? (Icons[it.id] || Icons.dashboard) : Icons.users;
            return (
              <div
                key={it.key}
                className={'cmdk-item' + (i === selIdx ? ' on' : '')}
                onMouseEnter={() => setSel(i)}
                onClick={() => run(it)}
              >
                <Icon width={15} height={15} />
                <span>{it.label}</span>
                <em>{it.kind === 'page' ? 'page' : 'user'}</em>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

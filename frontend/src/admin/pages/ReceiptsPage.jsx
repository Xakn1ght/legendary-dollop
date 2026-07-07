import React, { useEffect, useMemo, useRef, useState } from 'react';

import { apiFetch } from '../api.js';
import { useModal } from '../components/Modal.jsx';
import { useToast } from '../components/Toast.jsx';
import { Icons } from '../icons.jsx';
import { useShell } from '../ShellContext.js';
import { fmtNum, parseTs } from '../util.js';

// Purchase / charge / VIP receipt approvals. Money-critical — approve/deny
// endpoints and their accepted response messages are ported 1:1 from
// index-main.js approveReceipt/denyReceipt.
export function ReceiptsPage() {
  const { receipts: rc } = useShell();
  const modal = useModal();
  const toast = useToast();
  const [q, setQ] = useState('');
  const [source, setSource] = useState('all');
  const [sort, setSort] = useState('newest');
  const [drawer, setDrawer] = useState(null);
  const [lightbox, setLightbox] = useState(null); // {url, zoom}
  const inFlight = useRef(new Set());

  // Fraud signals, computed over the whole pending queue:
  //  - the exact same receipt image attached to 2+ orders (strong)
  //  - one user with 2+ pending orders (soft — could be legit)
  const dupes = useMemo(() => {
    const all = Array.isArray(rc.receipts) ? rc.receipts : [];
    const byImg = new Map();
    const byUser = new Map();
    for (const r of all) {
      if (r.receipt_image_url) byImg.set(r.receipt_image_url, (byImg.get(r.receipt_image_url) || 0) + 1);
      const uk = r.user_name || r.username || r.user_id;
      if (uk) byUser.set(uk, (byUser.get(uk) || 0) + 1);
    }
    return {
      img: (r) => r.receipt_image_url && byImg.get(r.receipt_image_url) > 1,
      user: (r) => {
        const uk = r.user_name || r.username || r.user_id;
        return uk && byUser.get(uk) > 1;
      },
    };
  }, [rc.receipts]);

  const list = useMemo(() => {
    let out = Array.isArray(rc.receipts) ? rc.receipts.slice() : [];
    if (source === 'web') out = out.filter((r) => !!r.is_web_receipt);
    if (source === 'telegram') out = out.filter((r) => !r.is_web_receipt);
    const query = q.trim().toLowerCase();
    if (query) {
      out = out.filter((r) => [r.user_name, r.username, r.plan_name, r.service_name, String(r.id || '')]
        .filter(Boolean).join(' ').toLowerCase().includes(query));
    }
    const ts = (v) => parseTs(v)?.getTime() || 0;
    if (sort === 'newest') out.sort((a, b) => ts(b.created_at) - ts(a.created_at));
    if (sort === 'oldest') out.sort((a, b) => ts(a.created_at) - ts(b.created_at));
    if (sort === 'price_high') out.sort((a, b) => (Number(b.price) || 0) - (Number(a.price) || 0));
    if (sort === 'price_low') out.sort((a, b) => (Number(a.price) || 0) - (Number(b.price) || 0));
    return out;
  }, [rc.receipts, q, source, sort]);

  function endpointFor(type, id, action) {
    if (type === 'vip') return `/api/admin/vip-orders/${id}/${action}`;
    if (type === 'charge') return `/api/admin/charges/${id}/${action}`;
    return `/api/admin/receipts/${id}/${action}`;
  }

  // Keyboard triage: j/k or arrows move through the queue, A approves,
  // D denies, Esc closes. Disabled while typing in an input or in a modal.
  // Refs keep the (empty-dep) listener reading fresh state/handlers.
  const listRef = useRef([]);
  listRef.current = list;
  const drawerRef = useRef(null);
  drawerRef.current = drawer;
  const actRef = useRef(null);
  useEffect(() => {
    const onKey = (e) => {
      const tag = (document.activeElement?.tagName || '').toLowerCase();
      if (tag === 'input' || tag === 'textarea' || tag === 'select') return;
      if (document.querySelector('.cmdk-backdrop')) return;
      const cur = drawerRef.current;
      const items = listRef.current;
      const idx = cur ? items.findIndex((x) => x.id === cur.id && (x.type || 'subscription') === (cur.type || 'subscription')) : -1;
      const k = e.key.toLowerCase();
      if (k === 'escape') { setLightbox(null); setDrawer(null); return; }
      if (k === 'j' || e.key === 'ArrowRight') {
        e.preventDefault();
        setDrawer(items[Math.min(idx + 1, items.length - 1)] || null);
      } else if (k === 'k' || e.key === 'ArrowLeft') {
        e.preventDefault();
        setDrawer(idx > 0 ? items[idx - 1] : items[0] || null);
      } else if (k === 'a' && cur) {
        e.preventDefault();
        actRef.current && actRef.current(cur, 'approve');
      } else if (k === 'd' && cur) {
        e.preventDefault();
        actRef.current && actRef.current(cur, 'deny');
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function act(r, action) {
    const type = r.type || 'subscription';
    const key = `${type}-${r.id}`;
    if (inFlight.current.has(key)) return;
    const isVip = type === 'vip';
    const isCharge = type === 'charge';
    const verb = action === 'approve' ? 'Approve' : 'Deny';
    const msg = action === 'approve'
      ? (isVip ? 'Approve this VIP purchase and activate VIP membership?' : isCharge ? 'Approve this charge request and add data/days?' : 'Approve this receipt and activate the service?')
      : (isVip ? 'Deny this VIP purchase?' : isCharge ? 'Deny this charge request?' : 'Deny this receipt? (Service will not be activated)');
    const ok = await modal.confirm(`${verb} receipt`, msg, { okText: verb, danger: action === 'deny' });
    if (!ok) return;

    inFlight.current.add(key);
    try {
      const res = await apiFetch(endpointFor(type, r.id, action), { method: 'POST' });
      let data = {};
      try { data = await res.json(); } catch (_) { data = {}; }
      const good = action === 'approve' ? 'approved' : 'denied';
      if (data.ok && (data.message === good || data.message === 'already_processed')) {
        toast(`Receipt ${good}`, 'success');
        if (drawer && drawer.id === r.id && (drawer.type || 'subscription') === type) setDrawer(null);
        await rc.reload();
        return;
      }
      await modal.alert(`${verb} failed`, (data && (data.error || data.message)) || `${verb} failed`);
    } catch (_) {
      await modal.alert('Connection error', 'Could not reach server. Please try again.');
    } finally {
      inFlight.current.delete(key);
    }
  }
  actRef.current = act; // latest-ref for the keyboard listener

  return (
    <>
      <div className="filter-bar glass-card" style={{ display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'center' }}>
        <div className="search-wrapper" style={{ flex: 1, minWidth: 180 }}>
          <input className="search-input input-field" placeholder="Search receipts…" value={q} onChange={(e) => setQ(e.target.value)} />
        </div>
        <select className="input-field" style={{ width: 'auto' }} value={source} onChange={(e) => setSource(e.target.value)}>
          <option value="all">All sources</option>
          <option value="web">Web</option>
          <option value="telegram">Telegram</option>
        </select>
        <select className="input-field" style={{ width: 'auto' }} value={sort} onChange={(e) => setSort(e.target.value)}>
          <option value="newest">Newest</option>
          <option value="oldest">Oldest</option>
          <option value="price_high">Price ↓</option>
          <option value="price_low">Price ↑</option>
        </select>
        <span style={{ fontSize: 13, color: 'var(--text-muted)' }}>{list.length} pending</span>
        <button className="refresh-btn" onClick={() => rc.reload()} title="Refresh" disabled={rc.loading}>⟳</button>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: 16, paddingTop: 20 }}>
        {list.length === 0 && (
          <div className="receipts-empty" style={{ gridColumn: '1/-1', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 10, color: 'var(--text-muted)', padding: 48 }}>
            <span className="fx-sparkle" style={{ color: 'var(--success)' }}><Icons.check width={30} height={30} /></span>
            No pending receipts
          </div>
        )}
        {list.map((r) => {
          const type = r.type || 'subscription';
          const isVip = type === 'vip';
          const isCharge = type === 'charge';
          const sourceLabel = isVip ? 'VIP' : isCharge ? 'CHARGE' : (r.is_web_receipt ? 'WEB' : 'TELEGRAM');
          return (
            <div className="glass-card receipt-card fx-tilt" key={`${type}-${r.id}`} onClick={() => setDrawer(r)}>
              <div className="receipt-top">
                <div className="receipt-ident">
                  <div className="receipt-avatar">{(r.user_name || 'U').trim().charAt(0).toUpperCase()}</div>
                  <div className="receipt-who">
                    <div className="receipt-name">{r.user_name || 'Unknown User'}{r.is_vip ? <span className="receipt-vip" title="VIP"><Icons.crown width={14} height={14} /></span> : null}</div>
                    <div className="receipt-handle">{r.username ? '@' + r.username : '—'}</div>
                  </div>
                </div>
                <div className="receipt-chips">
                  <span className="receipt-chip">{sourceLabel}</span>
                  <span className="receipt-chip">{r.plan_name || 'Plan'}{Number(r.plan_gb) ? ` • ${Number(r.plan_gb)}GB` : ''}</span>
                  {dupes.img(r) && <span className="receipt-chip flag-hard" title="Same receipt image attached to multiple orders"><Icons.alert width={11} height={11} /> DUPE IMAGE</span>}
                  {!dupes.img(r) && dupes.user(r) && <span className="receipt-chip flag-soft" title="This user has multiple pending orders">multi-pending</span>}
                </div>
              </div>
              <div className="receipt-mid">
                <div className="receipt-kv"><div className="receipt-k">Service</div><div className="receipt-v">{isVip ? 'VIP Membership' : isCharge ? `Charge: ${r.service_name || '—'}` : (r.service_name || '—')}</div></div>
                <div className="receipt-kv"><div className="receipt-k">Total</div><div className="receipt-v receipt-price">{fmtNum(r.price)} T</div></div>
                <div className="receipt-kv"><div className="receipt-k">Submitted</div><div className="receipt-v">{parseTs(r.created_at)?.toLocaleString() || '—'}</div></div>
              </div>
              <div className="receipt-actions">
                <button onClick={(e) => { e.stopPropagation(); act(r, 'approve'); }} className="btn btn-primary">Approve</button>
                <button onClick={(e) => { e.stopPropagation(); act(r, 'deny'); }} className="btn btn-secondary receipt-deny">Deny</button>
              </div>
            </div>
          );
        })}
      </div>

      {drawer && (
        <div className="v3-modal-backdrop open" onClick={(e) => { if (e.target === e.currentTarget) setDrawer(null); }}>
          <div className="v3-modal" role="dialog" aria-modal="true" style={{ maxWidth: 520 }}>
            <div className="v3-modal-head">
              <div>
                <div className="v3-modal-title">{drawer.user_name || 'Receipt'}</div>
                <div className="v3-modal-sub">{drawer.username ? '@' + drawer.username : ''} · {(drawer.type || 'subscription').toUpperCase()}</div>
              </div>
              <button className="mini-close" type="button" onClick={() => setDrawer(null)}>✕</button>
            </div>
            <div className="v3-modal-body">
              <div className="receipt-kv"><div className="receipt-k">Plan</div><div className="receipt-v">{drawer.plan_name || '—'}{Number(drawer.plan_gb) ? ` • ${Number(drawer.plan_gb)}GB` : ''}</div></div>
              <div className="receipt-kv"><div className="receipt-k">Total</div><div className="receipt-v receipt-price">{fmtNum(drawer.price)} T</div></div>
              {Number(drawer.credit_used) > 0 && <div className="receipt-kv"><div className="receipt-k">Credit used</div><div className="receipt-v">−{fmtNum(drawer.credit_used)}</div></div>}
              <div className="receipt-kv"><div className="receipt-k">Submitted</div><div className="receipt-v">{parseTs(drawer.created_at)?.toLocaleString() || '—'}</div></div>
              {dupes.img(drawer) && (
                <div className="receipt-fraud-note">
                  <Icons.alert width={14} height={14} /> This exact receipt image is attached to more than one pending order — verify before approving.
                </div>
              )}
              {drawer.receipt_image_url && (
                <button
                  type="button"
                  className="receipt-img-btn"
                  onClick={() => setLightbox({ url: drawer.receipt_image_url, zoom: false })}
                  title="Click to zoom"
                >
                  <img src={drawer.receipt_image_url} alt="receipt" style={{ width: '100%', borderRadius: 12, marginTop: 12, border: '1px solid var(--border-subtle)', display: 'block' }} />
                  <span className="receipt-img-zoom"><Icons.zoom width={14} height={14} /></span>
                </button>
              )}
              <div className="receipt-hotkeys">hotkeys: <kbd>j</kbd>/<kbd>k</kbd> next/prev · <kbd>A</kbd> approve · <kbd>D</kbd> deny · <kbd>Esc</kbd> close</div>
            </div>
            <div className="v3-modal-actions">
              <button className="btn btn-secondary btn-danger" onClick={() => act(drawer, 'deny')}>Deny</button>
              <button className="btn btn-primary" onClick={() => act(drawer, 'approve')}>Approve</button>
            </div>
          </div>
        </div>
      )}

      {lightbox && (
        <div className="lightbox-backdrop">
          {/* real <button> scrim: iOS won't synthesize clicks on a plain div,
              which left the fullscreen photo impossible to dismiss by tap */}
          <button type="button" className="lightbox-scrim" aria-label="Close photo" onClick={() => setLightbox(null)} />
          <img
            src={lightbox.url}
            alt="receipt zoom"
            className={'lightbox-img' + (lightbox.zoom ? ' zoomed' : '')}
            onClick={(e) => { e.stopPropagation(); setLightbox((l) => ({ ...l, zoom: !l.zoom })); }}
          />
          <button className="lightbox-close" onClick={() => setLightbox(null)}><Icons.close width={18} height={18} /></button>
        </div>
      )}
    </>
  );
}

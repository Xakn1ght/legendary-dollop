import React, { useEffect, useMemo, useRef, useState } from 'react';

import { apiFetch } from '../api.js';
import { useModal } from '../components/Modal.jsx';
import { useToast } from '../components/Toast.jsx';
import { Icons } from '../icons.jsx';
import { useShell } from '../ShellContext.js';
import { fmtDateTime, fmtNum, parseTs, saveImageLocally } from '../util.js';

// Purchase / charge / VIP receipt approvals. Money-critical — approve/deny
// endpoints and their accepted response messages are ported 1:1 from
// index-main.js approveReceipt/denyReceipt.

function agoShort(d) {
  if (!d) return '—';
  const s = Math.max(0, Math.floor((Date.now() - d.getTime()) / 1000));
  if (s < 60) return 'now';
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return `${Math.floor(s / 86400)}d ago`;
}

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
    if (type === 'cashout') return `/api/admin/cashouts/${id}/${action}`;
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
    const isCashout = type === 'cashout';
    const verb = action === 'approve' ? (isCashout ? 'Mark paid' : 'Approve') : 'Deny';
    const msg = action === 'approve'
      ? (isCashout
        ? 'Mark this cash-out as PAID? Confirm only after you have transferred the money to the user.'
        : isVip ? 'Approve this VIP purchase and activate VIP membership?' : isCharge ? 'Approve this charge request and add data/days?' : 'Approve this receipt and activate the service?')
      : (isCashout
        ? 'Deny this cash-out? The reserved amount returns to the user\u2019s wallet.'
        : isVip ? 'Deny this VIP purchase?' : isCharge ? 'Deny this charge request?' : 'Deny this receipt? (Service will not be activated)');
    const ok = await modal.confirm(isCashout ? `${verb}: cash-out` : `${verb} receipt`, msg, { okText: verb, danger: action === 'deny' });
    if (!ok) return;

    inFlight.current.add(key);
    try {
      const res = await apiFetch(endpointFor(type, r.id, action), { method: 'POST' });
      let data = {};
      try { data = await res.json(); } catch (_) { data = {}; }
      const good = action === 'approve' ? 'approved' : 'denied';
      if (data.ok && (data.message === good || data.message === 'already_processed')) {
        toast(type === 'cashout' ? `Cash-out ${action === 'approve' ? 'marked paid' : 'denied'}` : `Receipt ${good}`, 'success');
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
      <div className="filter-bar glass-card rcp-bar">
        <div className="search-wrapper rcp-search">
          <input className="search-input input-field" placeholder="Search receipts…" value={q} onChange={(e) => setQ(e.target.value)} />
        </div>
        <div className="rcp-bar-row">
          <select className="input-field" value={source} onChange={(e) => setSource(e.target.value)}>
            <option value="all">All sources</option>
            <option value="web">Web</option>
            <option value="telegram">Telegram</option>
          </select>
          <select className="input-field" value={sort} onChange={(e) => setSort(e.target.value)}>
            <option value="newest">Newest</option>
            <option value="oldest">Oldest</option>
            <option value="price_high">Price: high first</option>
            <option value="price_low">Price: low first</option>
          </select>
          <span className="rcp-count">{list.length} pending</span>
          <button className="refresh-btn" onClick={() => rc.reload()} title="Refresh" disabled={rc.loading}>
            <Icons.refresh width={15} height={15} />
          </button>
        </div>
      </div>

      <div className="rcp-grid">
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
          const isCashout = type === 'cashout';
          const sourceLabel = isVip ? 'VIP' : isCharge ? 'CHARGE' : isCashout ? 'CASH-OUT' : (r.is_web_receipt ? 'WEB' : 'TELEGRAM');
          const service = isVip ? 'VIP Membership' : isCharge ? `Charge: ${r.service_name || '—'}` : isCashout ? `To: ${r.cashout_destination || '—'}` : (r.service_name || '—');
          const when = parseTs(r.created_at);
          return (
            <div
              className="glass-card receipt-card fx-tilt"
              key={`${type}-${r.id}`}
              role="button"
              tabIndex={0}
              onClick={() => setDrawer(r)}
              onKeyDown={(e) => { if (e.key === 'Enter') setDrawer(r); }}
            >
              <div className="rcp-head">
                <div className="receipt-avatar">{(r.user_name || 'U').trim().charAt(0).toUpperCase()}</div>
                <div className="rcp-who">
                  <div className="receipt-name">
                    <bdi>{r.user_name || 'Unknown User'}</bdi>
                    {r.is_vip ? <span className="receipt-vip" title="VIP"><Icons.crown width={14} height={14} /></span> : null}
                  </div>
                  <div className="receipt-handle">{r.username ? '@' + r.username : '—'}</div>
                </div>
                <span className={'receipt-chip rcp-src' + (isVip ? ' receipt-chip-vip' : '')}>{sourceLabel}</span>
              </div>

              <div className="rcp-meta">
                <div className="rcp-meta-l">
                  {/* bdi keeps Persian plan names from garbling against the GB suffix */}
                  <div className="rcp-plan"><bdi>{r.plan_name || 'Plan'}</bdi>{Number(r.plan_gb) ? <span className="rcp-gb">{Number(r.plan_gb)}GB</span> : null}</div>
                  {r.renewal_plan && (
                    <div className="rcp-booking" title="Paid auto-renew booking included in the total">
                      <Icons.refresh width={11} height={11} /> <bdi>{r.renewal_plan}</bdi>
                    </div>
                  )}
                  <div className="rcp-sub">
                    <span className="rcp-service" dir="ltr">{service}</span>
                    <span className="rcp-dot" aria-hidden="true" />
                    <time title={when ? fmtDateTime(r.created_at) : ''}>{agoShort(when)}</time>
                  </div>
                </div>
                <div className="rcp-price" title="Amount that must appear on the bank receipt">{fmtNum(r.price)}<span> T</span></div>
              </div>

              {(dupes.img(r) || dupes.user(r) || r.receipt_image_url) && (
                <div className="rcp-flags">
                  {r.receipt_image_url && (
                    <button
                      type="button"
                      className="receipt-chip rcp-photo"
                      title="View receipt photo"
                      onClick={(e) => { e.stopPropagation(); setLightbox({ url: r.receipt_image_url, zoom: false }); }}
                    >
                      <Icons.camera width={11} height={11} /> Receipt
                    </button>
                  )}
                  {dupes.img(r) && <span className="receipt-chip flag-hard" title="Same receipt image attached to multiple orders"><Icons.alert width={11} height={11} /> DUPE IMAGE</span>}
                  {!dupes.img(r) && dupes.user(r) && <span className="receipt-chip flag-soft" title="This user has multiple pending orders">multi-pending</span>}
                </div>
              )}

              <div className="receipt-actions rcp-actions">
                <button onClick={(e) => { e.stopPropagation(); act(r, 'deny'); }} className="btn btn-secondary receipt-deny">Deny</button>
                <button onClick={(e) => { e.stopPropagation(); act(r, 'approve'); }} className="btn btn-primary">{isCashout ? 'Mark paid' : 'Approve'}</button>
              </div>
            </div>
          );
        })}
      </div>

      {drawer && (() => {
        const dType = drawer.type || 'subscription';
        const dCashout = dType === 'cashout';
        const dCharge = dType === 'charge';
        const dVip = dType === 'vip';
        const srcLabel = dVip ? 'VIP' : dCashout ? 'CASH-OUT' : dCharge ? 'CHARGE' : (drawer.is_web_receipt ? 'WEB' : 'TELEGRAM');
        const when = parseTs(drawer.created_at);

        // Invoice line items — mirrors the bot receipt caption 1:1: plan,
        // booking, deductions, then the single number to match on the receipt.
        const items = [];
        if (dCashout) {
          items.push({ key: 'amount', label: 'Withdrawal amount', name: null, value: drawer.plan_price });
        } else {
          items.push({ key: 'plan', label: dCharge ? 'Top-up' : dVip ? 'Membership' : 'Plan', name: drawer.plan_name, value: drawer.plan_price });
          if (dType === 'subscription' && drawer.renewal_plan) {
            items.push({ key: 'renewal', label: 'Auto-renew booking', name: drawer.renewal_plan, value: drawer.renewal_price });
          }
          if (Number(drawer.discount_amount) > 0) {
            items.push({ key: 'discount', label: 'Discount / coupon', name: null, value: -drawer.discount_amount, minus: true });
          }
          if (Number(drawer.credit_used) > 0) {
            items.push({ key: 'credit', label: 'Wallet credit', name: null, value: -drawer.credit_used, minus: true });
          }
        }

        const meta = [
          { k: 'Order', v: '#' + drawer.id },
          { k: 'Source', v: srcLabel },
          dCashout
            ? { k: 'Destination', v: drawer.cashout_destination || '—', ltr: true }
            : { k: 'Service', v: drawer.service_name || '—', ltr: true },
          { k: 'User ID', v: drawer.user_chat_id || '—', ltr: true },
          Number(drawer.plan_gb) ? { k: 'Volume', v: `${Number(drawer.plan_gb)} GB` } : null,
          dVip && drawer.vip_days ? { k: 'VIP days', v: drawer.vip_days } : null,
          dCharge && drawer.charge_type === 'booking' ? { k: 'Type', v: 'Plan booking' } : null,
          dCharge && drawer.charge_type === 'normal_5gb_limit' ? { k: 'Type', v: '5GB-transfer charge' } : null,
          // Verify aid: last-4 of OUR card — the receipt must show money sent here.
          !dCashout && drawer.payto_last4 ? { k: 'Pay-to card', v: `•••• ${drawer.payto_last4}`, ltr: true } : null,
          { k: 'Submitted', v: fmtDateTime(drawer.created_at) },
        ].filter(Boolean);

        // Buyer history (approved/denied counts from the backend) — a first-time
        // buyer or a deny-heavy history deserves a closer look at the receipt.
        const bhA = Number(drawer.buyer_approved_count);
        const bhD = Number(drawer.buyer_denied_count);
        const hasHistory = Number.isFinite(bhA) && Number.isFinite(bhD);

        return (
          <div className="v3-modal-backdrop open rcp-drawer-wrap" onClick={(e) => { if (e.target === e.currentTarget) setDrawer(null); }}>
            <div className="v3-modal rcp-drawer" role="dialog" aria-modal="true">
              <div className="v3-modal-head">
                <div style={{ minWidth: 0 }}>
                  <div className="v3-modal-title rcp-d-title">
                    <bdi>{drawer.user_name || 'Receipt'}</bdi>
                    {drawer.is_vip ? <span className="receipt-vip" title="VIP"><Icons.crown width={14} height={14} /></span> : null}
                  </div>
                  <div className="v3-modal-sub">{drawer.username ? '@' + drawer.username + ' · ' : ''}Order #{drawer.id} · {srcLabel}</div>
                </div>
                <button className="mini-close" type="button" onClick={() => setDrawer(null)}>✕</button>
              </div>
              <div className="v3-modal-body">
                <div className="inv">
                  {items.map((it) => (
                    <div className="inv-row" key={it.key}>
                      <div className="inv-l">
                        {it.label}
                        {it.name ? <span className="inv-name"><bdi>{it.name}</bdi></span> : null}
                      </div>
                      <div className={'inv-v' + (it.minus ? ' inv-minus' : '')}>{it.minus ? '−' : ''}{fmtNum(Math.abs(Number(it.value) || 0))}</div>
                    </div>
                  ))}
                  <div className="inv-row inv-total">
                    <div className="inv-l">{dCashout ? 'Pay to user' : 'Amount on receipt'}</div>
                    <div className="inv-v">{fmtNum(drawer.price)}<span className="inv-cur"> T</span></div>
                  </div>
                </div>

                <div className="rcp-meta-grid">
                  {meta.map((m) => (
                    <div className="rcp-mg-item" key={m.k}>
                      <div className="rcp-mg-k">{m.k}</div>
                      <div className="rcp-mg-v" dir={m.ltr ? 'ltr' : undefined}><bdi>{m.v}</bdi></div>
                    </div>
                  ))}
                </div>

                {hasHistory && (
                  <div className={'rcp-buyer-history' + (bhD > bhA ? ' warn' : '')}>
                    Buyer history: {bhA} approved · {bhD} denied
                  </div>
                )}

                {dupes.img(drawer) && (
                  <div className="receipt-fraud-note">
                    <Icons.alert width={14} height={14} /> This exact receipt image is attached to more than one pending order — verify before approving.
                  </div>
                )}
                {drawer.receipt_image_url ? (
                  <button
                    type="button"
                    className="receipt-img-btn"
                    onClick={() => setLightbox({ url: drawer.receipt_image_url, zoom: false })}
                    title="Click to zoom"
                  >
                    <img src={drawer.receipt_image_url} alt="receipt" style={{ width: '100%', borderRadius: 12, border: '1px solid var(--border-subtle)', display: 'block' }} />
                    <span className="receipt-img-zoom"><Icons.zoom width={14} height={14} /></span>
                  </button>
                ) : (!dCashout && (
                  <div className="rcp-noimg">
                    <Icons.camera width={14} height={14} /> Receipt photo was sent in Telegram — check the bot card for order #{drawer.id}.
                  </div>
                ))}
                <div className="receipt-hotkeys">hotkeys: <kbd>j</kbd>/<kbd>k</kbd> next/prev · <kbd>A</kbd> approve · <kbd>D</kbd> deny · <kbd>Esc</kbd> close</div>
              </div>
              <div className="v3-modal-actions">
                <button className="btn btn-secondary btn-danger" onClick={() => act(drawer, 'deny')}>Deny</button>
                <button className="btn btn-primary" onClick={() => act(drawer, 'approve')}>{dCashout ? 'Mark paid' : 'Approve'}</button>
              </div>
            </div>
          </div>
        );
      })()}

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
          <button className="lightbox-save" title="Save image" aria-label="Save image" onClick={(e) => { e.stopPropagation(); saveImageLocally(lightbox.url); }}>
            <Icons.download width={18} height={18} />
          </button>
        </div>
      )}
    </>
  );
}

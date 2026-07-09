import React, { useCallback, useEffect, useState } from 'react';

import { apiJson, postJson } from '../api.js';
import { useModal } from '../components/Modal.jsx';
import { useToast } from '../components/Toast.jsx';
import { Icons } from '../icons.jsx';
import { parseTs } from '../util.js';

// "expires in 9d" / "expired 3d ago" — full date lives in the title attr.
function expiresLabel(v) {
  const d = parseTs(v);
  if (!d) return { text: '—', soon: false };
  const days = Math.ceil((d.getTime() - Date.now()) / 86400e3);
  if (days < 0) return { text: `expired ${-days}d ago`, soon: false };
  if (days === 0) return { text: 'expires today', soon: true };
  return { text: `in ${days}d`, soon: days <= 3 };
}

const TYPES = [
  { id: 'discount_percent', label: 'Percent discount', hint: '% off at checkout (capped to a ~100GB plan value)' },
  { id: 'free_gb', label: 'Bonus GB', hint: 'extra traffic added to the purchased plan' },
  { id: 'free_plan', label: 'Free plan', hint: 'zeroes a plan up to the granted plan\'s value' },
];

function IssueForm({ onIssued }) {
  const toast = useToast();
  const [type, setType] = useState('discount_percent');
  const [pct, setPct] = useState(20);
  const [gb, setGb] = useState(10);
  const [planGb, setPlanGb] = useState(30);
  const [planDays, setPlanDays] = useState(30);
  const [expDays, setExpDays] = useState(14);
  const [campaign, setCampaign] = useState('');
  const [mode, setMode] = useState('user');
  const [chatId, setChatId] = useState('');
  const [notify, setNotify] = useState(true);
  const [busy, setBusy] = useState(false);

  async function submit() {
    if (busy) return;
    const payload = type === 'discount_percent' ? { discount_percent: Number(pct) }
      : type === 'free_gb' ? { gb: Number(gb) }
      : { plan_gb: Number(planGb), duration_days: Number(planDays) };
    if (mode === 'user' && !chatId.trim()) { toast('Enter a chat id or @username', 'error'); return; }
    if (mode !== 'user' && !window.confirm(`Issue this coupon to ${mode === 'all' ? 'ALL users' : 'every user with an active subscription'}?`)) return;
    setBusy(true);
    try {
      const { data } = await postJson('/api/admin/coupons', {
        coupon_type: type, payload, expires_days: Number(expDays), campaign: campaign.trim(),
        notify, target: { mode, chat_id: chatId.trim() },
      });
      if (data.ok) {
        toast(`Issued ${data.issued} coupon(s)${data.notified ? `, notified ${data.notified}` : ''}`, 'success');
        onIssued();
      } else toast(`Failed: ${data.error || 'unknown'}`, 'error');
    } catch (_) { toast('Request failed', 'error'); }
    setBusy(false);
  }

  return (
    <div className="glass-card coupon-form">
      <div className="rev-title" style={{ marginBottom: 14 }}><Icons.coupon width={16} height={16} /> Issue coupons</div>

      <div className="coupon-types">
        {TYPES.map((t) => (
          <button key={t.id} className={'coupon-type' + (type === t.id ? ' on' : '')} onClick={() => setType(t.id)} title={t.hint}>
            {t.label}
          </button>
        ))}
      </div>

      <div className="coupon-grid">
        {type === 'discount_percent' && (
          <label>Percent off
            <input type="number" min="1" max="100" value={pct} onChange={(e) => setPct(e.target.value)} />
          </label>
        )}
        {type === 'free_gb' && (
          <label>Bonus GB
            <input type="number" min="1" max="1000" value={gb} onChange={(e) => setGb(e.target.value)} />
          </label>
        )}
        {type === 'free_plan' && (
          <>
            <label>Plan GB
              <input type="number" min="1" max="1000" value={planGb} onChange={(e) => setPlanGb(e.target.value)} />
            </label>
            <label>Plan days
              <input type="number" min="1" max="365" value={planDays} onChange={(e) => setPlanDays(e.target.value)} />
            </label>
          </>
        )}
        <label>Expires in (days)
          <input type="number" min="1" max="365" value={expDays} onChange={(e) => setExpDays(e.target.value)} />
        </label>
        <label>Campaign tag (optional)
          <input type="text" placeholder="e.g. nowruz-1405" value={campaign} onChange={(e) => setCampaign(e.target.value)} />
        </label>
      </div>

      <div className="coupon-target">
        <span className="coupon-target-label">Give to</span>
        <div className="rev-controls">
          <button className={'chip-btn' + (mode === 'user' ? ' on' : '')} onClick={() => setMode('user')}>One user</button>
          <button className={'chip-btn' + (mode === 'active_subs' ? ' on' : '')} onClick={() => setMode('active_subs')}>Active subs</button>
          <button className={'chip-btn' + (mode === 'all' ? ' on' : '')} onClick={() => setMode('all')}>Everyone</button>
        </div>
        {mode === 'user' && (
          <input type="text" className="coupon-user-input" placeholder="chat id or @username"
                 value={chatId} onChange={(e) => setChatId(e.target.value)} />
        )}
        <label className="coupon-notify">
          <input type="checkbox" checked={notify} onChange={(e) => setNotify(e.target.checked)} /> DM users about it
        </label>
      </div>

      <button className="btn btn-primary" disabled={busy} onClick={submit} style={{ marginTop: 14 }}>
        {busy ? 'Issuing…' : 'Issue coupon'}
      </button>
    </div>
  );
}

export function CouponsPage() {
  const modal = useModal();
  const toast = useToast();
  const [data, setData] = useState(null);
  const [status, setStatus] = useState('');
  const [q, setQ] = useState('');
  const [page, setPage] = useState(1);

  const load = useCallback(async () => {
    try {
      const params = new URLSearchParams({ page: String(page), limit: '50' });
      if (status) params.set('status', status);
      if (q.trim()) params.set('q', q.trim());
      const { data: d } = await apiJson(`/api/admin/coupons?${params}`);
      if (d.ok) setData(d);
    } catch (_) { /* ignore */ }
  }, [page, status, q]);

  useEffect(() => { load(); }, [load]);

  async function revoke(c) {
    const ok = await modal.confirm(
      'Revoke coupon?',
      `#${c.id} (${c.coupon_type}) from ${c.user_name || c.chat_id} will stop working immediately.`,
      { okText: 'Revoke', danger: true },
    );
    if (!ok) return;
    const { data: d } = await postJson('/api/admin/coupons/revoke', { coupon_id: c.id });
    if (d.ok) { toast('Coupon revoked', 'success'); load(); }
    else toast('Revoke failed', 'error');
  }

  const describe = (c) => {
    const p = c.payload || {};
    if (c.coupon_type === 'discount_percent') return `${p.discount_percent}% off`;
    if (c.coupon_type === 'free_gb') return `+${p.gb} GB`;
    if (c.coupon_type === 'free_plan') return `${p.plan_gb}GB / ${p.duration_days}d free`;
    return c.coupon_type;
  };

  const counts = data?.counts || {};
  const pages = data ? Math.max(1, Math.ceil(data.total / data.limit)) : 1;

  return (
    <>
      <IssueForm onIssued={load} />

      <div className="glass-card cpn-card">
        <div className="cpn-head">
          <h3>Issued coupons</h3>
          <input type="text" className="coupon-user-input cpn-search" placeholder="Search user / campaign…"
                 value={q} onChange={(e) => { setQ(e.target.value); setPage(1); }} />
          <div className="rev-controls cpn-filters">
            {['', 'active', 'used', 'expired', 'revoked'].map((s) => (
              <button key={s || 'all'} className={'chip-btn' + (status === s ? ' on' : '')}
                      onClick={() => { setStatus(s); setPage(1); }}>
                {s || 'all'}{s && counts[s] != null ? ` · ${counts[s]}` : ''}
              </button>
            ))}
          </div>
        </div>

        <div className="cpn-feed">
          {!data && <div className="act-state">Loading…</div>}
          {data && data.coupons.length === 0 && <div className="act-state">No coupons yet — issue one above.</div>}
          {data && data.coupons.map((c) => {
            const exp = expiresLabel(c.expires_at);
            return (
              <div className={'cpn-row' + (c.status !== 'active' ? ' dim' : '')} key={c.id}>
                <span className={'cpn-ic ' + c.coupon_type} aria-hidden="true"><Icons.coupon width={15} height={15} /></span>
                <div className="cpn-main">
                  <div className="cpn-top">
                    <b className="cpn-what">{describe(c)}</b>
                    <span className={'cpn-st ' + c.status}>{c.status}</span>
                    {c.campaign && <span className="cpn-camp" title="Campaign">{c.campaign}</span>}
                  </div>
                  <div className="cpn-sub">
                    <bdi className="cpn-user">{c.user_name || c.chat_id || `user ${c.user_id}`}</bdi>
                    <span className="rcp-dot" aria-hidden="true" />
                    <span>#{c.id}</span>
                    <span className="rcp-dot" aria-hidden="true" />
                    <span>{c.source}</span>
                    <span className="rcp-dot" aria-hidden="true" />
                    <time className={exp.soon ? 'soon' : ''} title={parseTs(c.expires_at)?.toLocaleString() || ''}>{exp.text}</time>
                  </div>
                </div>
                {c.status === 'active' && (
                  <button className="btn btn-secondary btn-sm cpn-revoke" onClick={() => revoke(c)}>Revoke</button>
                )}
              </div>
            );
          })}
        </div>

        {pages > 1 && (
          <div className="cpn-pager">
            <button className="chip-btn" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>Prev</button>
            <span>{page} / {pages}</span>
            <button className="chip-btn" disabled={page >= pages} onClick={() => setPage((p) => p + 1)}>Next</button>
          </div>
        )}
      </div>
    </>
  );
}

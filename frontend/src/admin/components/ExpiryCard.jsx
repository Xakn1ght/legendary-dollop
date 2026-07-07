import React, { useEffect, useState } from 'react';

import { apiJson, postJson } from '../api.js';
import { Icons } from '../icons.jsx';
import { useToast } from './Toast.jsx';

export function ExpiryCard() {
  const toast = useToast();
  const [data, setData] = useState(null);
  const [tab, setTab] = useState('expiring');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const { data: d } = await apiJson('/api/admin/analytics/expiring?window=7');
        if (alive && d.ok) setData(d);
      } catch (_) { /* ignore */ }
    })();
    return () => { alive = false; };
  }, []);

  const rows = data ? (tab === 'expiring' ? data.expiring : data.expired) : [];
  const remindable = rows.filter((r) => r.chat_id && !r.renewal_paid);

  async function remindAll() {
    if (!remindable.length || busy) return;
    if (!window.confirm(`Send a renewal reminder to ${remindable.length} user(s)?`)) return;
    setBusy(true);
    try {
      const { data: res } = await postJson('/api/admin/analytics/expiring/remind', {
        chat_ids: remindable.map((r) => r.chat_id),
      });
      if (res.ok) toast ? toast(`Reminder sent to ${res.sent} user(s)`, 'success') : alert(`Sent: ${res.sent}`);
      else toast ? toast('Reminder failed', 'error') : alert('failed');
    } catch (_) { toast && toast('Reminder failed', 'error'); }
    setBusy(false);
  }

  return (
    <div className="glass-card expiry-card">
      <div className="rev-head">
        <div className="rev-title"><Icons.bell width={16} height={16} /> Expiry Center</div>
        <div className="rev-controls">
          <button className={'chip-btn' + (tab === 'expiring' ? ' on' : '')} onClick={() => setTab('expiring')}>
            Expiring 7d {data ? `(${data.counts.expiring})` : ''}
          </button>
          <button className={'chip-btn' + (tab === 'expired' ? ' on' : '')} onClick={() => setTab('expired')}>
            Expired {data ? `(${data.counts.expired})` : ''}
          </button>
        </div>
      </div>

      <div className="expiry-list">
        {!data && <div className="rev-empty">Loading…</div>}
        {data && rows.length === 0 && <div className="rev-empty">Nothing {tab === 'expiring' ? 'expiring soon' : 'recently expired'}.</div>}
        {rows.slice(0, 30).map((r) => (
          <div className="expiry-row" key={r.username}>
            <div className="expiry-who">
              <span className="expiry-user">{r.user_name || r.username}</span>
              <span className="expiry-svc">{r.username}{r.plan_name ? ` · ${r.plan_name}` : ''}</span>
            </div>
            <div className="expiry-meta">
              {r.renewal_paid && <span className="expiry-paid" title="Renewal already paid">renewal paid</span>}
              {/* churn radar: expiring AND silent for days = probably already gone */}
              {r.likely_churned && (
                <span className="expiry-churn" title={`Client last connected ${r.inactive_days}d ago`}>
                  silent {Math.round(r.inactive_days)}d
                </span>
              )}
              <span className={'expiry-days' + (r.days_left < 0 ? ' neg' : r.days_left <= 2 ? ' hot' : '')}>
                {r.days_left < 0 ? `${Math.abs(r.days_left).toFixed(0)}d ago` : `${r.days_left.toFixed(1)}d`}
              </span>
            </div>
          </div>
        ))}
      </div>

      {tab === 'expiring' && (
        <button className="btn btn-secondary expiry-remind" disabled={!remindable.length || busy} onClick={remindAll}>
          <Icons.bell width={14} height={14} />
          {busy ? 'Sending…' : `Send renewal reminder (${remindable.length})`}
        </button>
      )}
    </div>
  );
}

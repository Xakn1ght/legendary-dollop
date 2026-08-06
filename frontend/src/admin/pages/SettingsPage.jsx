import React, { useEffect, useMemo, useRef, useState } from 'react';

import { apiFetch, apiJson, postJson } from '../api.js';
import { useModal } from '../components/Modal.jsx';
import { useToast } from '../components/Toast.jsx';
import { Icons } from '../icons.jsx';
import { fmtDateTime, fmtNum } from '../util.js';

// ONE catalog (2026-07-18): a top-up IS a purchase plan, so the separate
// "Charge Packages" editor is gone — Plans is the only product list.
const SECTIONS = [
  { id: 'plans', label: 'Plans', desc: 'Subscription and top-up catalog', icon: 'subscriptions' },
  { id: 'payment', label: 'Payment', desc: 'Card shown to buyers', icon: 'crown' },
  { id: 'sms', label: 'SMS Auto-Approve', desc: 'Bank-SMS receipt matching', icon: 'check' },
  { id: 'jobs', label: 'Job Schedules', desc: 'Background job intervals', icon: 'refresh' },
  { id: 'sessions', label: 'Admin Sessions', desc: 'Multi-device logins', icon: 'users' },
];

function useNarrow() {
  const [narrow, setNarrow] = useState(() => window.matchMedia('(max-width: 860px)').matches);
  useEffect(() => {
    const mq = window.matchMedia('(max-width: 860px)');
    const on = () => setNarrow(mq.matches);
    mq.addEventListener('change', on);
    return () => mq.removeEventListener('change', on);
  }, []);
  return narrow;
}

export function SettingsPage() {
  const narrow = useNarrow();
  const [active, setActive] = useState(narrow ? null : 'plans');
  const [dirtyMap, setDirtyMap] = useState({});
  const modal = useModal();

  // Guard against losing unsaved edits when switching sections
  async function go(id) {
    if (active && dirtyMap[active] && id !== active) {
      const ok = await modal.confirm('Discard changes?', 'You have unsaved changes in this section.', { danger: true, okText: 'Discard' });
      if (!ok) return;
      setDirtyMap((m) => ({ ...m, [active]: false }));
    }
    setActive(id);
  }
  const setDirty = (id, v) => setDirtyMap((m) => (m[id] === v ? m : { ...m, [id]: v }));

  const Section = { plans: PlansEditor, payment: PaymentEditor, sms: SmsControlEditor, jobs: JobsEditor, sessions: SessionsEditor }[active];

  const nav = (
    <nav className="set-nav">
      {SECTIONS.map((s) => {
        const Icon = Icons[s.icon] || Icons.settings;
        return (
          <button key={s.id} className={'set-nav-item' + (active === s.id ? ' active' : '')} onClick={() => go(s.id)}>
            <span className="set-nav-ic"><Icon width={18} height={18} /></span>
            <span className="set-nav-txt">
              <span className="set-nav-label">{s.label}{dirtyMap[s.id] && <span className="set-dot" title="Unsaved changes" />}</span>
              <span className="set-nav-desc">{s.desc}</span>
            </span>
            <span className="set-nav-chev"><Icons.close style={{ display: 'none' }} /><svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2"><path d="M9 18l6-6-6-6" /></svg></span>
          </button>
        );
      })}
    </nav>
  );

  if (narrow) {
    return (
      <div className="set-wrap set-narrow">
        {!active && nav}
        {active && Section && (
          <div className="set-pane">
            <button className="set-back" onClick={() => go(null)}>
              <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2"><path d="M15 18l-6-6 6-6" /></svg>
              {SECTIONS.find((s) => s.id === active)?.label}
            </button>
            <Section onDirty={(v) => setDirty(active, v)} />
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="set-wrap">
      <div className="glass-card set-nav-card">{nav}</div>
      <div className="set-pane glass-card">
        <div className="set-pane-head">
          <h3>{SECTIONS.find((s) => s.id === active)?.label}</h3>
          <p>{SECTIONS.find((s) => s.id === active)?.desc}</p>
        </div>
        {Section && <Section onDirty={(v) => setDirty(active, v)} />}
      </div>
    </div>
  );
}

/* ---- SMS auto-approve control ------------------------------------------- */
function SmsControlEditor() {
  const modal = useModal();
  const toast = useToast();
  const [state, setState] = useState(null);
  const [busy, setBusy] = useState(false);

  const load = async () => {
    try {
      const { data } = await apiJson('/api/admin/sms-control');
      if (data.ok !== false) setState(data);
    } catch (_) { /* ignore */ }
  };
  useEffect(() => { load(); }, []);

  async function toggle() {
    if (!state || busy) return;
    const arming = !state.enabled;
    const ok = await modal.confirm(
      arming ? 'ARM SMS auto-approve?' : 'Disarm SMS auto-approve?',
      arming
        ? 'Incoming PARSIANBANK deposit SMS will auto-approve the one unambiguous matching pending order (exact amount + time window). Ambiguous cases always stay manual.'
        : 'Auto-approval stops immediately; every receipt goes back to manual review.',
      { okText: arming ? 'ARM' : 'Disarm', danger: arming },
    );
    if (!ok) return;
    setBusy(true);
    try {
      const { data } = await postJson('/api/admin/sms-control', { enabled: arming });
      if (data.ok) { toast(arming ? 'SMS auto-approve ARMED' : 'SMS auto-approve disarmed', 'success'); await load(); }
      else toast(data.error === 'source_chat_not_configured' ? 'SMS_SOURCE_CHAT_ID is not configured on the server' : 'Failed', 'error');
    } catch (_) { toast('Request failed', 'error'); }
    setBusy(false);
  }

  const deposits = state?.deposits || [];
  const log = state?.log || [];

  return (
    <div className="sms-panel">
      <div className="sms-arm-row">
        <div>
          <div className="sms-arm-title">
            Auto-approval is <b style={{ color: state?.enabled ? 'var(--success)' : 'var(--text-muted)' }}>{state ? (state.enabled ? 'ARMED' : 'OFF') : '…'}</b>
          </div>
          <div className="sms-arm-sub">
            {state?.source_chat_configured
              ? 'Source channel configured; matches require exact amount + time window.'
              : 'SMS_SOURCE_CHAT_ID is missing in config/.env — arming is blocked.'}
          </div>
        </div>
        <button
          className={'btn ' + (state?.enabled ? 'btn-secondary' : 'btn-primary')}
          disabled={!state || busy || (!state.enabled && !state.source_chat_configured)}
          onClick={toggle}
        >
          {busy ? '…' : state?.enabled ? 'Disarm' : 'Arm'}
        </button>
      </div>

      <div className="set-pane-head" style={{ marginTop: 18 }}>
        <h3 style={{ fontSize: 14 }}>Pooled deposits ({deposits.length})</h3>
        <p>Bank SMS waiting for a matching order (kept for the late-receipt sweep).</p>
      </div>
      <div className="table-responsive">
        <table>
          <thead><tr><th>When</th><th>Amount (rial)</th><th>Tracking</th><th>Card</th><th>Matched</th></tr></thead>
          <tbody>
            {deposits.length === 0 && <tr><td colSpan={5} style={{ textAlign: 'center', color: 'var(--text-muted)', padding: 20 }}>No pooled deposits</td></tr>}
            {deposits.map((d, i) => (
              <tr key={i}>
                <td>{d.ts ? fmtDateTime(d.ts * 1000) : '—'}</td>
                <td style={{ fontVariantNumeric: 'tabular-nums' }}>{Number(d.amount_rial || 0).toLocaleString()}</td>
                <td>{d.tracking || '—'}</td>
                <td>{d.card_last4 ? `…${d.card_last4}` : '—'}</td>
                <td>{d.matched ? <b style={{ color: 'var(--success)' }}>{d.matched}</b> : <span style={{ color: 'var(--text-muted)' }}>waiting</span>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="set-pane-head" style={{ marginTop: 18 }}>
        <h3 style={{ fontSize: 14 }}>Recent SMS activity</h3>
        <p>Last [SMS] lines from the bot log — matches, misses, and approvals.</p>
      </div>
      <pre className="sms-log">{log.length ? log.join('\n') : 'No SMS log lines yet.'}</pre>
    </div>
  );
}

/* ---- shared save bar ---------------------------------------------------- */
function SaveBar({ dirty, saving, onSave, onReset, disabled }) {
  if (!dirty) return null;
  return (
    <div className="set-savebar">
      <span className="set-savebar-txt">Unsaved changes</span>
      <div className="set-savebar-actions">
        <button className="btn btn-secondary" onClick={onReset} disabled={saving}>Discard</button>
        <button className="btn btn-primary" onClick={onSave} disabled={saving || disabled}>{saving ? 'Saving…' : 'Save changes'}</button>
      </div>
    </div>
  );
}

/* ---- plans / charge packages (shared row editor) ------------------------ */
function CatalogEditor({ endpoint, listKey, kind, defaultDays, onDirty }) {
  const modal = useModal();
  const toast = useToast();
  const [items, setItems] = useState(null);
  const [orig, setOrig] = useState('[]');
  const [saving, setSaving] = useState(false);

  const load = async () => {
    const { data } = await apiJson(endpoint);
    const list = (data[listKey] || []).map((p) => ({ name: p.name || '', price: p.price ?? 0, gb: p.gb ?? 0, days: p.days ?? defaultDays }));
    setItems(list); setOrig(JSON.stringify(list));
  };
  useEffect(() => { load(); /* eslint-disable-next-line */ }, []);

  const dirty = items !== null && JSON.stringify(items) !== orig;
  useEffect(() => { onDirty(dirty); }, [dirty, onDirty]);

  const invalid = (items || []).some((p) => !String(p.name).trim() || p.price < 0 || p.gb < 0 || p.days < 0);

  const update = (i, k, v) => setItems((arr) => arr.map((r, idx) => (idx === i ? { ...r, [k]: v } : r)));
  const num = (v) => { const n = parseInt(v, 10); return Number.isFinite(n) ? n : 0; };

  async function save() {
    const valid = items.filter((p) => String(p.name).trim());
    if (kind === 'plans' && !valid.length) { await modal.alert('Missing plans', 'Add at least one valid plan.'); return; }
    setSaving(true);
    const { data } = await postJson(endpoint, { [listKey]: valid });
    setSaving(false);
    if (data.ok) { toast(`${kind === 'plans' ? 'Plans' : 'Packages'} saved`, 'success'); const l = valid.map((p) => ({ ...p })); setItems(l); setOrig(JSON.stringify(l)); }
    else await modal.alert('Error', data.error || 'Save failed.');
  }
  const reset = () => { setItems(JSON.parse(orig)); };

  if (items === null) return <div className="set-loading">Loading…</div>;

  return (
    <div className="set-body">
      <div className="set-rows">
        {items.length === 0 && <div className="set-empty">No {kind === 'plans' ? 'plans' : 'packages'} yet. Add one below.</div>}
        {items.map((p, i) => {
          const bad = !String(p.name).trim();
          return (
            <div className="set-row-card" key={i}>
              <div className="set-field set-field-grow">
                <label>Name</label>
                <input className={'input-field' + (bad ? ' set-invalid' : '')} value={p.name} placeholder="e.g. 60 گیگ | یکماه" onChange={(e) => update(i, 'name', e.target.value)} />
              </div>
              <div className="set-field set-field-price"><label>Price (T)</label><input className="input-field" type="number" min="0" value={p.price} onChange={(e) => update(i, 'price', num(e.target.value))} /></div>
              <div className="set-field"><label>GB</label><input className="input-field" type="number" min="0" value={p.gb} onChange={(e) => update(i, 'gb', num(e.target.value))} /></div>
              <div className="set-field"><label>Days</label><input className="input-field" type="number" min="0" value={p.days} onChange={(e) => update(i, 'days', num(e.target.value))} /></div>
              <button className="set-row-del" title="Remove" onClick={() => setItems((arr) => arr.filter((_, idx) => idx !== i))}>
                <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2"><path d="M18 6 6 18M6 6l12 12" /></svg>
              </button>
            </div>
          );
        })}
      </div>
      <button className="btn btn-secondary set-add" onClick={() => setItems((a) => [...a, { name: '', price: 0, gb: 0, days: defaultDays }])}>
        <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 5v14M5 12h14" /></svg> Add {kind === 'plans' ? 'plan' : 'package'}
      </button>
      <SaveBar dirty={dirty} saving={saving} disabled={invalid} onSave={save} onReset={reset} />
    </div>
  );
}
const PlansEditor = ({ onDirty }) => <CatalogEditor endpoint="/api/admin/settings/plans" listKey="plans" kind="plans" defaultDays={35} onDirty={onDirty} />;

/* ---- payment ------------------------------------------------------------ */
function PaymentEditor({ onDirty }) {
  const modal = useModal();
  const toast = useToast();
  const [card, setCard] = useState(null);
  const [holder, setHolder] = useState('');
  const [orig, setOrig] = useState('');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    (async () => {
      const { data } = await apiJson('/api/admin/settings/payment');
      if (data.ok) { setCard(data.card_number || ''); setHolder(data.card_holder || ''); setOrig((data.card_number || '') + '|' + (data.card_holder || '')); }
      else { setCard(''); }
    })();
  }, []);

  const digits = (card || '').replace(/\D/g, '');
  const dirty = card !== null && (card + '|' + holder) !== orig;
  useEffect(() => { onDirty(dirty); }, [dirty, onDirty]);
  const invalid = digits.length > 0 && digits.length !== 16;

  async function save() {
    setSaving(true);
    const { data } = await postJson('/api/admin/settings/payment', { card_number: digits, card_holder: holder.trim() });
    setSaving(false);
    if (data.ok) { toast('Payment settings saved', 'success'); setOrig(digits + '|' + holder.trim()); setCard(digits); }
    else await modal.alert('Error', 'Save failed.');
  }

  if (card === null) return <div className="set-loading">Loading…</div>;
  const pretty = digits.replace(/(.{4})/g, '$1 ').trim();

  return (
    <div className="set-body">
      <div className="set-field-block">
        <label>Card Number</label>
        <input className={'input-field' + (invalid ? ' set-invalid' : '')} inputMode="numeric" value={pretty} onChange={(e) => setCard(e.target.value)} placeholder="6221 0611 0395 3057" />
        {invalid && <span className="set-err">Card number must be 16 digits ({digits.length} entered)</span>}
      </div>
      <div className="set-field-block">
        <label>Card Holder</label>
        <input className="input-field" value={holder} onChange={(e) => setHolder(e.target.value)} placeholder="Name on card" />
      </div>
      <div className="set-card-preview">
        <div className="set-card-chip" />
        <div className="set-card-num">{pretty || '•••• •••• •••• ••••'}</div>
        <div className="set-card-holder">{holder || 'CARD HOLDER'}</div>
      </div>
      <SaveBar dirty={dirty} saving={saving} disabled={invalid} onSave={save} onReset={() => { const [c, h] = orig.split('|'); setCard(c || ''); setHolder(h || ''); }} />
    </div>
  );
}

/* ---- job schedules ------------------------------------------------------ */
// The GET payload is raw JOB_SCHEDULES: APScheduler interval kwargs
// (`minutes` / `seconds` / `hours`), NOT `interval_minutes` — the old reads
// left every input empty (audit finding). Display converts any unit to
// minutes; an edit rewrites the job with a single clean `minutes` key so the
// saved config stays valid add_job kwargs (untouched jobs keep their shape).
function jobEveryMinutes(s) {
  if (Number.isFinite(s?.minutes)) return s.minutes;
  if (Number.isFinite(s?.seconds)) return Math.round((s.seconds / 60) * 100) / 100;
  if (Number.isFinite(s?.hours)) return s.hours * 60;
  return '';
}

function JobsEditor({ onDirty }) {
  const modal = useModal();
  const toast = useToast();
  const [jobs, setJobs] = useState(null);
  const [orig, setOrig] = useState('{}');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    (async () => {
      const { data } = await apiJson('/api/admin/settings/job-schedules');
      if (data.ok) { setJobs(data.schedules || {}); setOrig(JSON.stringify(data.schedules || {})); }
      else setJobs({});
    })();
  }, []);

  const dirty = jobs !== null && JSON.stringify(jobs) !== orig;
  useEffect(() => { onDirty(dirty); }, [dirty, onDirty]);
  const setJob = (k, patch) => setJobs((j) => ({ ...j, [k]: { ...j[k], ...patch } }));
  const setJobMinutes = (k, v) => setJobs((j) => {
    const { minutes: _m, seconds: _s, hours: _h, ...rest } = j[k] || {};
    return { ...j, [k]: { ...rest, minutes: v } };
  });

  async function save() {
    setSaving(true);
    const { data } = await postJson('/api/admin/settings/job-schedules', { schedules: jobs });
    setSaving(false);
    if (data.ok) { toast('Schedules saved (restart to apply)', 'success'); setOrig(JSON.stringify(jobs)); }
    else await modal.alert('Error', 'Save failed.');
  }

  if (jobs === null) return <div className="set-loading">Loading…</div>;
  const entries = Object.entries(jobs);

  return (
    <div className="set-body">
      {entries.length === 0 && <div className="set-empty">No schedules configured.</div>}
      <div className="set-rows">
        {entries.map(([key, s]) => (
          <div className="set-job" key={key}>
            <div className="set-job-name">{key.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())}</div>
            <div className="set-job-ctl">
              <div className="set-field set-field-sm"><label>Every (min)</label><input className="input-field" type="number" min="0" step="any" value={jobEveryMinutes(s)} onChange={(e) => setJobMinutes(key, parseFloat(e.target.value) || 0)} /></div>
              <label className="set-toggle">
                <input type="checkbox" checked={s.enabled !== false} onChange={(e) => setJob(key, { enabled: e.target.checked })} />
                <span className="set-toggle-track"><span className="set-toggle-knob" /></span>
                <span className="set-toggle-label">{s.enabled !== false ? 'Active' : 'Off'}</span>
              </label>
            </div>
          </div>
        ))}
      </div>
      <div className="set-note">Changes to job intervals apply after the bot restarts.</div>
      <SaveBar dirty={dirty} saving={saving} onSave={save} onReset={() => setJobs(JSON.parse(orig))} />
    </div>
  );
}

/* ---- admin sessions ----------------------------------------------------- */
function SessionsEditor() {
  const modal = useModal();
  const toast = useToast();
  const [sessions, setSessions] = useState(null);

  const load = async () => { const { data } = await apiJson('/api/admin/sessions'); setSessions(data.ok ? (data.sessions || []) : []); };
  useEffect(() => { load(); }, []);

  const revoke = async (sid) => {
    const ok = await modal.confirm('Revoke session?', 'Logs that device out immediately.', { danger: true, okText: 'Revoke' });
    if (!ok) return;
    const { data } = await postJson('/api/admin/sessions/revoke', { session_id: sid });
    if (data.ok) { toast('Session revoked', 'success'); load(); } else await modal.alert('Error', 'Failed to revoke.');
  };
  const revokeOthers = async () => {
    const ok = await modal.confirm('Revoke other devices?', 'Keeps THIS device; logs out everything else.', { danger: true, okText: 'Revoke others' });
    if (!ok) return;
    const res = await apiFetch('/api/admin/sessions/revoke-others', { method: 'POST' });
    let data = {}; try { data = await res.json(); } catch (_) { data = {}; }
    if (data.ok) { toast(`Revoked ${Number(data.revoked || 0)}`, 'success'); load(); } else await modal.alert('Error', 'Failed.');
  };

  if (sessions === null) return <div className="set-loading">Loading…</div>;
  return (
    <div className="set-body">
      <div className="set-sessions-top">
        <span>{sessions.length} device{sessions.length === 1 ? '' : 's'}</span>
        <button className="btn btn-secondary" onClick={revokeOthers}>Revoke other devices</button>
      </div>
      {sessions.length === 0 && <div className="set-empty">No sessions</div>}
      {sessions.map((s) => {
        const tag = s.is_current ? 'CURRENT' : (s.revoked ? 'REVOKED' : 'ACTIVE');
        return (
          <div className="set-session" key={s.session_id}>
            <div className="set-session-main">
              <div className="set-session-top"><span className="set-session-ua">{s.user_agent || 'Unknown device'}</span><span className={'set-session-tag t-' + tag.toLowerCase()}>{tag}</span></div>
              <div className="set-session-meta">{s.ip || '—'} · seen {fmtDateTime(s.last_seen_at)}</div>
            </div>
            <button className="btn btn-secondary btn-danger" disabled={s.is_current || s.revoked} onClick={() => revoke(s.session_id)}>Revoke</button>
          </div>
        );
      })}
    </div>
  );
}

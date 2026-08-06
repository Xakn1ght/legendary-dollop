import React, { useEffect, useMemo, useState } from 'react';

import { apiJson } from '../api.js';
import { Icons } from '../icons.jsx';
import { fmtNum } from '../util.js';

const LEVEL_CHIPS = [
  { id: 'all', label: 'All' },
  { id: 'info', label: 'Info' },
  { id: 'warn', label: 'Warn' },
  { id: 'error', label: 'Error' },
];

// An entry is a raw string (current backend) or a legacy {timestamp, level,
// message} object — normalize both into one shape for filtering/rendering.
function normalizeEntry(l) {
  const text = (l && typeof l === 'object')
    ? [l.timestamp || '', l.level ? `[${l.level}]` : '', l.message || ''].filter(Boolean).join(' ')
    : String(l);
  let level = 'info';
  if (l && typeof l === 'object' && l.level) {
    const lv = String(l.level).toUpperCase();
    level = lv === 'ERROR' || lv === 'CRITICAL' ? 'error' : (lv.startsWith('WARN') ? 'warn' : 'info');
  } else if (/\b(ERROR|CRITICAL|Traceback)\b/.test(text)) {
    level = 'error';
  } else if (/\bWARN(ING)?\b/.test(text)) {
    level = 'warn';
  }
  return { text, level };
}

// Calm mono palette (audit leftover): default ink for the line, tint only the
// level tag — warning accent for WARN, danger for ERROR. No terminal green.
function LogLine({ entry }) {
  const { text, level } = entry;
  const tagColor = level === 'error' ? 'var(--danger)' : level === 'warn' ? 'var(--warning)' : null;
  const m = tagColor ? /\b(ERROR|CRITICAL|WARNING|WARN)\b/.exec(text) : null;
  return (
    <div style={{ marginBottom: 4, color: 'var(--text)', whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
      {m ? (
        <>
          {text.slice(0, m.index)}
          <span style={{ color: tagColor, fontWeight: 700 }}>{m[0]}</span>
          {text.slice(m.index + m[0].length)}
        </>
      ) : text}
    </div>
  );
}

// Logs + arcade cheat flags. Audit fix (JS#6): the backend /api/admin/logs
// returns raw strings, but the legacy code read l.timestamp/l.level/l.message →
// 100 blank rows. Render robustly whether an entry is a string or an object.
export function LogsPage() {
  const [logs, setLogs] = useState([]);
  const [flags, setFlags] = useState([]);
  const [loading, setLoading] = useState(true);
  const [q, setQ] = useState('');
  const [level, setLevel] = useState('all');

  const load = async () => {
    setLoading(true);
    try {
      const { data } = await apiJson('/api/admin/logs');
      if (data.ok) setLogs(Array.isArray(data.logs) ? data.logs : []);
    } catch (_) { /* ignore */ }
    try {
      const { data } = await apiJson('/api/admin/arcade/flags?limit=100');
      if (data.ok) setFlags(Array.isArray(data.flags) ? data.flags : []);
    } catch (_) { /* ignore */ } finally { setLoading(false); }
  };
  useEffect(() => { load(); }, []);

  const entries = useMemo(() => logs.map(normalizeEntry), [logs]);
  const view = useMemo(() => {
    const query = q.trim().toLowerCase();
    return entries.filter((e) => (level === 'all' || e.level === level)
      && (!query || e.text.toLowerCase().includes(query)));
  }, [entries, q, level]);

  return (
    <>
      <div className="glass-card" style={{ padding: 0 }}>
        <div className="table-header" style={{ padding: '16px 20px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <h3 style={{ margin: 0, fontSize: 16 }}>System Logs</h3>
          <button className="refresh-btn" onClick={load} title="Refresh" disabled={loading}>
            <Icons.refresh width={15} height={15} />
          </button>
        </div>
        <div style={{ padding: '0 20px 12px', display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
          <input
            className="input-field" placeholder="Search logs…" value={q}
            onChange={(e) => setQ(e.target.value)}
            style={{ flex: '1 1 180px', minWidth: 140 }}
          />
          <div style={{ display: 'flex', gap: 6 }}>
            {LEVEL_CHIPS.map((c) => (
              <button
                key={c.id} type="button"
                className={'chip-btn' + (level === c.id ? ' on' : '')}
                onClick={() => setLevel(c.id)}
              >{c.label}</button>
            ))}
          </div>
        </div>
        <div style={{ padding: '0 16px 16px', fontFamily: 'ui-monospace, Menlo, monospace', fontSize: 12, maxHeight: '48vh', overflow: 'auto' }}>
          {loading && <div style={{ color: 'var(--text-muted)' }}>Loading…</div>}
          {!loading && entries.length === 0 && <div style={{ color: 'var(--text-muted)' }}>No logs</div>}
          {!loading && entries.length > 0 && view.length === 0 && <div style={{ color: 'var(--text-muted)' }}>No lines match the current filter</div>}
          {view.map((e, i) => <LogLine key={i} entry={e} />)}
        </div>
      </div>

      <div className="glass-card" style={{ padding: 0, marginTop: 16 }}>
        <div className="table-header" style={{ padding: '16px 20px' }}>
          <h3 style={{ margin: 0, fontSize: 16 }}>Arcade Cheat Flags</h3>
        </div>
        <div className="table-responsive">
          <table>
            <thead><tr><th>Time</th><th>Player</th><th>Score</th><th>Claimed</th><th>Server</th><th>Reason</th><th>Flags</th></tr></thead>
            <tbody>
              {flags.length === 0 && <tr><td colSpan={7} style={{ textAlign: 'center', color: 'var(--text-muted)', padding: 16 }}>No flagged submissions. The scoreboard is clean.</td></tr>}
              {flags.map((f, i) => (
                <tr key={i}>
                  <td style={{ whiteSpace: 'nowrap' }}>{String(f.created_at || '').replace('T', ' ').slice(0, 16)}</td>
                  <td>{f.name}<br /><small style={{ color: 'var(--text-muted)' }}>{f.chat_id}</small></td>
                  <td style={{ fontWeight: 700 }}>{fmtNum(f.score)}</td>
                  <td>{f.claimed_duration}s</td>
                  <td>{f.server_elapsed == null ? '—' : f.server_elapsed + 's'}</td>
                  <td><span style={{ color: f.reason === 'no_token' ? 'var(--danger)' : 'var(--warning)', fontWeight: 600 }}>{f.reason}</span></td>
                  <td style={{ textAlign: 'center', fontWeight: 700, color: f.total_flags > 2 ? 'var(--danger)' : undefined }}>{f.total_flags}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}

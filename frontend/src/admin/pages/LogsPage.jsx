import React, { useEffect, useState } from 'react';

import { apiJson } from '../api.js';
import { fmtNum } from '../util.js';

// Logs + arcade cheat flags. Audit fix (JS#6): the backend /api/admin/logs
// returns raw strings, but the legacy code read l.timestamp/l.level/l.message →
// 100 blank rows. Render robustly whether an entry is a string or an object.
export function LogsPage() {
  const [logs, setLogs] = useState([]);
  const [flags, setFlags] = useState([]);
  const [loading, setLoading] = useState(true);

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

  function renderLog(l, i) {
    if (l && typeof l === 'object') {
      const level = l.level || 'INFO';
      return (
        <div key={i} style={{ marginBottom: 6 }}>
          <span style={{ color: 'var(--text-muted)' }}>{l.timestamp || ''} </span>
          <span style={{ color: level === 'ERROR' ? 'var(--danger)' : 'var(--success)', fontWeight: 700 }}>[{level}] </span>
          <span>{l.message || ''}</span>
        </div>
      );
    }
    const line = String(l);
    const isErr = /error|traceback|critical/i.test(line);
    return <div key={i} style={{ marginBottom: 4, color: isErr ? 'var(--danger)' : 'var(--text)' }}>{line}</div>;
  }

  return (
    <>
      <div className="glass-card" style={{ padding: 0 }}>
        <div className="table-header" style={{ padding: '16px 20px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <h3 style={{ margin: 0, fontSize: 16 }}>System Logs</h3>
          <button className="refresh-btn" onClick={load} title="Refresh" disabled={loading}>⟳</button>
        </div>
        <div style={{ padding: 16, fontFamily: 'ui-monospace, Menlo, monospace', fontSize: 12, maxHeight: '48vh', overflow: 'auto' }}>
          {loading && <div style={{ color: 'var(--text-muted)' }}>Loading…</div>}
          {!loading && logs.length === 0 && <div style={{ color: 'var(--text-muted)' }}>No logs</div>}
          {logs.map(renderLog)}
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

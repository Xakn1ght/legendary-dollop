import React, { useEffect, useMemo, useRef, useState } from 'react';

import { apiJson, postJson } from '../api.js';
import { useModal } from '../components/Modal.jsx';

function fmtCell(v) {
  if (v === null || v === undefined) return 'NULL';
  if (typeof v === 'object') { try { return JSON.stringify(v); } catch (_) { return String(v); } }
  return String(v);
}

export function DatabasePage() {
  const modal = useModal();
  const [caps, setCaps] = useState({ allow_write: false });
  const [dialect, setDialect] = useState('');
  const [tables, setTables] = useState([]);
  const [tableQuery, setTableQuery] = useState('');
  const [active, setActive] = useState(null);
  const [cols, setCols] = useState([]);
  const [rows, setRows] = useState([]);
  const [offset, setOffset] = useState(0);
  const [sql, setSql] = useState('');
  const [queryCols, setQueryCols] = useState([]);
  const [queryRows, setQueryRows] = useState([]);
  const [queryMsg, setQueryMsg] = useState('Run a query.');
  const limit = 50;
  const offsetRef = useRef(0);

  async function reload() {
    try {
      const caps = await apiJson('/api/admin/db/capabilities');
      if (caps.data.ok) setCaps(caps.data.capabilities || {});
      const t = await apiJson('/api/admin/db/tables');
      if (t.data.ok) { setDialect(t.data.dialect || ''); setTables(t.data.tables || []); }
    } catch (_) { /* ignore */ }
  }
  useEffect(() => { reload(); }, []);

  const shownTables = useMemo(() => {
    const q = tableQuery.trim().toLowerCase();
    return tables.filter((t) => !q || t.toLowerCase().includes(q));
  }, [tables, tableQuery]);

  async function loadRows(name, off) {
    const { data } = await apiJson(`/api/admin/db/table/${encodeURIComponent(name)}/rows?limit=${limit}&offset=${off}`);
    if (data.ok) { setCols(data.columns || []); setRows(data.rows || []); }
    else { setCols([]); setRows([]); }
  }
  async function selectTable(name) {
    setActive(name); setOffset(0); offsetRef.current = 0;
    try {
      const s = await apiJson(`/api/admin/db/table/${encodeURIComponent(name)}/schema`);
      if (!s.data.ok) throw new Error('schema');
      await loadRows(name, 0);
    } catch (_) { await modal.alert('Database', 'Failed to load table.'); }
  }
  function pageBy(delta) {
    const next = Math.max(0, offsetRef.current + delta * limit);
    offsetRef.current = next; setOffset(next);
    if (active) loadRows(active, next);
  }

  async function runQuery(isExec) {
    const q = sql.trim();
    if (!q) { await modal.alert('SQL', 'Please enter a SQL query.'); return; }
    if (isExec) {
      const ok = await modal.confirm('Dangerous SQL', 'This can modify or delete data. Continue only if you know exactly what you are doing.', { danger: true, okText: 'Execute', sub: 'ADMIN_DB_DANGEROUS_SQL must be enabled' });
      if (!ok) return;
    }
    setQueryMsg('Running…');
    try {
      const path = isExec ? '/api/admin/db/exec' : '/api/admin/db/query';
      const init = { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ sql: q }) };
      if (isExec) init.headers['X-Admin-Dangerous'] = 'YES';
      const { data } = await apiJson(path, init);
      if (!data.ok) throw new Error((data.error || 'request_failed') + (data.detail ? ': ' + data.detail : ''));
      if (isExec) {
        setQueryMsg('Done.');
        await modal.alert('SQL', `Executed successfully. Rowcount: ${data.rowcount ?? '—'}`);
        if (active) loadRows(active, offsetRef.current);
        return;
      }
      setQueryCols(data.columns || []);
      setQueryRows(data.rows || []);
      setQueryMsg(data.truncated ? 'Result truncated.' : '');
    } catch (e) {
      setQueryMsg('Failed.');
      await modal.alert('SQL', 'Query failed.', String(e.message || e));
    }
  }

  return (
    <>
      <div className="glass-card" style={{ marginBottom: 16, padding: 16 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
          <div>
            <h3 style={{ margin: 0, fontSize: 16 }}>Database Explorer</h3>
            <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 6 }}>Read-only by default. {caps.allow_write ? <b style={{ color: 'var(--danger)' }}>Danger mode enabled</b> : 'Writes disabled.'} {dialect && `· ${dialect}`}</div>
          </div>
          <button className="btn btn-secondary" onClick={reload}>Refresh</button>
        </div>
      </div>

      <div className="page-two-col aside-left">
        <div className="glass-card" style={{ padding: 14 }}>
          <input className="input-field" placeholder="Search tables…" value={tableQuery} onChange={(e) => setTableQuery(e.target.value)} style={{ marginBottom: 12 }} />
          <div style={{ maxHeight: '60vh', overflow: 'auto', fontSize: 13 }}>
            {shownTables.map((t) => (
              <div key={t} className={'db-table-item' + (active === t ? ' active' : '')} onClick={() => selectTable(t)}
                style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8, padding: '8px 10px', borderRadius: 8, cursor: 'pointer' }}>
                <span style={{ fontWeight: 700, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{t}</span>
                <span className="db-pill">{(dialect || 'db').toLowerCase().startsWith('post') ? 'pg' : dialect || 'db'}</span>
              </div>
            ))}
            {shownTables.length === 0 && <div style={{ color: 'var(--text-muted)', padding: 10 }}>No tables found.</div>}
          </div>
        </div>

        <div>
          <div className="glass-card" style={{ padding: 14, marginBottom: 16 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
              <div><div style={{ fontWeight: 700 }}>Table</div><div style={{ color: 'var(--text-muted)', fontSize: 12 }}>{active || '—'}</div></div>
              <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
                <button className="btn btn-secondary" onClick={() => pageBy(-1)} disabled={offset === 0}>← Prev</button>
                <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>{rows.length ? `${offset + 1}–${offset + rows.length}` : '0–0'}</div>
                <button className="btn btn-secondary" onClick={() => pageBy(1)} disabled={rows.length < limit}>Next →</button>
              </div>
            </div>
            <div className="table-responsive" style={{ marginTop: 12, overflow: 'auto' }}>
              <table>
                <thead><tr>{cols.length ? cols.map((c) => <th key={c}>{c}</th>) : <th>—</th>}</tr></thead>
                <tbody>
                  {rows.length === 0 && <tr><td colSpan={Math.max(1, cols.length)} style={{ color: 'var(--text-muted)', padding: 18 }}>{active ? 'No rows.' : 'Select a table.'}</td></tr>}
                  {rows.map((r, ri) => (
                    <tr key={ri}>{cols.map((_, ci) => { const v = Array.isArray(r) ? r[ci] : null; const s = fmtCell(v); return <td key={ci} style={v == null ? { color: 'var(--text-muted)', fontStyle: 'italic' } : undefined}>{s.length > 400 ? s.slice(0, 400) + '…' : s}</td>; })}</tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <div className="glass-card" style={{ padding: 14 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
              <div style={{ fontWeight: 700 }}>SQL Runner</div>
              <div style={{ display: 'flex', gap: 10 }}>
                <button className="btn btn-primary" onClick={() => runQuery(false)}>Run (read-only)</button>
                {caps.allow_write && <button className="btn btn-danger" onClick={() => runQuery(true)}>Execute (danger)</button>}
              </div>
            </div>
            <textarea className="input-field" value={sql} onChange={(e) => setSql(e.target.value)} placeholder="SELECT * FROM users LIMIT 50" style={{ width: '100%', minHeight: 120, marginTop: 10, fontFamily: 'ui-monospace, Menlo, monospace', fontSize: 12 }} />
            <div style={{ marginTop: 8, fontSize: 12, color: 'var(--text-muted)' }}>{queryMsg}</div>
            <div className="table-responsive" style={{ marginTop: 12, overflow: 'auto' }}>
              <table>
                <thead><tr>{queryCols.length ? queryCols.map((c) => <th key={c}>{c}</th>) : <th>—</th>}</tr></thead>
                <tbody>
                  {queryRows.length === 0 && <tr><td colSpan={Math.max(1, queryCols.length)} style={{ color: 'var(--text-muted)', padding: 18 }}>Run a query.</td></tr>}
                  {queryRows.map((r, ri) => (
                    <tr key={ri}>{queryCols.map((_, ci) => { const v = Array.isArray(r) ? r[ci] : null; const s = fmtCell(v); return <td key={ci} style={v == null ? { color: 'var(--text-muted)', fontStyle: 'italic' } : undefined}>{s.length > 400 ? s.slice(0, 400) + '…' : s}</td>; })}</tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}

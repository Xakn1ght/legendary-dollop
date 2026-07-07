import React, { useEffect, useRef, useState } from 'react';

import { apiJson } from '../api.js';

// PasarGuard realtime stats refresh every few seconds on the panel; 10s here
// keeps the page feeling live without hammering it. Paused while hidden.
const REFRESH_MS = 10000;

const STATUS_COLOR = {
  connected: 'var(--success)',
  healthy: 'var(--success)',
  connecting: 'var(--warning)',
  limited: 'var(--warning)',
  error: 'var(--danger)',
  disabled: 'var(--muted, #6b7684)',
};

function fmtSpeed(bps) {
  const n = Number(bps) || 0;
  if (n >= 1024 * 1024) return (n / 1024 / 1024).toFixed(1) + ' MB/s';
  if (n >= 1024) return (n / 1024).toFixed(0) + ' KB/s';
  return n + ' B/s';
}

function fmtUptime(sec) {
  const s = Number(sec) || 0;
  if (s >= 86400) return Math.floor(s / 86400) + 'd ' + Math.floor((s % 86400) / 3600) + 'h';
  if (s >= 3600) return Math.floor(s / 3600) + 'h ' + Math.floor((s % 3600) / 60) + 'm';
  return Math.floor(s / 60) + 'm';
}

export function ServersPage() {
  const [nodes, setNodes] = useState(null);
  const [system, setSystem] = useState(null);
  const timerRef = useRef(null);

  const load = async () => {
    try {
      const { data } = await apiJson('/api/admin/nodes');
      if (data.ok) { setNodes(data.nodes || []); setSystem(data.system || null); }
    } catch (_) { /* keep last snapshot */ }
  };

  useEffect(() => {
    load();
    timerRef.current = setInterval(() => { if (!document.hidden) load(); }, REFRESH_MS);
    return () => clearInterval(timerRef.current);
  }, []);

  const list = nodes || [];
  const live = list.filter((n) => n.up);
  const downSpeed = live.reduce((s, n) => s + (Number(n.down_speed) || 0), 0);
  const upSpeed = live.reduce((s, n) => s + (Number(n.up_speed) || 0), 0);

  return (
    <>
      <div className="stats-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 16 }}>
        <div className="glass-card stat-card" style={{ padding: 20 }}>
          <div className="stat-label">Nodes</div>
          <div className="stat-value">{list.length}</div>
          <div className="stat-change positive">{live.length} connected</div>
        </div>
        <div className="glass-card stat-card" style={{ padding: 20 }}>
          <div className="stat-label">Live Throughput</div>
          <div className="stat-value" style={{ fontSize: 22 }}>↓ {fmtSpeed(downSpeed)}</div>
          <div className="stat-change">↑ {fmtSpeed(upSpeed)}</div>
        </div>
        <div className="glass-card stat-card" style={{ padding: 20 }}>
          <div className="stat-label">Panel Users</div>
          <div className="stat-value">{system?.total_user ?? '—'}</div>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: 20, marginTop: 20 }}>
        {nodes === null && <div style={{ gridColumn: '1/-1', textAlign: 'center', color: 'var(--text-muted)', padding: 40 }}>Loading…</div>}
        {nodes !== null && list.length === 0 && <div style={{ gridColumn: '1/-1', textAlign: 'center', color: 'var(--text-muted)', padding: 40 }}>No nodes</div>}
        {list.map((n) => {
          const color = STATUS_COLOR[n.status] || 'var(--muted, #6b7684)';
          const memPct = n.mem_total ? Math.round((n.mem_used / n.mem_total) * 100) : null;
          const cpuPct = n.cpu_usage != null ? Math.round(n.cpu_usage) : null;
          return (
            <div className="glass-card" key={n.id} style={{ padding: 22, position: 'relative', overflow: 'hidden' }}>
              <div style={{ position: 'absolute', top: 0, left: 0, width: 4, height: '100%', background: color }} />
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start', marginBottom: 12 }}>
                <div>
                  <h3 style={{ margin: 0, fontSize: 16 }}>{n.name}</h3>
                  <div style={{ fontSize: 11.5, color: 'var(--text-muted)', fontVariantNumeric: 'tabular-nums' }}>
                    {n.address}{n.port ? ':' + n.port : ''}{n.xray_version ? ' · xray ' + n.xray_version : ''}
                  </div>
                </div>
                <span style={{
                  fontSize: 10, fontWeight: 700, letterSpacing: '0.06em', textTransform: 'uppercase',
                  color, padding: '3px 9px', borderRadius: 999,
                  background: 'color-mix(in srgb, ' + color + ' 14%, transparent)',
                  border: '1px solid color-mix(in srgb, ' + color + ' 32%, transparent)',
                }}>{n.status}</span>
              </div>

              {n.up && (
                <>
                  <div style={{ display: 'flex', gap: 18, marginBottom: 10, fontVariantNumeric: 'tabular-nums' }}>
                    <div><div style={{ fontSize: 10.5, color: 'var(--text-muted)' }}>DOWN</div><div style={{ fontWeight: 600 }}>{fmtSpeed(n.down_speed)}</div></div>
                    <div><div style={{ fontSize: 10.5, color: 'var(--text-muted)' }}>UP</div><div style={{ fontWeight: 600 }}>{fmtSpeed(n.up_speed)}</div></div>
                    {n.uptime != null && <div><div style={{ fontSize: 10.5, color: 'var(--text-muted)' }}>UPTIME</div><div style={{ fontWeight: 600 }}>{fmtUptime(n.uptime)}</div></div>}
                  </div>
                  {(cpuPct != null || memPct != null) && (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                      {cpuPct != null && (
                        <div title={'CPU ' + cpuPct + '%'}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10.5, color: 'var(--text-muted)' }}><span>CPU</span><span>{cpuPct}%</span></div>
                          <div style={{ height: 5, borderRadius: 4, background: 'rgba(255,255,255,0.08)' }}>
                            <div style={{ width: Math.min(cpuPct, 100) + '%', height: '100%', borderRadius: 4, background: cpuPct > 85 ? 'var(--danger)' : cpuPct > 60 ? 'var(--warning)' : 'var(--success)' }} />
                          </div>
                        </div>
                      )}
                      {memPct != null && (
                        <div title={'RAM ' + memPct + '%'}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10.5, color: 'var(--text-muted)' }}><span>RAM</span><span>{memPct}%</span></div>
                          <div style={{ height: 5, borderRadius: 4, background: 'rgba(255,255,255,0.08)' }}>
                            <div style={{ width: Math.min(memPct, 100) + '%', height: '100%', borderRadius: 4, background: memPct > 85 ? 'var(--danger)' : memPct > 60 ? 'var(--warning)' : 'var(--success)' }} />
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </>
              )}
              {!n.up && n.message && (
                <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>{String(n.message).slice(0, 120)}</div>
              )}
            </div>
          );
        })}
      </div>
    </>
  );
}

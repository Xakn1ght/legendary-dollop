import React, { useEffect, useRef, useState } from 'react';

import { apiJson, postJson } from '../api.js';
import { useModal } from '../components/Modal.jsx';
import { useToast } from '../components/Toast.jsx';
import { Icons } from '../icons.jsx';
import { timeAgo } from '../util.js';

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

// Lifetime totals reach TB scale (probed: 10+ TB downlink on busy nodes).
function fmtTotal(bytes) {
  const b = Number(bytes) || 0;
  if (b >= 1024 ** 4) return (b / 1024 ** 4).toFixed(2) + ' TB';
  if (b >= 1024 ** 3) return (b / 1024 ** 3).toFixed(1) + ' GB';
  if (b >= 1024 ** 2) return (b / 1024 ** 2).toFixed(0) + ' MB';
  return b + ' B';
}

function fmtUptime(sec) {
  const s = Number(sec) || 0;
  if (s >= 86400) return Math.floor(s / 86400) + 'd ' + Math.floor((s % 86400) / 3600) + 'h';
  if (s >= 3600) return Math.floor(s / 3600) + 'h ' + Math.floor((s % 3600) / 60) + 'm';
  return Math.floor(s / 60) + 'm';
}

// Public node IPs stay masked (first octet + last octet) unless the admin
// reveals them per card — display-only, screenshots/shoulder-surfing guard.
function maskAddr(addr) {
  const s = String(addr || '');
  const m = s.match(/^(\d{1,3})\.\d{1,3}\.\d{1,3}\.(\d{1,3})$/);
  return m ? `${m[1]}.\u2022.\u2022.${m[2]}` : s;
}

export function ServersPage() {
  const modal = useModal();
  const toast = useToast();
  const [nodes, setNodes] = useState(null);
  const [system, setSystem] = useState(null);
  const [revealed, setRevealed] = useState({}); // node id -> true
  const [reconnecting, setReconnecting] = useState({}); // node id -> true
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

  // Panel-side reconnect (audited server-side as node.reconnect). Danger
  // confirm names the node — this pokes live infrastructure.
  async function reconnect(n) {
    const ok = await modal.confirm(
      `Reconnect "${n.name}"?`,
      `The panel will drop and re-establish its connection to node "${n.name}". Users on this node may blip for a few seconds.`,
      { danger: true, okText: 'Reconnect' },
    );
    if (!ok) return;
    setReconnecting((m) => ({ ...m, [n.id]: true }));
    try {
      const { data } = await postJson(`/api/admin/nodes/${encodeURIComponent(n.id)}/reconnect`, {});
      if (data.ok) toast(`Reconnect requested for ${data.name || n.name}`, 'success');
      else toast(data.error === 'node_not_found' ? 'Node no longer exists on the panel' : 'Reconnect failed', 'error');
    } catch (_) { toast('Reconnect failed', 'error'); }
    setReconnecting((m) => ({ ...m, [n.id]: false }));
    setTimeout(load, 1500); // give the panel a beat before re-reading status
  }

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
          {system?.online_users != null && <div className="stat-change positive">{system.online_users} online now</div>}
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: 20, marginTop: 20 }}>
        {nodes === null && <div style={{ gridColumn: '1/-1', textAlign: 'center', color: 'var(--text-muted)', padding: 40 }}>Loading…</div>}
        {nodes !== null && list.length === 0 && <div style={{ gridColumn: '1/-1', textAlign: 'center', color: 'var(--text-muted)', padding: 40 }}>No nodes</div>}
        {list.map((n) => {
          const color = STATUS_COLOR[n.status] || 'var(--muted, #6b7684)';
          const memPct = n.mem_total ? Math.round((n.mem_used / n.mem_total) * 100) : null;
          const cpuPct = n.cpu_usage != null ? Math.round(n.cpu_usage) : null;
          const masked = maskAddr(n.address);
          const maskable = masked !== String(n.address || '');
          const shown = revealed[n.id] ? n.address : masked;
          const EyeIcon = revealed[n.id] ? Icons.eyeOff : Icons.eye;
          const versions = [
            n.xray_version || n.core_version ? 'xray ' + (n.xray_version || n.core_version) : null,
            n.node_version ? 'node ' + n.node_version : null,
          ].filter(Boolean).join(' · ');
          const hasLifetime = (Number(n.lifetime_uplink) || 0) + (Number(n.lifetime_downlink) || 0) > 0;
          return (
            <div className="glass-card" key={n.id} style={{ padding: 22, position: 'relative', overflow: 'hidden' }}>
              <div style={{ position: 'absolute', top: 0, left: 0, width: 4, height: '100%', background: color }} />
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start', marginBottom: 12 }}>
                <div>
                  <h3 style={{ margin: 0, fontSize: 16 }}>{n.name}</h3>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 11.5, color: 'var(--text-muted)', fontVariantNumeric: 'tabular-nums' }}>
                    <span>{shown}{n.port ? ':' + n.port : ''}</span>
                    {maskable && (
                      <button
                        type="button"
                        className="srv-reveal"
                        title={revealed[n.id] ? 'Hide address' : 'Reveal address'}
                        aria-label={revealed[n.id] ? 'Hide address' : 'Reveal address'}
                        onClick={() => setRevealed((m) => ({ ...m, [n.id]: !m[n.id] }))}
                      >
                        <EyeIcon width={13} height={13} />
                      </button>
                    )}
                  </div>
                  {versions && <div style={{ fontSize: 11, color: 'var(--text-muted)', fontVariantNumeric: 'tabular-nums' }}>{versions}</div>}
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

              {!n.up && (
                <div style={{ fontSize: 12, color: 'var(--text-muted)', display: 'grid', gap: 3 }}>
                  <span>{n.last_seen ? 'Last seen online ' + timeAgo(n.last_seen * 1000) : 'Not seen online since tracking began'}</span>
                  {n.message && <span>{String(n.message).slice(0, 120)}</span>}
                </div>
              )}

              {hasLifetime && (
                <div style={{ display: 'flex', gap: 18, marginTop: 10, fontVariantNumeric: 'tabular-nums' }}>
                  <div><div style={{ fontSize: 10.5, color: 'var(--text-muted)' }}>LIFETIME DOWN</div><div style={{ fontWeight: 600 }}>{fmtTotal(n.lifetime_downlink)}</div></div>
                  <div><div style={{ fontSize: 10.5, color: 'var(--text-muted)' }}>LIFETIME UP</div><div style={{ fontWeight: 600 }}>{fmtTotal(n.lifetime_uplink)}</div></div>
                </div>
              )}

              {n.status !== 'disabled' && (
                <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 12 }}>
                  <button
                    type="button"
                    className="btn btn-secondary btn-danger"
                    style={{ fontSize: 12, padding: '5px 12px' }}
                    disabled={!!reconnecting[n.id]}
                    onClick={() => reconnect(n)}
                    title="Panel-side reconnect; users on this node may blip"
                  >
                    {reconnecting[n.id] ? 'Reconnecting…' : 'Reconnect'}
                  </button>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </>
  );
}

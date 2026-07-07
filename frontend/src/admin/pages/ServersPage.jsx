import React, { useEffect, useState } from 'react';

import { apiJson } from '../api.js';

export function ServersPage() {
  const [servers, setServers] = useState([]);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    try {
      const { data } = await apiJson('/api/admin/servers');
      if (data.ok) setServers(data.servers || []);
    } catch (_) { /* ignore */ } finally { setLoading(false); }
  };
  useEffect(() => { load(); }, []);

  const online = servers.filter((s) => s.active).length;
  const totalTraffic = servers.reduce((sum, s) => sum + (parseFloat(s.traffic_gb) || 0), 0);
  const totalUsers = servers.reduce((sum, s) => sum + (Number(s.users) || 0), 0);

  return (
    <>
      <div className="stats-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 16 }}>
        <div className="glass-card stat-card" style={{ padding: 20 }}><div className="stat-label">Total Servers</div><div className="stat-value">{servers.length}</div><div className="stat-change positive">{online} Online</div></div>
        <div className="glass-card stat-card" style={{ padding: 20 }}><div className="stat-label">Total Traffic</div><div className="stat-value">{totalTraffic.toFixed(1)} GB</div></div>
        <div className="glass-card stat-card" style={{ padding: 20 }}><div className="stat-label">Active Users</div><div className="stat-value">{totalUsers}</div></div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: 20, marginTop: 20 }}>
        {loading && <div style={{ gridColumn: '1/-1', textAlign: 'center', color: 'var(--text-muted)', padding: 40 }}>Loading…</div>}
        {!loading && servers.length === 0 && <div style={{ gridColumn: '1/-1', textAlign: 'center', color: 'var(--text-muted)', padding: 40 }}>No servers</div>}
        {servers.map((s, i) => (
          <div className="glass-card fx-tilt" key={i} style={{ padding: 24, position: 'relative', overflow: 'hidden' }}>
            <div style={{ position: 'absolute', top: 0, left: 0, width: 4, height: '100%', background: s.active ? 'var(--success)' : 'var(--danger)' }} />
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start', marginBottom: 16 }}>
              <div>
                <h3 style={{ margin: 0, fontSize: 16 }}>{s.name}</h3>
                <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>{s.location || 'Unknown'}</div>
              </div>
              <div style={{ width: 10, height: 10, borderRadius: '50%', background: s.active ? 'var(--success)' : 'var(--danger)', boxShadow: `0 0 10px ${s.active ? 'var(--success)' : 'var(--danger)'}` }} />
            </div>
            <div style={{ display: 'flex', gap: 20 }}>
              <div><div style={{ fontSize: 11, color: 'var(--text-muted)' }}>USERS</div><div style={{ fontWeight: 600 }}>{s.users || 0}</div></div>
              <div><div style={{ fontSize: 11, color: 'var(--text-muted)' }}>TRAFFIC</div><div style={{ fontWeight: 600 }}>{s.traffic_gb ? parseFloat(s.traffic_gb).toFixed(1) : 0} GB</div></div>
            </div>
          </div>
        ))}
      </div>
    </>
  );
}

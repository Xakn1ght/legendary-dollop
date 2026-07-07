import { useCallback, useEffect, useRef, useState } from 'react';

import { apiJson } from './api.js';

// Live receipts: WebSocket-first with polling fallback, ported from
// index-main.js startAdminEventsWs + loadReceipts. Owns the pending list so
// the sidebar badge and the receipts page share one source of truth.
// Fixes over legacy: single visibilitychange listener, capped reconnect backoff.
export function useReceipts() {
  const [receipts, setReceipts] = useState([]);
  const [loading, setLoading] = useState(false);
  const wsRef = useRef(null);
  const pollRef = useRef(null);
  const connectedRef = useRef(false);
  const reconnectRef = useRef(0);
  const activePageRef = useRef('');

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await apiJson('/api/admin/receipts/pending');
      if (data.ok && Array.isArray(data.receipts)) setReceipts(data.receipts);
    } catch (_) { /* ignore */ } finally {
      setLoading(false);
    }
  }, []);

  const stopPolling = useCallback(() => {
    if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
  }, []);

  const startPolling = useCallback(() => {
    if (pollRef.current || connectedRef.current) return;
    // skip fetches while the mini app is backgrounded (battery)
    pollRef.current = setInterval(() => { if (!document.hidden) load(); }, 5000);
  }, [load]);

  const connect = useCallback(() => {
    if (wsRef.current) return;
    let ws;
    try {
      const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      ws = new WebSocket(`${proto}//${window.location.host}/api/admin/ws/support`);
    } catch (_) {
      startPolling();
      return;
    }
    wsRef.current = ws;
    let pingTimer = null;
    let pongDeadline = null;
    const stopPing = () => { clearInterval(pingTimer); clearTimeout(pongDeadline); pingTimer = pongDeadline = null; };

    ws.onopen = () => {
      connectedRef.current = true;
      reconnectRef.current = 0;
      stopPolling();
      stopPing();
      pingTimer = setInterval(() => {
        try {
          ws.send(JSON.stringify({ action: 'ping' }));
          clearTimeout(pongDeadline);
          pongDeadline = setTimeout(() => { try { ws.close(); } catch (_) { /* ignore */ } }, 10000);
        } catch (_) { try { ws.close(); } catch (__) { /* ignore */ } }
      }, 20000);
    };
    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data || '{}');
        if (msg.type === 'pong') { clearTimeout(pongDeadline); pongDeadline = null; return; }
        if (msg.type === 'receipts_updated') load();
        // Support events (new ticket / new user message): let the shell bump
        // its support badge live instead of waiting out the 30s poll.
        if (msg.type === 'tickets_updated' || msg.type === 'new_message') {
          try { window.dispatchEvent(new CustomEvent('admin-support-activity', { detail: msg })); } catch (_) { /* ignore */ }
        }
      } catch (_) { /* ignore */ }
    };
    ws.onclose = () => {
      stopPing();
      wsRef.current = null;
      connectedRef.current = false;
      startPolling();
      // capped backoff (legacy hammered every 2s forever)
      const n = Math.min(reconnectRef.current++, 5);
      setTimeout(connect, 2000 * (n + 1));
    };
    ws.onerror = () => {};
  }, [load, startPolling, stopPolling]);

  useEffect(() => {
    connect();
    load();
    const onVis = () => { if (!document.hidden && !connectedRef.current) load(); };
    document.addEventListener('visibilitychange', onVis);
    return () => {
      document.removeEventListener('visibilitychange', onVis);
      stopPolling();
      try { wsRef.current && wsRef.current.close(); } catch (_) { /* ignore */ }
      wsRef.current = null;
    };
  }, [connect, load, stopPolling]);

  const setActivePage = useCallback((p) => { activePageRef.current = p; }, []);
  return { receipts, loading, reload: load, setActivePage };
}

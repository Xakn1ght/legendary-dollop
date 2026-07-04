// Support realtime transport: WebSocket first, polling fallback.
// - /api/dashboard/ws/support with init_data or auth query param
// - on WS down: tickets list poll every 5s, open-ticket messages poll every 3s
// - max 3 reconnect attempts, 5s apart, then polling only (legacy parity)

import { getAuthToken } from '../shared/auth.js';
import { getWebApp } from '../shared/telegram.js';

const WS_MAX_RECONNECT = 3;

export function createSupportRealtime({ onEvent, pollTickets, pollMessages }) {
  let ws = null;
  let wsConnected = false;
  let reconnectAttempts = 0;
  let reconnectTimer = null;
  let ticketsInterval = null;
  let messagesInterval = null;
  let watchedTicketId = null;
  let destroyed = false;

  function startTicketsPolling() {
    if (ticketsInterval || destroyed) return;
    try { pollTickets(); } catch (_) { /* ignore */ }
    ticketsInterval = setInterval(() => {
      if (!wsConnected) pollTickets();
    }, 5000);
  }

  function stopTicketsPolling() {
    if (!ticketsInterval) return;
    clearInterval(ticketsInterval);
    ticketsInterval = null;
  }

  function startMessagePolling() {
    if (wsConnected || destroyed) return;
    if (messagesInterval) clearInterval(messagesInterval);
    messagesInterval = setInterval(() => {
      if (watchedTicketId != null) pollMessages(watchedTicketId);
    }, 3000);
  }

  function stopMessagePolling() {
    if (messagesInterval) clearInterval(messagesInterval);
    messagesInterval = null;
  }

  function onVisibility() {
    if (!document.hidden && !wsConnected) pollTickets();
  }
  document.addEventListener('visibilitychange', onVisibility);

  function connect() {
    if (destroyed) return;
    if (ws && ws.readyState === WebSocket.OPEN) return;
    if (reconnectAttempts >= WS_MAX_RECONNECT) {
      startTicketsPolling();
      return;
    }
    const tg = getWebApp();
    const initData = (tg?.initData && tg.initData.length > 10) ? tg.initData : '';
    const authToken = getAuthToken();
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const qp = new URLSearchParams();
    if (initData) qp.set('init_data', initData);
    else if (authToken) qp.set('auth', authToken);
    const wsUrl = `${protocol}//${window.location.host}/api/dashboard/ws/support${qp.toString() ? ('?' + qp.toString()) : ''}`;

    try {
      ws = new WebSocket(wsUrl);

      ws.onopen = () => {
        wsConnected = true;
        reconnectAttempts = 0;
        stopTicketsPolling();
        if (watchedTicketId != null) {
          ws.send(JSON.stringify({ action: 'watch_ticket', ticket_id: watchedTicketId }));
          stopMessagePolling();
        }
      };

      ws.onmessage = (event) => {
        try { onEvent(JSON.parse(event.data)); } catch (_) { /* ignore malformed */ }
      };

      ws.onclose = () => {
        wsConnected = false;
        ws = null;
        if (destroyed) return;
        startTicketsPolling();
        if (watchedTicketId != null) startMessagePolling();
        reconnectAttempts++;
        if (reconnectAttempts < WS_MAX_RECONNECT) {
          reconnectTimer = setTimeout(connect, 5000);
        }
      };

      ws.onerror = () => {
        wsConnected = false;
        startTicketsPolling();
      };
    } catch (_e) {
      wsConnected = false;
      startTicketsPolling();
    }
  }

  return {
    connect,
    get connected() { return wsConnected; },
    watchTicket(ticketId) {
      watchedTicketId = ticketId;
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ action: 'watch_ticket', ticket_id: ticketId }));
        stopMessagePolling();
      } else {
        startMessagePolling();
      }
    },
    unwatchTicket() {
      watchedTicketId = null;
      stopMessagePolling();
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ action: 'unwatch_ticket' }));
      }
    },
    destroy() {
      destroyed = true;
      document.removeEventListener('visibilitychange', onVisibility);
      stopTicketsPolling();
      stopMessagePolling();
      if (reconnectTimer) clearTimeout(reconnectTimer);
      try { ws?.close(); } catch (_) { /* ignore */ }
      ws = null;
    },
  };
}

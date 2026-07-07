// Admin support realtime: WebSocket-first with polling fallback + capped
// backoff, ported from support-main.js connectWebSocket. Cookie auth rides the
// upgrade request; no query token needed on the admin side.
export function createAdminSupportRealtime({ onEvent, pollTickets, pollMessages }) {
  let ws = null;
  let connected = false;
  let attempts = 0;
  let watching = null;
  let msgPoll = null;
  let ticketPoll = null;
  let destroyed = false;
  const MAX = 5;

  function startPolling() {
    // guards skip fetches while the mini app is backgrounded (battery)
    if (!ticketPoll) ticketPoll = setInterval(() => { if (!document.hidden && pollTickets) pollTickets(); }, 8000);
    if (watching && !msgPoll) msgPoll = setInterval(() => { if (!document.hidden && pollMessages) pollMessages(watching); }, 4000);
  }
  function stopMsgPoll() { if (msgPoll) { clearInterval(msgPoll); msgPoll = null; } }

  function connect() {
    if (destroyed || (ws && ws.readyState === WebSocket.OPEN)) return;
    if (attempts >= MAX) { startPolling(); return; }
    let sock;
    try {
      const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      sock = new WebSocket(`${proto}//${window.location.host}/api/admin/ws/support`);
    } catch (_) { startPolling(); return; }
    ws = sock;
    let ping = null;
    let pong = null;
    const stopPing = () => { clearInterval(ping); clearTimeout(pong); ping = pong = null; };

    sock.onopen = () => {
      connected = true; attempts = 0;
      if (ticketPoll) { clearInterval(ticketPoll); ticketPoll = null; }
      stopMsgPoll();
      if (watching) sock.send(JSON.stringify({ action: 'watch_ticket', ticket_id: watching }));
      stopPing();
      ping = setInterval(() => {
        try {
          sock.send(JSON.stringify({ action: 'ping' }));
          clearTimeout(pong);
          pong = setTimeout(() => { try { sock.close(); } catch (_) { /* ignore */ } }, 10000);
        } catch (_) { try { sock.close(); } catch (__) { /* ignore */ } }
      }, 20000);
    };
    sock.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data || '{}');
        if (data.type === 'pong') { clearTimeout(pong); pong = null; return; }
        onEvent && onEvent(data);
      } catch (_) { /* ignore */ }
    };
    sock.onclose = () => {
      stopPing();
      ws = null; connected = false;
      if (destroyed) return;
      startPolling();
      attempts += 1;
      setTimeout(connect, 2000 * Math.min(attempts, MAX));
    };
    sock.onerror = () => {};
  }

  return {
    connect,
    watchTicket(id) {
      watching = id;
      if (connected && ws) { try { ws.send(JSON.stringify({ action: 'watch_ticket', ticket_id: id })); } catch (_) { /* ignore */ } }
      else if (!msgPoll) msgPoll = setInterval(() => { if (!document.hidden && pollMessages) pollMessages(watching); }, 4000);
    },
    // typing contract (see handoff): client emits {type:'typing', ticket_id};
    // server relays {type:'typing', from:'user'|'admin'} to the other side.
    sendTyping(id) {
      if (connected && ws) { try { ws.send(JSON.stringify({ type: 'typing', ticket_id: id })); } catch (_) { /* ignore */ } }
    },
    unwatchTicket() { watching = null; stopMsgPoll(); },
    destroy() {
      destroyed = true;
      stopMsgPoll();
      if (ticketPoll) clearInterval(ticketPoll);
      try { ws && ws.close(); } catch (_) { /* ignore */ }
    },
  };
}

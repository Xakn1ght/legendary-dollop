"""Broadcast generic admin dashboard events over WebSockets."""

import time

from ..state import CONNECTION_TIMEOUT, admin_connections, connection_health


async def broadcast_admin_event(event_type: str, payload: dict | None = None):
    """
    Broadcast a lightweight admin event to all admin WebSocket connections.
    Used for "live" UI updates outside tickets (e.g. receipts).
    """
    message = {
        "type": event_type,
        "data": payload or {},
    }
    current_time = time.time()
    dead_connections = []
    for ws in list(admin_connections):
        try:
            if ws.closed:
                dead_connections.append(ws)
                continue
            last_activity = connection_health.get(ws, 0)
            if current_time - last_activity > CONNECTION_TIMEOUT:
                dead_connections.append(ws)
                continue
            await ws.send_json(message)
            connection_health[ws] = current_time
        except Exception:
            dead_connections.append(ws)
    for dead_ws in dead_connections:
        admin_connections.discard(dead_ws)
        connection_health.pop(dead_ws, None)

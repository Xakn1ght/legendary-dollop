"""Notify a user's support WebSocket that their ticket list should refresh."""

import time

from ..state import (
    CONNECTION_TIMEOUT,
    connection_health,
    user_connection_map,
    user_connections,
)


async def broadcast_user_ticket_list_update(user_chat_id: int):
    """
    Broadcast to the given user's support WS connection(s) that their ticket list changed.
    Used when a user creates a new ticket from another device/session.
    """
    try:
        uid = int(user_chat_id)
    except Exception:
        return

    message = {"type": "tickets_updated"}
    current_time = time.time()
    dead_connections = []

    for ws in list(user_connections):
        try:
            if ws.closed:
                dead_connections.append(ws)
                continue
            ws_user_id = user_connection_map.get(ws)
            if int(ws_user_id or 0) != uid:
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
        user_connections.discard(dead_ws)
        user_connection_map.pop(dead_ws, None)
        connection_health.pop(dead_ws, None)

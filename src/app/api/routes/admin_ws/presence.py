"""Helpers to introspect live dashboard/support WebSocket state."""

import time

from .state import (
    CONNECTION_TIMEOUT,
    active_connections,
    connection_health,
    user_connection_map,
    user_connections,
)


def is_user_watching_ticket(user_chat_id: int, ticket_id: int) -> bool:
    """
    Return True if the given user (chat_id) currently has an active WebSocket
    watching the given ticket (i.e., support chat is open on that ticket).
    """
    try:
        tid = int(ticket_id)
        uid = int(user_chat_id)
    except Exception:
        return False

    watchers = active_connections.get(tid)
    if not watchers:
        return False

    for ws in list(watchers):
        try:
            if ws.closed:
                continue
            if int(user_connection_map.get(ws) or 0) == uid:
                return True
        except Exception:
            continue
    return False


def is_user_connected_to_support(user_chat_id: int) -> bool:
    """
    Return True if the given user (chat_id) currently has an active WebSocket
    connection to the dashboard support WS (support page is open).
    """
    try:
        uid = int(user_chat_id)
    except Exception:
        return False

    current_time = time.time()
    for ws in list(user_connections):
        try:
            if ws.closed:
                continue
            if int(user_connection_map.get(ws) or 0) != uid:
                continue
            # Respect health timeout so stale connections don't suppress Telegram.
            last_activity = connection_health.get(ws, 0)
            if current_time - last_activity > CONNECTION_TIMEOUT:
                continue
            return True
        except Exception:
            continue
    return False


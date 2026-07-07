"""Relay live "typing" hints between the two sides of a support ticket.

Fire-and-forget: no DB writes, no delivery guarantees. A user typing in the
dashboard chat is relayed only to admin sockets watching that ticket, and
vice versa. Rate-limited to one relay per 2s per (ticket, side) so keystroke
storms never amplify into socket spam.
"""

import time
from typing import Dict, Tuple
from weakref import WeakSet

from ..state import active_connections, admin_connections, logger

TYPING_RELAY_MIN_INTERVAL = 2.0  # seconds per (ticket, side)

# (ticket_id, "user"|"admin") -> monotonic time of last relay
_typing_last_relay: Dict[Tuple[int, str], float] = {}


async def broadcast_typing(ticket_id: int, from_side: str):
    """Relay a typing hint for ``ticket_id`` to the opposite side's watchers."""
    try:
        tid = int(ticket_id)
    except (TypeError, ValueError):
        return
    if from_side not in ("user", "admin"):
        return

    now = time.monotonic()
    key = (tid, from_side)
    if now - _typing_last_relay.get(key, 0.0) < TYPING_RELAY_MIN_INTERVAL:
        return
    _typing_last_relay[key] = now
    # Bounded memory: this dict only ever holds tickets typed in since restart;
    # prune anything stale once it grows past a sane size.
    if len(_typing_last_relay) > 2048:
        cutoff = now - 60.0
        for k in [k for k, v in _typing_last_relay.items() if v < cutoff]:
            _typing_last_relay.pop(k, None)

    watchers = active_connections.get(tid, WeakSet())
    message = {"type": "typing", "ticket_id": tid, "from": from_side}
    deliver_to_admin = from_side == "user"

    for ws in list(watchers):
        try:
            if ws.closed:
                continue
            # active_connections mixes both sides; admin sockets are the ones
            # registered in admin_connections, everything else is a user socket.
            is_admin_ws = ws in admin_connections
            if is_admin_ws != deliver_to_admin:
                continue
            await ws.send_json(message)
        except Exception as e:
            logger.debug(f"typing relay send failed (ignored): {e}")

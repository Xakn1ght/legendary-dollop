"""Shared WebSocket connection registries and health timeout."""

import logging
from typing import Dict
from weakref import WeakSet

from aiohttp import web

logger = logging.getLogger(__name__)

# Store active WebSocket connections
# Key: ticket_id, Value: set of WebSocket connections watching that ticket
# Both admin AND user connections are stored here
active_connections: Dict[int, WeakSet] = {}

# Store all admin connections (for ticket list updates)
admin_connections: WeakSet = WeakSet()

# Store user connections (for their own ticket updates)
user_connections: WeakSet = WeakSet()

# Map WebSocket connections to user_id: {ws: user_id}
# This allows us to send updates only to the ticket owner
user_connection_map: Dict[web.WebSocketResponse, int] = {}

# Connection health tracking: {ws: last_ping_time}
connection_health: Dict[web.WebSocketResponse, float] = {}

# Maximum time without ping before considering connection dead (seconds)
CONNECTION_TIMEOUT = 120  # 2 minutes

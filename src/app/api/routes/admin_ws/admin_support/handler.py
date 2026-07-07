"""Admin support WebSocket endpoint."""

import asyncio
import json
import time
from weakref import WeakSet

from aiohttp import WSMsgType, web

from ..broadcasts.typing import broadcast_typing
from ..state import active_connections, admin_connections, connection_health, logger


async def handle_admin_support_ws(request: web.Request):
    """
    WebSocket endpoint for admin support real-time updates.

    Usage from frontend:
    ws = new WebSocket('ws://host/api/admin/ws/support')
    ws.send(JSON.stringify({action: 'watch_ticket', ticket_id: 123}))
    ws.send(JSON.stringify({action: 'unwatch_ticket', ticket_id: 123}))

    Authentication: Uses HttpOnly admin_session cookie (automatically sent with WS upgrade)
    """

    # Reject cross-site WS upgrades before doing anything else. The admin session
    # cookie is SameSite=None (needed for the Telegram embed), so a page an admin
    # visits could otherwise open this socket with their ambient cookie and stream
    # live support events (CSWSH). Browsers always send Origin on WS; a mismatched
    # Origin is refused. A missing Origin (native/non-browser client) still has to
    # pass token auth below, so it carries no ambient-cookie risk.
    origin = request.headers.get("Origin", "")
    if origin:
        try:
            from urllib.parse import urlparse

            from app.core.settings import is_admin_host_allowed

            oh = urlparse(origin).hostname or ""
            tg_ok = oh.endswith(".telegram.org") or oh in ("telegram.org", "web.telegram.org")
            if not (tg_ok or is_admin_host_allowed(oh)):
                raise web.HTTPForbidden(text="bad origin")
        except web.HTTPException:
            raise
        except Exception:
            raise web.HTTPForbidden(text="bad origin")

    ws = web.WebSocketResponse(heartbeat=30)
    await ws.prepare(request)

    token = request.cookies.get("admin_session", "") or request.query.get("token", "")

    if not token:
        await ws.close(code=4001, message=b"No token provided")
        return ws
    try:
        from app.api.routes.admin_auth import verify_admin_token

        sess = verify_admin_token(token)
    except Exception:
        sess = None
    if not sess:
        await ws.close(code=4003, message=b"Unauthorized")
        return ws

    admin_connections.add(ws)
    connection_health[ws] = time.time()

    watched_ticket_id = None

    try:
        await ws.send_json(
            {
                "type": "connected",
                "message": "WebSocket connected",
            }
        )

        async for msg in ws:
            connection_health[ws] = time.time()

            if msg.type == WSMsgType.TEXT:
                try:
                    data = json.loads(msg.data)
                    action = data.get("action") or data.get("type")

                    if action == "typing":
                        # Fire-and-forget typing hint -> user sockets watching
                        # this ticket (relayed only for the watched ticket).
                        try:
                            ticket_id = int(data.get("ticket_id"))
                        except (TypeError, ValueError):
                            ticket_id = None
                        if ticket_id and watched_ticket_id and ticket_id == int(watched_ticket_id):
                            try:
                                await broadcast_typing(watched_ticket_id, "admin")
                            except Exception:
                                pass

                    elif action == "watch_ticket":
                        ticket_id = data.get("ticket_id")
                        if ticket_id:
                            if watched_ticket_id and watched_ticket_id in active_connections:
                                active_connections[watched_ticket_id].discard(ws)

                            if ticket_id not in active_connections:
                                active_connections[ticket_id] = WeakSet()
                            active_connections[ticket_id].add(ws)
                            watched_ticket_id = ticket_id

                            await ws.send_json(
                                {
                                    "type": "watching",
                                    "ticket_id": ticket_id,
                                }
                            )

                    elif action == "unwatch_ticket":
                        if watched_ticket_id and watched_ticket_id in active_connections:
                            active_connections[watched_ticket_id].discard(ws)
                        watched_ticket_id = None

                        await ws.send_json(
                            {
                                "type": "unwatched",
                            }
                        )

                    elif action == "ping":
                        connection_health[ws] = time.time()
                        await ws.send_json({"type": "pong"})

                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON received from WebSocket: {msg.data}")

            elif msg.type == WSMsgType.ERROR:
                error = ws.exception()
                logger.error(f"WebSocket error for admin connection: {error}")
                break

            elif msg.type == WSMsgType.CLOSE:
                logger.info("WebSocket closed by client")
                break

    except asyncio.CancelledError:
        logger.info("WebSocket connection cancelled")
        raise
    except Exception as e:
        logger.error(f"WebSocket handler error: {e}", exc_info=True)

    finally:
        admin_connections.discard(ws)
        connection_health.pop(ws, None)
        if watched_ticket_id and watched_ticket_id in active_connections:
            active_connections[watched_ticket_id].discard(ws)
        logger.debug("Admin WebSocket connection cleaned up")

    return ws

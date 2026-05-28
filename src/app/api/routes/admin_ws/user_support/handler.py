"""User (dashboard) support WebSocket endpoint."""

import asyncio
import json
import time
from weakref import WeakSet

from aiohttp import WSMsgType, web

from ..state import active_connections, connection_health, logger, user_connection_map, user_connections


async def handle_user_support_ws(request: web.Request):
    """
    WebSocket endpoint for user support real-time updates.
    Users can watch their own tickets for admin replies.

    Usage from frontend:
    ws = new WebSocket('ws://host/api/dashboard/ws/support?auth=xxx')
    ws.send(JSON.stringify({action: 'watch_ticket', ticket_id: 123}))
    """

    ws = web.WebSocketResponse(heartbeat=30)
    await ws.prepare(request)

    from app.api.deps import _verify_webapp_auth

    user_id, _ = _verify_webapp_auth(request)

    if not user_id:
        logger.warning(
            "WebSocket connection rejected: No authentication. query_auth=%s cookies=%s",
            bool(request.query.get("auth", "")),
            list(request.cookies.keys()),
        )
        try:
            await ws.close(code=4001, message=b"Authentication required")
        except Exception:
            pass
        return ws

    logger.debug(f"User WebSocket connected: user_id={user_id}")

    user_connections.add(ws)
    user_connection_map[ws] = user_id
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
                    action = data.get("action")

                    if action == "watch_ticket":
                        ticket_id = data.get("ticket_id")
                        if ticket_id:
                            try:
                                from app.database.models import AsyncSessionLocal, Ticket

                                async with AsyncSessionLocal() as session:
                                    ticket = await session.get(Ticket, int(ticket_id))
                                    if not ticket or int(ticket.user_id) != int(user_id):
                                        logger.warning(
                                            "WS watch denied: user_id=%s ticket_id=%s",
                                            user_id,
                                            ticket_id,
                                        )
                                        await ws.send_json(
                                            {
                                                "type": "error",
                                                "message": "unauthorized_ticket",
                                            }
                                        )
                                        continue
                            except Exception:
                                logger.warning(
                                    "WS watch check failed: user_id=%s ticket_id=%s",
                                    user_id,
                                    ticket_id,
                                )
                                await ws.send_json(
                                    {
                                        "type": "error",
                                        "message": "ticket_check_failed",
                                    }
                                )
                                continue
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
                        await ws.send_json({"type": "unwatched"})

                    elif action == "ping":
                        connection_health[ws] = time.time()
                        await ws.send_json({"type": "pong"})

                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON received from user WebSocket: {msg.data}")

            elif msg.type == WSMsgType.ERROR:
                error = ws.exception()
                logger.error(f"WebSocket error for user connection: {error}")
                break

            elif msg.type == WSMsgType.CLOSE:
                logger.info("User WebSocket closed by client")
                break

    except asyncio.CancelledError:
        logger.info("User WebSocket connection cancelled")
        raise
    except Exception as e:
        logger.error(f"User WebSocket error: {e}", exc_info=True)

    finally:
        user_connections.discard(ws)
        user_connection_map.pop(ws, None)
        connection_health.pop(ws, None)
        if watched_ticket_id and watched_ticket_id in active_connections:
            active_connections[watched_ticket_id].discard(ws)
        logger.debug("User WebSocket connection cleaned up")

    return ws

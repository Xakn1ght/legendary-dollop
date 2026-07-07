"""Admin view: the ticket owner's Telegram profile photo (for the chat header
and message avatars). Sits behind the /api/admin auth middleware; reuses the
dashboard's disk cache so Telegram is hit at most once a day per user."""

import logging

from aiohttp import web

from app.api.routes.dashboard.profile_photo import get_cached_profile_photo
from app.database.models import AsyncSessionLocal, Ticket, User
from app.utils.admin_bot_helper import resolve_user_bot

logger = logging.getLogger(__name__)


async def handle_admin_ticket_user_photo(request: web.Request):
    try:
        ticket_id = int(request.match_info["ticket_id"])
    except (ValueError, KeyError):
        return web.json_response({"ok": False, "error": "invalid_ticket_id"}, status=400)

    async with AsyncSessionLocal() as session:
        ticket = await session.get(Ticket, ticket_id)
        if not ticket:
            return web.json_response({"ok": False, "error": "ticket_not_found"}, status=404)
        user = await session.get(User, ticket.user_id)
        if not user:
            return web.json_response({"ok": False, "error": "user_not_found"}, status=404)
        chat_id = user.chat_id

    try:
        bot = resolve_user_bot(request.app.get("bot"))
        if not bot:
            return web.json_response({"ok": False, "error": "unavailable"}, status=404)
        data = await get_cached_profile_photo(bot, int(chat_id))
        if not data:
            return web.json_response({"ok": False, "error": "no_photo"}, status=404)
        return web.Response(
            body=data,
            content_type="image/jpeg",
            headers={"Cache-Control": "private, max-age=3600"},
        )
    except Exception as e:
        logger.warning("admin ticket user-photo fetch failed for ticket %s: %s", ticket_id, e)
        return web.json_response({"ok": False, "error": "fetch_failed"}, status=404)

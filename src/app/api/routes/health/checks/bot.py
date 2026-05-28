"""Telegram user-bot probe."""

from typing import Any, Dict

from aiohttp import web

from app.utils.admin_bot_helper import resolve_user_bot


async def check_bot_health(request: web.Request) -> Dict[str, Any]:
    """Check if bot is running and polling."""
    try:
        bot = resolve_user_bot(request.app.get("bot"))

        if bot is None:
            return {
                "status": "unavailable",
                "error": "Bot instance not found",
            }

        bot_info = await bot.get_me()

        return {
            "status": "running",
            "bot_username": bot_info.username,
            "bot_id": bot_info.id,
        }

    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
        }

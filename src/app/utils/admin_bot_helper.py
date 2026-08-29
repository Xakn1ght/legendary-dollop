"""
Helper functions to get admin bot instance for sending messages to admin.
This ensures receipts and admin notifications go to the admin bot, not user bot.

Telegram does not allow the admin bot to *forward* from a private user chat unless it is
a member of that chat; for typical user-bot DMs we fall back to downloading the photo with
the user bot and re-uploading with the admin bot.
"""
from __future__ import annotations

from io import BytesIO
from typing import TYPE_CHECKING

from aiogram import Bot
from aiogram.types import BufferedInputFile

from app.core.settings import ADMIN_BOT_TOKEN, ADMIN_ID, BOT_TOKEN
from app.utils.bot_session import bot_session

if TYPE_CHECKING:
    from aiogram.types import Message

_admin_bot_instance: Bot | None = None
_user_bot_instance: Bot | None = None


def get_admin_bot() -> Bot | None:
    """Get or create admin bot instance."""
    global _admin_bot_instance
    if not ADMIN_BOT_TOKEN:
        return None
    if _admin_bot_instance is None:
        _admin_bot_instance = Bot(token=ADMIN_BOT_TOKEN, session=bot_session())
    return _admin_bot_instance


def get_user_bot() -> Bot | None:
    """Bot instance for Telegram actions toward **users** (DM), e.g. when a handler runs on the admin bot."""
    global _user_bot_instance
    if not BOT_TOKEN:
        return None
    if _user_bot_instance is None:
        _user_bot_instance = Bot(token=BOT_TOKEN, session=bot_session())
    return _user_bot_instance


def resolve_user_bot(app_bot: Bot | None) -> Bot | None:
    """Prefer the aiohttp-embedded user bot; otherwise a lazily-created client using ``BOT_TOKEN``."""
    return app_bot or get_user_bot()


async def relay_user_receipt_photo_to_admin(
    user_bot: Bot,
    admin_bot: Bot,
    admin_chat_id: int,
    message: Message,
    caption: str | None = None,
    reply_markup=None,
):
    """Deliver a user-sent receipt photo to the admin Telegram chat.

    With ``caption``/``reply_markup`` the photo, order details and action buttons
    arrive as ONE message (a plain forward can't carry custom buttons, so that
    path is only used when neither is requested). Falls back to
    download-via-user-bot + ``send_photo`` via admin bot.
    """
    if not message.photo:
        return None

    if caption is None and reply_markup is None:
        try:
            return await admin_bot.forward_message(
                chat_id=admin_chat_id,
                from_chat_id=message.chat.id,
                message_id=message.message_id,
            )
        except Exception:
            pass

    try:
        buf = BytesIO()
        await user_bot.download(message.photo[-1], destination=buf)
        buf.seek(0)
        raw = buf.getvalue()
        cap = caption if caption is not None else (message.caption or None)
        return await admin_bot.send_photo(
            admin_chat_id,
            photo=BufferedInputFile(raw, filename="receipt.jpg"),
            caption=cap,
            reply_markup=reply_markup,
        )
    except Exception:
        return None


async def send_to_admin_bot(method_name: str, *args, **kwargs):
    """Helper to send messages to admin bot."""
    admin_bot = get_admin_bot()
    if not admin_bot:
        return None
    method = getattr(admin_bot, method_name)
    return await method(chat_id=ADMIN_ID, *args, **kwargs)

async def close_admin_bot():
    """Close admin bot session (call on shutdown)."""
    global _admin_bot_instance
    if _admin_bot_instance:
        await _admin_bot_instance.session.close()
        _admin_bot_instance = None


async def close_user_bot():
    """Close lazily-created user bot session (call on shutdown)."""
    global _user_bot_instance
    if _user_bot_instance:
        await _user_bot_instance.session.close()
        _user_bot_instance = None


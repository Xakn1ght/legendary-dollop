"""Ingest forwarded bank-deposit SMS from the configured channel.

The user bot must be a member/admin of ``SMS_SOURCE_CHAT_ID``. Registering the
channel_post handler also makes aiogram include ``channel_post`` in the polled
update types. Handlers are scoped to that one chat, so nothing else is affected;
if the channel isn't configured, this router has no handlers and is inert.
"""
from aiogram import Bot, F, Router
from aiogram.types import Message

from app.services import sms_ingest

router = Router()

_CHAT_ID = None
try:
    if sms_ingest.SMS_SOURCE_CHAT_ID:
        _CHAT_ID = int(sms_ingest.SMS_SOURCE_CHAT_ID)
except (TypeError, ValueError):
    _CHAT_ID = None


if _CHAT_ID is not None:

    @router.channel_post(F.chat.id == _CHAT_ID)
    async def _sms_channel_post(message: Message, bot: Bot):
        text = message.text or message.caption or ''
        if text:
            await sms_ingest.handle_incoming_sms(bot, text)

    @router.message(F.chat.id == _CHAT_ID)
    async def _sms_group_message(message: Message, bot: Bot):
        text = message.text or message.caption or ''
        if text:
            await sms_ingest.handle_incoming_sms(bot, text)

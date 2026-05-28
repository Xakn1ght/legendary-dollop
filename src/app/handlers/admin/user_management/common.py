from aiogram import Bot, Router
from aiogram.filters import BaseFilter
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message

from app.core.chat_sessions import user_to_admin
from app.utils.bot_i18n import get_cached_lang, guess_lang_from_telegram

router = Router()


def _lang_for_tg_user(tg_user) -> str:
    return get_cached_lang(tg_user.id) or guess_lang_from_telegram(
        getattr(tg_user, "language_code", None)
    )


class UserManagementStates(StatesGroup):
    waiting_search_term = State()
    waiting_user_edit = State()
    waiting_credit_amount = State()
    waiting_broadcast_message = State()
    waiting_traffic_amount = State()
    waiting_referrer_id = State()  # For adding referral manually


class IsUserInAdminChat(BaseFilter):
    async def __call__(self, message: Message, bot: Bot) -> bool:
        if message.from_user.id in user_to_admin:
            if message.text and message.text == "/endchat":
                return True
            if message.voice or message.photo or (
                message.text and not message.text.startswith("/")
            ):
                return True
            await bot.send_message(
                message.from_user.id,
                "❌ نوع پیام پشتیبانی نمی‌شود. لطفاً متن، صدا یا عکس ارسال کنید.",
            )
            return False
        return False

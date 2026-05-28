from aiogram import F
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import crud
from app.utils.bot_i18n import (
    get_cached_lang,
    guess_lang_from_telegram,
    normalize_lang,
    set_cached_lang,
    t,
    text_matches,
)

from .common import router


@router.callback_query(lambda c: c.data and c.data.startswith("delete_") and len(c.data.split("_")) == 2)
async def delete_subscription(callback: CallbackQuery, session: AsyncSession):
    """Deletion via bot is disabled."""
    lang = get_cached_lang(callback.from_user.id)
    await callback.answer(t(lang, "deletion_disabled"), show_alert=True)


async def _show_services_list(target, session: AsyncSession):
    """Render the services list for a Message or a CallbackQuery target."""
    user_id = target.from_user.id if hasattr(target, "from_user") else target.chat.id
    user = await crud.get_user(session, user_id)
    if not user:
        lang = get_cached_lang(user_id) or guess_lang_from_telegram(getattr(target.from_user, "language_code", None))
        if isinstance(target, CallbackQuery):
            await target.answer(t(lang, "start_bot_first"), show_alert=True)
        else:
            await target.answer(t(lang, "start_bot_first"))
        return
    lang = normalize_lang(getattr(user, "language", None))
    set_cached_lang(user.chat_id, lang)

    subs = await crud.get_user_subscriptions(session, user.id)

    if not subs:
        text = (
            "شما هیچ سرویس فعالی ندارید. برای خرید سرویس، دکمه <b>💳 خرید سرویس</b> را از منوی اصلی انتخاب کنید."
            if lang == "fa"
            else "You have no active services. To buy one, tap <b>Buy Service 💳</b> in the main menu."
        )
        if isinstance(target, CallbackQuery):
            await target.message.edit_text(text, parse_mode="HTML")
            await target.answer()
        else:
            await target.answer(text, parse_mode="HTML")
        return

    kb = InlineKeyboardBuilder()
    for s in subs:
        if s.status == 'pending':
            label = f"⌛️ {s.marzban_username or ('در انتظار تایید' if lang == 'fa' else 'Pending approval')}"
            kb.button(text=label, callback_data=f"pending_{s.id}")
        elif s.status == 'active':
            kb.button(text=s.marzban_username, callback_data=f"svc_{s.id}")
        else:
            kb.button(text=f"🚫 {s.marzban_username}", callback_data=f"svc_{s.id}")

    kb.adjust(1)
    text = "لطفاً یکی از سرویس های زیر را برای مشاهده جزئیات انتخاب کنید:" if lang == "fa" else "Select a service to view details:"
    if isinstance(target, CallbackQuery):
        try:
            await target.message.edit_text(text, reply_markup=kb.as_markup())
        except TelegramBadRequest:
            await target.message.answer(text, reply_markup=kb.as_markup())
        await target.answer()
    else:
        await target.answer(text, reply_markup=kb.as_markup())


@router.message(text_matches("btn_my_services"))
async def my_services_handler(message: Message, session: AsyncSession):
    """Present list of user subscriptions as inline buttons (message entry)."""
    await _show_services_list(message, session)


@router.callback_query(F.data == "my_services_list")
async def my_services_list_cb(callback: CallbackQuery, session: AsyncSession):
    """Show the services list from an inline callback (e.g., back from pending)."""
    await _show_services_list(callback, session)

from aiogram import F
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from app.utils.bot_i18n import get_cached_lang, t

from .common import router


@router.callback_query(F.data.startswith("support_for_sub_"))
async def support_for_subscription(callback: CallbackQuery, state: FSMContext):
    """Start support flow pre-selecting this subscription."""
    lang = get_cached_lang(callback.from_user.id)
    try:
        sub_id = int(callback.data.removeprefix("support_for_sub_"))
    except Exception:
        await callback.answer()
        return
    await state.update_data(subscription_id=sub_id)
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    from app.core.settings import SUPPORT_CATEGORIES
    kb = InlineKeyboardBuilder()
    # SUPPORT_CATEGORIES is {callback_key: label} — the keys are the working
    # support_quick_* callbacks. The old dict-style access crashed with
    # TypeError, leaving the «گزارش مشکل» button dead (caught by
    # tests/test_my_services_buttons.py, 2026-07-13).
    for cat_key, label in SUPPORT_CATEGORIES.items():
        kb.button(text=label, callback_data=cat_key)
    kb.adjust(2)
    kb.button(text=t(lang, "btn_back"), callback_data="support_back_main")
    # Try to update the existing card (may be a media message). Fallback to sending a new message.
    support_text = t(lang, "support_choose_category")
    try:
        await callback.message.edit_caption(
            caption=support_text,
            reply_markup=kb.as_markup()
        )
    except (TelegramBadRequest, AttributeError):
        try:
            await callback.message.edit_text(
                support_text,
                reply_markup=kb.as_markup()
            )
        except TelegramBadRequest:
            await callback.message.answer(
                support_text,
                reply_markup=kb.as_markup()
            )
    await callback.answer()

import logging

from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import crud
from app.handlers.admin.common import ADMIN_IDS, _send_pending_requests
from app.services.marzban import marzban_api
from app.utils.bot_i18n import get_cached_lang, guess_lang_from_telegram, t

router = Router()

# --------------------------
#  Show toggle request
# --------------------------

@router.callback_query(F.data.startswith("show_toggle_"))
async def show_toggle_request(callback: CallbackQuery, session: AsyncSession):
    lang = get_cached_lang(callback.from_user.id) or guess_lang_from_telegram(getattr(callback.from_user, "language_code", None))
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer(t(lang, "not_authorized"), show_alert=True)
        return

    sub_id = int(callback.data.split("_")[2])
    from app.database.models import Subscription

    sub: Subscription | None = await session.get(Subscription, sub_id)
    if not sub:
        await callback.answer(t(lang, "admin_toggle_sub_not_found"), show_alert=True)
        return

    await session.refresh(sub, attribute_names=["user"])

    kb = InlineKeyboardBuilder()
    if sub.status == 'pending_disable':
        kb.button(text='✅ تایید غیرفعال', callback_data=f'approve_disable_{sub_id}_{sub.user.chat_id}_0')
        kb.button(text='❌ رد', callback_data=f'deny_disable_{sub_id}_{sub.user.chat_id}_0')
    elif sub.status == 'pending_enable':
        kb.button(text='✅ تایید فعال', callback_data=f'approve_enable_{sub_id}_{sub.user.chat_id}_0')
        kb.button(text='❌ رد', callback_data=f'deny_enable_{sub_id}_{sub.user.chat_id}_0')
    kb.button(text=('💬 Chat' if lang == 'en' else '💬 چت'), callback_data=f'chat_sub_{sub_id}_{sub.user.chat_id}')
    kb.adjust(2)

    await callback.message.edit_text(
        t(lang, "admin_toggle_request_details").format(
            username=sub.marzban_username,
            id=sub_id,
            user=(sub.user.full_name if sub.user else sub.user_id),
            action=t(lang, "admin_toggle_action_disable") if sub.status == 'pending_disable' else t(lang, "admin_toggle_action_enable"),
        ),
        reply_markup=kb.as_markup()
    )
    await callback.answer()

# --------------------------
#  Disable / Enable actions
# --------------------------

@router.callback_query(F.data.startswith("approve_disable_"))
async def approve_disable(callback: CallbackQuery, session: AsyncSession, bot: Bot):
    lang = get_cached_lang(callback.from_user.id) or guess_lang_from_telegram(getattr(callback.from_user, "language_code", None))
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer(t(lang, "not_authorized"), show_alert=True)
        return

    parts = callback.data.split("_")
    sub_id = int(parts[2])
    user_chat_id = int(parts[3]) if len(parts) > 3 else None
    user_msg_id = int(parts[4]) if len(parts) > 4 else None

    from app.database.models import Subscription
    sub: Subscription | None = await session.get(Subscription, sub_id)
    if not sub:
        await callback.answer(t(lang, "admin_toggle_sub_not_found"), show_alert=True)
        return

    await session.refresh(sub, attribute_names=["user"])

    if sub.status == 'disabled':
        await callback.answer(t(lang, "admin_toggle_already_disabled"))
        return

    if sub.status not in ('pending_disable', 'active'):
        await callback.answer(t(lang, "admin_toggle_invalid_disable"), show_alert=True)
        return

    success = await marzban_api.toggle_user_status(sub.marzban_username, 'disabled')
    if not success:
        await callback.answer(t(lang, "admin_toggle_marzban_failed"), show_alert=True)
        return

    sub.status = 'disabled'
    await session.commit()

    await bot.send_message(sub.user.chat_id, "⛔ سرویس شما توسط ادمین غیرفعال شد.")

    if user_chat_id and user_msg_id:
        try:
            user_info = await marzban_api.get_user_info(sub.marzban_username)
            if user_info:
                from app.handlers.user.my_services import build_subscription_detail
                text, kb = build_subscription_detail(sub, user_info)
                await bot.edit_message_text(text=text, chat_id=user_chat_id, message_id=user_msg_id, parse_mode="HTML", reply_markup=kb.as_markup())
        except Exception as e:
            logging.error(f"Failed to edit old detail message after disable: {e}")

    await callback.answer(t(lang, "admin_toggle_disabled"))
    await _send_pending_requests(bot, session, callback.from_user.id, callback.message.message_id)


@router.callback_query(F.data.startswith("deny_disable_"))
async def deny_disable(callback: CallbackQuery, session: AsyncSession, bot: Bot):
    lang = get_cached_lang(callback.from_user.id) or guess_lang_from_telegram(getattr(callback.from_user, "language_code", None))
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer(t(lang, "not_authorized"), show_alert=True)
        return

    sub_id = int(callback.data.split("_")[2])
    from app.database.models import Subscription
    sub: Subscription | None = await session.get(Subscription, sub_id)
    if not sub:
        await callback.answer(t(lang, "admin_toggle_sub_not_found"), show_alert=True)
        return

    await session.refresh(sub, attribute_names=["user"])

    await bot.send_message(sub.user.chat_id, "درخواست شما برای غیرفعال‌سازی سرویس توسط ادمین رد شد.")
    sub.status = 'active'
    await session.commit()

    await callback.answer(t(lang, "admin_toggle_request_denied"))
    await _send_pending_requests(bot, session, callback.from_user.id, callback.message.message_id)


@router.callback_query(F.data.startswith("approve_enable_"))
async def approve_enable(callback: CallbackQuery, session: AsyncSession, bot: Bot):
    lang = get_cached_lang(callback.from_user.id) or guess_lang_from_telegram(getattr(callback.from_user, "language_code", None))
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer(t(lang, "not_authorized"), show_alert=True)
        return

    parts = callback.data.split("_")
    sub_id = int(parts[2])
    user_chat_id = int(parts[3]) if len(parts) > 3 else None
    user_msg_id = int(parts[4]) if len(parts) > 4 else None

    from app.database.models import Subscription
    sub: Subscription | None = await session.get(Subscription, sub_id)
    if not sub:
        await callback.answer(t(lang, "admin_toggle_sub_not_found"), show_alert=True)
        return

    await session.refresh(sub, attribute_names=["user"])

    if sub.status == 'active':
        await callback.answer(t(lang, "admin_toggle_already_active"))
        return

    if sub.status not in ('pending_enable', 'disabled'):
        await callback.answer(t(lang, "admin_toggle_invalid_enable"), show_alert=True)
        return

    if not await marzban_api.toggle_user_status(sub.marzban_username, 'active'):
        await callback.answer(t(lang, "admin_toggle_marzban_failed"), show_alert=True)
        return

    sub.status = 'active'
    await session.commit()

    await bot.send_message(sub.user.chat_id, "✅ سرویس شما دوباره فعال شد.")

    if user_chat_id and user_msg_id:
        try:
            user_info = await marzban_api.get_user_info(sub.marzban_username)
            if user_info:
                from app.handlers.user.my_services import build_subscription_detail
                text, kb = build_subscription_detail(sub, user_info)
                await bot.edit_message_text(text=text, chat_id=user_chat_id, message_id=user_msg_id, parse_mode="HTML", reply_markup=kb.as_markup())
        except Exception as e:
            logging.error(f"Failed to edit old detail message after enable: {e}")

    await callback.answer(t(lang, "admin_toggle_enabled"))
    await _send_pending_requests(bot, session, callback.from_user.id, callback.message.message_id)


@router.callback_query(F.data.startswith("deny_enable_"))
async def deny_enable(callback: CallbackQuery, session: AsyncSession, bot: Bot):
    lang = get_cached_lang(callback.from_user.id) or guess_lang_from_telegram(getattr(callback.from_user, "language_code", None))
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer(t(lang, "not_authorized"), show_alert=True)
        return

    sub_id = int(callback.data.split("_")[2])
    from app.database.models import Subscription
    sub: Subscription | None = await session.get(Subscription, sub_id)
    if not sub:
        await callback.answer(t(lang, "admin_toggle_sub_not_found"), show_alert=True)
        return

    await session.refresh(sub, attribute_names=["user"])

    await bot.send_message(sub.user.chat_id, "درخواست شما برای فعال‌سازی سرویس توسط ادمین رد شد.")
    sub.status = 'disabled'
    await session.commit()

    await callback.answer(t(lang, "admin_toggle_request_denied"))
    await _send_pending_requests(bot, session, callback.from_user.id, callback.message.message_id) 

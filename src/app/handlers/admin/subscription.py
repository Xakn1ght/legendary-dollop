import logging

from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import crud

# Keyboard imports moved to function level to avoid circular imports
from app.handlers.admin.common import ADMIN_IDS, _send_pending_requests
from app.services.subscription_processing import process_approved_subscription
from app.utils.admin_bot_helper import get_user_bot
from app.utils.bot_i18n import guess_lang_from_telegram, normalize_lang, set_cached_lang, t

router = Router()

async def _admin_lang(session: AsyncSession, tg_user) -> str:
    try:
        u = await crud.get_user(session, tg_user.id)
        lang = normalize_lang(getattr(u, "language", None)) if u else guess_lang_from_telegram(getattr(tg_user, "language_code", None))
        set_cached_lang(int(tg_user.id), lang)
        return lang
    except Exception:
        return guess_lang_from_telegram(getattr(tg_user, "language_code", None))

# --------------------------
#  Pending subscription details
# --------------------------

@router.callback_query(F.data.startswith("show_sub_"))
async def show_sub_request(callback: CallbackQuery, session: AsyncSession):
    lang = await _admin_lang(session, callback.from_user)
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer(t(lang, "not_authorized"), show_alert=True)
        return

    sub_id = int(callback.data.split("_")[2])
    from app.database.models import Subscription
    sub: Subscription | None = await session.get(Subscription, sub_id)
    if not sub:
        await callback.answer(t(lang, "admin_sub_not_found"), show_alert=True)
        return

    if sub.status != 'pending':
        await callback.answer(t(lang, "admin_sub_already_handled"), show_alert=True)
        try:
            await callback.message.edit_text(t(lang, "admin_sub_no_longer_available"))
        except Exception:
            pass
        return

    await session.refresh(sub, attribute_names=["user"])

    kb = InlineKeyboardBuilder()
    kb.button(text="✅ تایید", callback_data=f"approve_sub_{sub_id}")
    kb.button(text="❌ رد", callback_data=f"deny_sub_{sub_id}")
    kb.button(text="💬 Chat", callback_data=f"chat_sub_{sub_id}_{sub.user.chat_id}")
    kb.adjust(2)

    details = t(lang, "admin_sub_request_details").format(
        id=sub_id,
        user=(sub.user.full_name if sub.user else sub.user_id),
        plan=sub.plan_name,
        username=sub.marzban_username,
    )
    markup = kb.as_markup()
    try:
        if callback.message.photo:
            await callback.message.edit_caption(caption=details, reply_markup=markup)
        else:
            await callback.message.edit_text(details, reply_markup=markup)
    except Exception:
        await callback.message.answer(details, reply_markup=markup)
    await callback.answer()

# --------------------------
#  Approve / Deny subscription
# --------------------------

@router.callback_query(F.data.startswith("approve_sub_"))
async def approve_subscription(callback: CallbackQuery, session: AsyncSession, bot: Bot):
    lang = await _admin_lang(session, callback.from_user)
    sub_id = int(callback.data.split("_")[2])

    # Idempotency / stale button protection: don't process if already handled
    from app.database.models import Subscription as _Subscription
    existing_sub = await session.get(_Subscription, sub_id)
    if not existing_sub:
        await callback.answer(t(lang, "admin_sub_not_found"), show_alert=True)
        return
    if existing_sub.status != 'pending':
        await callback.answer(t(lang, "admin_sub_already_processed"), show_alert=True)
        try:
            await callback.message.edit_text("✅ این درخواست قبلاً پردازش شده است.")
        except Exception:
            pass
        return

    # Get subscription info before processing for notification
    from app.database.models import Subscription
    sub = await session.get(Subscription, sub_id)
    user_id = sub.user_id if sub else None
    plan_name = sub.plan_name if sub else None
    service_name = sub.marzban_username if sub else None

    user_bot = get_user_bot()
    if not user_bot:
        await callback.answer(
            "User bot unavailable (BOT_TOKEN). Cannot notify users.",
            show_alert=True,
        )
        return

    success = await process_approved_subscription(sub_id, session, user_bot)

    if success:
        # Create dashboard notification for user
        if user_id:
            try:
                from app.database.notifications_crud import create_notification
                notif_msg = f'سرویس "{service_name}" ({plan_name}) با موفقیت فعال شد.' if service_name else f'سرویس {plan_name or "شما"} با موفقیت فعال شد.'
                notif_msg += ' از داشبورد می‌توانید اطلاعات اتصال را مشاهده کنید.'
                await create_notification(
                    db=session,
                    user_id=user_id,
                    type='purchase_approved',
                    title='سرویس فعال شد',
                    message=notif_msg,
                    sent_to_webapp=True,
                    sent_to_bot=False
                )
            except Exception as e:
                logging.warning(f"Failed to create approval notification: {e}")

        await callback.answer(t(lang, "admin_sub_approved"))
        try:
            await callback.message.delete()
        except Exception:
            pass
        session.expire_all()
        await _send_pending_requests(bot, session, callback.from_user.id, None)
    else:
        fail_msg = t(lang, "admin_sub_process_failed")
        if lang == "fa":
            fail_msg += "\n\nسرور VPN (پنل) کاربر را نساخت. لاگ admin_bot_error.log را ببینید."
        else:
            fail_msg += "\n\nPasarGuard did not create the user. See admin_bot_error.log."
        await callback.answer(fail_msg, show_alert=True)
        try:
            await callback.message.delete()
        except Exception:
            pass
        session.expire_all()
        await _send_pending_requests(bot, session, callback.from_user.id, None)


@router.callback_query(F.data.startswith("deny_sub_"))
async def deny_subscription(callback: CallbackQuery, session: AsyncSession, bot: Bot):
    lang = await _admin_lang(session, callback.from_user)
    sub_id = int(callback.data.split("_")[2])
    user_bot = get_user_bot()

    from app.services.flows.errors import FlowError
    from app.services.flows.purchase import deny_purchase_order

    try:
        result = await deny_purchase_order(session, sub_id)
    except FlowError as e:
        if e.code == "not_found":
            await callback.answer(t(lang, "admin_sub_not_found"), show_alert=True)
        else:
            await callback.answer(t(lang, "admin_sub_already_processed"), show_alert=True)
            try:
                await callback.message.edit_text("✅ این درخواست قبلاً پردازش شده است.")
            except Exception:
                pass
        return

    credit_refunded = result.credit_refunded
    discounts_restored = result.discounts_restored

    from app.database.models import User
    result_chat = await session.execute(select(User.chat_id).filter(User.id == result.user_id))
    user_chat_id = result_chat.scalar_one_or_none()

    # Try to notify the user if we found their chat_id
    if user_chat_id and user_bot:
        try:
            msg = "❌ درخواست سرویس شما توسط ادمین رد شد."
            details = []
            if credit_refunded > 0:
                details.append(f"بازگشت اعتبار: {credit_refunded:,} تومان")
            if discounts_restored:
                details.append("تخفیف‌های استفاده‌شده به حساب شما بازگردانده شد.")
            if result.coupon_restored:
                details.append("کوپن استفاده‌شده به حساب شما بازگردانده شد.")
            if details:
                msg += "\n" + "\n".join(details)
            await user_bot.send_message(user_chat_id, msg)
        except Exception as e:
            logging.warning(f"Failed to notify user {user_chat_id} about denied subscription {sub_id}: {e}")

    # Create dashboard notification
    if result.user_id:
        try:
            from app.database.notifications_crud import create_notification
            service_name = result.service_name
            plan_name = result.plan_name
            notif_msg = f'درخواست سرویس "{service_name}" ({plan_name}) رد شد.' if service_name else "درخواست خرید سرویس شما رد شد."
            if credit_refunded > 0:
                notif_msg += f" اعتبار {credit_refunded:,} تومان به حساب شما برگشت."
            if discounts_restored:
                notif_msg += " تخفیف‌های استفاده‌شده بازگردانده شد."
            await create_notification(
                db=session,
                user_id=result.user_id,
                type='purchase_denied',
                title='درخواست رد شد',
                message=notif_msg,
                sent_to_webapp=True,
                sent_to_bot=False
            )
        except Exception as e:
            logging.warning(f"Failed to create denial notification: {e}")

    await callback.answer(t(lang, "admin_sub_denied"))
    try:
        await callback.message.delete()
    except Exception:
        pass
    session.expire_all()
    await _send_pending_requests(bot, session, callback.from_user.id, None)

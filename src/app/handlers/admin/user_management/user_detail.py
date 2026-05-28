from aiogram import F
from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import (
    ChargeRequest,
    Referral,
    ReferralReward,
    Subscription,
    User,
)
from app.shared.admin_access import ADMIN_IDS
from app.utils.bot_i18n import t
from app.utils.logger import bot_logger

from .common import _lang_for_tg_user, router


@router.callback_query(F.data.startswith("user_details_"))
async def show_user_details(callback_or_message, user=None, session=None, user_id=None):
    """Show detailed user information"""
    if hasattr(callback_or_message, "from_user"):
        # It's a callback
        if callback_or_message.from_user.id not in ADMIN_IDS:
            await callback_or_message.answer(
                t(_lang_for_tg_user(callback_or_message.from_user), "not_authorized"),
                show_alert=True,
            )
            return
        user_id = int(callback_or_message.data.split("_")[2])
        result = await session.execute(select(User).filter_by(chat_id=user_id))
        user = result.scalar_one_or_none()
        message = callback_or_message.message
        is_callback = True
    else:
        # It's a direct message call
        message = callback_or_message
        is_callback = False

    if not user:
        text = "❌ کاربر یافت نشد."
        if is_callback:
            await callback_or_message.message.edit_text(text)
            await callback_or_message.answer()
        else:
            await message.answer(text)
        return

    # Get user's subscriptions
    subs_query = select(Subscription).filter(Subscription.user_id == user.id)
    subs_result = await session.execute(subs_query)
    subscriptions = subs_result.scalars().all()

    # Get user's charge requests
    charges_query = select(ChargeRequest).filter(ChargeRequest.user_id == user.chat_id)
    charges_result = await session.execute(charges_query)
    charge_requests = charges_result.scalars().all()

    # Count rewards
    rewards_count = (
        await session.scalar(
            select(func.count(ReferralReward.id)).filter(
                ReferralReward.referrer_id == user.chat_id
            )
        )
        or 0
    )

    # Check if user has a referrer (was referred by someone)
    referral_entry = await session.scalar(
        select(Referral).filter(Referral.referee_id == user.id)
    )
    has_referrer = referral_entry is not None
    referrer_info = ""
    if referral_entry:
        referrer = await session.get(User, referral_entry.referrer_id)
        if referrer:
            referrer_info = (
                f"\n👤 معرف: {referrer.full_name or referrer.username or f'ID:{referrer.chat_id}'}"
            )

    # Format user details
    status_emoji = "🚫 مسدود" if user.banned else "✅ فعال"
    created_date = (
        user.created_at.strftime("%Y-%m-%d %H:%M") if user.created_at else "نامشخص"
    )

    user_text = (
        f"👤 **اطلاعات کاربر**\n\n"
        f"🆔 شناسه: `{user.chat_id}`\n"
        f"👤 نام: {user.full_name or 'نامشخص'}\n"
        f"🏷 نام کاربری: @{user.username or 'ندارد'}\n"
        f"📞 شماره: {user.phone_number or 'ندارد'}\n"
        f"💰 موجودی: `{user.credit:,}` تومان\n"
        f"⭐ امتیاز: `{user.stars}`\n"
        f"🔗 کد دعوت: `{user.referral_code or 'ندارد'}`\n"
        f"📅 عضویت: {created_date}\n"
        f"🔄 وضعیت: {status_emoji}\n"
        f"🏷️ دسته‌بندی: `{user.category}`{referrer_info}\n\n"
        f"📊 **آمار:**\n"
        f"🛍 اشتراک‌ها: `{len(subscriptions)}`\n"
        f"💳 درخواست شارژ: `{len(charge_requests)}`\n"
        f"🎁 پاداش‌ها: `{rewards_count}`"
    )

    # Create action buttons
    kb = InlineKeyboardBuilder()
    kb.button(text="💰 تغییر موجودی", callback_data=f"edit_credit_{user.chat_id}")
    kb.button(
        text="🏷️ ویرایش دسته‌بندی",
        callback_data=f"edit_category_{user.chat_id}",
    )
    if user.banned:
        kb.button(text="✅ رفع مسدودی", callback_data=f"unban_user_{user.chat_id}")
    else:
        kb.button(text="🚫 مسدود کردن", callback_data=f"ban_user_{user.chat_id}")
    kb.button(text="🛍 اشتراک‌ها", callback_data=f"user_subs_{user.chat_id}")
    kb.button(text="💬 چت", callback_data=f"chat_with_user_{user.chat_id}")
    if not has_referrer:
        kb.button(text="➕ افزودن معرف", callback_data=f"add_referrer_{user.chat_id}")
    kb.adjust(2)

    if is_callback:
        await callback_or_message.message.edit_text(
            user_text,
            reply_markup=kb.as_markup(),
            parse_mode="Markdown",
        )
        await callback_or_message.answer()
    else:
        await message.answer(user_text, reply_markup=kb.as_markup(), parse_mode="Markdown")


@router.callback_query(F.data.startswith("edit_user_"))
async def edit_user(callback: CallbackQuery, session: AsyncSession):
    """Show user edit options"""
    try:
        user_id = int(callback.data.split("_")[2])
        await callback.answer("⏳ در حال بارگذاری گزینه‌های ویرایش...")

        result = await session.execute(select(User).filter_by(chat_id=user_id))
        user = result.scalar_one_or_none()

        if not user:
            await callback.message.edit_text("❌ کاربر یافت نشد.")
            return

        text = (
            f"✏️ **ویرایش کاربر {user.full_name or user.username or user.chat_id}**\n\n"
            "گزینه مورد نظر را انتخاب کنید:"
        )

        kb = InlineKeyboardBuilder()
        kb.button(text="💰 تغییر موجودی", callback_data=f"edit_credit_{user.chat_id}")
        kb.button(text="🔙 بازگشت", callback_data=f"user_details_{user.chat_id}")
        kb.adjust(2)

        await callback.message.edit_text(
            text, reply_markup=kb.as_markup(), parse_mode="Markdown"
        )

    except Exception as e:
        bot_logger.error("Error in edit_user handler", exc_info=e)
        await callback.answer("❌ خطای داخلی رخ داد.", show_alert=True)


@router.callback_query(F.data.startswith("user_subs_"))
async def show_user_subscriptions(callback: CallbackQuery, session: AsyncSession):
    """Show user's subscriptions"""
    try:
        user_id = int(callback.data.split("_")[2])
        await callback.answer("⏳ در حال دریافت اشتراک‌ها...")

        result = await session.execute(select(User).filter_by(chat_id=user_id))
        user = result.scalar_one_or_none()

        if not user:
            await callback.message.edit_text("❌ کاربر یافت نشد.")
            return

        # Get user's subscriptions
        subs_query = (
            select(Subscription)
            .filter(Subscription.user_id == user.id)
            .order_by(desc(Subscription.created_at))
        )
        subs_result = await session.execute(subs_query)
        subscriptions = subs_result.scalars().all()

        if not subscriptions:
            text = (
                f"🛍 **اشتراک‌های {user.full_name or user.username or user.chat_id}**\n\n"
                "❌ هیچ اشتراکی یافت نشد."
            )
        else:
            text = (
                f"🛍 **اشتراک‌های {user.full_name or user.username or user.chat_id}**\n\n"
                f"📊 تعداد کل: `{len(subscriptions)}`\n\n"
            )

            for i, sub in enumerate(subscriptions[:10], 1):  # Show only first 10
                status_emoji = {
                    "active": "✅",
                    "pending": "⏳",
                    "expired": "❌",
                    "cancelled": "🚫",
                }.get(sub.status, "❓")

                created_date = (
                    sub.created_at.strftime("%Y-%m-%d") if sub.created_at else "نامشخص"
                )
                text += (
                    f"{i}. {status_emoji} **{sub.marzban_username or 'نامشخص'}**\n"
                    f"   📦 پلن: {sub.plan_name or 'نامشخص'}\n"
                    f"   💰 قیمت: `{sub.price:,}` تومان\n"
                    f"   📅 تاریخ: {created_date}\n\n"
                )

            if len(subscriptions) > 10:
                text += f"... و `{len(subscriptions) - 10}` اشتراک دیگر\n"

        kb = InlineKeyboardBuilder()
        if subscriptions:
            # Add buttons for each subscription (first 5)
            for sub in subscriptions[:5]:
                kb.button(
                    text=f"📝 {sub.marzban_username or f'ID:{sub.id}'}",
                    callback_data=f"sub_details_{sub.id}",
                )

        kb.button(text="🔙 بازگشت", callback_data=f"user_details_{user.chat_id}")
        kb.adjust(1)

        await callback.message.edit_text(
            text, reply_markup=kb.as_markup(), parse_mode="Markdown"
        )

    except Exception as e:
        bot_logger.error("Error in show_user_subscriptions handler", exc_info=e)
        await callback.answer("❌ خطای داخلی رخ داد.", show_alert=True)

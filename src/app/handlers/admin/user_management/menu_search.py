import asyncio
from datetime import datetime, timedelta

from aiogram import Bot, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Subscription, User
from app.shared.admin_access import ADMIN_IDS
from app.utils.bot_i18n import t
from app.utils.logger import bot_logger
from app.utils.validation import sanitize_user_input

from .common import UserManagementStates, _lang_for_tg_user, router
from .user_detail import show_user_details


@router.message(F.text.in_(["👥 کاربران", "کاربران"]))
async def user_management_menu(message: Message, session: AsyncSession):
    """Display the main user management menu with statistics."""
    try:
        # Get statistics
        total_users_query = select(func.count(User.id))
        total_users = await session.scalar(total_users_query)

        active_users_query = select(func.count(User.id)).filter(User.banned == False)
        active_users = await session.scalar(active_users_query)

        banned_users = total_users - active_users

        # New users today
        today_start = datetime.now().replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        new_users_today_query = select(func.count(User.id)).filter(
            User.created_at >= today_start
        )
        new_users_today = await session.scalar(new_users_today_query)

        text = (
            f"📊 <b>آمار کاربران</b>\n\n"
            f"👥 <b>کل کاربران:</b> {total_users:,}\n"
            f"✅ <b>فعال:</b> {active_users:,}\n"
            f"🚫 <b>مسدود:</b> {banned_users:,}\n"
            f"🆕 <b>جدید امروز:</b> {new_users_today:,}\n\n"
            "عملیات مورد نظر را انتخاب کنید:"
        )

        kb = InlineKeyboardBuilder()
        kb.button(text="🔍 جستجوی کاربر", callback_data="search_user")
        kb.button(text="👥 لیست کاربران", callback_data="list_users")
        kb.button(text="📊 آمار کاربران", callback_data="user_stats")
        kb.button(text="🚫 کاربران مسدود", callback_data="banned_users")
        kb.button(text="💰 برترین کاربران", callback_data="top_users")
        kb.button(text="🎯 عملیات گروهی", callback_data="bulk_actions")
        kb.adjust(2)

        # Use a try-except block to handle cases where the message is deleted
        try:
            # Always try to edit first, then send new if that fails
            await message.edit_text(text, reply_markup=kb.as_markup(), parse_mode="HTML")
        except Exception as e:
            bot_logger.info(f"Could not edit message, sending new one. Error: {e}")
            await message.answer(text, reply_markup=kb.as_markup(), parse_mode="HTML")
    except Exception as e:
        bot_logger.error("Error in user_management_menu handler", exc_info=e)
        await message.answer("❌ خطای داخلی در نمایش منو رخ داد.", show_alert=True)


@router.callback_query(F.data == "bulk_actions")
async def bulk_actions_menu(callback: CallbackQuery):
    """Show the bulk actions menu."""
    kb = InlineKeyboardBuilder()
    kb.button(text="📢 ارسال پیام همگانی", callback_data="broadcast_message")
    kb.button(text="🔙 بازگشت", callback_data="back_to_user_management")
    kb.adjust(1)

    await callback.message.edit_text(
        " لطفا یک عملیات گروهی را انتخاب کنید:",
        reply_markup=kb.as_markup(),
    )


@router.callback_query(F.data == "broadcast_message")
async def broadcast_message_prompt(callback: CallbackQuery, state: FSMContext):
    """Prompt the admin to send a message for broadcasting."""
    await state.set_state(UserManagementStates.waiting_broadcast_message)
    await callback.message.edit_text(
        "لطفا پیامی را که می‌خواهید برای همه کاربران ارسال کنید، تایپ کنید. شما می‌توانید از قالب‌بندی Markdown استفاده کنید.",
        reply_markup=InlineKeyboardBuilder()
        .button(text="🔙 لغو", callback_data="bulk_actions")
        .as_markup(),
    )


@router.message(UserManagementStates.waiting_broadcast_message)
async def broadcast_message_confirm(message: Message, state: FSMContext):
    """Show a preview of the broadcast message and ask for confirmation."""
    await state.update_data(broadcast_message_text=message.text)

    kb = InlineKeyboardBuilder()
    kb.button(text="✅ ارسال", callback_data="send_broadcast")
    kb.button(text="✏️ ویرایش", callback_data="broadcast_message")
    kb.button(text="🔙 لغو", callback_data="bulk_actions")
    kb.adjust(2)

    await message.answer(
        "پیش‌نمایش:\n\n" + message.text,
        reply_markup=kb.as_markup(),
        parse_mode="Markdown",
    )


@router.callback_query(F.data == "send_broadcast")
async def send_broadcast_message(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession, bot: Bot
):
    """Send the broadcast message to all non-banned users."""
    data = await state.get_data()
    message_text = data.get("broadcast_message_text")
    await state.clear()

    await callback.message.edit_text("⏳ در حال ارسال پیام همگانی...")

    users_query = select(User.chat_id).filter(User.banned == False)
    users_result = await session.execute(users_query)
    user_ids = users_result.scalars().all()

    sent_count = 0
    failed_count = 0

    for user_id in user_ids:
        try:
            await bot.send_message(user_id, message_text, parse_mode="Markdown")
            sent_count += 1
            await asyncio.sleep(0.1)  # Avoid hitting rate limits
        except Exception as e:
            failed_count += 1
            bot_logger.error(f"Failed to send broadcast to {user_id}: {e}")

    await callback.message.edit_text(
        f"✅ پیام همگانی با موفقیت ارسال شد.\\n\\n"
        f"👥 ارسال شده به: {sent_count} کاربر\\n"
        f"❌ خطا در ارسال: {failed_count} کاربر",
        reply_markup=InlineKeyboardBuilder()
        .button(text="🔙 بازگشت", callback_data="bulk_actions")
        .as_markup(),
    )


@router.callback_query(F.data == "user_stats")
async def user_stats(callback: CallbackQuery, session: AsyncSession):
    """Show detailed user statistics."""
    try:
        await callback.answer("⏳ در حال محاسبه آمار...")

        total_users = await session.scalar(select(func.count(User.id))) or 0
        active_users = (
            await session.scalar(
                select(func.count(User.id)).where(User.banned == False)
            )
            or 0
        )
        banned_users = total_users - active_users

        one_day_ago = datetime.now() - timedelta(days=1)
        new_users_last_24h = (
            await session.scalar(
                select(func.count(User.id)).where(User.created_at >= one_day_ago)
            )
            or 0
        )

        one_week_ago = datetime.now() - timedelta(days=7)
        new_users_last_7d = (
            await session.scalar(
                select(func.count(User.id)).where(User.created_at >= one_week_ago)
            )
            or 0
        )

        total_subscriptions = (
            await session.scalar(select(func.count(Subscription.id))) or 0
        )

        stats_text = (
            f"📊 <b>آمار کاربران</b>\n\n"
            f"👥 <b>کل کاربران:</b> {total_users:,}\n"
            f"✅ <b>فعال:</b> {active_users:,}\n"
            f"🚫 <b>مسدود:</b> {banned_users:,}\n\n"
            f"📈 <b>کاربران جدید:</b>\n"
            f"  -  <b>۲۴ ساعت گذشته:</b> {new_users_last_24h:,}\n"
            f"  -  <b>۷ روز گذشته:</b> {new_users_last_7d:,}\n\n"
            f"🛍️ <b>کل اشتراک‌ها:</b> {total_subscriptions:,}"
        )

        kb = InlineKeyboardBuilder()
        kb.button(text="🔙 بازگشت", callback_data="back_to_user_management")

        await callback.message.edit_text(
            stats_text, reply_markup=kb.as_markup(), parse_mode="HTML"
        )

    except Exception as e:
        bot_logger.error("Error in user_stats handler", exc_info=e)
        await callback.answer("❌ خطای داخلی رخ داد.", show_alert=True)


@router.callback_query(F.data == "back_to_user_management")
async def back_to_user_management_menu(callback: CallbackQuery, session: AsyncSession):
    """Returns to the main user management menu."""

    try:
        # Get statistics
        total_users_query = select(func.count(User.id))
        total_users = await session.scalar(total_users_query)

        active_users_query = select(func.count(User.id)).filter(User.banned == False)
        active_users = await session.scalar(active_users_query)

        banned_users = total_users - active_users

        # New users today
        today_start = datetime.now().replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        new_users_today_query = select(func.count(User.id)).filter(
            User.created_at >= today_start
        )
        new_users_today = await session.scalar(new_users_today_query)

        text = (
            f"📊 <b>آمار کاربران</b>\n\n"
            f"👥 <b>کل کاربران:</b> {total_users:,}\n"
            f"✅ <b>فعال:</b> {active_users:,}\n"
            f"🚫 <b>مسدود:</b> {banned_users:,}\n"
            f"🆕 <b>جدید امروز:</b> {new_users_today:,}\n\n"
            "عملیات مورد نظر را انتخاب کنید:"
        )

        kb = InlineKeyboardBuilder()
        kb.button(text="🔍 جستجوی کاربر", callback_data="search_user")
        kb.button(text="👥 لیست کاربران", callback_data="list_users")
        kb.button(text="📊 آمار کاربران", callback_data="user_stats")
        kb.button(text="🚫 کاربران مسدود", callback_data="banned_users")
        kb.button(text="💰 برترین کاربران", callback_data="top_users")
        kb.button(text="🎯 عملیات گروهی", callback_data="bulk_actions")
        kb.adjust(2)

        await callback.message.edit_text(
            text, reply_markup=kb.as_markup(), parse_mode="HTML"
        )
        await callback.answer()

    except Exception as e:
        bot_logger.error("Error in back_to_user_management_menu handler", exc_info=e)
        await callback.answer("❌ خطای داخلی در نمایش منو رخ داد.", show_alert=True)


@router.callback_query(F.data == "search_user")
async def search_user_prompt(callback: CallbackQuery, state: FSMContext):
    """Prompt for user search"""
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer(
            t(_lang_for_tg_user(callback.from_user), "not_authorized"),
            show_alert=True,
        )
        return

    await state.set_state(UserManagementStates.waiting_search_term)
    await callback.message.edit_text(
        "🔍 **جستجوی کاربر**\n\n"
        "لطفاً یکی از موارد زیر را وارد کنید:\n"
        "• نام کاربری (username)\n"
        "• نام کامل\n"
        "• شناسه عددی (user ID)\n"
        "• شماره تلفن\n\n"
        "برای لغو: /cancel"
    )
    await callback.answer()


@router.message(UserManagementStates.waiting_search_term)
async def search_user_results(message: Message, state: FSMContext, session: AsyncSession):
    """Search for users and display results"""
    if message.from_user.id not in ADMIN_IDS:
        return

    search_term = sanitize_user_input(message.text)

    if search_term == "/cancel":
        await state.clear()
        await message.answer("جستجو لغو شد.")
        return

    # Search in multiple fields
    search_conditions = []

    # Try to parse as user ID
    try:
        user_id = int(search_term)
        search_conditions.append(User.chat_id == user_id)
    except ValueError:
        pass

    # Search in text fields
    search_conditions.extend(
        [
            User.username.ilike(f"%{search_term}%"),
            User.full_name.ilike(f"%{search_term}%"),
            User.phone_number.ilike(f"%{search_term}%"),
        ]
    )

    # Execute search
    search_query = select(User).filter(or_(*search_conditions)).limit(10)
    result = await session.execute(search_query)
    users = result.scalars().all()

    await state.clear()

    if not users:
        await message.answer("❌ کاربری با این مشخصات یافت نشد.")
        return

    if len(users) == 1:
        # Single user found, show details directly
        await show_user_details(message, users[0], session)
    else:
        # Multiple users found, show list
        kb = InlineKeyboardBuilder()
        for user in users:
            display_name = user.full_name or user.username or f"ID: {user.chat_id}"
            status_emoji = "🚫" if user.banned else "✅"
            kb.button(
                text=f"{status_emoji} {display_name[:30]}",
                callback_data=f"user_details_{user.chat_id}",
            )
        kb.adjust(1)

        await message.answer(
            f"🔍 یافت شد {len(users)} کاربر:\n\nکاربر مورد نظر را انتخاب کنید:",
            reply_markup=kb.as_markup(),
        )

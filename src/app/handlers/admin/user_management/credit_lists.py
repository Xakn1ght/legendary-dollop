from datetime import datetime

from aiogram import F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import desc, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import ReferralReward, Subscription, User
from app.shared.admin_access import ADMIN_IDS
from app.utils.bot_i18n import t
from app.utils.logger import bot_logger
from app.utils.validation import sanitize_user_input

from .common import UserManagementStates, _lang_for_tg_user, router


@router.callback_query(F.data.startswith("edit_credit_"))
async def edit_credit_prompt(callback: CallbackQuery, state: FSMContext):
    """Prompt for credit edit"""
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer(
            t(_lang_for_tg_user(callback.from_user), "not_authorized"),
            show_alert=True,
        )
        return

    user_id = int(callback.data.split("_")[2])
    await state.set_data({"user_id": user_id})
    await state.set_state(UserManagementStates.waiting_credit_amount)
    bot_logger.info(f"State set to waiting_credit_amount for user_id: {user_id}")

    await callback.message.edit_text(
        "💰 **تغییر موجودی کاربر**\n\n"
        "مقدار جدید موجودی را به تومان وارد کنید:\n"
        "• برای اضافه کردن: +مقدار (مثل +50000)\n"
        "• برای کم کردن: -مقدار (مثل -20000)\n"
        "• برای تنظیم دقیق: مقدار (مثل 100000)\n\n"
        "برای لغو: /cancel"
    )
    await callback.answer()


@router.message(UserManagementStates.waiting_credit_amount)
async def edit_credit_process(
    message: Message, state: FSMContext, session: AsyncSession
):
    """Process credit edit"""
    bot_logger.info("Entered edit_credit_process handler")
    if message.from_user.id not in ADMIN_IDS:
        bot_logger.warning(
            f"Unauthorized access attempt to edit_credit_process by user {message.from_user.id}"
        )
        return

    bot_logger.info(
        f"Message received in waiting_credit_amount state: '{message.text}'"
    )
    data = await state.get_data()
    user_id = data.get("user_id")

    if not user_id:
        bot_logger.error("Could not find user_id in state data.")
        await message.answer(
            "❌ خطای داخلی: شناسه کاربر یافت نشد. لطفاً دوباره تلاش کنید."
        )
        await state.clear()
        return

    bot_logger.info(f"Editing credit for user_id: {user_id}")

    if message.text == "/cancel":
        await state.clear()
        await message.answer("تغییر موجودی لغو شد.")
        bot_logger.info(f"Credit edit cancelled for user {user_id}.")
        return

    try:
        amount_str = sanitize_user_input(message.text).replace(",", "")
        bot_logger.info(f"Sanitized amount string for user {user_id}: {amount_str}")

        # Get current user
        result = await session.execute(select(User).filter_by(chat_id=user_id))
        user = result.scalar_one_or_none()

        if not user:
            await message.answer("❌ کاربر یافت نشد.")
            bot_logger.warning(
                f"User with chat_id {user_id} not found in database during credit edit."
            )
            await state.clear()
            return

        bot_logger.info(
            f"User {user.full_name} (ID: {user_id}) found, current credit: {user.credit}"
        )
        current_credit = user.credit or 0

        if amount_str.startswith("+"):
            # Add to current
            amount = int(amount_str[1:])
            new_credit = current_credit + amount
            operation = f"اضافه شد {amount:,} تومان"
        elif amount_str.startswith("-"):
            # Subtract from current
            amount = int(amount_str[1:])
            new_credit = max(0, current_credit - amount)
            operation = f"کم شد {amount:,} تومان"
        else:
            # Set exact amount
            new_credit = int(amount_str)
            operation = f"تنظیم شد روی {new_credit:,} تومان"

        bot_logger.info(
            f"User {user_id} - Operation: {operation}, New credit: {new_credit}"
        )

        # Update credit
        await session.execute(
            update(User).filter(User.chat_id == user_id).values(credit=new_credit)
        )
        await session.commit()
        bot_logger.info(f"Successfully updated credit for user {user_id} to {new_credit}")

        await message.answer(
            f"✅ موجودی کاربر بروزرسانی شد\n\n"
            f"موجودی قبلی: `{current_credit:,}` تومان\n"
            f"عملیات: {operation}\n"
            f"موجودی جدید: `{new_credit:,}` تومان",
            parse_mode="Markdown",
        )

    except ValueError:
        await message.answer("❌ مقدار وارد شده نامعتبر است. لطفاً عدد وارد کنید.")
        bot_logger.error(
            f"ValueError while processing credit edit for user {user_id}: invalid amount '{message.text}'"
        )
        return
    except Exception as e:
        await message.answer(f"❌ خطا در بروزرسانی موجودی: {str(e)}")
        bot_logger.exception(
            f"Exception while processing credit edit for user {user_id}", exc_info=e
        )

    await state.clear()
    bot_logger.info(f"Exiting edit_credit_process for user {user_id}")


@router.callback_query(F.data == "list_users")
async def list_users(callback: CallbackQuery, session: AsyncSession):
    """Show paginated list of users"""
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer(
            t(_lang_for_tg_user(callback.from_user), "not_authorized"),
            show_alert=True,
        )
        return

    # Get recent users
    users_query = select(User).order_by(desc(User.created_at)).limit(20)
    result = await session.execute(users_query)
    users = result.scalars().all()

    if not users:
        await callback.message.edit_text("❌ کاربری یافت نشد.")
        await callback.answer()
        return

    kb = InlineKeyboardBuilder()
    for user in users:
        display_name = user.full_name or user.username or f"ID: {user.chat_id}"
        status_emoji = "🚫" if user.banned else "✅"
        created_date = user.created_at.strftime("%m-%d") if user.created_at else ""

        kb.button(
            text=f"{status_emoji} {display_name[:25]} ({created_date})",
            callback_data=f"user_details_{user.chat_id}",
        )

    kb.button(text="🔄 بروزرسانی", callback_data="list_users")
    kb.adjust(1)

    await callback.message.edit_text(
        f"👥 **آخرین کاربران ({len(users)} نفر)**\n\n"
        "کاربر مورد نظر را انتخاب کنید:",
        reply_markup=kb.as_markup(),
        parse_mode="Markdown",
    )
    await callback.answer()


@router.callback_query(F.data == "banned_users")
async def banned_users(callback: CallbackQuery, session: AsyncSession):
    """Show a list of banned users"""
    try:
        await callback.answer("⏳ در حال بررسی کاربران مسدود...")

        # Get banned users, order by creation date
        banned_users_query = (
            select(User).filter(User.banned == True).order_by(User.created_at.desc())
        )
        banned_users_result = await session.execute(banned_users_query)
        users = banned_users_result.scalars().all()

        if not users:
            await callback.message.edit_text("✅ هیچ کاربر مسدودی یافت نشد.")
            return

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        text = f"🚫 <b>کاربران مسدود</b> (به روز شده در {timestamp})\n\n"
        for user in users:
            text += f"▪️ `{user.chat_id}` - {user.full_name}\n"

        kb = InlineKeyboardBuilder()
        kb.button(text="🔄 به روز رسانی", callback_data="banned_users")
        kb.button(text="🔙 بازگشت", callback_data="back_to_user_management")

        await callback.message.edit_text(
            text,
            reply_markup=kb.as_markup(),
            parse_mode="Markdown",
        )

    except Exception as e:
        bot_logger.error("Error in banned_users handler", exc_info=e)
        await callback.answer(
            "❌ خطای داخلی در دریافت لیست کاربران مسدود رخ داد.",
            show_alert=True,
        )


@router.callback_query(F.data == "top_users")
async def top_users(callback: CallbackQuery, session: AsyncSession):
    """Shows a menu to select top user rankings."""
    try:
        await callback.answer()

        text = "🏆 **برترین کاربران**\n\nنوع رتبه‌بندی را انتخاب کنید:"

        kb = InlineKeyboardBuilder()
        kb.button(text="💰 بالاترین موجودی", callback_data="top_by_credit")
        kb.button(text="⭐ بیشترین امتیاز", callback_data="top_by_stars")
        kb.button(text="🎁 بیشترین اشتراک", callback_data="top_by_subs")
        kb.button(text="🎁 بیشترین پاداش", callback_data="top_by_rewards")
        kb.button(text="🔙 بازگشت", callback_data="back_to_user_management")
        kb.adjust(2)

        await callback.message.edit_text(
            text, reply_markup=kb.as_markup(), parse_mode="Markdown"
        )

    except Exception as e:
        bot_logger.error("Error in top_users handler", exc_info=e)
        await callback.answer(
            "❌ خطای داخلی در نمایش رتبه‌بندی رخ داد.", show_alert=True
        )


@router.callback_query(F.data == "top_by_credit")
async def top_by_credit(callback: CallbackQuery, session: AsyncSession):
    """Show users with highest credit"""
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer(
            t(_lang_for_tg_user(callback.from_user), "not_authorized"),
            show_alert=True,
        )
        return

    top_users_query = (
        select(User).filter(User.credit > 0).order_by(desc(User.credit)).limit(10)
    )
    result = await session.execute(top_users_query)
    users = result.scalars().all()

    if not users:
        await callback.message.edit_text("❌ کاربری با موجودی یافت نشد.")
        await callback.answer()
        return

    text = "💰 **برترین کاربران (موجودی)**\n\n"
    kb = InlineKeyboardBuilder()

    for i, user in enumerate(users, 1):
        display_name = user.full_name or user.username or f"ID: {user.chat_id}"
        text += f"{i}. {display_name}: `{user.credit:,}` تومان\n"

        kb.button(
            text=f"{i}. {display_name[:20]}",
            callback_data=f"user_details_{user.chat_id}",
        )

    kb.button(text="⬅️ بازگشت", callback_data="top_users")
    kb.adjust(2)

    await callback.message.edit_text(
        text,
        reply_markup=kb.as_markup(),
        parse_mode="Markdown",
    )
    await callback.answer()


@router.callback_query(F.data == "top_by_stars")
async def top_by_stars(callback: CallbackQuery, session: AsyncSession):
    """Show users with highest stars"""
    try:
        await callback.answer("⏳ در حال دریافت برترین کاربران...")

        # Show all users ordered by stars (including those with 0 stars)
        top_users_query = select(User).order_by(desc(User.stars)).limit(10)
        result = await session.execute(top_users_query)
        users = result.scalars().all()

        if not users:
            await callback.message.edit_text(
                "❌ هیچ کاربری یافت نشد.",
                reply_markup=InlineKeyboardBuilder()
                .button(text="🔙 بازگشت", callback_data="top_users")
                .as_markup(),
            )
            return

        text = "⭐ **برترین کاربران (امتیاز)**\n\n"

        if users[0].stars == 0:
            text += "_هنوز هیچ کاربری امتیاز کسب نکرده است_\n\n"

        for i, user in enumerate(users, 1):
            display_name = user.full_name or user.username or f"ID: {user.chat_id}"
            text += f"{i}. {display_name}: `{user.stars}` ⭐\n"

        kb = InlineKeyboardBuilder()
        kb.button(text="🔙 بازگشت", callback_data="top_users")

        await callback.message.edit_text(
            text, reply_markup=kb.as_markup(), parse_mode="Markdown"
        )

    except Exception as e:
        bot_logger.error("Error in top_by_stars handler", exc_info=e)
        await callback.answer("❌ خطای داخلی رخ داد.", show_alert=True)


@router.callback_query(F.data == "top_by_subs")
async def top_by_subs(callback: CallbackQuery, session: AsyncSession):
    """Show users with most subscriptions"""
    try:
        await callback.answer("⏳ در حال دریافت برترین کاربران...")

        # Count subscriptions per user (including users with 0 subscriptions)
        top_users_query = (
            select(
                User, func.coalesce(func.count(Subscription.id), 0).label("sub_count")
            )
            .outerjoin(Subscription, User.id == Subscription.user_id)
            .group_by(User.id)
            .order_by(desc("sub_count"))
            .limit(10)
        )
        result = await session.execute(top_users_query)
        users_with_counts = result.all()

        if not users_with_counts:
            await callback.message.edit_text(
                "❌ هیچ کاربری یافت نشد.",
                reply_markup=InlineKeyboardBuilder()
                .button(text="🔙 بازگشت", callback_data="top_users")
                .as_markup(),
            )
            return

        text = "🎁 **برترین کاربران (اشتراک‌ها)**\n\n"

        if users_with_counts[0][1] == 0:
            text += "_هنوز هیچ کاربری اشتراک ندارد_\n\n"

        for i, (user, sub_count) in enumerate(users_with_counts, 1):
            display_name = user.full_name or user.username or f"ID: {user.chat_id}"
            text += f"{i}. {display_name}: `{sub_count}` اشتراک\n"

        kb = InlineKeyboardBuilder()
        kb.button(text="🔙 بازگشت", callback_data="top_users")

        await callback.message.edit_text(
            text, reply_markup=kb.as_markup(), parse_mode="Markdown"
        )

    except Exception as e:
        bot_logger.error("Error in top_by_subs handler", exc_info=e)
        await callback.answer("❌ خطای داخلی رخ داد.", show_alert=True)


@router.callback_query(F.data == "top_by_rewards")
async def top_by_rewards(callback: CallbackQuery, session: AsyncSession):
    """Show users with most referral rewards"""
    try:
        await callback.answer("⏳ در حال دریافت برترین کاربران...")

        # Count referral rewards per user (including users with 0 rewards)
        top_users_query = (
            select(
                User,
                func.coalesce(func.count(ReferralReward.id), 0).label("reward_count"),
            )
            .outerjoin(ReferralReward, User.id == ReferralReward.referrer_id)
            .group_by(User.id)
            .order_by(desc("reward_count"))
            .limit(10)
        )
        result = await session.execute(top_users_query)
        users_with_counts = result.all()

        if not users_with_counts:
            await callback.message.edit_text(
                "❌ هیچ کاربری یافت نشد.",
                reply_markup=InlineKeyboardBuilder()
                .button(text="🔙 بازگشت", callback_data="top_users")
                .as_markup(),
            )
            return

        text = "🎁 **برترین کاربران (پاداش‌ها)**\n\n"

        if users_with_counts[0][1] == 0:
            text += "_هنوز هیچ کاربری پاداش دریافت نکرده است_\n\n"

        for i, (user, reward_count) in enumerate(users_with_counts, 1):
            display_name = user.full_name or user.username or f"ID: {user.chat_id}"
            text += f"{i}. {display_name}: `{reward_count}` پاداش\n"

        kb = InlineKeyboardBuilder()
        kb.button(text="🔙 بازگشت", callback_data="top_users")

        await callback.message.edit_text(
            text, reply_markup=kb.as_markup(), parse_mode="Markdown"
        )

    except Exception as e:
        bot_logger.error("Error in top_by_rewards handler", exc_info=e)
        await callback.answer("❌ خطای داخلی رخ داد.", show_alert=True)

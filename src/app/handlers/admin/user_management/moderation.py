from typing import Union

from aiogram import Bot, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.chat_sessions import _message_map, admin_to_user, user_to_admin
from app.database import crud
from app.database.models import User
from app.shared.admin_access import ADMIN_IDS
from app.utils.bot_i18n import t
from app.utils.logger import bot_logger

from .common import IsUserInAdminChat, _lang_for_tg_user, router
from .user_detail import show_user_details


@router.callback_query(F.data.startswith("ban_user_"))
async def ban_user(callback: CallbackQuery, session: AsyncSession):
    """Ban a user"""
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer(
            t(_lang_for_tg_user(callback.from_user), "not_authorized"),
            show_alert=True,
        )
        return

    user_id = int(callback.data.split("_")[2])

    # Update user status
    await session.execute(
        update(User).filter(User.chat_id == user_id).values(banned=True)
    )
    await session.commit()

    await callback.answer("✅ کاربر مسدود شد", show_alert=True)

    # Notify the user they have been banned and provide a plead button
    try:
        plead_kb = InlineKeyboardBuilder()
        plead_kb.button(
            text="🙏 درخواست بازنگری", callback_data=f"plead_unban_{user_id}"
        )
        await callback.bot.send_message(
            user_id,
            "🚫 شما از ربات مسدود شده‌اید. برای درخواست بازنگری، دکمه زیر را فشار دهید.",
            reply_markup=plead_kb.as_markup(),
        )
    except Exception as e:
        bot_logger.error(f"Failed to send ban notification to user {user_id}: {e}")

    # Refresh the details view
    await show_user_details(callback, session=session, user_id=user_id)


@router.callback_query(F.data.startswith("chat_with_user_"))
async def start_chat_with_user(
    callback: CallbackQuery, state: FSMContext, _session: AsyncSession
):
    """Initiate a chat session with a user."""
    try:
        user_chat_id = int(callback.data.split("_")[3])
        admin_chat_id = callback.from_user.id

        # Store session for both admin and user
        admin_to_user[admin_chat_id] = user_chat_id
        user_to_admin[user_chat_id] = admin_chat_id

        end_chat_kb = (
            InlineKeyboardBuilder().button(text=" پایان چت", callback_data="end_chat").as_markup()
        )

        await callback.message.answer(
            f"شما اکنون در حالت چت با کاربر `{user_chat_id}` هستید. "
            "برای خروج، از دکمه زیر یا دستور /endchat استفاده کنید.",
            reply_markup=end_chat_kb,
        )
        await callback.bot.send_message(
            user_chat_id,
            "ادمین یک چت با شما آغاز کرده است. پیام‌های شما به او ارسال خواهد شد. برای خروج، از دکمه زیر یا دستور /endchat استفاده کنید.",
            reply_markup=end_chat_kb,
        )
        await callback.answer()

    except Exception as e:
        bot_logger.error(f"Error in start_chat_with_user: {e}")
        await callback.answer("❌ خطای داخلی رخ داد.", show_alert=True)


@router.callback_query(F.data == "end_chat")
@router.message(F.text == "/endchat")
async def end_chat_handler(
    update: Union[CallbackQuery, Message], bot: Bot, session: AsyncSession
):
    """End the chat session for either user or admin."""
    initiator_id = update.from_user.id
    is_admin = initiator_id in admin_to_user

    user_chat_id = admin_to_user.pop(initiator_id, None) if is_admin else initiator_id
    admin_chat_id = user_to_admin.pop(user_chat_id, None)

    # Notify both parties
    if is_admin:
        await bot.send_message(initiator_id, "💬 چت با کاربر پایان یافت.")
        if user_chat_id:
            await bot.send_message(user_chat_id, "💬 چت با ادمین پایان یافت.")
    else:
        await bot.send_message(initiator_id, "💬 چت با ادمین پایان یافت.")
        if admin_chat_id:
            await bot.send_message(
                admin_chat_id, f"💬 کاربر `{user_chat_id}` به چت پایان داد."
            )

    if isinstance(update, CallbackQuery):
        await update.answer("چت پایان یافت")

    # If admin ended the chat, show the plea menu again
    if is_admin and user_chat_id:
        user = await crud.get_user(session, user_chat_id)
        if user:
            admin_kb = InlineKeyboardBuilder()
            admin_kb.button(
                text="✅ رفع مسدودیت", callback_data=f"unban_user_{user.chat_id}"
            )
            admin_kb.button(
                text="💬 چت", callback_data=f"chat_with_user_{user.chat_id}"
            )
            admin_kb.button(text="👁️ نادیده گرفتن", callback_data="ignore_plea")

            admin_message = (
                f"اقدام بعدی برای کاربر `{user.chat_id}`:\n\n"
                f"کاربر: {user.full_name}"
            )
            await bot.send_message(
                admin_chat_id,
                admin_message,
                reply_markup=admin_kb.as_markup(),
                parse_mode="HTML",
            )


@router.message(lambda msg: msg.from_user.id in admin_to_user)
async def relay_message_to_user(message: Message, bot: Bot):
    """Relay a message from the admin to the user."""
    admin_chat_id = message.from_user.id
    user_chat_id = admin_to_user.get(admin_chat_id)

    if not user_chat_id:
        await message.answer("خطا: چت فعال یافت نشد.")
        return

    try:
        reply_to_user_msg_id = None
        if message.reply_to_message:
            reply_to_user_msg_id = _message_map.get(message.reply_to_message.message_id)

        relayed_msg = await bot.copy_message(
            chat_id=user_chat_id,
            from_chat_id=message.chat.id,
            message_id=message.message_id,
            reply_to_message_id=reply_to_user_msg_id,
        )
        _message_map[relayed_msg.message_id] = message.message_id
    except Exception as e:
        bot_logger.error(f"Failed to relay message to user {user_chat_id}: {e}")
        await message.answer("❌ ارسال پیام با خطا مواجه شد.")


@router.message(IsUserInAdminChat())
async def relay_message_to_admin(message: Message, bot: Bot):
    """Relay a message from a user to the admin they are in a chat with."""
    user_chat_id = message.from_user.id
    admin_chat_id = user_to_admin.get(user_chat_id)

    if not admin_chat_id:
        return

    try:
        reply_to_admin_msg_id = None
        if message.reply_to_message:
            reply_to_admin_msg_id = _message_map.get(message.reply_to_message.message_id)

        relayed_msg = await bot.copy_message(
            chat_id=admin_chat_id,
            from_chat_id=message.chat.id,
            message_id=message.message_id,
            reply_to_message_id=reply_to_admin_msg_id,
        )
        _message_map[relayed_msg.message_id] = message.message_id
    except Exception as e:
        bot_logger.error(
            f"Failed to relay message from {user_chat_id} to admin {admin_chat_id}: {e}"
        )


@router.callback_query(F.data.startswith("plead_unban_"))
async def plead_unban_request(callback: CallbackQuery, session: AsyncSession):
    """Handle a user's request to be unbanned."""
    try:
        user_chat_id = int(callback.data.split("_")[2])
        user = await crud.get_user(session, user_chat_id)

        if not user:
            await callback.answer("❌ کاربر یافت نشد.", show_alert=True)
            return

        await callback.answer("✅ درخواست شما برای بازنگری ارسال شد.", show_alert=True)

        admin_kb = InlineKeyboardBuilder()
        admin_kb.button(
            text="✅ رفع مسدودیت", callback_data=f"unban_user_{user_chat_id}"
        )
        admin_kb.button(
            text="💬 چت", callback_data=f"chat_with_user_{user_chat_id}"
        )
        admin_kb.button(text="👁️ نادیده گرفتن", callback_data="ignore_plea")

        admin_message = (
            f"🙏 <b>درخواست بازنگری برای رفع مسدودیت</b>\n\n"
            f"کاربر: {user.full_name} (`{user.chat_id}`)\n"
            "لطفاً این درخواست را بررسی کنید."
        )

        # Send to all admins
        for admin_id in ADMIN_IDS:
            try:
                await callback.bot.send_message(
                    admin_id,
                    admin_message,
                    reply_markup=admin_kb.as_markup(),
                    parse_mode="HTML",
                )
            except Exception as e:
                bot_logger.error(f"Failed to send plea to admin {admin_id}: {e}")

    except Exception as e:
        bot_logger.error(f"Error in plead_unban_request: {e}")
        await callback.answer("❌ خطای داخلی رخ داد.", show_alert=True)


@router.callback_query(F.data == "ignore_plea")
async def ignore_plea_handler(callback: CallbackQuery, bot: Bot):
    """Handle the admin's choice to ignore a plea."""
    try:
        # Extract user_id from the original message text
        lines = callback.message.text.split("\n")
        user_line = next((line for line in lines if line.startswith("کاربر:")), None)
        if user_line:
            user_id_str = user_line.split("`")[1]
            user_id = int(user_id_str)
            await bot.send_message(
                user_id, "🙏 درخواست بازنگری شما در حال حاضر تایید نشد."
            )
    except Exception as e:
        bot_logger.error(
            f"Could not parse user_id or send notification in ignore_plea_handler: {e}"
        )

    await callback.message.delete()
    await callback.answer("✅ درخواست بازنگری نادیده گرفته شد.")


@router.callback_query(F.data.startswith("unban_user_"))
async def unban_user(callback: CallbackQuery, session: AsyncSession):
    """Unban a user"""
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer(
            t(_lang_for_tg_user(callback.from_user), "not_authorized"),
            show_alert=True,
        )
        return

    user_id = int(callback.data.split("_")[2])

    # Update user status
    await session.execute(
        update(User).filter(User.chat_id == user_id).values(banned=False)
    )
    await session.commit()

    await callback.answer("✅ کاربر رفع مسدودیت شد", show_alert=True)

    # Notify the user
    try:
        await callback.bot.send_message(user_id, "✅ شما از حالت مسدودیت خارج شدید.")
    except Exception as e:
        bot_logger.error(f"Failed to send unban notification to user {user_id}: {e}")

    # Refresh the details view
    await show_user_details(callback, session=session, user_id=user_id)

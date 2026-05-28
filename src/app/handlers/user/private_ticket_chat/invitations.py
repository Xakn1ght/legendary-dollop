from __future__ import annotations

import asyncio
from datetime import datetime

from aiogram import Dispatcher, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import crud
from app.handlers.admin.common import ADMIN_IDS
from app.utils.logger import log_error

from .common import (
    PrivateChatStates,
    control_msg_registry,
    get_chat_keyboard,
    get_invitation_keyboard,
    router,
    safe_edit_message,
)


@router.callback_query(F.data.startswith("admin_sup_start_chat_"))
async def start_private_chat_request(callback: CallbackQuery, session: AsyncSession):
    """Admin initiates a private chat with user"""
    if callback.from_user.id not in ADMIN_IDS:
        from app.utils.bot_i18n import guess_lang_from_telegram, t
        lang = guess_lang_from_telegram(getattr(callback.from_user, "language_code", None))
        await callback.answer(t(lang, "not_authorized"), show_alert=True)
        return

    ticket_id = int(callback.data.removeprefix("admin_sup_start_chat_"))
    ticket = await crud.get_ticket_by_id(session, ticket_id)
    
    if not ticket:
        await callback.answer("تیکت یافت نشد", show_alert=True)
        return
    
    # Check if ticket already has an active chat
    if ticket.is_private_chat and ticket.chat_invitation_accepted and not ticket.chat_ended_at:
        await callback.answer("این تیکت در حال حاضر یک چت خصوصی فعال دارد", show_alert=True)
        return
    
    # Get user information
    user = await crud.get_user_by_id(session, ticket.user_id)
    if not user:
        await callback.answer("کاربر یافت نشد", show_alert=True)
        return
    
    # Make sure admin is in the database
    admin = await crud.get_user_by_id(session, callback.from_user.id)
    if not admin:
        # Create admin user record if it doesn't exist
        from app.database.crud import create_user
        try:
            admin = await create_user(
                session,
                chat_id=callback.message.chat.id,
                username=callback.from_user.username,
                full_name=callback.from_user.full_name
            )
        except Exception as e:
            log_error(e, {"operation": "create_admin_user"})
            await callback.answer("خطا در ایجاد کاربر ادمین", show_alert=True)
            return
    
    # Start the chat process by updating the ticket
    updated_ticket = await crud.start_private_chat(session, ticket_id, callback.from_user.id)
    if not updated_ticket:
        await callback.answer("خطا در شروع چت", show_alert=True)
        return
    
    # Send invitation to the user
    try:
        invitation_text = (
            f"🔔 **درخواست گفتگوی خصوصی**\n\n"
            f"ادمین مایل به گفتگو در مورد تیکت #{ticket_id} شما است.\n"
            f"موضوع تیکت: {ticket.category}\n\n"
            f"این دعوت تا ۱۰ دقیقه دیگر معتبر است."
        )
        
        invitation_msg = await callback.bot.send_message(
            user.chat_id, 
            invitation_text, 
            reply_markup=get_invitation_keyboard(ticket_id),
            parse_mode="Markdown"
        )
        
        # Schedule invitation expiry
        asyncio.create_task(expire_invitation_after_timeout(
            callback.bot, session, ticket_id, user.chat_id, invitation_msg.message_id
        ))
        
        # Notify admin
        await callback.answer("دعوت به گفتگو ارسال شد", show_alert=True)
        await safe_edit_message(
            callback, 
            f"دعوت به گفتگو برای تیکت #{ticket_id} به کاربر ارسال شد.\n"
            f"در حال انتظار برای پاسخ کاربر..."
        )
        
    except Exception as e:
        log_error(e, {"operation": "send_chat_invitation", "ticket_id": ticket_id})
        await callback.answer("خطا در ارسال دعوت", show_alert=True)


async def expire_invitation_after_timeout(bot, session: AsyncSession, ticket_id: int, user_chat_id: int, message_id: int):
    """Expire chat invitation after 10 minutes if not accepted"""
    await asyncio.sleep(10 * 60)  # 10 minutes
    
    # Check if invitation is still pending
    ticket = await crud.get_ticket_by_id(session, ticket_id)
    
    if ticket and ticket.chat_invitation_sent and not ticket.chat_invitation_accepted and not ticket.chat_invitation_expired:
        # Mark invitation as expired
        await crud.expire_chat_invitation(session, ticket_id)
        
        # Update message
        try:
            await bot.edit_message_text(
                "⏱ درخواست گفتگو منقضی شد. ادمین تلاش کرد با شما صحبت کند اما پاسخی دریافت نکرد.",
                chat_id=user_chat_id,
                message_id=message_id,
                reply_markup=InlineKeyboardBuilder().button(
                    text="🔄 درخواست گفتگوی جدید",
                    callback_data=f"chat_request_new_{ticket_id}"
                ).as_markup()
            )
        except Exception as e:
            log_error(e, {"operation": "expire_invitation", "ticket_id": ticket_id})


@router.callback_query(F.data.startswith("chat_accept_"))
async def accept_chat_invitation(callback: CallbackQuery, session: AsyncSession, state: FSMContext, dispatcher: Dispatcher):
    """User accepts chat invitation"""
    ticket_id = int(callback.data.removeprefix("chat_accept_"))
    
    # Get ticket and verify it's valid for accepting
    ticket = await crud.get_ticket_by_id(session, ticket_id)
    
    if not ticket or not ticket.chat_invitation_sent or ticket.chat_invitation_expired:
        await callback.answer("این دعوت دیگر معتبر نیست", show_alert=True)
        return
    
    # Mark invitation as accepted
    updated_ticket = await crud.accept_chat_invitation(session, ticket_id)
    if not updated_ticket:
        await callback.answer("خطا در پذیرش دعوت", show_alert=True)
        return
    
    # Get admin chat ID
    admin = await crud.get_user_by_id(session, ticket.assigned_admin_id)
    if not admin:
        # If assigned admin not found, try to use the default admin ID
        from app.core.settings import ADMIN_ID, ADMIN_USERNAME
        admin = await crud.get_user_by_id(session, ADMIN_ID)
        
        # If admin still not found, create admin record
        if not admin:
            from app.database.crud import create_user
            try:
                # Create admin user with default values
                admin = await create_user(
                    session,
                    chat_id=ADMIN_ID,  # Use admin ID as chat_id
                    username=ADMIN_USERNAME or "admin",
                    full_name="Administrator"
                )
                
                # Update the ticket with the new admin ID
                ticket.assigned_admin_id = ADMIN_ID
                await session.commit()
                
                # If still couldn't create admin
                if not admin:
                    await callback.answer("ادمین یافت نشد", show_alert=True)
                    await safe_edit_message(
                        callback,
                        "متاسفانه ادمین در دسترس نیست. لطفا بعدا دوباره امتحان کنید."
                    )
                    return
            except Exception as e:
                log_error(e, {"operation": "create_admin_user_during_chat_accept"})
                await callback.answer("خطا در برقراری ارتباط با ادمین", show_alert=True)
                await safe_edit_message(
                    callback,
                    "متاسفانه مشکلی در ارتباط با ادمین پیش آمد. لطفا بعدا دوباره امتحان کنید."
                )
                return
    
    # Setup FSM for user
    await state.set_state(PrivateChatStates.in_chat)
    await state.update_data(ticket_id=ticket_id, partner_chat_id=admin.chat_id, role="user")
    # Remember user's control message id (the message being edited by this callback)
    user_control_msg_id = callback.message.message_id

    # Setup FSM for admin (send a message to admin's chat to set context)
    from app.utils.logger import bot_logger
    bot_logger.info(f"DEBUG: Setting FSM for admin | Admin chat_id: {admin.chat_id}")
    try:
        key = StorageKey(bot_id=callback.bot.id, chat_id=admin.chat_id, user_id=admin.chat_id)
        admin_state = FSMContext(storage=dispatcher.storage, key=key)
        await admin_state.set_state(PrivateChatStates.in_chat)
        await admin_state.update_data(ticket_id=ticket_id, partner_chat_id=callback.message.chat.id, role="admin")
        bot_logger.info(f"DEBUG: Admin FSM set successfully for chat_id {admin.chat_id}")
    except Exception as e:
        bot_logger.error(f"DEBUG: Failed to set FSM for admin | {str(e)}")
        # Send error message to admin
        await callback.bot.send_message(admin.chat_id, "خطا در تنظیم چت خصوصی. لطفا دوباره امتحان کنید.")

    # Notify both
    await safe_edit_message(
        callback,
        "✅ گفتگوی خصوصی آغاز شد. پیام‌های شما به ادمین کپی می‌شود.",
        reply_markup=get_chat_keyboard()
    )
    
    admin_sent = await callback.bot.send_message(
        admin.chat_id,
        "✅ چت شروع شد. پیام‌های شما به کاربر کپی می‌شود.",
        reply_markup=get_chat_keyboard()
    )

    # Track control messages for later cleanup
    control_msg_registry[ticket_id] = {
        'user_msg_id': user_control_msg_id,
        'admin_msg_id': admin_sent.message_id,
        'user_chat_id': callback.message.chat.id,
        'admin_chat_id': admin.chat_id,
    }


@router.callback_query(F.data.startswith("chat_reject_"))
async def reject_chat_invitation(callback: CallbackQuery, session: AsyncSession):
    """User rejects chat invitation"""
    ticket_id = int(callback.data.removeprefix("chat_reject_"))
    
    # Get ticket
    ticket = await crud.get_ticket_by_id(session, ticket_id)
    
    if not ticket:
        await callback.answer("تیکت یافت نشد", show_alert=True)
        return
    
    # Mark invitation as expired (rejected)
    await crud.expire_chat_invitation(session, ticket_id)
    
    # Notify both parties
    await safe_edit_message(
        callback,
        "❌ دعوت به گفتگو رد شد."
    )
    
    # Notify admin
    try:
        admin = await crud.get_user_by_id(session, ticket.assigned_admin_id)
        if not admin:
            # Try with default admin ID if assigned admin not found
            from app.core.settings import ADMIN_ID
            admin = await crud.get_user_by_id(session, ADMIN_ID)
            
        if admin and admin.chat_id:
            await callback.bot.send_message(
                admin.chat_id,
                f"❌ کاربر دعوت گفتگو برای تیکت #{ticket_id} را رد کرد."
            )
    except Exception as e:
        log_error(e, {"operation": "notify_chat_rejection", "ticket_id": ticket_id})


@router.callback_query(F.data.startswith("chat_request_new_"))
async def request_new_chat(callback: CallbackQuery, session: AsyncSession):
    """User requests a new chat after expiration"""
    ticket_id = int(callback.data.removeprefix("chat_request_new_"))
    
    # Get ticket
    ticket = await crud.get_ticket_by_id(session, ticket_id)
    
    if not ticket:
        await callback.answer("تیکت یافت نشد", show_alert=True)
        return
    
    # Reset chat invitation flags but keep private chat flag
    ticket.chat_invitation_sent = False
    ticket.chat_invitation_expired = False
    ticket.chat_invitation_accepted = False
    ticket.updated_at = datetime.utcnow()
    await session.commit()
    
    # Notify admin
    try:
        # First try to get assigned admin
        admin = await crud.get_user_by_id(session, ticket.assigned_admin_id)
        
        # If not found, try default admin
        if not admin:
            from app.core.settings import ADMIN_ID, ADMIN_USERNAME
            admin = await crud.get_user_by_id(session, ADMIN_ID)
            
            # If admin still not found, create admin record
            if not admin:
                from app.database.crud import create_user
                try:
                    # Create admin user with default values
                    admin = await create_user(
                        session,
                        chat_id=ADMIN_ID,  # Use admin ID as chat_id
                        username=ADMIN_USERNAME or "admin",
                        full_name="Administrator"
                    )
                except Exception as e:
                    log_error(e, {"operation": "create_admin_user"})
        
        if admin and admin.chat_id:
            kb = InlineKeyboardBuilder()
            kb.button(text="✅ شروع گفتگو", callback_data=f"admin_sup_start_chat_{ticket_id}")
            kb.adjust(1)
            
            await callback.bot.send_message(
                admin.chat_id,
                f"🔔 کاربر درخواست گفتگوی جدید برای تیکت #{ticket_id} دارد.",
                reply_markup=kb.as_markup()
            )
            
            await callback.answer("درخواست شما به ادمین ارسال شد", show_alert=True)
        else:
            await callback.answer("ادمین یافت نشد", show_alert=True)
            await safe_edit_message(
                callback,
                "متاسفانه در حال حاضر ادمین در دسترس نیست. لطفا از طریق پشتیبانی معمولی اقدام کنید."
            )
    except Exception as e:
        log_error(e, {"operation": "request_new_chat", "ticket_id": ticket_id})

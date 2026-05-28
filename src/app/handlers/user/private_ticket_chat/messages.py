from __future__ import annotations

from aiogram import F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import crud
from app.database.models import TicketMessage
from app.handlers.admin.common import ADMIN_IDS

from .common import PrivateChatStates, last_db_message_id, message_map, router, safe_edit_message
from .forwarding import forward_message_between_chats


@router.message(PrivateChatStates.in_chat)
async def handle_chat_message(message: Message, state: FSMContext, session: AsyncSession):
    from app.utils.logger import bot_logger
    bot_logger.info(f"DEBUG: FSM handler triggered for chat_id {message.chat.id} | User_id {message.from_user.id}")
    data = await state.get_data()
    ticket_id = data.get("ticket_id")
    partner_chat_id = data.get("partner_chat_id")
    role = data.get("role")

    bot_logger.info(f"DEBUG: Handler triggered for {role} | Ticket: {ticket_id} | Partner: {partner_chat_id}")

    if not ticket_id or not partner_chat_id:
        bot_logger.info(f"DEBUG: Invalid data for {role} | ticket_id: {ticket_id} | partner_chat_id: {partner_chat_id}")
        await message.answer("خطا: جلسه چت معتبر نیست.")
        return

    bot_logger.info(f"DEBUG: Calling forward_message_between_chats for {role}")
    # Relay the message
    try:
        await forward_message_between_chats(message, session, partner_chat_id, ticket_id, role)
    except Exception as e:
        bot_logger.error(f"DEBUG: Exception in forward_message_between_chats | {str(e)}")
        await message.reply("خطا در ارسال پیام به طرف مقابل")


@router.edited_message(PrivateChatStates.in_chat, F.text)
async def handle_edited_text(message: Message, state: FSMContext, session: AsyncSession):
    from app.utils.logger import bot_logger
    data = await state.get_data()
    ticket_id = data.get("ticket_id")
    role = data.get("role")
    partner_chat_id = data.get("partner_chat_id")
    if not ticket_id or not role:
        return
    key = (ticket_id, role, message.message_id)
    db_msg_id = last_db_message_id.get(key)
    if not db_msg_id:
        # try DB lookup by telegram id
        try:
            m = await crud.get_ticket_message_by_telegram_id(session, message.message_id)
            if m:
                db_msg_id = m.id
        except Exception:
            db_msg_id = None
    if not db_msg_id:
        return
    try:
        # Update the stored text for the edited message both by DB id and by telegram_message_id for safety
        safe_text = message.text or ""
        try:
            if db_msg_id:
                await session.execute(update(TicketMessage).where(TicketMessage.id == db_msg_id).values(text=safe_text))
                await session.commit()
            # Also ensure row is updated if only telegram id is known
            await crud.update_ticket_message_text_by_telegram_id(session, message.message_id, safe_text)
        except Exception:
            # Fallback only by telegram id
            await crud.update_ticket_message_text_by_telegram_id(session, message.message_id, safe_text)
        bot_logger.info(f"DEBUG: Synced edited message text for db_id={db_msg_id} ticket={ticket_id}")
        # Also edit the mirrored copy in partner chat if we have its message id
        try:
            target_msg_id = message_map.get((ticket_id, message.message_id))
            if target_msg_id and partner_chat_id:
                await message.bot.edit_message_text(
                    safe_text,
                    chat_id=partner_chat_id,
                    message_id=target_msg_id
                )
                bot_logger.info(f"DEBUG: Mirrored edit applied | ticket={ticket_id} target_msg_id={target_msg_id}")
        except Exception as e:
            bot_logger.error(f"DEBUG: Failed editing mirrored message | {e}")
    except Exception as e:
        bot_logger.error(f"DEBUG: Failed syncing edited text | {e}")


@router.message(F.from_user.id.in_(ADMIN_IDS))
async def handle_admin_message_passthrough(message: Message, state: FSMContext, session: AsyncSession):
    """Ensure admin messages are relayed when admin is in chat state.
    This bypasses any potential handler ordering/filter issues.
    """
    from app.utils.logger import bot_logger
    current_state = await state.get_state()
    if current_state != PrivateChatStates.in_chat.state:
        return  # Admin not in private chat session

    data = await state.get_data()
    ticket_id = data.get("ticket_id")
    partner_chat_id = data.get("partner_chat_id")
    role = data.get("role") or "admin"

    bot_logger.info(f"DEBUG: Admin passthrough | State={current_state} | Ticket: {ticket_id} | Partner: {partner_chat_id}")

    if not ticket_id or not partner_chat_id:
        await message.answer("خطا: جلسه چت معتبر نیست.")
        return

    try:
        await forward_message_between_chats(message, session, partner_chat_id, ticket_id, role)
    except Exception as e:
        bot_logger.error(f"DEBUG: Admin passthrough exception | {str(e)}")
        await message.reply("خطا در ارسال پیام به طرف مقابل")

@router.callback_query(F.data.startswith("admin_sup_active_chats"))
async def list_active_chats(callback: CallbackQuery, session: AsyncSession):
    """List all active private chats for admin"""
    if callback.from_user.id not in ADMIN_IDS:
        from app.utils.bot_i18n import guess_lang_from_telegram, t
        lang = guess_lang_from_telegram(getattr(callback.from_user, "language_code", None))
        await callback.answer(t(lang, "not_authorized"), show_alert=True)
        return
    
    active_chats = await crud.get_active_chat_tickets(session)
    
    if not active_chats:
        await safe_edit_message(callback, "هیچ گفتگوی خصوصی فعالی وجود ندارد.")
        await callback.answer()
        return
    
    kb = InlineKeyboardBuilder()
    for chat in active_chats:
        user = await crud.get_user_by_id(session, chat.user_id)
        user_name = user.full_name or user.username or f"User {user.id}"
        
        kb.button(
            text=f"#{chat.id} | {user_name} | {chat.category}",
            callback_data=f"admin_sup_open_{chat.id}"
        )
    
    kb.adjust(1)
    kb.button(text="⬅️ بازگشت", callback_data="admin_sup_back_main")
    
    await safe_edit_message(callback, "گفتگوهای خصوصی فعال:", kb.as_markup())
    await callback.answer()

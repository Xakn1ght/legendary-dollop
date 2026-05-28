from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.shared.admin_access import ADMIN_IDS
from app.utils.logger import bot_logger

from .common import router


@router.message(lambda m: m.from_user.id in ADMIN_IDS)
async def admin_private_chat_relay(
    message: Message, state: FSMContext, session: AsyncSession
):
    from app.handlers.user.private_ticket_chat import (
        PrivateChatStates,
        forward_message_between_chats,
    )

    current_state = await state.get_state()
    if current_state != PrivateChatStates.in_chat.state:
        return

    data = await state.get_data()
    ticket_id = data.get("ticket_id")
    partner_chat_id = data.get("partner_chat_id")
    if not ticket_id or not partner_chat_id:
        bot_logger.info(
            f"DEBUG: Admin relay skipped due to missing data | ticket_id={ticket_id} partner={partner_chat_id}"
        )
        return

    try:
        await forward_message_between_chats(
            message, session, partner_chat_id, ticket_id, "admin"
        )
    except Exception as e:
        bot_logger.error(f"DEBUG: Admin relay failed | {str(e)}")


# Debug handler - placed at the end to act as catch-all
@router.message(lambda m: m.from_user.id in ADMIN_IDS)
async def debug_admin_messages(message: Message, state: FSMContext):
    """Debug handler to log all admin messages and their FSM state"""
    current_state = await state.get_state()
    state_data = await state.get_data()
    bot_logger.info(
        f"DEBUG: Admin {message.from_user.id} sent message '{message.text}' | Current FSM state: {current_state} | State data: {state_data}"
    )
    # Don't process the message here, just log it

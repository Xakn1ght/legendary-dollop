from __future__ import annotations

from typing import Dict

from aiogram import Router
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

router = Router()

# Track message IDs for reply functionality
# Key: (ticket_id, telegram_message_id), Value: original_message_id_in_other_chat
message_map: Dict[tuple[int, int], int] = {}

# Buffer for media groups (albums)
# Key: (ticket_id, target_chat_id, media_group_id)
album_buffers: Dict[tuple[int, int, str], dict] = {}

# Store control message IDs to allow keyboard cleanup on end
# ticket_id -> { 'user_msg_id': int, 'admin_msg_id': int, 'user_chat_id': int, 'admin_chat_id': int }
control_msg_registry: Dict[int, Dict[str, int]] = {}

# Keep minimal cache of last sent DB message per (ticket_id, sender, telegram_message_id)
last_db_message_id: Dict[tuple[int, str, int], int] = {}

# FSM states for private chat
class PrivateChatStates(StatesGroup):
    waiting_for_response = State()
    in_chat = State()
    waiting_for_media = State()


async def safe_edit_message(callback: CallbackQuery, text: str, reply_markup=None):
    """Safely edit message with fallback to sending new message."""
    try:
        await callback.message.edit_text(text, reply_markup=reply_markup)
    except Exception:
        # Fallback: send new message if edit fails
        await callback.message.answer(text, reply_markup=reply_markup)


def get_chat_keyboard():
    """Keyboard for active chat session"""
    kb = InlineKeyboardBuilder()
    kb.button(text="🔚 پایان گفتگو", callback_data="private_chat_end")
    kb.adjust(1)
    return kb.as_markup()


def get_invitation_keyboard(ticket_id: int):
    """Keyboard for chat invitation"""
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ قبول کردن", callback_data=f"chat_accept_{ticket_id}")
    kb.button(text="❌ رد کردن", callback_data=f"chat_reject_{ticket_id}")
    kb.adjust(2)
    return kb.as_markup()

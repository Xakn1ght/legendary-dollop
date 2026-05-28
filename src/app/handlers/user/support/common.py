from __future__ import annotations

from typing import List

from aiogram import Router
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

router = Router()


class SupportStates(StatesGroup):
    choosing_category = State()
    choosing_subscription = State()
    connection_choose_os = State()
    connection_choose_isp = State()
    collecting_texts = State()  # legacy
    collecting_images = State()  # legacy
    review = State()  # legacy
    adding_message = State()  # legacy
    editing_text = State()  # legacy
    # --- New simplified flow ---
    description_one = State()
    ask_images = State()
    images_two = State()
    confirm_simple = State()
    edit_description = State()
    # --- Private chat states ---
    private_chat_active = State()
    private_chat_waiting = State()


def _two_column_builder(labels_and_callbacks: List[tuple[str, str]], back_cb: str = "back_main") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for text, cb in labels_and_callbacks:
        builder.button(text=text, callback_data=cb)
    builder.adjust(2)
    builder.button(text="بازگشت🔙", callback_data=back_cb)
    return builder.as_markup()


def _mask_sensitive(text: str) -> str:
    """Redact share-link tokens and config URIs from user-provided text."""
    import re

    if not text:
        return text
    # Mask /sub/<token>
    text = re.sub(r"/sub/[A-Za-z0-9_\-]+", "/sub/****", text)
    # Mask vmess/vless/trojan URIs
    text = re.sub(r"\b(vmess|vless|trojan)://[A-Za-z0-9+/=\-_.:;?@#&%]+", r"\1://…", text)
    return text


async def safe_edit_message(callback: CallbackQuery, text: str, reply_markup=None):
    """Safely edit message with fallback to sending new message."""
    try:
        await callback.message.edit_text(text, reply_markup=reply_markup)
    except Exception:
        # Fallback: send new message if edit fails
        await callback.message.answer(text, reply_markup=reply_markup)


def _controls_markup_simple() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✏️ ویرایش متن", callback_data="support_edit_desc")
    builder.button(text="✅ ارسال", callback_data="support_send")
    builder.adjust(1)
    builder.button(text="بازگشت🔙", callback_data="support_back_main")
    return builder.as_markup()


def _images_step_kb(current: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="➡️ ادامه و نوشتن متن", callback_data="support_continue_to_text")
    builder.adjust(1)
    builder.button(text="بازگشت🔙", callback_data="support_back_main")
    return builder.as_markup()


def _text_confirmation_kb(idx: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="✏️ ویرایش", callback_data=f"support_text_edit_{idx}")
    kb.button(text="🗑 حذف", callback_data=f"support_text_del_{idx}")
    kb.button(text="✅ ارسال", callback_data="support_send")
    kb.adjust(2)
    kb.button(text="بازگشت🔙", callback_data="support_back_main")
    return kb.as_markup()


def _image_confirmation_kb(idx: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="🗑 حذف", callback_data=f"support_img_del_{idx}")
    kb.button(text="✅ ارسال", callback_data="support_send")
    kb.adjust(2)
    kb.button(text="بازگشت🔙", callback_data="support_back_main")
    return kb.as_markup()

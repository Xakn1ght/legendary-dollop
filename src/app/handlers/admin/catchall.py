"""Quiet fallback for callbacks from retired admin-bot menus.

The menu-navigation surfaces were removed 2026-07-21 (the admin web panel
replaced them), but old messages with inline buttons may still sit in the
admin's chat history. Registered VERY LAST in admin_main so it only fires
when no surviving handler matched the callback.
"""

from aiogram import Router
from aiogram.types import CallbackQuery, WebAppInfo
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.core.settings import DASHBOARD_PUBLIC_BASE_URL
from app.shared.admin_access import ADMIN_IDS

router = Router()

_MOVED_TEXT = "این بخش به پنل منتقل شد"


def _panel_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="باز کردن پنل ادمین", web_app=WebAppInfo(url=f"{DASHBOARD_PUBLIC_BASE_URL}/admin/"))
    kb.adjust(1)
    return kb.as_markup()


@router.callback_query()
async def retired_menu_callback(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer()
        return
    await callback.answer(_MOVED_TEXT)
    # Replace the stale menu message with the pointer to the panel so the
    # dead buttons disappear instead of soaking up more taps.
    try:
        if callback.message.photo:
            await callback.message.edit_caption(caption=_MOVED_TEXT, reply_markup=_panel_kb())
        else:
            await callback.message.edit_text(_MOVED_TEXT, reply_markup=_panel_kb())
    except Exception:
        try:
            await callback.message.answer(_MOVED_TEXT, reply_markup=_panel_kb())
        except Exception:
            pass

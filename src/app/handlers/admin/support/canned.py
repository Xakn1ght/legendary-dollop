from aiogram import F
from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import CANNED_RESPONSES
from app.database import crud
from app.database.crud import get_user_by_id
from app.handlers.admin.common import ADMIN_IDS
from app.utils.admin_bot_helper import get_user_bot
from app.utils.bot_i18n import t

from .common import _lang_for_tg_user, router, safe_edit_message
from .ticket_detail import render_ticket_view


@router.callback_query(F.data == "admin_sup_canned")
async def admin_canned(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer(
            t(_lang_for_tg_user(callback.from_user), "not_authorized"),
            show_alert=True,
        )
        return
    kb = InlineKeyboardBuilder()
    kb.button(text="➕ افزودن", callback_data="admin_sup_canned_add")
    kb.button(text="🗑 حذف", callback_data="admin_sup_canned_del")
    kb.button(text="⬅️ بازگشت", callback_data="admin_sup_back_main")
    kb.adjust(2)
    await safe_edit_message(callback, "مدیریت پاسخ‌های آماده:", kb.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("admin_sup_canned_reply_"))
async def admin_canned_reply_select_category(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer(
            t(_lang_for_tg_user(callback.from_user), "not_authorized"),
            show_alert=True,
        )
        return
    ticket_id = int(callback.data.removeprefix("admin_sup_canned_reply_"))
    kb = InlineKeyboardBuilder()
    cats = sorted({r.get("category", "all") or "all" for r in CANNED_RESPONSES})
    for c in cats:
        kb.button(text=c, callback_data=f"admin_sup_canned_pick_{ticket_id}_{c}")
    kb.adjust(2)
    kb.button(text="⬅️ بازگشت", callback_data=f"admin_sup_open_{ticket_id}")
    await safe_edit_message(callback, "انتخاب دسته پاسخ آماده:", kb.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("admin_sup_canned_pick_"))
async def admin_canned_pick(callback: CallbackQuery, session: AsyncSession):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer(
            t(_lang_for_tg_user(callback.from_user), "not_authorized"),
            show_alert=True,
        )
        return
    parts = callback.data.split("_")
    ticket_id = int(parts[4])
    cat = parts[5]
    items = [r for r in CANNED_RESPONSES if (r.get("category") or "all") == cat]
    kb = InlineKeyboardBuilder()
    for i, r in enumerate(items):
        kb.button(
            text=r.get("title", f"#{i + 1}"),
            callback_data=f"admin_sup_canned_send_{ticket_id}_{i}",
        )
    kb.adjust(1)
    kb.button(text="⬅️ بازگشت", callback_data=f"admin_sup_open_{ticket_id}")
    await safe_edit_message(callback, "انتخاب پاسخ:", kb.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("admin_sup_canned_send_"))
async def admin_canned_send(callback: CallbackQuery, session: AsyncSession):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer(
            t(_lang_for_tg_user(callback.from_user), "not_authorized"),
            show_alert=True,
        )
        return
    parts = callback.data.split("_")
    ticket_id = int(parts[4])
    idx = int(parts[5])
    item = CANNED_RESPONSES[idx]
    body = item.get("body", "")
    await crud.add_ticket_message(
        session, ticket_id, sender="admin", content_type="text", text=body
    )
    tkt = await crud.get_ticket_by_id(session, ticket_id)
    user = await get_user_by_id(session, tkt.user_id)
    try:
        # DM the user via the USER bot (this handler runs on the admin bot)
        await (get_user_bot() or callback.bot).send_message(
            user.chat_id, f"پاسخ ادمین به تیکت #{tkt.id}:\n{body}"
        )
    except Exception:
        pass
    await render_ticket_view(callback, session, ticket_id)
    await callback.answer("ارسال شد.")

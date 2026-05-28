from aiogram import F
from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import crud
from app.database.models import Subscription
from app.handlers.admin.common import ADMIN_IDS
from app.utils.bot_i18n import t

from .common import _lang_for_tg_user, router, safe_edit_message


@router.callback_query(F.data.startswith("admin_sup_cat_"))
async def admin_list_category(callback: CallbackQuery, session: AsyncSession):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer(
            t(_lang_for_tg_user(callback.from_user), "not_authorized"),
            show_alert=True,
        )
        return
    category = callback.data.removeprefix("admin_sup_cat_")
    tickets = await crud.list_tickets_by_category(session, category, limit=50)
    kb = InlineKeyboardBuilder()
    for tkt in tickets:
        title = f"#{tkt.id} | {tkt.status} | u{tkt.user_id}"
        if tkt.subscription_id:
            sub = await session.get(Subscription, tkt.subscription_id)
            if sub:
                title += f" | 🔗{sub.marzban_username}"
        if tkt.category == "connection":
            title += f" | {tkt.os or '-'} / {tkt.isp or '-'}"
        kb.button(text=title, callback_data=f"admin_sup_open_{tkt.id}")
    kb.adjust(1)
    kb.button(text="⬅️ بازگشت", callback_data="admin_sup_back_main")
    await safe_edit_message(callback, f"تیکت‌های دسته {category}:", kb.as_markup())
    await callback.answer()


@router.callback_query(F.data == "admin_sup_all")
async def admin_list_all(callback: CallbackQuery, session: AsyncSession):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer(
            t(_lang_for_tg_user(callback.from_user), "not_authorized"),
            show_alert=True,
        )
        return
    tickets = await crud.list_all_tickets(session, limit=50)
    kb = InlineKeyboardBuilder()
    for tkt in tickets:
        title = f"#{tkt.id} | {tkt.category} | {tkt.status} | u{tkt.user_id}"
        if tkt.subscription_id:
            sub = await session.get(Subscription, tkt.subscription_id)
            if sub:
                title += f" | 🔗{sub.marzban_username}"
        kb.button(text=title, callback_data=f"admin_sup_open_{tkt.id}")
    kb.adjust(1)
    kb.button(text="⬅️ بازگشت", callback_data="admin_sup_back_main")
    await safe_edit_message(callback, "همه تیکت‌ها:", kb.as_markup())
    await callback.answer()

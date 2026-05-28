from datetime import datetime

from aiogram import F
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import SUPPORT_CATEGORIES
from app.database.models import Ticket
from app.handlers.admin.common import ADMIN_IDS
from app.utils.bot_i18n import t

from .common import (
    _lang_for_tg_user,
    _support_main_keyboard,
    router,
    safe_edit_message,
)


@router.message(Command("support"))
@router.message(F.text.startswith("/support"))
@router.message(F.text == "🎫 پشتیبانی")
async def admin_support_menu(message: Message, session: AsyncSession):
    if message.from_user.id not in ADMIN_IDS:
        return

    counts: dict[str, int] = {}
    total_stats = {
        "pending": 0,
        "open": 0,
        "closed_today": 0,
        "avg_response_time": 0,
    }

    for cat in SUPPORT_CATEGORIES:
        key = cat["key"]
        result = await session.execute(
            select(func.count(Ticket.id)).where(
                Ticket.category == key, Ticket.status.in_(["pending", "open"])
            )
        )
        counts[key] = int(result.scalar() or 0)

    pending_result = await session.execute(
        select(func.count(Ticket.id)).where(Ticket.status == "pending")
    )
    total_stats["pending"] = int(pending_result.scalar() or 0)

    open_result = await session.execute(
        select(func.count(Ticket.id)).where(Ticket.status == "open")
    )
    total_stats["open"] = int(open_result.scalar() or 0)

    today = datetime.utcnow().date()
    closed_today_result = await session.execute(
        select(func.count(Ticket.id)).where(
            Ticket.status == "closed",
            func.date(Ticket.closed_at) == today,
        )
    )
    total_stats["closed_today"] = int(closed_today_result.scalar() or 0)

    dashboard_text = (
        f"🎯 **داشبورد پشتیبانی**\n\n"
        f"📊 **آمار کلی:**\n"
        f"• 🟡 در صف: {total_stats['pending']}\n"
        f"• 🟢 در حال بررسی: {total_stats['open']}\n"
        f"• ✅ بسته شده امروز: {total_stats['closed_today']}\n\n"
        f"📈 **آمار دسته‌بندی:**\n"
    )

    for cat in SUPPORT_CATEGORIES:
        key = cat["key"]
        label = cat["label"]
        count = counts[key]
        dashboard_text += f"• {label}: {count}\n"

    kb = InlineKeyboardBuilder()

    for cat in SUPPORT_CATEGORIES:
        key = cat["key"]
        label = cat["label"]
        count = counts[key]
        kb.button(text=f"{label} ({count})", callback_data=f"admin_sup_cat_{key}")

    kb.button(text="💬 چت‌های فعال", callback_data="admin_sup_active_chats")
    kb.button(text="📊 آمار تفصیلی", callback_data="admin_sup_analytics")
    kb.button(text="⚡ عملیات گروهی", callback_data="admin_sup_bulk")
    kb.button(text="📄 پاسخ‌های آماده", callback_data="admin_sup_canned")
    kb.button(text="⚙️ تنظیمات", callback_data="admin_sup_settings")

    kb.adjust(2, 3)

    await message.answer(
        dashboard_text, reply_markup=kb.as_markup(), parse_mode="Markdown"
    )


@router.callback_query(F.data == "admin_sup_back_main")
async def admin_sup_back_main(callback: CallbackQuery, session: AsyncSession):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer(
            t(_lang_for_tg_user(callback.from_user), "not_authorized"),
            show_alert=True,
        )
        return
    counts: dict[str, int] = {}
    for cat in SUPPORT_CATEGORIES:
        key = cat["key"]
        result = await session.execute(
            select(func.count(Ticket.id)).where(
                Ticket.category == key, Ticket.status.in_(["pending", "open"])
            )
        )
        counts[key] = int(result.scalar() or 0)
    kb = _support_main_keyboard(counts)
    await safe_edit_message(
        callback, "مدیریت پشتیبانی – یک دسته را انتخاب کنید:", kb.as_markup()
    )
    await callback.answer()

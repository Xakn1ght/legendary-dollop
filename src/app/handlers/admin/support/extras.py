from datetime import datetime, timedelta

from aiogram import F
from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import SUPPORT_CATEGORIES
from app.database import crud
from app.database.models import Ticket
from app.handlers.admin.common import ADMIN_IDS
from app.utils.bot_i18n import t

from .common import _lang_for_tg_user, router, safe_edit_message


@router.callback_query(F.data == "admin_sup_analytics")
async def admin_support_analytics(callback: CallbackQuery, session: AsyncSession):
    """Detailed support analytics"""
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer(
            t(_lang_for_tg_user(callback.from_user), "not_authorized"),
            show_alert=True,
        )
        return

    week_ago = datetime.utcnow() - timedelta(days=7)

    week_tickets_result = await session.execute(
        select(func.count(Ticket.id)).where(Ticket.created_at >= week_ago)
    )
    week_tickets = int(week_tickets_result.scalar() or 0)

    week_closed_result = await session.execute(
        select(func.count(Ticket.id)).where(
            Ticket.status == "closed",
            Ticket.closed_at >= week_ago,
        )
    )
    week_closed = int(week_closed_result.scalar() or 0)

    avg_response_result = await session.execute(
        select(
            func.avg(
                func.julianday(Ticket.closed_at) - func.julianday(Ticket.created_at)
            )
        ).where(Ticket.status == "closed")
    )
    avg_response_days = float(avg_response_result.scalar() or 0)
    avg_response_hours = avg_response_days * 24

    category_stats = {}
    for cat in SUPPORT_CATEGORIES:
        key = cat["key"]
        result = await session.execute(
            select(func.count(Ticket.id)).where(Ticket.category == key)
        )
        category_stats[key] = int(result.scalar() or 0)

    analytics_text = (
        f"📊 **آمار تفصیلی پشتیبانی**\n\n"
        f"📈 **آمار هفته گذشته:**\n"
        f"• تیکت‌های جدید: {week_tickets}\n"
        f"• تیکت‌های بسته شده: {week_closed}\n"
        f"• میانگین زمان پاسخ: {avg_response_hours:.1f} ساعت\n\n"
        f"📋 **توزیع دسته‌بندی:**\n"
    )

    for cat in SUPPORT_CATEGORIES:
        key = cat["key"]
        label = cat["label"]
        count = category_stats[key]
        analytics_text += f"• {label}: {count}\n"

    kb = InlineKeyboardBuilder()
    kb.button(text="🔄 بروزرسانی", callback_data="admin_sup_analytics")
    kb.button(text="📤 گزارش CSV", callback_data="admin_sup_export")
    kb.button(text="⬅️ بازگشت", callback_data="admin_sup_back_main")
    kb.adjust(2)

    await safe_edit_message(callback, analytics_text, kb.as_markup())
    await callback.answer()


@router.callback_query(F.data == "admin_sup_bulk")
async def admin_support_bulk_operations(callback: CallbackQuery, session: AsyncSession):
    """Bulk operations for tickets"""
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer(
            t(_lang_for_tg_user(callback.from_user), "not_authorized"),
            show_alert=True,
        )
        return

    pending_tickets = await crud.list_all_tickets(session, status="pending", limit=20)

    bulk_text = (
        f"⚡ **عملیات گروهی**\n\n"
        f"📋 تیکت‌های در صف: {len(pending_tickets)}\n\n"
        f"**عملیات موجود:**\n"
        f"• اختصاص همه به من\n"
        f"• تغییر اولویت همه\n"
        f"• ارسال پاسخ گروهی\n"
        f"• بستن تیکت‌های قدیمی"
    )

    kb = InlineKeyboardBuilder()
    kb.button(text="📌 اختصاص همه به من", callback_data="admin_sup_bulk_assign")
    kb.button(text="⚖️ تغییر اولویت", callback_data="admin_sup_bulk_priority")
    kb.button(text="📨 پاسخ گروهی", callback_data="admin_sup_bulk_reply")
    kb.button(text="🗑 بستن قدیمی‌ها", callback_data="admin_sup_bulk_close_old")
    kb.button(text="⬅️ بازگشت", callback_data="admin_sup_back_main")
    kb.adjust(2)

    await safe_edit_message(callback, bulk_text, kb.as_markup())
    await callback.answer()


@router.callback_query(F.data == "admin_sup_bulk_assign")
async def admin_support_bulk_assign(callback: CallbackQuery, session: AsyncSession):
    """Assign all pending tickets to current admin"""
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer(
            t(_lang_for_tg_user(callback.from_user), "not_authorized"),
            show_alert=True,
        )
        return

    pending_tickets = await crud.list_all_tickets(session, status="pending", limit=100)

    assigned_count = 0
    for ticket in pending_tickets:
        await crud.assign_ticket(session, ticket.id, callback.from_user.id)
        assigned_count += 1

    await callback.answer(
        f"{assigned_count} تیکت به شما اختصاص یافت.", show_alert=True
    )

    await admin_support_bulk_operations(callback, session)


@router.callback_query(F.data == "admin_sup_settings")
async def admin_support_settings(callback: CallbackQuery):
    """Support system settings"""
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer(
            t(_lang_for_tg_user(callback.from_user), "not_authorized"),
            show_alert=True,
        )
        return

    settings_text = (
        f"⚙️ **تنظیمات پشتیبانی**\n\n"
        f"**تنظیمات فعلی:**\n"
        f"• زمان یادآوری: 2 ساعت\n"
        f"• بستن خودکار: 3 روز\n"
        f"• میانگین زمان پاسخ: 10 دقیقه\n\n"
        f"**گزینه‌های تنظیمات:**\n"
        f"• تغییر زمان یادآوری\n"
        f"• تنظیم بستن خودکار\n"
        f"• مدیریت پاسخ‌های آماده\n"
        f"• تنظیمات اعلان‌ها"
    )

    kb = InlineKeyboardBuilder()
    kb.button(text="⏰ زمان یادآوری", callback_data="admin_sup_set_reminder")
    kb.button(text="🔒 بستن خودکار", callback_data="admin_sup_set_autoclose")
    kb.button(text="📄 پاسخ‌های آماده", callback_data="admin_sup_canned")
    kb.button(text="🔔 اعلان‌ها", callback_data="admin_sup_notifications")
    kb.button(text="⬅️ بازگشت", callback_data="admin_sup_back_main")
    kb.adjust(2)

    await safe_edit_message(callback, settings_text, kb.as_markup())
    await callback.answer()

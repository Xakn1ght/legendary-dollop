from datetime import datetime

from aiogram import F
from aiogram.types import Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import ChargeRequest, Subscription, User
from app.handlers.admin.common import ADMIN_IDS

from .common import router


@router.message(F.text.in_(["💰 مالی", "مالی"]))
async def financial_management_menu(message: Message, session: AsyncSession):
    """Main financial management interface"""
    if message.from_user.id not in ADMIN_IDS:
        return

    total_revenue = (
        await session.scalar(
            select(func.coalesce(func.sum(Subscription.price), 0)).filter(
                Subscription.status.in_(["active", "expired"])
            )
        )
        or 0
    )

    pending_revenue = (
        await session.scalar(
            select(func.coalesce(func.sum(Subscription.price), 0)).filter(
                Subscription.status == "pending"
            )
        )
        or 0
    )

    total_wallets = (
        await session.scalar(select(func.coalesce(func.sum(User.credit), 0))) or 0
    )

    pending_charges = (
        await session.scalar(
            select(func.coalesce(func.sum(ChargeRequest.price), 0)).filter(
                ChargeRequest.status == "pending"
            )
        )
        or 0
    )

    current_month_start = datetime.now().replace(
        day=1, hour=0, minute=0, second=0, microsecond=0
    )
    monthly_revenue = (
        await session.scalar(
            select(func.coalesce(func.sum(Subscription.price), 0)).filter(
                and_(
                    Subscription.created_at >= current_month_start,
                    Subscription.status.in_(["active", "expired"]),
                )
            )
        )
        or 0
    )

    stats_text = (
        "💰 **مدیریت مالی**\n\n"
        "📊 **خلاصه مالی:**\n"
        f"💳 کل درآمد: `{total_revenue:,}` تومان\n"
        f"⏳ درآمد در انتظار: `{pending_revenue:,}` تومان\n"
        f"🏦 موجودی کیف پول‌ها: `{total_wallets:,}` تومان\n"
        f"💵 شارژ در انتظار: `{pending_charges:,}` تومان\n"
        f"📅 درآمد این ماه: `{monthly_revenue:,}` تومان\n\n"
        "عملیات مالی مورد نظر را انتخاب کنید:"
    )

    kb = InlineKeyboardBuilder()
    kb.button(text="📈 گزارش درآمد", callback_data="revenue_reports")
    kb.button(text="💳 تراکنش‌ها", callback_data="transactions_view")
    kb.button(text="🏧 برداشت‌ها", callback_data="cashout_requests")
    kb.adjust(2)

    await message.answer(stats_text, reply_markup=kb.as_markup(), parse_mode="Markdown")

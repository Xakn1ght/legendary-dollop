from datetime import datetime, timedelta

from aiogram import F
from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import and_, extract, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Subscription
from app.handlers.admin.common import ADMIN_IDS
from app.utils.bot_i18n import t

from .common import _lang_for_tg_user, router


@router.callback_query(F.data == "revenue_reports")
async def revenue_reports(callback: CallbackQuery, session: AsyncSession):
    """Show revenue reports with time filtering"""
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer(
            t(_lang_for_tg_user(callback.from_user), "not_authorized"),
            show_alert=True,
        )
        return

    kb = InlineKeyboardBuilder()
    kb.button(text="📅 امروز", callback_data="revenue_today")
    kb.button(text="🗓 این هفته", callback_data="revenue_week")
    kb.button(text="📅 این ماه", callback_data="revenue_month")
    kb.button(text="📊 سه ماه گذشته", callback_data="revenue_quarter")
    kb.button(text="📈 سال جاری", callback_data="revenue_year")
    kb.button(text="🔄 همه زمان‌ها", callback_data="revenue_all")
    kb.adjust(2)

    await callback.message.edit_text(
        "📈 **گزارش درآمد**\n\nبازه زمانی مورد نظر را انتخاب کنید:",
        reply_markup=kb.as_markup(),
        parse_mode="Markdown",
    )
    await callback.answer()


@router.callback_query(
    F.data.in_(
        {
            "revenue_today",
            "revenue_week",
            "revenue_month",
            "revenue_quarter",
            "revenue_year",
            "revenue_all",
        }
    )
)
async def show_revenue_report(callback: CallbackQuery, session: AsyncSession):
    """Show revenue report for specific time period"""
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer(
            t(_lang_for_tg_user(callback.from_user), "not_authorized"),
            show_alert=True,
        )
        return

    period = callback.data.split("_")[1]
    now = datetime.now()

    if period == "today":
        start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
        title = "📅 درآمد امروز"
    elif period == "week":
        start_date = now - timedelta(days=7)
        title = "🗓 درآمد هفته گذشته"
    elif period == "month":
        start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        title = "📅 درآمد این ماه"
    elif period == "quarter":
        start_date = now - timedelta(days=90)
        title = "📊 درآمد سه ماه گذشته"
    elif period == "year":
        start_date = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        title = "📈 درآمد سال جاری"
    else:
        start_date = None
        title = "🔄 کل درآمد"

    revenue_query = select(func.coalesce(func.sum(Subscription.price), 0)).filter(
        Subscription.status.in_(["active", "expired"])
    )
    count_query = select(func.count(Subscription.id)).filter(
        Subscription.status.in_(["active", "expired"])
    )

    if start_date:
        revenue_query = revenue_query.filter(Subscription.created_at >= start_date)
        count_query = count_query.filter(Subscription.created_at >= start_date)

    total_revenue = await session.scalar(revenue_query) or 0
    total_sales = await session.scalar(count_query) or 0

    avg_per_sale = total_revenue / total_sales if total_sales > 0 else 0

    daily_breakdown = ""
    if period in ["today", "week", "month"]:
        daily_query = (
            select(
                extract("day", Subscription.created_at).label("day"),
                func.coalesce(func.sum(Subscription.price), 0).label("revenue"),
                func.count(Subscription.id).label("count"),
            )
            .filter(
                and_(
                    Subscription.status.in_(["active", "expired"]),
                    Subscription.created_at >= start_date if start_date else True,
                )
            )
            .group_by(extract("day", Subscription.created_at))
            .order_by("day")
        )

        daily_result = await session.execute(daily_query)
        daily_data = daily_result.fetchall()

        if daily_data:
            daily_breakdown = "\n📊 **تفکیک روزانه:**\n"
            for row in daily_data[-7:]:
                daily_breakdown += (
                    f"روز {int(row.day)}: `{int(row.revenue):,}` تومان "
                    f"({int(row.count)} فروش)\n"
                )

    top_plans_query = (
        select(
            Subscription.plan_name,
            func.coalesce(func.sum(Subscription.price), 0).label("revenue"),
            func.count(Subscription.id).label("count"),
        )
        .filter(
            and_(
                Subscription.status.in_(["active", "expired"]),
                Subscription.plan_name.isnot(None),
                Subscription.created_at >= start_date if start_date else True,
            )
        )
        .group_by(Subscription.plan_name)
        .order_by(func.sum(Subscription.price).desc())
        .limit(5)
    )

    top_plans_result = await session.execute(top_plans_query)
    top_plans = top_plans_result.fetchall()

    plans_breakdown = ""
    if top_plans:
        plans_breakdown = "\n🏆 **برترین پلن‌ها:**\n"
        for i, plan in enumerate(top_plans, 1):
            plans_breakdown += (
                f"{i}. {plan.plan_name}: `{int(plan.revenue):,}` تومان "
                f"({plan.count} فروش)\n"
            )

    report_text = (
        f"{title}\n\n"
        f"💰 **کل درآمد:** `{total_revenue:,}` تومان\n"
        f"📦 **تعداد فروش:** `{total_sales:,}`\n"
        f"📊 **میانگین فروش:** `{avg_per_sale:,.0f}` تومان\n"
        f"{daily_breakdown}"
        f"{plans_breakdown}\n"
        f"🕐 **تاریخ گزارش:** `{now.strftime('%Y-%m-%d %H:%M')}`"
    )

    kb = InlineKeyboardBuilder()
    kb.button(text="⬅️ بازگشت", callback_data="revenue_reports")
    kb.adjust(2)

    await callback.message.edit_text(
        report_text,
        reply_markup=kb.as_markup(),
        parse_mode="Markdown",
    )
    await callback.answer()

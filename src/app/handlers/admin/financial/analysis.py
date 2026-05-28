from datetime import datetime, timedelta

from aiogram import F
from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import and_, desc, extract, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import ReferralReward, Subscription, User
from app.handlers.admin.common import ADMIN_IDS
from app.utils.bot_i18n import t

from .common import _lang_for_tg_user, router


@router.callback_query(F.data == "sales_analysis")
async def sales_analysis(callback: CallbackQuery, session: AsyncSession):
    """Analyze sales patterns and trends"""
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer(
            t(_lang_for_tg_user(callback.from_user), "not_authorized"),
            show_alert=True,
        )
        return

    now = datetime.now()
    last_month = now - timedelta(days=30)
    last_week = now - timedelta(days=7)

    current_month_sales = (
        await session.scalar(
            select(func.count(Subscription.id)).filter(
                and_(
                    Subscription.created_at
                    >= now.replace(day=1, hour=0, minute=0, second=0, microsecond=0),
                    Subscription.status.in_(["active", "expired"]),
                )
            )
        )
        or 0
    )

    current_month_revenue = (
        await session.scalar(
            select(func.coalesce(func.sum(Subscription.price), 0)).filter(
                and_(
                    Subscription.created_at
                    >= now.replace(day=1, hour=0, minute=0, second=0, microsecond=0),
                    Subscription.status.in_(["active", "expired"]),
                )
            )
        )
        or 0
    )

    last_30_days_sales = (
        await session.scalar(
            select(func.count(Subscription.id)).filter(
                and_(
                    Subscription.created_at >= last_month,
                    Subscription.status.in_(["active", "expired"]),
                )
            )
        )
        or 0
    )

    prev_30_days_sales = (
        await session.scalar(
            select(func.count(Subscription.id)).filter(
                and_(
                    Subscription.created_at >= (last_month - timedelta(days=30)),
                    Subscription.created_at < last_month,
                    Subscription.status.in_(["active", "expired"]),
                )
            )
        )
        or 0
    )

    sales_growth = (
        ((last_30_days_sales - prev_30_days_sales) / prev_30_days_sales * 100)
        if prev_30_days_sales > 0
        else 0
    )
    growth_emoji = "📈" if sales_growth > 0 else "📉" if sales_growth < 0 else "➡️"

    best_plans = await session.execute(
        select(
            Subscription.plan_name,
            func.count(Subscription.id).label("count"),
            func.coalesce(func.sum(Subscription.price), 0).label("revenue"),
        )
        .filter(
            and_(
                Subscription.created_at >= last_month,
                Subscription.status.in_(["active", "expired"]),
                Subscription.plan_name.isnot(None),
            )
        )
        .group_by(Subscription.plan_name)
        .order_by(func.count(Subscription.id).desc())
        .limit(5)
    )
    best_plans_list = best_plans.fetchall()

    peak_hours = await session.execute(
        select(
            extract("hour", Subscription.created_at).label("hour"),
            func.count(Subscription.id).label("count"),
        )
        .filter(
            and_(
                Subscription.created_at >= last_week,
                Subscription.status.in_(["active", "expired"]),
            )
        )
        .group_by(extract("hour", Subscription.created_at))
        .order_by(func.count(Subscription.id).desc())
        .limit(3)
    )
    peak_hours_list = peak_hours.fetchall()

    analysis_text = (
        "📊 **تحلیل فروش**\n\n"
        f"📅 **این ماه:**\n"
        f"📦 فروش: `{current_month_sales:,}`\n"
        f"💰 درآمد: `{current_month_revenue:,}` تومان\n\n"
        f"📈 **مقایسه 30 روز:**\n"
        f"📊 30 روز گذشته: `{last_30_days_sales:,}` فروش\n"
        f"📊 30 روز قبل: `{prev_30_days_sales:,}` فروش\n"
        f"{growth_emoji} رشد: `{sales_growth:+.1f}%`\n\n"
    )

    if best_plans_list:
        analysis_text += "🏆 **محبوب‌ترین پلن‌ها (30 روز):**\n"
        for i, plan in enumerate(best_plans_list, 1):
            analysis_text += (
                f"{i}. {plan.plan_name}: `{plan.count}` فروش "
                f"(`{int(plan.revenue):,}` تومان)\n"
            )
        analysis_text += "\n"

    if peak_hours_list:
        analysis_text += "⏰ **ساعات پرفروش:**\n"
        for hour_data in peak_hours_list:
            hour = int(hour_data.hour)
            count = int(hour_data.count)
            analysis_text += f"🕐 {hour:02d}:00 - {hour + 1:02d}:00: `{count}` فروش\n"

    kb = InlineKeyboardBuilder()
    kb.adjust(2)

    await callback.message.edit_text(
        analysis_text,
        reply_markup=kb.as_markup(),
        parse_mode="Markdown",
    )
    await callback.answer()


@router.callback_query(F.data == "rewards_financial")
async def rewards_financial(callback: CallbackQuery, session: AsyncSession):
    """Manage rewards and discounts from financial perspective"""
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer(
            t(_lang_for_tg_user(callback.from_user), "not_authorized"),
            show_alert=True,
        )
        return

    total_rewards = await session.scalar(select(func.count(ReferralReward.id))) or 0

    total_reward_value = (
        await session.scalar(
            select(func.coalesce(func.sum(ReferralReward.reward_value), 0))
        )
        or 0
    )

    recent_rewards = await session.execute(
        select(ReferralReward, User)
        .join(User, ReferralReward.referrer_id == User.chat_id)
        .order_by(desc(ReferralReward.created_at))
        .limit(10)
    )
    recent_rewards_list = recent_rewards.fetchall()

    top_referrers = await session.execute(
        select(
            User.full_name,
            User.chat_id,
            func.count(ReferralReward.id).label("reward_count"),
            func.coalesce(func.sum(ReferralReward.reward_value), 0).label("total_value"),
        )
        .join(User, ReferralReward.referrer_id == User.chat_id)
        .group_by(User.chat_id, User.full_name)
        .order_by(func.count(ReferralReward.id).desc())
        .limit(5)
    )
    top_referrers_list = top_referrers.fetchall()

    rewards_text = (
        "🎁 **مدیریت پاداش‌ها**\n\n"
        f"📊 **آمار کلی:**\n"
        f"🎁 کل پاداش‌ها: `{total_rewards:,}`\n"
        f"💰 ارزش کل: `{total_reward_value:,}`\n\n"
    )

    if top_referrers_list:
        rewards_text += "🏆 **برترین معرف‌ها:**\n"
        for i, (name, chat_id, count, value) in enumerate(top_referrers_list, 1):
            user_name = name or f"ID:{chat_id}"
            rewards_text += (
                f"{i}. {user_name}: `{count}` پاداش (`{int(value):,}` ارزش)\n"
            )
        rewards_text += "\n"

    if recent_rewards_list:
        rewards_text += "🆕 **آخرین پاداش‌ها:**\n"
        for reward, user in recent_rewards_list[:5]:
            user_name = user.full_name or f"ID:{user.chat_id}"
            date_str = reward.created_at.strftime("%m-%d") if reward.created_at else ""
            rewards_text += (
                f"• {user_name}: پاداش `{reward.reward_value}` ({date_str})\n"
            )

    kb = InlineKeyboardBuilder()
    kb.adjust(2)

    await callback.message.edit_text(
        rewards_text,
        reply_markup=kb.as_markup(),
        parse_mode="Markdown",
    )
    await callback.answer()

from aiogram import F
from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import ChargeRequest, Subscription, User
from app.handlers.admin.common import ADMIN_IDS
from app.utils.bot_i18n import t

from .common import _lang_for_tg_user, router


@router.callback_query(F.data == "transactions_view")
async def transactions_view(callback: CallbackQuery, session: AsyncSession):
    """Show recent transactions and payment history"""
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer(
            t(_lang_for_tg_user(callback.from_user), "not_authorized"),
            show_alert=True,
        )
        return

    recent_transactions = await session.execute(
        select(Subscription, User)
        .join(User, Subscription.user_id == User.chat_id)
        .filter(Subscription.status.in_(["active", "expired"]))
        .order_by(desc(Subscription.created_at))
        .limit(10)
    )
    transactions = recent_transactions.fetchall()

    recent_charges = await session.execute(
        select(ChargeRequest, User)
        .join(User, ChargeRequest.user_id == User.chat_id)
        .order_by(desc(ChargeRequest.created_at))
        .limit(5)
    )
    charges = recent_charges.fetchall()

    transactions_text = "💳 **آخرین تراکنش‌ها**\n\n"

    if transactions:
        transactions_text += "🛍 **خرید سرویس:**\n"
        for sub, user in transactions:
            user_name = user.full_name or f"ID:{user.chat_id}"
            date_str = sub.created_at.strftime("%m-%d %H:%M") if sub.created_at else ""
            status_emoji = "✅" if sub.status == "active" else "❌"
            transactions_text += (
                f"{status_emoji} {user_name}: `{sub.price:,}` تومان ({date_str})\n"
            )
        transactions_text += "\n"

    if charges:
        transactions_text += "💵 **درخواست شارژ:**\n"
        for charge, user in charges:
            user_name = user.full_name or f"ID:{user.chat_id}"
            date_str = (
                charge.created_at.strftime("%m-%d %H:%M")
                if charge.created_at
                else ""
            )
            status_map = {"pending": "⏳", "approved": "✅", "rejected": "❌"}
            status_emoji = status_map.get(charge.status, "❓")
            transactions_text += (
                f"{status_emoji} {user_name}: `{charge.amount:,}` تومان ({date_str})\n"
            )

    kb = InlineKeyboardBuilder()
    kb.adjust(2)

    await callback.message.edit_text(
        transactions_text,
        reply_markup=kb.as_markup(),
        parse_mode="Markdown",
    )
    await callback.answer()


@router.callback_query(F.data == "wallet_management")
async def wallet_management(callback: CallbackQuery, session: AsyncSession):
    """Manage user wallets and credit distribution"""
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer(
            t(_lang_for_tg_user(callback.from_user), "not_authorized"),
            show_alert=True,
        )
        return

    total_wallets = (
        await session.scalar(select(func.coalesce(func.sum(User.credit), 0)))
        or 0
    )

    users_with_credit = (
        await session.scalar(select(func.count(User.id)).filter(User.credit > 0)) or 0
    )

    avg_wallet = total_wallets / users_with_credit if users_with_credit > 0 else 0

    top_wallets = await session.execute(
        select(User.full_name, User.chat_id, User.credit)
        .filter(User.credit > 0)
        .order_by(desc(User.credit))
        .limit(10)
    )
    top_wallet_users = top_wallets.fetchall()

    high_balance_users = (
        await session.scalar(
            select(func.count(User.id)).filter(User.credit > 1000000)
        )
        or 0
    )

    wallet_text = (
        "🏦 **مدیریت کیف پول‌ها**\n\n"
        f"💰 **آمار کلی:**\n"
        f"💳 کل موجودی: `{total_wallets:,}` تومان\n"
        f"👥 کاربران با موجودی: `{users_with_credit:,}`\n"
        f"📊 میانگین موجودی: `{avg_wallet:,.0f}` تومان\n"
        f"⚠️ موجودی‌های مشکوک: `{high_balance_users}` کاربر\n\n"
    )

    if top_wallet_users:
        wallet_text += "🏆 **بالاترین موجودی‌ها:**\n"
        for i, (name, chat_id, credit) in enumerate(top_wallet_users[:5], 1):
            user_name = name or f"ID:{chat_id}"
            wallet_text += f"{i}. {user_name}: `{credit:,}` تومان\n"

    kb = InlineKeyboardBuilder()
    kb.adjust(2)

    await callback.message.edit_text(
        wallet_text,
        reply_markup=kb.as_markup(),
        parse_mode="Markdown",
    )
    await callback.answer()

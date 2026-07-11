import logging
from datetime import datetime, timedelta

from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import and_, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import crud
from app.database.models import ChargeRequest, ReferralReward, Subscription, User
from app.handlers.admin.common import ADMIN_IDS
from app.services.pasarguard import pasarguard_api
from app.utils.bot_i18n import guess_lang_from_telegram, normalize_lang, set_cached_lang, t
from app.utils.validation import InputValidator, sanitize_user_input

router = Router()

# ================================
# ADMIN DASHBOARD
# ================================

async def _admin_lang(session: AsyncSession, tg_user) -> str:
    try:
        u = await crud.get_user(session, tg_user.id)
        lang = normalize_lang(getattr(u, "language", None)) if u else guess_lang_from_telegram(getattr(tg_user, "language_code", None))
        set_cached_lang(int(tg_user.id), lang)
        return lang
    except Exception:
        return guess_lang_from_telegram(getattr(tg_user, "language_code", None))

@router.message(F.text.in_(['📊 داشبورد', 'داشبورد']))
async def admin_dashboard(message: Message, session: AsyncSession):
    """Comprehensive admin dashboard with key metrics and quick actions"""
    if message.from_user.id not in ADMIN_IDS:
        return

    # Get comprehensive stats
    total_users = await session.scalar(select(func.count(User.id))) or 0
    total_subs = await session.scalar(select(func.count(Subscription.id))) or 0
    active_subs = await session.scalar(
        select(func.count(Subscription.id)).filter(Subscription.status == 'active')
    ) or 0
    pending_subs = await session.scalar(
        select(func.count(Subscription.id)).filter(Subscription.status == 'pending')
    ) or 0
    pending_charges = await session.scalar(
        select(func.count(ChargeRequest.id)).filter(ChargeRequest.status == 'pending')
    ) or 0
    
    # Recent activity (last 24 hours)
    yesterday = datetime.now() - timedelta(days=1)
    new_users_today = await session.scalar(
        select(func.count(User.id)).filter(User.created_at >= yesterday)
    ) or 0
    new_subs_today = await session.scalar(
        select(func.count(Subscription.id)).filter(Subscription.created_at >= yesterday)
    ) or 0
    
    # Revenue stats
    wallet_sum = await session.scalar(select(func.coalesce(func.sum(User.credit), 0))) or 0
    total_referral_rewards = await session.scalar(
        select(func.count(ReferralReward.id))
    ) or 0

    # System health indicators
    pasarguard_status = "🟢 آنلاین"
    try:
        # Quick check to PasarGuard API
        await pasarguard_api.get_users(limit=1)
    except:
        pasarguard_status = "🔴 آفلاین"

    dashboard_text = (
        "🚀 **داشبورد مدیریت**\n\n"
        "📈 **آمار کلی:**\n"
        f"👥 کل کاربران: `{total_users:,}`\n"
        f"🛍 کل اشتراک‌ها: `{total_subs:,}`\n"
        f"✅ فعال: `{active_subs:,}` | ⏳ انتظار: `{pending_subs:,}`\n"
        f"💵 درخواست شارژ: `{pending_charges:,}`\n\n"
        "📊 **فعالیت امروز (24 ساعت):**\n"
        f"🆕 کاربران جدید: `{new_users_today:,}`\n"
        f"📦 اشتراک‌های جدید: `{new_subs_today:,}`\n\n"
        "💰 **آمار مالی:**\n"
        f"💳 موجودی کل کیف پول‌ها: `{wallet_sum:,}` تومان\n"
        f"🎁 کل پاداش‌های ارجاع: `{total_referral_rewards:,}`\n\n"
        "⚡ **وضعیت سیستم:**\n"
        f"🖥 پنل: {pasarguard_status}\n"
        f"🤖 ربات: 🟢 آنلاین\n\n"
        f"🕐 آخرین بروزرسانی: `{datetime.now().strftime('%H:%M:%S')}`"
    )

    kb = InlineKeyboardBuilder()
    kb.button(text='🔄 بروزرسانی', callback_data='dashboard_refresh')
    kb.button(text='⚡ اقدامات سریع', callback_data='quick_actions')
    kb.button(text='📈 گزارش تفصیلی', callback_data='detailed_report')
    kb.button(text='🚨 هشدارها', callback_data='system_alerts')
    kb.adjust(2)

    await message.answer(dashboard_text, reply_markup=kb.as_markup(), parse_mode='Markdown')

@router.callback_query(F.data == 'dashboard_refresh')
async def refresh_dashboard(callback: CallbackQuery, session: AsyncSession):
    """Refresh dashboard stats"""
    lang = await _admin_lang(session, callback.from_user)
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer(t(lang, "not_authorized"), show_alert=True)
        return
    
    # Recreate the dashboard message
    await admin_dashboard(callback.message, session)
    await callback.message.delete()
    await callback.answer(t(lang, "admin_dashboard_refreshed"))

@router.callback_query(F.data == 'quick_actions')
async def quick_actions_menu(callback: CallbackQuery, session: AsyncSession):
    """Quick actions menu"""
    lang = await _admin_lang(session, callback.from_user)
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer(t(lang, "not_authorized"), show_alert=True)
        return

    kb = InlineKeyboardBuilder()
    kb.button(text='📢 پیام همگانی', callback_data='broadcast_message')
    kb.button(text='🔍 جستجوی کاربر', callback_data='search_user')
    # kb.button(text='💳 کد دعوت جدید', callback_data='generate_invite')
    # kb.button(text='🛠 تعمیر سیستم', callback_data='system_maintenance')
    # kb.button(text='📊 گزارش فوری', callback_data='emergency_report')
    kb.button(text='⬅️ بازگشت', callback_data='dashboard_refresh')
    kb.adjust(2)

    await callback.message.edit_text(
        "⚡ **اقدامات سریع**\n\nعملیات مدیریتی سریع را انتخاب کنید:",
        reply_markup=kb.as_markup(),
        parse_mode='Markdown'
    )
    await callback.answer()

@router.callback_query(F.data == 'detailed_report')
async def detailed_report(callback: CallbackQuery, session: AsyncSession):
    """Generate detailed system report"""
    lang = await _admin_lang(session, callback.from_user)
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer(t(lang, "not_authorized"), show_alert=True)
        return

    # Calculate detailed metrics
    last_week = datetime.now() - timedelta(days=7)
    last_month = datetime.now() - timedelta(days=30)
    
    # Weekly stats
    users_this_week = await session.scalar(
        select(func.count(User.id)).filter(User.created_at >= last_week)
    ) or 0
    subs_this_week = await session.scalar(
        select(func.count(Subscription.id)).filter(Subscription.created_at >= last_week)
    ) or 0
    
    # Monthly stats
    users_this_month = await session.scalar(
        select(func.count(User.id)).filter(User.created_at >= last_month)
    ) or 0
    subs_this_month = await session.scalar(
        select(func.count(Subscription.id)).filter(Subscription.created_at >= last_month)
    ) or 0

    # Get top users by credit
    top_users = await session.execute(
        select(User.full_name, User.credit)
        .filter(User.credit > 0)
        .order_by(desc(User.credit))
        .limit(5)
    )
    top_users_list = top_users.fetchall()

    report_text = (
        "📈 **گزارش تفصیلی سیستم**\n\n"
        "📅 **آمار هفتگی (7 روز گذشته):**\n"
        f"👥 کاربران جدید: `{users_this_week:,}`\n"
        f"📦 اشتراک‌های جدید: `{subs_this_week:,}`\n\n"
        "📅 **آمار ماهانه (30 روز گذشته):**\n"
        f"👥 کاربران جدید: `{users_this_month:,}`\n"
        f"📦 اشتراک‌های جدید: `{subs_this_month:,}`\n\n"
        "💰 **برترین کاربران (موجودی کیف پول):**\n"
    )
    
    for i, (name, credit) in enumerate(top_users_list, 1):
        report_text += f"{i}. {name}: `{credit:,}` تومان\n"

    kb = InlineKeyboardBuilder()
    kb.button(text='⭐ آمار ستاره‌ها', callback_data='star_analytics')
    # kb.button(text='📄 صادرات گزارش', callback_data='export_report')
    kb.button(text='⬅️ بازگشت', callback_data='dashboard_refresh')
    kb.adjust(2)

    await callback.message.edit_text(
        report_text,
        reply_markup=kb.as_markup(),
        parse_mode='Markdown'
    )
    await callback.answer()

@router.callback_query(F.data == 'system_alerts')
async def system_alerts(callback: CallbackQuery, session: AsyncSession):
    """Check for system alerts and issues"""
    lang = await _admin_lang(session, callback.from_user)
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer(t(lang, "not_authorized"), show_alert=True)
        return

    alerts = []
    
    # Check for pending requests
    pending_subs = await session.scalar(
        select(func.count(Subscription.id)).filter(Subscription.status == 'pending')
    ) or 0
    pending_charges = await session.scalar(
        select(func.count(ChargeRequest.id)).filter(ChargeRequest.status == 'pending')
    ) or 0
    
    if pending_subs > 0:
        alerts.append(f"🔔 {pending_subs} درخواست اشتراک در انتظار تایید")
    if pending_charges > 0:
        alerts.append(f"🔔 {pending_charges} درخواست شارژ در انتظار تایید")

    # Check for users with high credit (potential fraud)
    high_credit_users = await session.scalar(
        select(func.count(User.id)).filter(User.credit > 1000000)  # 1M+ tomans
    ) or 0
    
    if high_credit_users > 0:
        alerts.append(f"⚠️ {high_credit_users} کاربر با موجودی بالای 1 میلیون تومان")

    # Check PasarGuard connectivity
    try:
        await pasarguard_api.get_users(limit=1)
    except:
        alerts.append("🚨 مشکل در اتصال به پنل")

    if not alerts:
        alerts.append("✅ همه چیز عالی است!")

    alerts_text = "🚨 **هشدارهای سیستم**\n\n" + "\n".join(alerts)

    kb = InlineKeyboardBuilder()
    kb.button(text='🔄 بررسی مجدد', callback_data='system_alerts')
    kb.button(text='⬅️ بازگشت', callback_data='dashboard_refresh')
    kb.adjust(1)

    await callback.message.edit_text(
        alerts_text,
        reply_markup=kb.as_markup(),
        parse_mode='Markdown'
    )
    await callback.answer() 

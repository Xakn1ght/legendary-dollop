import logging
from datetime import datetime, timedelta

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import and_, delete, desc, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import crud
from app.database.models import ChargeRequest, Subscription, User
from app.handlers.admin.common import ADMIN_IDS
from app.services.marzban import marzban_api
from app.utils.bot_i18n import get_cached_lang, guess_lang_from_telegram, t
from app.utils.validation import InputValidator, sanitize_user_input

router = Router()

def _lang_for_tg_user(tg_user) -> str:
    return get_cached_lang(tg_user.id) or guess_lang_from_telegram(getattr(tg_user, "language_code", None))

class ServiceManagementStates(StatesGroup):
    waiting_bulk_action = State()
    waiting_service_filter = State()

# ================================
# SERVICE MANAGEMENT
# ================================

@router.message(F.text.in_(['🛍 سرویس‌ها', 'سرویس‌ها']))
async def service_management_menu(message: Message, session: AsyncSession):
    """Main service management interface"""
    if message.from_user.id not in ADMIN_IDS:
        return

    # Get service stats
    total_subs = await session.scalar(select(func.count(Subscription.id))) or 0
    active_subs = await session.scalar(
        select(func.count(Subscription.id)).filter(Subscription.status == 'active')
    ) or 0
    pending_subs = await session.scalar(
        select(func.count(Subscription.id)).filter(Subscription.status == 'pending')
    ) or 0
    expired_subs = await session.scalar(
        select(func.count(Subscription.id)).filter(Subscription.status == 'expired')
    ) or 0
    
    # Get Marzban sync status
    marzban_status = "🟢 متصل"
    try:
        marzban_users = await marzban_api.get_all_users(limit=1)
    except:
        marzban_status = "🔴 قطع"

    stats_text = (
        "🛍 **مدیریت سرویس‌ها**\n\n"
        f"📊 کل سرویس‌ها: `{total_subs:,}`\n"
        f"✅ فعال: `{active_subs:,}`\n"
        f"⏳ در انتظار: `{pending_subs:,}`\n"
        f"❌ منقضی: `{expired_subs:,}`\n\n"
        f"🖥 وضعیت مرزبان: {marzban_status}\n\n"
        "عملیات مورد نظر را انتخاب کنید:"
    )

    kb = InlineKeyboardBuilder()
    kb.button(text='📋 لیست سرویس‌ها', callback_data='list_services')
    # kb.button(text='🔍 جستجوی سرویس', callback_data='search_service')
    kb.button(text='⚠️ سرویس‌های مشکل‌دار', callback_data='problematic_services')
    kb.button(text='🔄 همگام‌سازی مرزبان', callback_data='sync_marzban')
    kb.button(text='🎯 عملیات گروهی', callback_data='bulk_service_operations')
    kb.button(text='📊 گزارش سرویس‌ها', callback_data='service_reports')
    kb.adjust(2)

    await message.answer(stats_text, reply_markup=kb.as_markup(), parse_mode='Markdown')

@router.callback_query(F.data == 'list_services')
async def list_services(callback: CallbackQuery, session: AsyncSession):
    """Show list of services with filtering options"""
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer(t(_lang_for_tg_user(callback.from_user), "not_authorized"), show_alert=True)
        return

    kb = InlineKeyboardBuilder()
    kb.button(text='✅ فعال', callback_data='filter_services_active')
    kb.button(text='⏳ در انتظار', callback_data='filter_services_pending')
    kb.button(text='❌ منقضی', callback_data='filter_services_expired')
    kb.button(text='🔄 همه', callback_data='filter_services_all')
    kb.button(text='📅 جدیدترین', callback_data='filter_services_recent')
    kb.button(text='💰 گران‌ترین', callback_data='filter_services_expensive')
    kb.adjust(2)

    await callback.message.edit_text(
        "📋 **فیلتر سرویس‌ها**\n\n"
        "نوع فیلتر را انتخاب کنید:",
        reply_markup=kb.as_markup(),
        parse_mode='Markdown'
    )
    await callback.answer()

@router.callback_query(F.data.startswith('filter_services_'))
async def filter_services(callback: CallbackQuery, session: AsyncSession):
    """Show filtered services"""
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer(t(_lang_for_tg_user(callback.from_user), "not_authorized"), show_alert=True)
        return

    filter_type = callback.data.split('_')[2]
    
    # Build query based on filter (eager load user to avoid lazy loading errors)
    from sqlalchemy.orm import selectinload
    query = select(Subscription).options(selectinload(Subscription.user)).join(User)
    
    if filter_type == 'active':
        query = query.filter(Subscription.status == 'active')
        title = "✅ سرویس‌های فعال"
    elif filter_type == 'pending':
        query = query.filter(Subscription.status == 'pending')
        title = "⏳ سرویس‌های در انتظار"
    elif filter_type == 'expired':
        query = query.filter(Subscription.status == 'expired')
        title = "❌ سرویس‌های منقضی"
    elif filter_type == 'recent':
        yesterday = datetime.now() - timedelta(days=1)
        query = query.filter(Subscription.created_at >= yesterday)
        title = "📅 سرویس‌های جدید (24 ساعت)"
    elif filter_type == 'expensive':
        query = query.order_by(desc(Subscription.price))
        title = "💰 گران‌ترین سرویس‌ها"
    else:  # all
        title = "🔄 همه سرویس‌ها"

    # Execute query
    query = query.order_by(desc(Subscription.created_at)).limit(15)
    result = await session.execute(query)
    services = result.scalars().all()

    if not services:
        await callback.message.edit_text(f"{title}\n\n❌ سرویسی یافت نشد.")
        await callback.answer()
        return

    kb = InlineKeyboardBuilder()
    text = f"{title}\n\n"
    
    for i, service in enumerate(services, 1):
        user_name = service.user.full_name if service.user else "نامشخص"
        status_emoji = {"active": "✅", "pending": "⏳", "expired": "❌"}.get(service.status, "❓")
        price_str = f"{service.price:,}" if service.price else "0"
        
        text += f"{i}. {status_emoji} {service.marzban_username} - {user_name} ({price_str}ت)\n"
        
        kb.button(
            text=f"{status_emoji} {service.marzban_username[:20]}",
            callback_data=f"service_details_{service.id}"
        )

    kb.button(text='🔄 بروزرسانی', callback_data=f'filter_services_{filter_type}')
    kb.button(text='⬅️ بازگشت', callback_data='list_services')
    kb.adjust(2)

    await callback.message.edit_text(
        text,
        reply_markup=kb.as_markup(),
        parse_mode='Markdown'
    )
    await callback.answer()

@router.callback_query(F.data.startswith('service_details_'))
async def service_details(callback: CallbackQuery, session: AsyncSession):
    """Show detailed service information"""
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer(t(_lang_for_tg_user(callback.from_user), "not_authorized"), show_alert=True)
        return

    service_id = int(callback.data.split('_')[2])
    service = await session.get(Subscription, service_id)
    
    if not service:
        await callback.answer("سرویس یافت نشد", show_alert=True)
        return

    # Refresh user relationship
    await session.refresh(service, attribute_names=["user"])

    # Get Marzban info if active
    marzban_info = ""
    if service.status == 'active' and service.marzban_username:
        try:
            marzban_user = await marzban_api.get_user_info(service.marzban_username)
            if marzban_user:
                used_gb = marzban_user.get('used_traffic', 0) / (1024**3)  # Convert to GB
                total_gb = marzban_user.get('data_limit', 0) / (1024**3) if marzban_user.get('data_limit') else 0
                expire_date = marzban_user.get('expire', 'نامحدود')
                
                marzban_info = (
                    f"\n🖥 **اطلاعات مرزبان:**\n"
                    f"📊 مصرف: `{used_gb:.1f}` / `{total_gb:.1f}` GB\n"
                    f"📅 انقضا: {expire_date}\n"
                    f"🔄 وضعیت: {'فعال' if marzban_user.get('status') == 'active' else 'غیرفعال'}"
                )
        except:
            marzban_info = "\n🖥 **مرزبان:** خطا در دریافت اطلاعات"

    created_date = service.created_at.strftime('%Y-%m-%d %H:%M') if service.created_at else "نامشخص"
    status_emoji = {"active": "✅", "pending": "⏳", "expired": "❌"}.get(service.status, "❓")
    
    service_text = (
        f"🛍 **جزئیات سرویس**\n\n"
        f"🆔 شناسه: `{service.id}`\n"
        f"👤 کاربر: {service.user.full_name if service.user else 'نامشخص'} (`{service.user_id}`)\n"
        f"🏷 نام سرویس: `{service.marzban_username}`\n"
        f"💰 قیمت: `{service.price:,}` تومان\n"
        f"📦 پلن: {service.plan_name or 'نامشخص'}\n"
        f"📅 ایجاد: {created_date}\n"
        f"🔄 وضعیت: {status_emoji} {service.status}"
        # (removed `service.charge_request_id` — no such column on Subscription;
        #  it raised AttributeError on every tap outside the try/except — audit fix)
        f"{marzban_info}"
    )

    # Create action buttons
    kb = InlineKeyboardBuilder()
    
    if service.status == 'pending':
        # kb.button(text='✅ تایید', callback_data=f'approve_service_{service.id}')
        # kb.button(text='❌ رد', callback_data=f'deny_service_{service.id}')
        pass
    elif service.status == 'active':
        # kb.button(text='⏸ غیرفعال', callback_data=f'disable_service_{service.id}')
        # kb.button(text='🔄 تمدید', callback_data=f'renew_service_{service.id}')
        pass
    elif service.status == 'expired':
        # kb.button(text='🔄 بازفعالی', callback_data=f'reactivate_service_{service.id}')
        pass
    
    # kb.button(text='✏️ ویرایش', callback_data=f'edit_service_{service.id}')
    # kb.button(text='💬 چت با کاربر', callback_data=f'chat_service_user_{service.user_id}')
    # kb.button(text='🗑 حذف', callback_data=f'delete_service_{service.id}')
    kb.button(text='⬅️ بازگشت', callback_data='list_services')
    kb.adjust(2)

    await callback.message.edit_text(
        service_text,
        reply_markup=kb.as_markup(),
        parse_mode='Markdown'
    )
    await callback.answer()

@router.callback_query(F.data == 'problematic_services')
async def problematic_services(callback: CallbackQuery, session: AsyncSession):
    """Show services that have issues"""
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer(t(_lang_for_tg_user(callback.from_user), "not_authorized"), show_alert=True)
        return

    issues = []
    
    # Find services that are active but don't exist in Marzban
    active_services = await session.execute(
        select(Subscription).filter(
            and_(
                Subscription.status == 'active',
                Subscription.marzban_username.isnot(None)
            )
        ).limit(50)
    )
    
    marzban_issues = []
    for service in active_services.scalars():
        try:
            marzban_user = await marzban_api.get_user(service.marzban_username)
            if not marzban_user:
                marzban_issues.append(service)
        except:
            marzban_issues.append(service)
    
    # Find old pending services (EAGER LOAD user)
    old_pending = await session.execute(
        select(Subscription).options(selectinload(Subscription.user)).filter(
            and_(
                Subscription.status == 'pending',
                Subscription.created_at < datetime.now() - timedelta(days=7)
            )
        ).limit(20)
    )
    old_pending_list = old_pending.scalars().all()
    
    # Find services without proper user link
    orphaned_services = await session.execute(
        select(Subscription).filter(Subscription.user_id.is_(None)).limit(10)
    )
    orphaned_list = orphaned_services.scalars().all()

    issues_text = "⚠️ **سرویس‌های مشکل‌دار**\n\n"
    
    if marzban_issues:
        issues_text += f"🖥 **مشکل مرزبان ({len(marzban_issues)} سرویس):**\n"
        for service in marzban_issues[:5]:
            issues_text += f"• {service.marzban_username} - فعال ولی در مرزبان موجود نیست\n"
        if len(marzban_issues) > 5:
            issues_text += f"• ... و {len(marzban_issues) - 5} سرویس دیگر\n"
        issues_text += "\n"
    
    if old_pending_list:
        issues_text += f"⏳ **درخواست‌های قدیمی ({len(old_pending_list)} سرویس):**\n"
        for service in old_pending_list[:5]:
            user_name = service.user.full_name if service.user else "نامشخص"
            issues_text += f"• {service.marzban_username} - {user_name} (7+ روز انتظار)\n"
        if len(old_pending_list) > 5:
            issues_text += f"• ... و {len(old_pending_list) - 5} سرویس دیگر\n"
        issues_text += "\n"
    
    if orphaned_list:
        issues_text += f"👤 **سرویس‌های بدون کاربر ({len(orphaned_list)} سرویس):**\n"
        for service in orphaned_list[:5]:
            issues_text += f"• {service.marzban_username} - بدون ارتباط کاربر\n"
        issues_text += "\n"
    
    if not (marzban_issues or old_pending_list or orphaned_list):
        issues_text += "✅ مشکل خاصی یافت نشد!"

    kb = InlineKeyboardBuilder()
    # if marzban_issues:
    #     kb.button(text='🔧 تعمیر مرزبان', callback_data='fix_marzban_issues')
    # if old_pending_list:
    #     kb.button(text='⏳ تعمیر انتظارات', callback_data='fix_pending_issues')
    # if orphaned_list:
    #     kb.button(text='👤 تعمیر بدون کاربر', callback_data='fix_orphaned_issues')
    
    kb.button(text='🔄 بررسی مجدد', callback_data='problematic_services')
    kb.adjust(2)

    await callback.message.edit_text(
        issues_text,
        reply_markup=kb.as_markup(),
        parse_mode='Markdown'
    )
    await callback.answer()

@router.callback_query(F.data == 'sync_marzban')
async def sync_marzban(callback: CallbackQuery, session: AsyncSession):
    """Synchronize with Marzban server"""
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer(t(_lang_for_tg_user(callback.from_user), "not_authorized"), show_alert=True)
        return

    await callback.answer("در حال همگام‌سازی با مرزبان...", show_alert=True)
    
    try:
        # Get all users from Marzban
        marzban_users = await marzban_api.get_all_users()
        
        # Get all active subscriptions
        active_subs = await session.execute(
            select(Subscription).filter(Subscription.status == 'active')
        )
        
        sync_results = {
            'found_in_both': 0,
            'only_in_db': 0,
            'only_in_marzban': 0,
            'status_mismatch': 0
        }
        
        db_usernames = {sub.marzban_username for sub in active_subs.scalars() if sub.marzban_username}
        marzban_usernames = {user['username'] for user in marzban_users if user.get('username')}
        
        sync_results['found_in_both'] = len(db_usernames & marzban_usernames)
        sync_results['only_in_db'] = len(db_usernames - marzban_usernames)
        sync_results['only_in_marzban'] = len(marzban_usernames - db_usernames)
        
        sync_text = (
            "🔄 **نتایج همگام‌سازی مرزبان**\n\n"
            f"✅ موجود در هر دو: `{sync_results['found_in_both']}`\n"
            f"🔍 فقط در دیتابیس: `{sync_results['only_in_db']}`\n"
            f"🆕 فقط در مرزبان: `{sync_results['only_in_marzban']}`\n\n"
            "همگام‌سازی کامل شد ✅"
        )
        
        await callback.message.edit_text(sync_text, parse_mode='Markdown')
        
    except Exception as e:
        await callback.message.edit_text(
            f"❌ خطا در همگام‌سازی:\n`{str(e)}`",
            parse_mode='Markdown'
        )

@router.callback_query(F.data == 'bulk_service_operations')
async def bulk_service_operations(callback: CallbackQuery):
    """Show bulk operations menu"""
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer(t(_lang_for_tg_user(callback.from_user), "not_authorized"), show_alert=True)
        return

    kb = InlineKeyboardBuilder()
    kb.button(text='✅ تایید همه انتظارات', callback_data='bulk_approve_pending')
    # kb.button(text='❌ رد همه انتظارات قدیمی', callback_data='bulk_deny_old_pending')
    # kb.button(text='🗑 حذف منقضی‌های قدیمی', callback_data='bulk_delete_expired')
    # kb.button(text='🔄 تمدید گروهی', callback_data='bulk_renew_services')
    # kb.button(text='⏸ غیرفعال‌سازی گروهی', callback_data='bulk_disable_services')
    # kb.button(text='📊 گزارش گروهی', callback_data='bulk_service_report')
    kb.adjust(2)

    await callback.message.edit_text(
        "🎯 **عملیات گروهی سرویس‌ها**\n\n"
        "⚠️ توجه: این عملیات بر روی چندین سرویس اعمال می‌شود\n\n"
        "عملیات مورد نظر را انتخاب کنید:",
        reply_markup=kb.as_markup(),
        parse_mode='Markdown'
    )
    await callback.answer()

@router.callback_query(F.data == 'bulk_approve_pending')
async def bulk_approve_pending(callback: CallbackQuery, session: AsyncSession):
    """Approve all pending subscriptions"""
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer(t(_lang_for_tg_user(callback.from_user), "not_authorized"), show_alert=True)
        return

    # Get all pending subscriptions
    pending_subs = await session.execute(
        select(Subscription).filter(Subscription.status == 'pending')
    )
    pending_list = pending_subs.scalars().all()
    
    if not pending_list:
        await callback.answer("سرویس در انتظاری یافت نشد", show_alert=True)
        return

    kb = InlineKeyboardBuilder()
    kb.button(text='✅ تایید همه', callback_data='confirm_bulk_approve')
    kb.button(text='❌ لغو', callback_data='bulk_service_operations')
    kb.adjust(2)

    await callback.message.edit_text(
        f"⚠️ **تایید عملیات گروهی**\n\n"
        f"آیا مطمئن هستید که می‌خواهید {len(pending_list)} سرویس در انتظار را تایید کنید؟\n\n"
        "این عملیات غیرقابل بازگشت است!",
        reply_markup=kb.as_markup(),
        parse_mode='Markdown'
    )
    await callback.answer()

@router.callback_query(F.data == 'confirm_bulk_approve')
async def confirm_bulk_approve(callback: CallbackQuery, session: AsyncSession):
    """Confirm and execute bulk approval"""
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer(t(_lang_for_tg_user(callback.from_user), "not_authorized"), show_alert=True)
        return

    await callback.answer("در حال تایید گروهی...")

    # CRITICAL (audit fix): the old code flipped every pending sub to 'active'
    # with a raw UPDATE — no Marzban user, no link DM, no reward grants. Those
    # became ghosts (active in DB, absent from the panel). Route each order
    # through the real provisioning flow, exactly like the single-receipt
    # approve, using the USER bot for the link DM.
    try:
        from app.services.subscription_processing import process_approved_subscription
        from app.utils.admin_bot_helper import get_user_bot

        result = await session.execute(
            select(Subscription.id).filter(Subscription.status == 'pending')
        )
        pending_ids = [row[0] for row in result.all()]
        user_bot = get_user_bot()

        approved_count = 0
        failed_count = 0
        for sub_id in pending_ids:
            try:
                ok = await process_approved_subscription(sub_id, session, user_bot)
                if ok:
                    approved_count += 1
                else:
                    failed_count += 1
            except Exception:
                failed_count += 1

        summary = (
            f"✅ **تایید گروهی کامل شد**\n\n"
            f"تایید و فعال‌سازی شده: `{approved_count}`\n"
        )
        if failed_count:
            summary += f"ناموفق (نیاز به بررسی دستی): `{failed_count}`\n"
        summary += "\nهر سرویس در پنل ساخته شد و لینک برای کاربر ارسال شد."
        await callback.message.edit_text(summary, parse_mode='Markdown')

    except Exception as e:
        await callback.message.edit_text(
            f"❌ خطا در تایید گروهی:\n`{str(e)}`",
            parse_mode='Markdown'
        )

@router.callback_query(F.data == 'service_reports')
async def service_reports(callback: CallbackQuery, session: AsyncSession):
    """Generate comprehensive service reports"""
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer(t(_lang_for_tg_user(callback.from_user), "not_authorized"), show_alert=True)
        return

    # Calculate various metrics
    now = datetime.now()
    last_week = now - timedelta(days=7)
    last_month = now - timedelta(days=30)
    
    # Total services by status
    total_services = await session.scalar(select(func.count(Subscription.id))) or 0
    active_services = await session.scalar(
        select(func.count(Subscription.id)).filter(Subscription.status == 'active')
    ) or 0
    pending_services = await session.scalar(
        select(func.count(Subscription.id)).filter(Subscription.status == 'pending')
    ) or 0
    expired_services = await session.scalar(
        select(func.count(Subscription.id)).filter(Subscription.status == 'expired')
    ) or 0
    
    # Recent activity
    new_services_week = await session.scalar(
        select(func.count(Subscription.id)).filter(Subscription.created_at >= last_week)
    ) or 0
    new_services_month = await session.scalar(
        select(func.count(Subscription.id)).filter(Subscription.created_at >= last_month)
    ) or 0
    
    # Revenue calculations
    total_revenue = await session.scalar(
        select(func.coalesce(func.sum(Subscription.price), 0))
        .filter(Subscription.status.in_(['active', 'expired']))
    ) or 0
    
    weekly_revenue = await session.scalar(
        select(func.coalesce(func.sum(Subscription.price), 0))
        .filter(
            and_(
                Subscription.created_at >= last_week,
                Subscription.status.in_(['active', 'expired'])
            )
        )
    ) or 0
    
    monthly_revenue = await session.scalar(
        select(func.coalesce(func.sum(Subscription.price), 0))
        .filter(
            and_(
                Subscription.created_at >= last_month,
                Subscription.status.in_(['active', 'expired'])
            )
        )
    ) or 0

    report_text = (
        "📊 **گزارش جامع سرویس‌ها**\n\n"
        "📈 **آمار کلی:**\n"
        f"🛍 کل سرویس‌ها: `{total_services:,}`\n"
        f"✅ فعال: `{active_services:,}` ({active_services/total_services*100 if total_services > 0 else 0:.1f}%)\n"
        f"⏳ در انتظار: `{pending_services:,}` ({pending_services/total_services*100 if total_services > 0 else 0:.1f}%)\n"
        f"❌ منقضی: `{expired_services:,}` ({expired_services/total_services*100 if total_services > 0 else 0:.1f}%)\n\n"
        "📅 **فعالیت اخیر:**\n"
        f"🗓 سرویس‌های هفته: `{new_services_week:,}`\n"
        f"📅 سرویس‌های ماه: `{new_services_month:,}`\n\n"
        "💰 **درآمد:**\n"
        f"💳 کل درآمد: `{total_revenue:,}` تومان\n"
        f"📊 درآمد هفتگی: `{weekly_revenue:,}` تومان\n"
        f"📈 درآمد ماهانه: `{monthly_revenue:,}` تومان\n\n"
        f"🕐 تاریخ گزارش: `{now.strftime('%Y-%m-%d %H:%M')}`"
    )

    kb = InlineKeyboardBuilder()
    # kb.button(text='📄 صادرات کامل', callback_data='export_service_report')
    # kb.button(text='📊 آمار تفصیلی', callback_data='detailed_service_stats')
    kb.button(text='🔄 بروزرسانی', callback_data='service_reports')
    kb.adjust(2)

    await callback.message.edit_text(
        report_text,
        reply_markup=kb.as_markup(),
        parse_mode='Markdown'
    )
    await callback.answer() 

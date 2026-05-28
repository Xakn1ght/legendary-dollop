import asyncio
import logging
from datetime import datetime, timedelta

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import and_, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import crud
from app.database.models import Subscription, User
from app.handlers.admin.common import ADMIN_IDS
from app.utils.bot_i18n import get_cached_lang, guess_lang_from_telegram, t
from app.utils.validation import InputValidator, sanitize_user_input

router = Router()

class BroadcastStates(StatesGroup):
    waiting_message = State()
    waiting_target_selection = State()
    waiting_schedule_time = State()

# ================================
# BROADCASTING SYSTEM
# ================================

@router.message(F.text.in_(['📢 اطلاع‌رسانی', 'اطلاع‌رسانی']))
async def broadcast_management_menu(message: Message, session: AsyncSession):
    """Main broadcasting management interface"""
    if message.from_user.id not in ADMIN_IDS:
        return

    # Get broadcast statistics
    total_users = await session.scalar(select(func.count(User.id))) or 0
    active_users = await session.scalar(
        select(func.count(User.id)).filter(User.banned == False)
    ) or 0
    users_with_subs = await session.scalar(
        select(func.count(User.id.distinct()))
        .select_from(User)
        .join(Subscription, User.chat_id == Subscription.user_id)
        .filter(and_(User.banned == False, Subscription.status == 'active'))
    ) or 0

    stats_text = (
        "📢 **سیستم اطلاع‌رسانی**\n\n"
        "📊 **آمار مخاطبان:**\n"
        f"👥 کل کاربران: `{total_users:,}`\n"
        f"✅ کاربران فعال: `{active_users:,}`\n"
        f"🛍 دارای سرویس فعال: `{users_with_subs:,}`\n\n"
        "نوع پیام‌رسانی را انتخاب کنید:"
    )

    kb = InlineKeyboardBuilder()
    kb.button(text='📤 پیام فوری', callback_data='broadcast_immediate')
    # kb.button(text='⏰ پیام زمان‌بندی شده', callback_data='broadcast_scheduled')
    kb.button(text='🎯 پیام هدفمند', callback_data='broadcast_targeted')
    # kb.button(text='📋 الگوهای پیام', callback_data='message_templates')
    kb.button(text='📊 آمار ارسال', callback_data='broadcast_stats')
    # kb.button(text='📝 تاریخچه پیام‌ها', callback_data='broadcast_history')
    kb.adjust(2)

    await message.answer(stats_text, reply_markup=kb.as_markup(), parse_mode='Markdown')

@router.callback_query(F.data == 'broadcast_immediate')
async def broadcast_immediate_setup(callback: CallbackQuery, state: FSMContext):
    """Setup immediate broadcast"""
    if callback.from_user.id not in ADMIN_IDS:
        lang = get_cached_lang(callback.from_user.id) or guess_lang_from_telegram(getattr(callback.from_user, "language_code", None))
        await callback.answer(t(lang, "not_authorized"), show_alert=True)
        return

    await state.set_data({'broadcast_type': 'immediate'})
    await state.set_state(BroadcastStates.waiting_message)
    
    await callback.message.edit_text(
        "📤 **پیام فوری**\n\n"
        "لطفاً متن پیام خود را ارسال کنید:\n\n"
        "💡 **راهنما:**\n"
        "• پیام به همه کاربران فعال ارسال می‌شود\n"
        "• از متن، عکس، ویدیو و... پشتیبانی می‌شود\n"
        "• برای لغو: /cancel\n\n"
        "⚠️ **توجه:** این پیام بلافاصله ارسال خواهد شد!"
    )
    await callback.answer()

@router.callback_query(F.data == 'broadcast_targeted')
async def broadcast_targeted_setup(callback: CallbackQuery, state: FSMContext):
    """Setup targeted broadcast"""
    if callback.from_user.id not in ADMIN_IDS:
        lang = get_cached_lang(callback.from_user.id) or guess_lang_from_telegram(getattr(callback.from_user, "language_code", None))
        await callback.answer(t(lang, "not_authorized"), show_alert=True)
        return

    kb = InlineKeyboardBuilder()
    kb.button(text='👥 همه کاربران', callback_data='target_all_users')
    kb.button(text='✅ کاربران فعال', callback_data='target_active_users')
    kb.button(text='🛍 دارای سرویس فعال', callback_data='target_active_subscribers')
    kb.button(text='💰 کاربران VIP (موجودی بالا)', callback_data='target_vip_users')
    kb.button(text='🆕 کاربران جدید', callback_data='target_new_users')
    kb.button(text='⏳ کاربران غیرفعال', callback_data='target_inactive_users')
    kb.adjust(2)

    await callback.message.edit_text(
        "🎯 **پیام هدفمند**\n\n"
        "مخاطبان هدف را انتخاب کنید:",
        reply_markup=kb.as_markup(),
        parse_mode='Markdown'
    )
    await callback.answer()

@router.callback_query(F.data.startswith('target_'))
async def set_target_audience(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Set target audience for broadcast"""
    if callback.from_user.id not in ADMIN_IDS:
        lang = get_cached_lang(callback.from_user.id) or guess_lang_from_telegram(getattr(callback.from_user, "language_code", None))
        await callback.answer(t(lang, "not_authorized"), show_alert=True)
        return

    target_type = callback.data.split('_', 1)[1]
    
    # Calculate audience size based on target type
    if target_type == 'all_users':
        count = await session.scalar(select(func.count(User.id))) or 0
        description = "همه کاربران"
    elif target_type == 'active_users':
        count = await session.scalar(
            select(func.count(User.id)).filter(User.banned == False)
        ) or 0
        description = "کاربران فعال (غیرمسدود)"
    elif target_type == 'active_subscribers':
        count = await session.scalar(
            select(func.count(User.id.distinct()))
            .select_from(User)
            .join(Subscription, User.chat_id == Subscription.user_id)
            .filter(and_(User.banned == False, Subscription.status == 'active'))
        ) or 0
        description = "کاربران با سرویس فعال"
    elif target_type == 'vip_users':
        count = await session.scalar(
            select(func.count(User.id))
            .filter(and_(User.banned == False, User.credit > 100000))
        ) or 0
        description = "کاربران VIP (موجودی بالای 100,000 تومان)"
    elif target_type == 'new_users':
        last_week = datetime.now() - timedelta(days=7)
        count = await session.scalar(
            select(func.count(User.id))
            .filter(and_(User.banned == False, User.created_at >= last_week))
        ) or 0
        description = "کاربران جدید (هفته گذشته)"
    elif target_type == 'inactive_users':
        last_month = datetime.now() - timedelta(days=30)
        # Users who haven't had any subscription in the last month
        count = await session.scalar(
            select(func.count(User.id))
            .filter(
                and_(
                    User.banned == False,
                    ~User.chat_id.in_(
                        select(Subscription.user_id)
                        .filter(Subscription.created_at >= last_month)
                    )
                )
            )
        ) or 0
        description = "کاربران غیرفعال (بدون سرویس در ماه گذشته)"
    else:
        count = 0
        description = "نامشخص"

    await state.set_data({
        'broadcast_type': 'targeted',
        'target_type': target_type,
        'target_count': count
    })
    await state.set_state(BroadcastStates.waiting_message)
    
    await callback.message.edit_text(
        f"🎯 **پیام هدفمند**\n\n"
        f"📊 **مخاطبان انتخاب شده:**\n"
        f"👥 گروه: {description}\n"
        f"📈 تعداد: `{count:,}` نفر\n\n"
        "لطفاً متن پیام خود را ارسال کنید:\n\n"
        "💡 **راهنما:**\n"
        "• از متن، عکس، ویدیو و... پشتیبانی می‌شود\n"
        "• برای لغو: /cancel"
    )
    await callback.answer()

@router.message(BroadcastStates.waiting_message)
async def receive_broadcast_message(message: Message, state: FSMContext, session: AsyncSession):
    """Receive and process broadcast message"""
    if message.from_user.id not in ADMIN_IDS:
        return

    if message.text and message.text == '/cancel':
        await state.clear()
        await message.answer("ارسال پیام لغو شد.")
        return

    data = await state.get_data()
    broadcast_type = data.get('broadcast_type', 'immediate')
    target_type = data.get('target_type', 'active_users')
    target_count = data.get('target_count', 0)

    # Store message content
    message_data = {
        'message_id': message.message_id,
        'chat_id': message.chat.id,
        'content_type': message.content_type,
        'text': message.text or message.caption,
    }
    
    await state.set_data({
        **data,
        'message_data': message_data
    })

    # Show confirmation
    content_type_map = {
        'text': '📝 متن',
        'photo': '🖼 عکس',
        'video': '🎥 ویدیو',
        'document': '📎 فایل',
        'animation': '🎬 GIF',
        'voice': '🎤 صدا',
        'sticker': '🎭 استیکر'
    }
    
    content_desc = content_type_map.get(message.content_type, '❓ نامشخص')
    preview_text = (message.text or message.caption or "")[:100]
    if len(preview_text) > 100:
        preview_text += "..."

    if broadcast_type == 'targeted':
        target_desc = f"🎯 گروه هدف: {target_count:,} نفر"
    else:
        target_desc = "👥 همه کاربران فعال"

    confirm_text = (
        "✅ **تایید ارسال پیام**\n\n"
        f"📋 **جزئیات:**\n"
        f"📄 نوع محتوا: {content_desc}\n"
        f"{target_desc}\n\n"
        f"📝 **پیش‌نمایش:**\n"
        f"`{preview_text}`\n\n"
        "آیا مطمئن هستید که می‌خواهید این پیام را ارسال کنید؟"
    )

    kb = InlineKeyboardBuilder()
    kb.button(text='✅ تایید و ارسال', callback_data='confirm_broadcast')
    # kb.button(text='⏰ زمان‌بندی', callback_data='schedule_broadcast')
    kb.button(text='❌ لغو', callback_data='cancel_broadcast')
    kb.adjust(2)

    await message.answer(confirm_text, reply_markup=kb.as_markup(), parse_mode='Markdown')

@router.callback_query(F.data == 'confirm_broadcast')
async def confirm_and_send_broadcast(callback: CallbackQuery, state: FSMContext, session: AsyncSession, bot: Bot):
    """Confirm and send broadcast message"""
    if callback.from_user.id not in ADMIN_IDS:
        lang = get_cached_lang(callback.from_user.id) or guess_lang_from_telegram(getattr(callback.from_user, "language_code", None))
        await callback.answer(t(lang, "not_authorized"), show_alert=True)
        return

    data = await state.get_data()
    message_data = data.get('message_data')
    target_type = data.get('target_type', 'active_users')
    
    if not message_data:
        await callback.answer("خطا: پیام یافت نشد", show_alert=True)
        return

    await callback.answer("در حال شروع ارسال...")
    
    # Get target users
    users_query = select(User.chat_id)
    
    if target_type == 'all_users':
        pass  # No filter
    elif target_type == 'active_users':
        users_query = users_query.filter(User.banned == False)
    elif target_type == 'active_subscribers':
        users_query = users_query.join(Subscription, User.chat_id == Subscription.user_id).filter(
            and_(User.banned == False, Subscription.status == 'active')
        ).distinct()
    elif target_type == 'vip_users':
        users_query = users_query.filter(and_(User.banned == False, User.credit > 100000))
    elif target_type == 'new_users':
        last_week = datetime.now() - timedelta(days=7)
        users_query = users_query.filter(and_(User.banned == False, User.created_at >= last_week))
    elif target_type == 'inactive_users':
        last_month = datetime.now() - timedelta(days=30)
        users_query = users_query.filter(
            and_(
                User.banned == False,
                ~User.chat_id.in_(
                    select(Subscription.user_id).filter(Subscription.created_at >= last_month)
                )
            )
        )

    result = await session.execute(users_query)
    target_users = [row[0] for row in result.fetchall()]

    if not target_users:
        await callback.message.edit_text("❌ هیچ کاربری برای ارسال پیام یافت نشد.")
        await state.clear()
        return

    # Start broadcasting
    await callback.message.edit_text(
        f"📤 **شروع ارسال پیام**\n\n"
        f"👥 تعداد مخاطبان: `{len(target_users):,}`\n"
        f"📊 پیشرفت: `0/{len(target_users)}`\n\n"
        "لطفاً صبر کنید..."
    )

    # Send messages with progress updates
    successful = 0
    failed = 0
    
    for i, user_id in enumerate(target_users, 1):
        try:
            # Copy message to user
            await bot.copy_message(
                chat_id=user_id,
                from_chat_id=message_data['chat_id'],
                message_id=message_data['message_id']
            )
            successful += 1
        except Exception as e:
            failed += 1
            logging.warning(f"Failed to send broadcast to {user_id}: {e}")
        
        # Update progress every 50 messages
        if i % 50 == 0 or i == len(target_users):
            try:
                await callback.message.edit_text(
                    f"📤 **ارسال پیام در حال انجام**\n\n"
                    f"👥 تعداد مخاطبان: `{len(target_users):,}`\n"
                    f"📊 پیشرفت: `{i}/{len(target_users)}`\n"
                    f"✅ موفق: `{successful}`\n"
                    f"❌ ناموفق: `{failed}`\n\n"
                    f"📈 درصد پیشرفت: `{i/len(target_users)*100:.1f}%`"
                )
            except:
                pass  # Ignore edit errors
        
        # Small delay to prevent flooding
        await asyncio.sleep(0.05)

    # Final report
    success_rate = (successful / len(target_users) * 100) if target_users else 0
    
    final_text = (
        f"✅ **ارسال پیام کامل شد**\n\n"
        f"📊 **گزارش نهایی:**\n"
        f"👥 کل مخاطبان: `{len(target_users):,}`\n"
        f"✅ ارسال موفق: `{successful:,}`\n"
        f"❌ ارسال ناموفق: `{failed:,}`\n"
        f"📈 نرخ موفقیت: `{success_rate:.1f}%`\n\n"
        f"🕐 زمان تکمیل: `{datetime.now().strftime('%H:%M:%S')}`"
    )

    await callback.message.edit_text(final_text, parse_mode='Markdown')
    await state.clear()

@router.callback_query(F.data == 'broadcast_stats')
async def broadcast_statistics(callback: CallbackQuery, session: AsyncSession):
    """Show broadcasting statistics and insights"""
    if callback.from_user.id not in ADMIN_IDS:
        lang = get_cached_lang(callback.from_user.id) or guess_lang_from_telegram(getattr(callback.from_user, "language_code", None))
        await callback.answer(t(lang, "not_authorized"), show_alert=True)
        return

    # Get various user segments for targeting insights
    total_users = await session.scalar(select(func.count(User.id))) or 0
    active_users = await session.scalar(
        select(func.count(User.id)).filter(User.banned == False)
    ) or 0
    banned_users = await session.scalar(
        select(func.count(User.id)).filter(User.banned == True)
    ) or 0
    
    # Users with active subscriptions
    active_subscribers = await session.scalar(
        select(func.count(User.id.distinct()))
        .select_from(User)
        .join(Subscription, User.chat_id == Subscription.user_id)
        .filter(and_(User.banned == False, Subscription.status == 'active'))
    ) or 0
    
    # VIP users (high credit)
    vip_users = await session.scalar(
        select(func.count(User.id))
        .filter(and_(User.banned == False, User.credit > 100000))
    ) or 0
    
    # New users (last week)
    last_week = datetime.now() - timedelta(days=7)
    new_users = await session.scalar(
        select(func.count(User.id))
        .filter(and_(User.banned == False, User.created_at >= last_week))
    ) or 0

    stats_text = (
        "📊 **آمار مخاطبان برای پیام‌رسانی**\n\n"
        f"👥 **کل کاربران:** `{total_users:,}`\n"
        f"✅ **فعال:** `{active_users:,}` ({active_users/total_users*100 if total_users > 0 else 0:.1f}%)\n"
        f"🚫 **مسدود:** `{banned_users:,}` ({banned_users/total_users*100 if total_users > 0 else 0:.1f}%)\n\n"
        f"🎯 **گروه‌های هدف:**\n"
        f"🛍 دارای سرویس فعال: `{active_subscribers:,}`\n"
        f"💎 کاربران VIP: `{vip_users:,}`\n"
        f"🆕 کاربران جدید (هفته): `{new_users:,}`\n\n"
        f"📈 **پتانسیل دسترسی:**\n"
        f"🎯 بهترین گزینه: کاربران فعال (`{active_users:,}` نفر)\n"
        f"💡 پیشنهاد: پیام‌های هدفمند نرخ بازخورد بهتری دارند"
    )

    kb = InlineKeyboardBuilder()
    kb.button(text='📤 شروع پیام‌رسانی', callback_data='broadcast_immediate')
    kb.button(text='🎯 پیام هدفمند', callback_data='broadcast_targeted')
    kb.button(text='🔄 بروزرسانی آمار', callback_data='broadcast_stats')
    kb.adjust(2)

    await callback.message.edit_text(
        stats_text,
        reply_markup=kb.as_markup(),
        parse_mode='Markdown'
    )
    await callback.answer()

@router.callback_query(F.data == 'message_templates')
async def message_templates(callback: CallbackQuery):
    """Show predefined message templates"""
    if callback.from_user.id not in ADMIN_IDS:
        lang = get_cached_lang(callback.from_user.id) or guess_lang_from_telegram(getattr(callback.from_user, "language_code", None))
        await callback.answer(t(lang, "not_authorized"), show_alert=True)
        return

    templates = {
        'welcome': {
            'title': '🎉 پیام خوشامدگویی',
            'content': (
                "🎉 به خانواده بزرگ ما خوش آمدید!\n\n"
                "🚀 با خدمات پریمیوم ما، اینترنت بدون محدودیت را تجربه کنید.\n"
                "💎 کیفیت بالا، سرعت فوق‌العاده، پشتیبانی 24/7\n\n"
                "🎁 کد تخفیف ویژه برای شما: WELCOME20\n"
                "📞 پشتیبانی: @support"
            )
        },
        'offer': {
            'title': '🔥 پیام تخفیف ویژه',
            'content': (
                "🔥 پیشنهاد فوق‌العاده!\n\n"
                "💥 تخفیف 30% برای تمامی پکیج‌ها\n"
                "⏰ فقط تا پایان هفته!\n\n"
                "🛍 همین حالا سفارش دهید:\n"
                "🎯 کد تخفیف: MEGA30\n\n"
                "📞 سفارش سریع: /start"
            )
        },
        'maintenance': {
            'title': '🔧 اطلاع تعمیرات',
            'content': (
                "🔧 اطلاعیه تعمیرات\n\n"
                "⚠️ سرورهای ما طی 2 ساعت آینده به‌روزرسانی خواهند شد.\n"
                "⏰ زمان: 02:00 الی 04:00 صبح\n\n"
                "💡 در این مدت ممکن است قطعی کوتاه‌مدت داشته باشید.\n"
                "🙏 از صبر و شکیبایی شما متشکریم."
            )
        },
        'reminder': {
            'title': '⏰ یادآوری تمدید',
            'content': (
                "⏰ یادآوری تمدید سرویس\n\n"
                "📅 سرویس شما تا 3 روز دیگر منقضی می‌شود.\n"
                "🔄 برای تمدید و ادامه استفاده:\n\n"
                "💳 گزینه 1: تمدید آنلاین\n"
                "💰 گزینه 2: شارژ کیف پول\n\n"
                "📞 راهنمایی: /start"
            )
        }
    }

    kb = InlineKeyboardBuilder()
    for key, template in templates.items():
        kb.button(text=template['title'], callback_data=f'template_{key}')
    # kb.button(text='➕ ساخت الگوی جدید', callback_data='create_template')
    kb.button(text='⬅️ بازگشت', callback_data='broadcast_management_menu')
    kb.adjust(1)

    await callback.message.edit_text(
        "📋 **الگوهای پیام آماده**\n\n"
        "یکی از الگوهای زیر را انتخاب کنید یا الگوی جدید ایجاد کنید:",
        reply_markup=kb.as_markup(),
        parse_mode='Markdown'
    )
    await callback.answer()

@router.callback_query(F.data.startswith('template_'))
async def use_message_template(callback: CallbackQuery, state: FSMContext):
    """Use a predefined message template"""
    if callback.from_user.id not in ADMIN_IDS:
        lang = get_cached_lang(callback.from_user.id) or guess_lang_from_telegram(getattr(callback.from_user, "language_code", None))
        await callback.answer(t(lang, "not_authorized"), show_alert=True)
        return

    template_key = callback.data.split('_')[1]
    
    templates = {
        'welcome': "🎉 به خانواده بزرگ ما خوش آمدید!\n\n🚀 با خدمات پریمیوم ما، اینترنت بدون محدودیت را تجربه کنید.\n💎 کیفیت بالا، سرعت فوق‌العاده، پشتیبانی 24/7\n\n🎁 کد تخفیف ویژه برای شما: WELCOME20\n📞 پشتیبانی: @support",
        'offer': "🔥 پیشنهاد فوق‌العاده!\n\n💥 تخفیف 30% برای تمامی پکیج‌ها\n⏰ فقط تا پایان هفته!\n\n🛍 همین حالا سفارش دهید:\n🎯 کد تخفیف: MEGA30\n\n📞 سفارش سریع: /start",
        'maintenance': "🔧 اطلاعیه تعمیرات\n\n⚠️ سرورهای ما طی 2 ساعت آینده به‌روزرسانی خواهند شد.\n⏰ زمان: 02:00 الی 04:00 صبح\n\n💡 در این مدت ممکن است قطعی کوتاه‌مدت داشته باشید.\n🙏 از صبر و شکیبایی شما متشکریم.",
        'reminder': "⏰ یادآوری تمدید سرویس\n\n📅 سرویس شما تا 3 روز دیگر منقضی می‌شود.\n🔄 برای تمدید و ادامه استفاده:\n\n💳 گزینه 1: تمدید آنلاین\n💰 گزینه 2: شارژ کیف پول\n\n📞 راهنمایی: /start"
    }
    
    template_content = templates.get(template_key, "")
    
    if not template_content:
        await callback.answer("الگو یافت نشد", show_alert=True)
        return

    # Store template as message data
    await state.set_data({
        'broadcast_type': 'immediate',
        'message_data': {
            'content_type': 'text',
            'text': template_content,
        }
    })

    kb = InlineKeyboardBuilder()
    kb.button(text='✅ ارسال فوری', callback_data='confirm_broadcast')
    kb.button(text='🎯 ارسال هدفمند', callback_data='broadcast_targeted')
    # kb.button(text='✏️ ویرایش متن', callback_data='edit_template')
    kb.button(text='❌ لغو', callback_data='cancel_broadcast')
    kb.adjust(2)

    await callback.message.edit_text(
        f"📋 **پیش‌نمایش الگو**\n\n"
        f"{template_content}\n\n"
        "✅ الگو انتخاب شد. حالا می‌توانید آن را ارسال کنید:",
        reply_markup=kb.as_markup()
    )
    await callback.answer()

@router.callback_query(F.data == 'cancel_broadcast')
async def cancel_broadcast(callback: CallbackQuery, state: FSMContext):
    """Cancel broadcast operation"""
    if callback.from_user.id not in ADMIN_IDS:
        lang = get_cached_lang(callback.from_user.id) or guess_lang_from_telegram(getattr(callback.from_user, "language_code", None))
        await callback.answer(t(lang, "not_authorized"), show_alert=True)
        return

    await state.clear()
    await callback.message.edit_text("❌ ارسال پیام لغو شد.")
    await callback.answer() 

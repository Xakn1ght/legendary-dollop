from __future__ import annotations

from aiogram import F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import ADMIN_ID, ADMIN_USERNAME
from app.database import crud

from .common import SupportStates, router, safe_edit_message


@router.message(F.text.in_(["پشتیبانی💬", "📞 پشتیبانی"]))
async def enter_support(message: Message, state: FSMContext, session: AsyncSession):
    await state.clear()
    
    # Welcome text (friend-style copy, adapted to AstroByte)
    welcome_text = (
        "به بخش پشتیبانی AstroByte خوش آمدید 🩷\n\n"
        "اَسـتروبایـت همیشه کنار شماست؛ اگر سوال یا مشکلی دارید، تیم پشتیبانی ما آماده است تا سریع و دقیق کمک کند.\n\n"
        "✅ پشتیبانی آنلاین\n"
        "✅ پاسخ سریع به پیام‌ها\n"
        "✅ رفع هرگونه مشکل فنی یا اتصال\n\n"
        "❗️ از گزینه‌های زیر برای ارتباط استفاده کنید 👇"
    )
    
    # Create enhanced keyboard with better organization
    kb = InlineKeyboardBuilder()
    
    # Main support categories
    kb.button(text="🔌 مشکل اتصال", callback_data="support_quick_connection")
    kb.button(text="💰 مشکل مالی", callback_data="support_quick_money")
    kb.button(text="❓ سوال عمومی", callback_data="support_quick_other")
    
    # Quick access
    kb.button(text="🎟 تیکت‌های من", callback_data="support_my_tickets")
    
    # Emergency contact
    admin_url = f"https://t.me/{ADMIN_USERNAME}" if ADMIN_USERNAME else f"tg://user?id={ADMIN_ID}"
    kb.button(text="🚨 تماس فوری با ادمین", url=admin_url)
    
    # Layout: [مشکل اتصال | مشکل مالی], [سوال عمومی | تیکت‌های من], [تماس فوری]
    kb.adjust(2, 2, 1)
    
    await message.answer(welcome_text, reply_markup=kb.as_markup(), parse_mode="Markdown")


# Quick support handlers for streamlined UX
@router.callback_query(F.data == "support_quick_connection")
async def quick_connection_support(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Quick connection support flow"""
    await state.clear()
    await state.update_data(category="connection")
    
    # Check if user has services
    user = await crud.get_user(session, callback.from_user.id)
    if not user:
        await callback.answer("ابتدا /start را ارسال کنید.", show_alert=True)
        return
    
    subs = await crud.get_user_subscriptions(session, user.id)
    if subs:
        # User has services - ask which one
        kb = InlineKeyboardBuilder()
        for sub in subs[:5]:  # Limit to 5 for UI
            kb.button(text=f"📱 {sub.marzban_username}", callback_data=f"support_sub_connection_{sub.id}")
        kb.button(text="➡️ ادامه بدون انتخاب", callback_data="support_sub_connection_none")
        kb.button(text="🔙 بازگشت", callback_data="support_back_main")
        kb.adjust(1)
        
        await safe_edit_message(callback, 
            "🔌 **مشکل اتصال**\n\nکدام سرویس مشکل دارد؟\n(یا بدون انتخاب ادامه دهید)", 
            kb.as_markup()
        )
    else:
        # No services - direct to connection troubleshooting
        await state.update_data(subscription_id=None)
        await state.set_state(SupportStates.connection_choose_os)
        builder = InlineKeyboardBuilder()
        os_list = ["Android", "iOS", "Windows", "macOS", "Linux", "Other"]
        for os_name in os_list:
            builder.button(text=os_name, callback_data=f"support_os_{os_name}")
        builder.adjust(2)
        builder.button(text="🔙 بازگشت", callback_data="support_back_main")
        
        await safe_edit_message(callback, 
            "🔌 **مشکل اتصال**\n\nمرحله 1 از 3: سیستم‌عامل را انتخاب کنید:", 
            builder.as_markup()
        )
    
    await callback.answer()


@router.callback_query(F.data == "support_quick_money")
async def quick_money_support(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Quick money support flow"""
    await state.clear()
    await state.update_data(category="money")
    
    # Check if user has services
    user = await crud.get_user(session, callback.from_user.id)
    if not user:
        await callback.answer("ابتدا /start را ارسال کنید.", show_alert=True)
        return
    
    subs = await crud.get_user_subscriptions(session, user.id)
    if subs:
        # User has services - ask which one
        kb = InlineKeyboardBuilder()
        for sub in subs[:5]:  # Limit to 5 for UI
            kb.button(text=f"📱 {sub.marzban_username}", callback_data=f"support_sub_money_{sub.id}")
        kb.button(text="➡️ ادامه بدون انتخاب", callback_data="support_sub_money_none")
        kb.button(text="🔙 بازگشت", callback_data="support_back_main")
        kb.adjust(1)
        
        await safe_edit_message(callback, 
            "💰 **مشکل مالی**\n\nمربوط به کدام سرویس است؟\n(یا بدون انتخاب ادامه دهید)", 
            kb.as_markup()
        )
    else:
        # No services - continue directly
        await state.update_data(subscription_id=None, texts=[], images=[], text_msg_ids=[], image_msg_ids=[])
        await state.set_state(SupportStates.images_two)
        await safe_edit_message(
            callback,
            "💰 **مشکل مالی**\n\n"
            "ابتدا در صورت امکان ۱ تا ۲ اسکرین‌شات/تصویر مرتبط ارسال کنید.\n"
            "سپس توضیح متنی را ارسال می‌گیریم.",
            _images_step_kb(0)
        )
    
    await callback.answer()


@router.callback_query(F.data == "support_quick_other")
async def quick_other_support(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Quick other support flow"""
    await state.clear()
    await state.update_data(category="other")
    
    # Check if user has services
    user = await crud.get_user(session, callback.from_user.id)
    if not user:
        await callback.answer("ابتدا /start را ارسال کنید.", show_alert=True)
        return
    
    subs = await crud.get_user_subscriptions(session, user.id)
    if subs:
        # User has services - ask which one
        kb = InlineKeyboardBuilder()
        for sub in subs[:5]:  # Limit to 5 for UI
            kb.button(text=f"📱 {sub.marzban_username}", callback_data=f"support_sub_other_{sub.id}")
        kb.button(text="➡️ ادامه بدون انتخاب", callback_data="support_sub_other_none")
        kb.button(text="🔙 بازگشت", callback_data="support_back_main")
        kb.adjust(1)
        
        await safe_edit_message(callback, 
            "❓ **سوال عمومی**\n\nمربوط به کدام سرویس است؟\n(یا بدون انتخاب ادامه دهید)", 
            kb.as_markup()
        )
    else:
        # No services - continue directly
        await state.update_data(subscription_id=None, texts=[], images=[], text_msg_ids=[], image_msg_ids=[])
        await state.set_state(SupportStates.images_two)
        await safe_edit_message(
            callback,
            "❓ **سوال عمومی**\n\n"
            "ابتدا (در صورت نیاز) ۱ تا ۲ تصویر ارسال کنید، سپس متن توضیح را بنویسید.",
            _images_step_kb(0)
        )
    
    await callback.answer()


# Removed quick guide entry by request


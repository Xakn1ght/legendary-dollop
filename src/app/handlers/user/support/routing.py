from __future__ import annotations

from aiogram import F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import ADMIN_ID, ADMIN_USERNAME, ISPS, SUPPORT_CATEGORIES
from app.database import crud
from app.utils.bot_i18n import guess_lang_from_telegram, t

from .common import SupportStates, router, safe_edit_message


@router.message(SupportStates.choosing_subscription)
async def list_subscriptions_for_support(message: Message, session: AsyncSession, state: FSMContext):
    user = await crud.get_user(session, message.from_user.id)
    if not user:
        lang = guess_lang_from_telegram(getattr(message.from_user, "language_code", None))
        await message.answer(t(lang, "send_start_first"))
        return
    subs = await crud.get_user_subscriptions(session, user.id)
    if not subs:
        # No services → show FAQ and direct admin DM buttons
        kb = InlineKeyboardBuilder()
        kb.button(text="❓ سوالات متداول (FAQ)", callback_data="support_faq")
        admin_url = f"https://t.me/{ADMIN_USERNAME}" if ADMIN_USERNAME else f"tg://user?id={ADMIN_ID}"
        kb.button(text="📝 پیام به ادمین", url=admin_url)
        kb.adjust(1)
        await message.answer(
            "شما هیچ سرویس فعالی ندارید.\nاگر سوالی دارید، از دکمه‌های زیر استفاده کنید:",
            reply_markup=kb.as_markup()
        )
        return
    kb = InlineKeyboardBuilder()
    for s in subs[:20]:
        kb.button(text=s.marzban_username, callback_data=f"support_sub_{s.id}")
    kb.button(text="سایر/نامشخص", callback_data="support_sub_none")
    kb.button(text="🎟 تیکت‌های من", callback_data="support_my_tickets")
    kb.adjust(2)
    await message.answer("یک مورد را انتخاب کنید:", reply_markup=kb.as_markup())


@router.callback_query(F.data.startswith("support_sub_connection_"))
async def pick_subscription_connection(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Handle subscription selection for connection issues"""
    token = callback.data.removeprefix("support_sub_connection_")
    sub_id = None if token == 'none' else int(token)
    await state.update_data(subscription_id=sub_id)
    
    # Continue to OS selection
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


@router.callback_query(F.data.startswith("support_sub_money_"))
async def pick_subscription_money(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Handle subscription selection for money issues"""
    token = callback.data.removeprefix("support_sub_money_")
    sub_id = None if token == 'none' else int(token)
    await state.update_data(subscription_id=sub_id, texts=[], images=[], text_msg_ids=[], image_msg_ids=[])
    
    # Continue to images/description
    await state.set_state(SupportStates.images_two)
    await safe_edit_message(
        callback,
        "💰 **مشکل مالی**\n\n"
        "ابتدا در صورت امکان ۱ تا ۲ اسکرین‌شات/تصویر مرتبط ارسال کنید.\n"
        "سپس توضیح متنی را ارسال می‌گیریم.",
        _images_step_kb(0)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("support_sub_other_"))
async def pick_subscription_other(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Handle subscription selection for other issues"""
    token = callback.data.removeprefix("support_sub_other_")
    sub_id = None if token == 'none' else int(token)
    await state.update_data(subscription_id=sub_id, texts=[], images=[], text_msg_ids=[], image_msg_ids=[])
    
    # Continue to images/description
    await state.set_state(SupportStates.images_two)
    await safe_edit_message(
        callback,
        "❓ **سوال عمومی**\n\n"
        "ابتدا (در صورت نیاز) ۱ تا ۲ تصویر ارسال کنید، سپس متن توضیح را بنویسید.",
        _images_step_kb(0)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("support_sub_"))
async def pick_subscription(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    token = callback.data.removeprefix("support_sub_")
    sub_id = None if token == 'none' else int(token)
    await state.update_data(subscription_id=sub_id)
    # Move to category selection
    await state.set_state(SupportStates.choosing_category)
    kb = InlineKeyboardBuilder()
    for cat in SUPPORT_CATEGORIES:
        kb.button(text=cat["label"], callback_data=f"support_cat_{cat['key']}")
    kb.button(text="🎟 تیکت‌های من", callback_data="support_my_tickets")
    kb.adjust(2)
    kb.button(text="بازگشت🔙", callback_data="support_back_main")
    await safe_edit_message(callback, "پشتیبانی | دسته مشکل را انتخاب کنید:", kb.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("support_back_main"))
async def back_from_support(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.answer("به منوی اصلی بازگشتید.", )
    await callback.answer()


@router.callback_query(F.data.startswith("support_cat_"))
async def choose_category(callback: CallbackQuery, state: FSMContext):
    cat_key = callback.data.removeprefix("support_cat_")
    await state.update_data(
        category=cat_key,
        texts=[],
        images=[],
        text_msg_ids=[],
        image_msg_ids=[],
        os=None,
        isp=None,
    )
    if cat_key == "connection":
        await state.set_state(SupportStates.connection_choose_os)
        builder = InlineKeyboardBuilder()
        os_list = ["Android", "iOS", "Windows", "macOS", "Linux", "Other"]
        for os_name in os_list:
            builder.button(text=os_name, callback_data=f"support_os_{os_name}")
        builder.adjust(2)
        builder.button(text="بازگشت🔙", callback_data="support_back_main")
        
        await safe_edit_message(callback, "مرحله 1 از 3: سیستم‌عامل را انتخاب کنید:", builder.as_markup())
    else:
        # money or other → directly ask for single-description message
        await state.set_state(SupportStates.description_one)
        await safe_edit_message(callback, "لطفاً مشکل را در یک پیام توضیح دهید (یک پیام متنی).")
        # Offer guided troubleshooter entry point for connection-like issues
        kb = InlineKeyboardBuilder()
        kb.button(text="🛠 شروع راهنمای مرحله‌به‌مرحله", callback_data="support_troubleshoot")
        kb.adjust(1)
        await callback.message.answer("اگر مایلید، از راهنمای مرحله‌به‌مرحله استفاده کنید:", reply_markup=kb.as_markup())
    await callback.answer()


@router.callback_query(F.data == "support_faq")
async def support_faq(callback: CallbackQuery):
    # Simple FAQ entry (can be expanded later)
    text = (
        "سوالات متداول:\n"
        "1) چطور سرویس بخرم؟ از دکمه «خرید سرویس💳».\n"
        "2) آموزش اتصال کجاست؟ از منوی «راهنمای اتصال📚».\n"
        "3) قیمت و پلن‌ها؟ از «خرید سرویس💳» یا تنظیمات داخل ربات."
    )
    await callback.message.answer(text)
    await callback.answer()


@router.callback_query(F.data == "support_msg_admin")
async def support_msg_admin(callback: CallbackQuery):
    # Provide a direct DM link to the admin (username preferred)
    admin_url = f"https://t.me/{ADMIN_USERNAME}" if ADMIN_USERNAME else f"tg://user?id={ADMIN_ID}"
    kb = InlineKeyboardBuilder()
    kb.button(text="باز کردن چت با ادمین", url=admin_url)
    kb.adjust(1)
    await callback.message.answer("برای گفتگو مستقیم با ادمین، دکمه زیر را بزنید:", reply_markup=kb.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("support_os_"))
async def choose_os(callback: CallbackQuery, state: FSMContext):
    os_name = callback.data.removeprefix("support_os_")
    await state.update_data(os=os_name)
    await state.set_state(SupportStates.connection_choose_isp)
    builder = InlineKeyboardBuilder()
    for isp in ISPS:
        builder.button(text=str(isp), callback_data=f"support_isp_{isp}")
    builder.adjust(2)
    builder.button(text="بازگشت🔙", callback_data="support_back_main")
    await safe_edit_message(callback, "مرحله 2 از 3: ارائه‌دهنده اینترنت (ISP) را انتخاب کنید:", builder.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("support_isp_"))
async def choose_isp(callback: CallbackQuery, state: FSMContext):
    isp = callback.data.removeprefix("support_isp_")
    await state.update_data(isp=isp, texts=[], images=[], text_msg_ids=[], image_msg_ids=[])
    await state.set_state(SupportStates.images_two)
    await safe_edit_message(
        callback,
        "مرحله 3 از 3: ابتدا ۱ تا ۲ اسکرین‌شات/تصویر مرتبط ارسال کنید (اختیاری).\n"
        "سپس ‘ادامه و نوشتن متن’ را بزنید و توضیح مشکل را بنویسید.",
        _images_step_kb(0)
    )
    await callback.answer()


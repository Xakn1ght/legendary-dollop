from __future__ import annotations

from datetime import datetime

from aiogram import F
from aiogram.fsm.context import FSMContext
from aiogram.types import KeyboardButton, Message, ReplyKeyboardMarkup
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import ADMIN_ID, CHARGE_PRESET_PACKAGES
from app.database import crud
from app.keyboards.reply import get_main_keyboard
from app.utils.bot_i18n import t, text_matches

from .common import GB, ChargeState, _get_lang, router


@router.message(ChargeState.receipt, F.photo)
async def process_receipt(message: Message, state: FSMContext, session: AsyncSession):
    lang = await _get_lang(message.chat.id, session)
    data = await state.get_data()
    sub_id = data['subscription_id']
    pkg_label = data.get('package_label')
    charge_type = data.get('charge_type', 'normal')

    user = await crud.get_user(session, message.chat.id)
    # Support custom extra days requests
    if pkg_label and pkg_label in CHARGE_PRESET_PACKAGES:
        pkg = CHARGE_PRESET_PACKAGES[pkg_label]
        price = pkg['price']
        traffic_bytes = int(pkg.get('gb', 0) * GB)
        extra_days = pkg.get('days')
    else:
        price = int(data.get('custom_price', 0))
        traffic_bytes = 0
        extra_days = int(data.get('custom_extra_days', 0)) if data.get('custom_extra_days') else None
    
    if charge_type == 'booking':
        # Handle booking as auto-renewal setup
        from app.handlers.user.purchase import PLANS
        plan_name = pkg_label  # Use package label as plan name for now
        
        # Update subscription with renewal settings
        await crud.update_subscription_renewal(
            session, sub_id, 
            renewal_paid=True,
            renewal_template=plan_name,
            renewal_price=price,
            renewal_requested_at=datetime.utcnow()
        )
        
        await state.clear()
        await message.answer(
            t(lang, "charge_booking_receipt_success").format(plan=pkg_label, price=f"{price:,}"),
            reply_markup=get_main_keyboard(message.chat.id, lang=lang)
        )
        
        # Notify admin on the **admin** bot only (separate from user bot).
        from app.utils.admin_bot_helper import get_admin_bot

        admin_bot = get_admin_bot()
        if admin_bot:
            try:
                await admin_bot.send_message(
                    ADMIN_ID,
                    f"📅 رزرو پلن جدید\nسرویس: {data.get('subscription_username', 'unknown')}\nکاربر: {user.full_name} ({user.chat_id})\nپلن: {pkg_label}\nمبلغ: {price:,} تومان",
                )
            except Exception:
                pass
        return
    
    # For normal and 5gb_limit charges, create ChargeRequest
    charge_req = await crud.create_charge_request(
        session, sub_id, user.id, traffic_bytes, extra_days, price, message.message_id
    )

    # Forward photo receipt to admin bot (not user bot)
    from app.utils.admin_bot_helper import get_admin_bot
    admin_bot = get_admin_bot()
    if admin_bot:
        try:
            from app.utils.admin_bot_helper import relay_user_receipt_photo_to_admin

            await relay_user_receipt_photo_to_admin(message.bot, admin_bot, ADMIN_ID, message)
        except Exception:
            pass

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    kb = InlineKeyboardBuilder()
    kb.button(text='✅ تایید', callback_data=f'approve_charge_{charge_req.id}')
    kb.button(text='❌ رد', callback_data=f'deny_charge_{charge_req.id}')
    kb.button(text='💬 چت', callback_data=f'chat_with_user_{user.chat_id}')
    kb.adjust(2, 1)  # First row: 2 buttons (approve/deny), Second row: 1 button (chat)

    # Fetch subscription username explicitly to avoid lazy-load problems
    from app.database import models as db_models
    sub_row = await session.get(db_models.Subscription, sub_id)
    sub_username = sub_row.marzban_username if sub_row else 'unknown'

    pkg_desc = []
    if traffic_bytes:
        pkg_desc.append(f"{int(traffic_bytes/GB)}GB")
    if extra_days:
        pkg_desc.append(f"+{extra_days}days")
    
    # Add charge type info (admin messages stay in Farsi)
    charge_type_desc = {
        'normal': '⚡️ شارژ عادی',
        'normal_5gb_limit': '⚠️ شارژ (حد 5GB)',
        'booking': '📅 رزرو پلن'
    }.get(charge_type, '⚡️ شارژ')

    charge_msg = f"{charge_type_desc}\nسرویس: {sub_username}\nکاربر: {user.full_name} ({user.chat_id})\nبسته: {' '.join(pkg_desc)}"
    
    # Send to admin bot (not user bot)
    if admin_bot:
        try:
            await admin_bot.send_message(ADMIN_ID, charge_msg, reply_markup=kb.as_markup())
        except Exception:
            pass

    await state.clear()
    await message.answer(t(lang, "charge_receipt_sent"), reply_markup=get_main_keyboard(message.chat.id, lang=lang))


@router.message(ChargeState.receipt, text_matches("btn_back"))
async def cancel_receipt(message: Message, state: FSMContext, session: AsyncSession):
    lang = await _get_lang(message.chat.id, session)
    await state.clear()
    await message.answer(t(lang, "charge_cancelled"), reply_markup=get_main_keyboard(message.chat.id, lang=lang))


@router.message(ChargeState.receipt)
async def receipt_catch_all(message: Message, state: FSMContext, session: AsyncSession):
    """Catch any other message in receipt state - allow /start to reset"""
    lang = await _get_lang(message.chat.id, session)
    
    # Allow /start to reset flow
    if message.text and message.text.startswith("/start"):
        await state.clear()
        return  # Let start handler handle it
    
    # Any other text/non-photo - remind user to send receipt or go back
    await message.answer(
        ("لطفاً تصویر رسید را ارسال کنید یا بازگشت را بزنید." if lang == "fa" else "Please send the receipt image or press back."),
        reply_markup=ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text=t(lang, "btn_back"))]], resize_keyboard=True)
    ) 

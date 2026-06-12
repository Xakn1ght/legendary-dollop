from __future__ import annotations

from aiogram import F
from aiogram.fsm.context import FSMContext
from aiogram.types import KeyboardButton, Message, ReplyKeyboardMarkup
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import ADMIN_ID, CHARGE_PRESET_PACKAGES
from app.database import crud
from app.keyboards.reply import get_main_keyboard
from app.services.flows.charge import (
    cancel_charge_order,
    start_charge_order,
    submit_charge_receipt,
)
from app.services.flows.errors import FlowError
from app.utils.bot_i18n import t, text_matches

from .common import ChargeState, _get_lang, router


@router.message(ChargeState.receipt, F.photo)
async def process_receipt(message: Message, state: FSMContext, session: AsyncSession):
    lang = await _get_lang(message.chat.id, session)
    data = await state.get_data()
    sub_id = data['subscription_id']
    pkg_label = data.get('package_label')
    charge_type = data.get('charge_type', 'normal')

    user = await crud.get_user(session, message.chat.id)

    try:
        charge_order_id = data.get('charge_order_id')
        if charge_order_id:
            # Booking flow: the order was created when the plan was picked.
            charge_req = await submit_charge_receipt(
                session, user, charge_order_id, receipt_message_id=message.message_id
            )
        elif pkg_label and pkg_label in CHARGE_PRESET_PACKAGES:
            # Preset packages go through the shared flow (server-side >5GB gate,
            # ownership/active checks); receipt is attached in the same step.
            result = await start_charge_order(
                session,
                user,
                subscription_id=sub_id,
                package_name=pkg_label,
                charge_type=charge_type,
                use_credit=False,
                status="draft",
            )
            charge_req = await submit_charge_receipt(
                session, user, result.charge_request.id, receipt_message_id=message.message_id
            )
        else:
            # Custom extra-days request (no preset package): price comes from the
            # admin-quoted amount held in FSM state.
            price = int(data.get('custom_price', 0))
            extra_days = int(data.get('custom_extra_days', 0)) if data.get('custom_extra_days') else None
            charge_req = await crud.create_charge_request(
                session, sub_id, user.id, 0, extra_days, price, message.message_id
            )
    except FlowError:
        await state.clear()
        await message.answer(
            ("این درخواست قابل پردازش نیست. لطفاً دوباره تلاش کنید." if lang == "fa" else "This request can't be processed. Please try again."),
            reply_markup=get_main_keyboard(message.chat.id, lang=lang),
        )
        return

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

    from app.utils.receipt_captions import charge_receipt_caption

    charge_msg = charge_receipt_caption(charge_req, user, sub_username, source="bot")

    # Notify admin web panel (live receipts list + badge)
    try:
        import asyncio as _asyncio

        from app.api.routes.admin_ws import broadcast_admin_event

        _asyncio.create_task(broadcast_admin_event('receipts_updated', {'order_id': charge_req.id, 'type': 'charge'}))
    except Exception:
        pass

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
    # If a draft order was already created (booking flow), cancel it properly so any
    # reserved credit comes back.
    data = await state.get_data()
    charge_order_id = data.get('charge_order_id')
    if charge_order_id:
        user = await crud.get_user(session, message.chat.id)
        try:
            await cancel_charge_order(session, user, charge_order_id)
        except FlowError:
            pass
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

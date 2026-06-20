from __future__ import annotations

from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import PLANS
from app.database import crud
from app.keyboards.reply import KEYBOARD_MARKUP_BACK, get_main_keyboard
from app.utils.bot_i18n import normalize_lang, set_cached_lang, t, text_matches
from app.utils.validation import InputValidator, sanitize_user_input

from .common import (
    ChargeState,
    _build_main_plan_keyboard,
    _build_package_keyboard,
    _build_subscription_keyboard,
    _build_traffic_options_keyboard,
    _get_lang,
    check_subscription_traffic,
    router,
)


@router.message(text_matches("btn_recharge"))
async def start_charge(message: Message, state: FSMContext, session: AsyncSession):
    # We need the internal User.id primary key, not Telegram chat_id.
    user = await crud.get_user(session, message.chat.id)
    lang = normalize_lang(getattr(user, "language", None)) if user else normalize_lang(getattr(message.from_user, "language_code", None))
    set_cached_lang(message.chat.id, lang)
    if not user:
        await message.answer(
            t(lang, "start_bot_first"),
            reply_markup=get_main_keyboard(message.chat.id, lang=lang),
        )
        return
    subs = await crud.get_user_active_subscriptions(session, user.id)
    if not subs:
        await message.answer(
            t(lang, "charge_no_services"),
            reply_markup=get_main_keyboard(message.chat.id, lang=lang),
        )
        return
    if len(subs) == 1:
        await state.update_data(subscription_id=subs[0].id)
        # Check traffic before proceeding
        await check_subscription_traffic(message, state, session, subs[0])
    else:
        await state.set_state(ChargeState.subscription)
        await message.answer(
            t(lang, "charge_which_service"),
            reply_markup=_build_subscription_keyboard(subs),
        )


@router.message(ChargeState.subscription)
async def choose_subscription(message: Message, state: FSMContext, session: AsyncSession):
    lang = await _get_lang(message.chat.id, session)
    
    # Allow /start to reset flow
    if message.text and message.text.startswith("/start"):
        await state.clear()
        return  # Let start handler handle it
    
    # Check for back button
    if message.text in (t("fa", "btn_back"), t("en", "btn_back")):
        await state.clear()
        await message.answer(t(lang, "charge_cancelled"), reply_markup=get_main_keyboard(message.chat.id, lang=lang))
        return
    
    # Validate input
    if not InputValidator.validate_safe_text(message.text):
        await message.answer(t(lang, "charge_invalid_service"))
        return
    
    if not InputValidator.validate_length(message.text, 'custom_username'):
        await message.answer(t(lang, "charge_invalid_service"))
        return
    
    # Sanitize input
    sanitized_username = sanitize_user_input(message.text)
    
    # find subscription by username (again using User.id)
    user = await crud.get_user(session, message.chat.id)
    if not user:
        await message.answer(t(lang, "start_bot_first"), reply_markup=get_main_keyboard(message.chat.id, lang=lang))
        return
    subs = await crud.get_user_active_subscriptions(session, user.id)
    selected = next((s for s in subs if s.marzban_username == sanitized_username), None)
    if not selected:
        await message.answer(t(lang, "charge_invalid_service"))
        return
    await state.update_data(subscription_id=selected.id)
    # Check traffic before proceeding
    await check_subscription_traffic(message, state, session, selected)


@router.message(ChargeState.traffic_check, text_matches("charge_now"))
async def proceed_with_5gb_limit(message: Message, state: FSMContext, session: AsyncSession):
    """User chooses to proceed with 5GB carryover limit"""
    lang = await _get_lang(message.chat.id, session)
    await state.update_data(charge_type='normal_5gb_limit')
    await state.set_state(ChargeState.package)
    await message.answer(
        t(lang, "charge_immediate_title"),
        reply_markup=_build_package_keyboard(lang)
    )


@router.message(ChargeState.traffic_check, text_matches("book_plan"))
async def choose_booking(message: Message, state: FSMContext, session: AsyncSession):
    """User chooses to book/reserve a plan: ask for main plan (PLANS), not charge packages."""
    lang = await _get_lang(message.chat.id, session)
    await state.update_data(charge_type='booking')
    await state.set_state(ChargeState.booking_plan)
    await message.answer(
        t(lang, "charge_booking_title"),
        reply_markup=_build_main_plan_keyboard(lang)
    )


@router.message(ChargeState.booking_plan)
async def booking_pick_plan(message: Message, state: FSMContext, session: AsyncSession):
    lang = await _get_lang(message.chat.id, session)
    
    # Allow /start to reset flow
    if message.text and message.text.startswith("/start"):
        await state.clear()
        return  # Let start handler handle it
    
    if message.text in (t("fa", "btn_back"), t("en", "btn_back")):
        await state.set_state(ChargeState.traffic_check)
        await message.answer(t(lang, "charge_back_step"), reply_markup=_build_traffic_options_keyboard(lang))
        return
    if message.text not in PLANS:
        await message.answer(t(lang, "charge_choose_plan"), reply_markup=_build_main_plan_keyboard(lang))
        return
    data = await state.get_data()
    sub_id = data.get('subscription_id')
    if not sub_id:
        await state.clear()
        await message.answer(t(lang, "charge_error_no_sub"), reply_markup=get_main_keyboard(message.chat.id, lang=lang))
        return
    plan_name = message.text
    plan_info = PLANS[plan_name]
    # A booking is paid like any other charge: create the order now and apply the
    # renewal only when an admin approves the receipt (flows.charge.approve_charge).
    from app.services.flows.charge import start_booking_order
    from app.services.flows.errors import FlowError

    user = await crud.get_user(session, message.chat.id)
    try:
        result = await start_booking_order(session, user, subscription_id=sub_id, plan_name=plan_name)
    except FlowError:
        await state.clear()
        await message.answer(t(lang, "charge_error_no_sub"), reply_markup=get_main_keyboard(message.chat.id, lang=lang))
        return

    await state.update_data(charge_order_id=result.charge_request.id, package_label=plan_name)
    await state.set_state(ChargeState.receipt)
    await message.answer(
        t(lang, "charge_booking_success").format(
            plan=plan_name,
            gb=plan_info.get("gb"),
            price=f'{plan_info.get("price"):,}'
        )
        + (
            "\n\n💳 لطفاً مبلغ را واریز کرده و تصویر رسید را ارسال کنید تا رزرو پس از تایید ادمین فعال شود."
            if lang == "fa"
            else "\n\n💳 Please pay and send the receipt image; the booking activates after admin approval."
        ),
        reply_markup=KEYBOARD_MARKUP_BACK,
    )


@router.message(ChargeState.traffic_check, text_matches("btn_back"))
async def back_from_traffic_check(message: Message, state: FSMContext, session: AsyncSession):
    lang = await _get_lang(message.chat.id, session)
    # Cancel and return to main
    await state.clear()
    await message.answer(t(lang, "charge_cancelled"), reply_markup=get_main_keyboard(message.chat.id, lang=lang))


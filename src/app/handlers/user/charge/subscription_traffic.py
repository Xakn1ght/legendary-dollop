from __future__ import annotations

from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import PLANS
from app.database import crud
from app.keyboards.reply import get_main_keyboard
from app.utils.bot_i18n import normalize_lang, set_cached_lang, t, text_matches
from app.utils.validation import InputValidator, sanitize_user_input

from .common import (
    ChargeState,
    _back_keyboard,
    _build_booking_months_keyboard,
    _build_main_plan_keyboard,
    _build_package_keyboard,
    _build_subscription_keyboard,
    _build_traffic_options_keyboard,
    _get_lang,
    booking_months_from_text,
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
            reply_markup=await _build_subscription_keyboard(state, subs, lang),
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
    from app.handlers.user.charge.common import _is_vip_chat
    await message.answer(
        t(lang, "charge_immediate_title"),
        reply_markup=await _build_package_keyboard(state, lang, is_vip=await _is_vip_chat(session, message.chat.id))
    )


@router.message(ChargeState.traffic_check, text_matches("book_plan"))
async def choose_booking(message: Message, state: FSMContext, session: AsyncSession):
    """Booking step 1 (2026-07-13, image-5 parity for the bot lane): pick the
    duration first — 1/2/3 prepaid months, exactly like the webapp picker.

    Multi-month is a VIP perk (2026-07-14, Pasha: "no other user except VIP
    should have the 2/3 months category") — non-VIP skips the months step and
    books a 1-month plan directly."""
    lang = await _get_lang(message.chat.id, session)
    from app.handlers.user.charge.common import _is_vip_chat
    is_vip = await _is_vip_chat(session, message.chat.id)
    await state.update_data(charge_type='booking', booking_months=1)
    if not is_vip:
        await state.set_state(ChargeState.booking_plan)
        await message.answer(
            t(lang, "charge_booking_title"),
            reply_markup=await _build_main_plan_keyboard(
                state, lang, include_custom=True, is_vip=False,
            ),
        )
        return
    await state.set_state(ChargeState.booking_months)
    await message.answer(
        t(lang, "charge_booking_months_title"),
        reply_markup=await _build_booking_months_keyboard(state, lang),
    )


@router.message(ChargeState.booking_months)
async def booking_pick_months(message: Message, state: FSMContext, session: AsyncSession):
    lang = await _get_lang(message.chat.id, session)
    if message.text and message.text.startswith("/start"):
        await state.clear()
        return
    if message.text in (t("fa", "btn_back"), t("en", "btn_back")):
        await state.set_state(ChargeState.traffic_check)
        await message.answer(t(lang, "charge_back_step"), reply_markup=await _build_traffic_options_keyboard(state, lang))
        return
    months = booking_months_from_text(message.text or "")
    if not months:
        await message.answer(
            t(lang, "charge_choose_from_buttons"),
            reply_markup=await _build_booking_months_keyboard(state, lang),
        )
        return
    from app.handlers.user.charge.common import _is_vip_chat
    await state.update_data(booking_months=months)
    await state.set_state(ChargeState.booking_plan)
    await message.answer(
        t(lang, "charge_booking_title"),
        # Custom GB builder is a 1-month product (same rule as the webapp).
        reply_markup=await _build_main_plan_keyboard(
            state, lang, include_custom=(months == 1),
            is_vip=await _is_vip_chat(session, message.chat.id),
        ),
    )


async def _start_booking(message: Message, state: FSMContext, session: AsyncSession, lang: str, plan_name: str):
    """Shared tail of the booking flow: create the order, ask for the receipt."""
    from app.services.flows.charge import start_booking_order
    from app.services.flows.errors import FlowError
    from app.services.flows.pricing import get_plan_info, plan_display_name

    data = await state.get_data()
    sub_id = data.get('subscription_id')
    if not sub_id:
        await state.clear()
        await message.answer(t(lang, "charge_error_no_sub"), reply_markup=get_main_keyboard(message.chat.id, lang=lang))
        return

    user = await crud.get_user(session, message.chat.id)
    try:
        result = await start_booking_order(session, user, subscription_id=sub_id, plan_name=plan_name)
    except FlowError as e:
        if e.code in ("invalid_plan", "vip_only_plan", "months_vip_only"):
            from app.handlers.user.charge.common import _is_vip_chat
            months = int(data.get('booking_months') or 1)
            await message.answer(
                t(lang, "charge_choose_plan"),
                reply_markup=await _build_main_plan_keyboard(
                    state, lang, include_custom=(months == 1),
                    is_vip=await _is_vip_chat(session, message.chat.id),
                ),
            )
            return
        await state.clear()
        await message.answer(t(lang, "charge_error_no_sub"), reply_markup=get_main_keyboard(message.chat.id, lang=lang))
        return

    label = plan_display_name(plan_name, lang)
    info = get_plan_info(plan_name, PLANS) or {}
    await state.update_data(charge_order_id=result.charge_request.id, package_label=label)
    await state.set_state(ChargeState.receipt)
    await message.answer(
        t(lang, "charge_booking_success").format(
            plan=label,
            gb=info.get("gb", "-"),
            # The order price is authoritative: months-scaled AND VIP-discounted.
            price=f'{result.charge_request.price:,}',
        )
        + (
            "\n\nلطفاً مبلغ را واریز کرده و تصویر رسید را ارسال کنید تا رزرو پس از تایید ادمین فعال شود."
            if lang == "fa"
            else "\n\nPlease pay and send the receipt image; the booking activates after admin approval."
        ),
        reply_markup=await _back_keyboard(state, lang),
    )


def _booking_custom_bounds(is_vip: bool) -> tuple[int, int]:
    from app.core.pricing import CUSTOM_MAX_GB, CUSTOM_MAX_GB_NONVIP
    return 1, (CUSTOM_MAX_GB if is_vip else CUSTOM_MAX_GB_NONVIP)


@router.message(ChargeState.booking_plan)
async def booking_pick_plan(message: Message, state: FSMContext, session: AsyncSession):
    lang = await _get_lang(message.chat.id, session)

    # Allow /start to reset flow
    if message.text and message.text.startswith("/start"):
        await state.clear()
        return  # Let start handler handle it

    if message.text in (t("fa", "btn_back"), t("en", "btn_back")):
        from app.handlers.user.charge.common import _is_vip_chat
        if await _is_vip_chat(session, message.chat.id):
            await state.set_state(ChargeState.booking_months)
            await message.answer(
                t(lang, "charge_booking_months_title"),
                reply_markup=await _build_booking_months_keyboard(state, lang),
            )
        else:
            # Non-VIP never saw a months step — back returns to the options.
            await state.set_state(ChargeState.traffic_check)
            await message.answer(t(lang, "charge_back_step"), reply_markup=await _build_traffic_options_keyboard(state, lang))
        return

    data = await state.get_data()
    months = int(data.get('booking_months') or 1)

    if message.text in (t("fa", "charge_custom_plan_btn"), t("en", "charge_custom_plan_btn")) and months == 1:
        from app.handlers.user.charge.common import _is_vip_chat, _persian_digits
        lo, hi = _booking_custom_bounds(await _is_vip_chat(session, message.chat.id))
        bounds = {"min": _persian_digits(lo) if lang == "fa" else lo, "max": _persian_digits(hi) if lang == "fa" else hi}
        await state.set_state(ChargeState.booking_custom_gb)
        await message.answer(
            t(lang, "charge_custom_gb_ask").format(**bounds),
            reply_markup=await _back_keyboard(state, lang),
        )
        return

    if message.text not in PLANS:
        from app.handlers.user.charge.common import _is_vip_chat
        await message.answer(
            t(lang, "charge_choose_plan"),
            reply_markup=await _build_main_plan_keyboard(
                state, lang, include_custom=(months == 1),
                is_vip=await _is_vip_chat(session, message.chat.id),
            ),
        )
        return

    plan_name = message.text if months <= 1 else f"{message.text}@{months}m"
    await _start_booking(message, state, session, lang, plan_name)


@router.message(ChargeState.booking_custom_gb)
async def booking_custom_gb(message: Message, state: FSMContext, session: AsyncSession):
    lang = await _get_lang(message.chat.id, session)
    if message.text and message.text.startswith("/start"):
        await state.clear()
        return
    if message.text in (t("fa", "btn_back"), t("en", "btn_back")):
        from app.handlers.user.charge.common import _is_vip_chat
        await state.set_state(ChargeState.booking_plan)
        await message.answer(
            t(lang, "charge_booking_title"),
            reply_markup=await _build_main_plan_keyboard(
                state, lang, include_custom=True,
                is_vip=await _is_vip_chat(session, message.chat.id),
            ),
        )
        return

    from app.handlers.user.charge.common import _is_vip_chat, _persian_digits
    lo, hi = _booking_custom_bounds(await _is_vip_chat(session, message.chat.id))
    raw = (message.text or "").strip().translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789"))
    try:
        gb = int(raw)
    except Exception:
        gb = None
    if gb is None or not (lo <= gb <= hi):
        bounds = {"min": _persian_digits(lo) if lang == "fa" else lo, "max": _persian_digits(hi) if lang == "fa" else hi}
        await message.answer(
            t(lang, "charge_invalid_gb").format(**bounds),
            reply_markup=await _back_keyboard(state, lang),
        )
        return
    await _start_booking(message, state, session, lang, f"custom:{gb}")


@router.message(ChargeState.traffic_check, text_matches("btn_back"))
async def back_from_traffic_check(message: Message, state: FSMContext, session: AsyncSession):
    lang = await _get_lang(message.chat.id, session)
    # Cancel and return to main
    await state.clear()
    await message.answer(t(lang, "charge_cancelled"), reply_markup=get_main_keyboard(message.chat.id, lang=lang))


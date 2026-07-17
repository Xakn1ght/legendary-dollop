from __future__ import annotations

from aiogram import F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import CHARGE_RATE_PER_DAY, DAY_PLANS
from app.database import crud
from app.handlers.user.flow_inline import ikb
from app.keyboards.reply import get_main_keyboard
from app.utils.bot_i18n import t

from .common import (
    ChargeState,
    _back_keyboard,
    _build_booking_months_keyboard,
    _get_lang,
    check_subscription_traffic,
    router,
)


@router.callback_query(F.data.startswith('charge_'))
async def cb_quick_charge(cb: CallbackQuery, state: FSMContext, session: AsyncSession):
    username = cb.data[len('charge_'):]
    lang = await _get_lang(cb.from_user.id, session)
    user = await crud.get_user(session, cb.from_user.id)
    if not user:
        await cb.answer(t(lang, "send_start_first"), show_alert=True)
        return
    subs = await crud.get_user_active_subscriptions(session, user.id)
    target = next((s for s in subs if s.marzban_username == username), None)
    if not target:
        await cb.answer(t(lang, "charge_service_not_found"), show_alert=True)
        return
    await state.update_data(subscription_id=target.id)
    # Route into normal charge flow starting with traffic check
    await check_subscription_traffic(cb.message, state, session, target)
    await cb.answer()


@router.callback_query(F.data.startswith('buydays_'))
async def cb_buy_days(cb: CallbackQuery, state: FSMContext, session: AsyncSession):
    # Format: buydays_{username}
    lang = await _get_lang(cb.from_user.id, session)
    try:
        _, username = cb.data.split('_', 1)
    except Exception:
        await cb.answer(t(lang, "invalid_request"), show_alert=True)
        return
    user = await crud.get_user(session, cb.from_user.id)
    if not user:
        await cb.answer(t(lang, "send_start_first"), show_alert=True)
        return
    subs = await crud.get_user_active_subscriptions(session, user.id)
    target = next((s for s in subs if s.marzban_username == username), None)
    if not target:
        await cb.answer(t(lang, "charge_service_not_found"), show_alert=True)
        return
    # Ask user to choose a day plan (admin-configurable)
    await state.update_data(subscription_id=target.id)
    rows = [[title] for title in DAY_PLANS.keys()]
    rows.append([t(lang, "btn_back")])
    await state.set_state(ChargeState.buy_days_plan)
    await cb.message.answer(t(lang, "charge_buy_days_title"), reply_markup=await ikb(state, rows))
    await cb.answer()


@router.message(ChargeState.buy_days_plan)
async def handle_buy_days_plan(message: Message, state: FSMContext, session: AsyncSession):
    lang = await _get_lang(message.chat.id, session)
    
    # Allow /start to reset flow
    if message.text and message.text.startswith("/start"):
        await state.clear()
        return  # Let start handler handle it
    
    if message.text in (t("fa", "btn_back"), t("en", "btn_back")):
        await state.clear()
        await message.answer(t(lang, "charge_cancelled"), reply_markup=get_main_keyboard(message.chat.id, lang=lang))
        return
    if message.text not in DAY_PLANS:
        await message.answer(t(lang, "charge_buy_days_choose"))
        return
    plan = DAY_PLANS[message.text]
    extra_days = int(plan.get('days', 0))
    price = int(plan.get('price', extra_days * CHARGE_RATE_PER_DAY))
    await state.update_data(custom_extra_days=extra_days, custom_price=price)
    await message.answer(
        t(lang, "charge_buy_days_summary").format(days=extra_days, price=f"{price:,}"),
        reply_markup=await _back_keyboard(state, lang)
    )
    await state.set_state(ChargeState.receipt)


@router.callback_query(F.data.startswith('renew_'))
async def cb_renew(cb: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Start renewal flow — months first, then plan/custom (image-5 parity).

    Months step is VIP-only (2026-07-14): non-VIP goes straight to the
    1-month plan keyboard."""
    lang = await _get_lang(cb.from_user.id, session)
    username = cb.data[len('renew_'):]
    user = await crud.get_user(session, cb.from_user.id)
    if not user:
        await cb.answer(t(lang, "send_start_first"), show_alert=True)
        return
    subs = await crud.get_user_active_subscriptions(session, user.id)
    target = next((s for s in subs if s.marzban_username == username), None)
    if not target:
        await cb.answer(t(lang, "charge_service_not_found"), show_alert=True)
        return
    await state.update_data(subscription_id=target.id, charge_type='booking', booking_months=1)
    is_vip = bool(await crud.is_user_vip(session, user.id))
    if not is_vip:
        from .common import _build_main_plan_keyboard
        await state.set_state(ChargeState.booking_plan)
        await cb.message.answer(
            t(lang, "charge_booking_title"),
            reply_markup=await _build_main_plan_keyboard(state, lang, include_custom=True, is_vip=False),
        )
        await cb.answer()
        return
    await state.set_state(ChargeState.booking_months)
    await cb.message.answer(
        t(lang, "charge_booking_months_title"),
        reply_markup=await _build_booking_months_keyboard(state, lang),
    )
    await cb.answer()

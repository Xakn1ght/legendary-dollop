from __future__ import annotations

from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import PLANS
from app.database import crud
from app.handlers.user.flow_inline import ikb
from app.keyboards.reply import get_main_keyboard
from app.utils.bot_i18n import t, text_matches
from app.utils.validation import InputValidator

from .common import (
    ChargeState,
    _back_keyboard,
    _build_package_keyboard,
    _build_subscription_keyboard,
    _build_traffic_options_keyboard,
    _get_lang,
    _persian_digits,
    router,
)


def _charge_plan_info(order_name: str) -> dict | None:
    """Resolve a top-up order name ("plan", "plan@Nm", "custom:<gb>") against
    the purchase PLANS — the single catalog since plan parity (2026-07-18)."""
    from app.services.flows.pricing import get_plan_info

    return get_plan_info(order_name, PLANS)


async def _send_package_summary(
    message: Message, state: FSMContext, session: AsyncSession, lang: str, order_name: str,
) -> None:
    """Shared summary step for preset AND custom top-ups (plan-parity path)."""
    from app.services.flows.pricing import plan_display_name

    info = _charge_plan_info(order_name)
    if not info:
        await message.answer(t(lang, "charge_choose_from_buttons"))
        return

    price = int(info.get("price") or 0)
    gb = int(info.get("gb") or 0)
    days = int(info.get("days") or 0)
    label = plan_display_name(order_name, lang)

    # Pricing parity law (2026-07-12): show the VIP % here exactly as the
    # order will be priced by flows/charge.py (vip_only plans exempt).
    from app.core.settings import VIP_PURCHASE_DISCOUNT_ENABLED, VIP_PURCHASE_DISCOUNT_PERCENT
    try:
        _user = await crud.get_user(session, message.chat.id)
        if (
            _user and price
            and not info.get("vip_only")
            and VIP_PURCHASE_DISCOUNT_ENABLED and VIP_PURCHASE_DISCOUNT_PERCENT > 0
            and await crud.is_user_vip(session, _user.id)
        ):
            price -= int(price * (VIP_PURCHASE_DISCOUNT_PERCENT / 100))
    except Exception:
        pass

    await state.update_data(package_label=order_name, package_display=label)

    data = await state.get_data()
    charge_type = data.get('charge_type', 'normal')
    remaining_gb = data.get('remaining_gb', 0)

    if lang == "fa":
        if charge_type == 'normal_5gb_limit':
            summary_lines = ['خلاصه شارژ (حد ۵ گیگ):\n', 'نوع: شارژ فوری با حد انتقال']
            summary_lines.append(_persian_digits(f'انتقال: 5GB (از {remaining_gb:.1f}GB موجود)'))
        else:
            summary_lines = ['خلاصه شارژ:\n', 'نوع: شارژ عادی']
        summary_lines.append(f'بسته: {label}')
        if gb:
            summary_lines.append(_persian_digits(f'حجم: {gb} گیگابایت'))
        if days:
            summary_lines.append(_persian_digits(f'اعتبار زمانی: {days} روز'))
        summary_lines.append(_persian_digits(f'مبلغ: {price:,} تومان'))
        if charge_type == 'normal_5gb_limit':
            summary_lines.append(_persian_digits('\nتنها 5GB از ترافیک فعلی انتقال داده می‌شود.'))
        summary_lines.append('\nبرای ادامه و ارسال رسید، گزینه تایید را بزنید.')
    else:
        if charge_type == 'normal_5gb_limit':
            summary_lines = ['Charge Summary (5GB limit):\n', 'Type: Immediate charge with transfer limit']
            summary_lines.append(f'Transfer: 5GB (from {remaining_gb:.1f}GB available)')
        else:
            summary_lines = ['Charge Summary:\n', 'Type: Normal charge']
        summary_lines.append(f'Package: {plan_display_name(order_name, "en")}')
        if gb:
            summary_lines.append(f'Traffic: {gb}GB')
        if days:
            summary_lines.append(f'Duration: {days} days')
        summary_lines.append(f'Price: {price:,} Toman')
        if charge_type == 'normal_5gb_limit':
            summary_lines.append('\nOnly 5GB of current traffic will be transferred.')
        summary_lines.append('\nTo continue and send receipt, tap Confirm.')

    confirm_kb = await ikb(state, [[t(lang, "charge_confirm")], [t(lang, "btn_back")]])
    await state.set_state(ChargeState.confirmation)
    await message.answer('\n'.join(summary_lines), reply_markup=confirm_kb)


def _custom_gb_bounds(is_vip: bool) -> tuple[int, int]:
    from app.core.pricing import CUSTOM_MAX_GB, CUSTOM_MAX_GB_NONVIP
    return 1, (CUSTOM_MAX_GB if is_vip else CUSTOM_MAX_GB_NONVIP)


def _registered_text(lang: str) -> str:
    # Attribute access at call time: the admin panel can change the card at runtime.
    from app.core.settings import payment_ui as _payment

    msg = t(lang, "charge_request_registered").format(card=_payment.PAYMENT_CARD_NUMBER)
    if _payment.PAYMENT_CARD_HOLDER:
        msg += f"\n{_payment.PAYMENT_CARD_HOLDER}"
    return msg


@router.message(ChargeState.package)
async def choose_package(message: Message, state: FSMContext, session: AsyncSession):
    lang = await _get_lang(message.chat.id, session)

    # Allow /start to reset flow
    if message.text and message.text.startswith("/start"):
        await state.clear()
        return  # Let start handler handle it

    if message.text in (t("fa", "btn_back"), t("en", "btn_back")):
        # aiogram stops at the FIRST matching handler — the "more specific"
        # back handler below never ran and the tap died silently. Call it.
        await back_from_package(message, state, session)
        return

    # Validate package selection
    if not InputValidator.validate_safe_text(message.text):
        await message.answer(t(lang, "charge_choose_from_buttons"))
        return

    # Custom GB builder (plan parity: same as purchase/booking custom).
    if message.text in (t("fa", "charge_custom_plan_btn"), t("en", "charge_custom_plan_btn")):
        from app.handlers.user.charge.common import _is_vip_chat
        lo, hi = _custom_gb_bounds(await _is_vip_chat(session, message.chat.id))
        bounds = {"min": _persian_digits(lo) if lang == "fa" else lo, "max": _persian_digits(hi) if lang == "fa" else hi}
        await state.set_state(ChargeState.package_custom_gb)
        await message.answer(
            t(lang, "charge_custom_gb_ask").format(**bounds),
            reply_markup=await _back_keyboard(state, lang),
        )
        return

    # A bare VIP plan name resolves to its min_months package (700GB/2mo) —
    # exactly the old fixed VIP bundles. Unknown text re-prompts.
    if message.text not in PLANS:
        await message.answer(t(lang, "charge_choose_from_buttons"))
        return
    await _send_package_summary(message, state, session, lang, message.text)


@router.message(ChargeState.package_custom_gb)
async def package_custom_gb(message: Message, state: FSMContext, session: AsyncSession):
    """Custom GB amount for a top-up ("custom:<gb>", priced by the shared curve)."""
    lang = await _get_lang(message.chat.id, session)
    if message.text and message.text.startswith("/start"):
        await state.clear()
        return
    if message.text in (t("fa", "btn_back"), t("en", "btn_back")):
        from app.handlers.user.charge.common import _is_vip_chat
        await state.set_state(ChargeState.package)
        await message.answer(
            t(lang, "charge_choose_package"),
            reply_markup=await _build_package_keyboard(state, lang, is_vip=await _is_vip_chat(session, message.chat.id)),
        )
        return

    from app.handlers.user.charge.common import _is_vip_chat
    lo, hi = _custom_gb_bounds(await _is_vip_chat(session, message.chat.id))
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
    await _send_package_summary(message, state, session, lang, f"custom:{gb}")


@router.message(ChargeState.package, text_matches("btn_back"))
async def back_from_package(message: Message, state: FSMContext, session: AsyncSession):
    """Step back from package selection to the previous logical step."""
    lang = await _get_lang(message.chat.id, session)
    data = await state.get_data()
    # If user had to choose between traffic options, return there
    if data.get('charge_type') in {'booking', 'normal_5gb_limit'} or (data.get('remaining_gb') or 0) > 5:
        await state.set_state(ChargeState.traffic_check)
        await message.answer(t(lang, "charge_back_step"), reply_markup=await _build_traffic_options_keyboard(state, lang))
        return

    # Otherwise, go back to subscription selection when multiple exist; cancel if none
    user = await crud.get_user(session, message.chat.id)
    if not user:
        await state.clear()
        await message.answer(t(lang, "start_bot_first"), reply_markup=get_main_keyboard(message.chat.id, lang=lang))
        return
    subs = await crud.get_user_active_subscriptions(session, user.id)
    if len(subs) > 1:
        await state.set_state(ChargeState.subscription)
        await message.answer(t(lang, "charge_back_to_services"), reply_markup=await _build_subscription_keyboard(state, subs, lang))
    else:
        await state.clear()
        await message.answer(t(lang, "charge_cancelled"), reply_markup=get_main_keyboard(message.chat.id, lang=lang))


@router.message(ChargeState.confirmation, text_matches("charge_confirm"))
async def confirm_charge(message: Message, state: FSMContext, session: AsyncSession):
    lang = await _get_lang(message.chat.id, session)

    # Wallet-credit option (same as the webapp charge flow). Offered for any
    # plan-parity top-up (fixed plan or custom:<gb>); the admin-quoted
    # day-extension path keeps its own handling.
    data = await state.get_data()
    user = await crud.get_user(session, message.chat.id)
    pkg_label = data.get('package_label')
    if user and (user.credit or 0) > 0 and pkg_label and _charge_plan_info(pkg_label):
        await state.set_state(ChargeState.ask_credit)
        credit_kb = await ikb(state, [
            [(f"✅ بله، {user.credit:,} تومان اعتبار را استفاده کن" if lang == "fa" else f"✅ Yes, use {user.credit:,} credit")],
            [("خیر، برای بعد ذخیره کن" if lang == "fa" else "No, save for later")],
        ])
        await message.answer(
            (f"شما **{user.credit:,} تومان اعتبار** دارید! آیا می‌خواهید آن را روی این شارژ استفاده کنید؟" if lang == "fa" else f"You have **{user.credit:,}** credit. Use it for this charge?"),
            reply_markup=credit_kb,
        )
        return

    await message.answer(
        _registered_text(lang),
        reply_markup=await _back_keyboard(state, lang),
        parse_mode="HTML"
    )
    await state.set_state(ChargeState.receipt)


@router.message(ChargeState.ask_credit)
async def charge_credit_choice(message: Message, state: FSMContext, session: AsyncSession):
    lang = await _get_lang(message.chat.id, session)

    if message.text and message.text.startswith("/start"):
        await state.clear()
        return  # Let start handler handle it

    data = await state.get_data()
    user = await crud.get_user(session, message.chat.id)
    use_credit = (message.text or "").startswith("✅ بله") or (message.text or "").startswith("✅ Yes")

    if not use_credit:
        await message.answer(
            _registered_text(lang),
            reply_markup=await _back_keyboard(state, lang),
            parse_mode="HTML"
        )
        await state.set_state(ChargeState.receipt)
        return

    # Create the order now so the credit is reserved on the row (refunded if the
    # user backs out at the receipt step).
    from app.services.flows.charge import start_charge_order
    from app.services.flows.errors import FlowError

    try:
        result = await start_charge_order(
            session,
            user,
            subscription_id=data['subscription_id'],
            package_name=data['package_label'],
            charge_type=data.get('charge_type', 'normal'),
            use_credit=True,
            status="draft",
        )
    except FlowError:
        await state.clear()
        await message.answer(t(lang, "charge_error_fetch"), reply_markup=get_main_keyboard(message.chat.id, lang=lang))
        return

    if result.final_price <= 0:
        # Fully covered by credit — already queued for admin approval by the service.
        await state.clear()
        await message.answer(
            ("✅ شارژ شما به طور کامل با اعتبار پرداخت شد و پس از تایید ادمین اعمال می‌شود." if lang == "fa" else "✅ Your charge was fully paid with credit and will be applied after admin approval."),
            reply_markup=get_main_keyboard(message.chat.id, lang=lang),
        )
        return

    await state.update_data(charge_order_id=result.charge_request.id)
    await message.answer(
        (
            f"💰 {result.credit_used:,} تومان از اعتبار شما استفاده شد.\n"
            f"💵 مبلغ باقیمانده برای پرداخت: {result.final_price:,} تومان\n\n" + _registered_text(lang)
            if lang == "fa"
            else f"💰 {result.credit_used:,} Toman of your credit was used.\n"
            f"💵 Remaining to pay: {result.final_price:,} Toman\n\n" + _registered_text(lang)
        ),
        reply_markup=await _back_keyboard(state, lang),
        parse_mode="HTML"
    )
    await state.set_state(ChargeState.receipt)


@router.message(ChargeState.confirmation, text_matches("btn_back"))
async def cancel_confirm(message: Message, state: FSMContext, session: AsyncSession):
    lang = await _get_lang(message.chat.id, session)
    # Return to package selection to allow changing choice
    await state.set_state(ChargeState.package)
    # (was `_build_package_keyboard(lang)` — unawaited + wrong args, this
    # back-path always crashed; fixed while adding the VIP filter)
    from app.handlers.user.charge.common import _is_vip_chat
    await message.answer(
        t(lang, "charge_back_to_packages"),
        reply_markup=await _build_package_keyboard(state, lang, is_vip=await _is_vip_chat(session, message.chat.id)),
    )


@router.message(ChargeState.confirmation)
async def confirmation_catch_all(message: Message, state: FSMContext, session: AsyncSession):
    """Catch any other message in confirmation state - allow /start to reset"""
    lang = await _get_lang(message.chat.id, session)
    
    # Allow /start to reset flow
    if message.text and message.text.startswith("/start"):
        await state.clear()
        return  # Let start handler handle it
    
    # Any other text - remind user to confirm or go back
    confirm_kb = await ikb(state, [[t(lang, "charge_confirm")], [t(lang, "btn_back")]])
    await message.answer(
        t(lang, "charge_confirm_or_back") if "charge_confirm_or_back" in dir(t) else 
        ("لطفاً تایید یا بازگشت را انتخاب کنید." if lang == "fa" else "Please choose confirm or back."),
        reply_markup=confirm_kb
    )

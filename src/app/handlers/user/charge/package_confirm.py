from __future__ import annotations

from aiogram.fsm.context import FSMContext
from aiogram.types import KeyboardButton, Message, ReplyKeyboardMarkup
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import CHARGE_PRESET_PACKAGES
from app.database import crud
from app.keyboards.reply import get_main_keyboard
from app.utils.bot_i18n import t, text_matches
from app.utils.validation import InputValidator

from .common import (
    ChargeState,
    _build_package_keyboard,
    _build_subscription_keyboard,
    _build_traffic_options_keyboard,
    _get_lang,
    router,
)


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
        # Handled by a more specific handler below
        return
    
    # Validate package selection
    if not InputValidator.validate_safe_text(message.text):
        await message.answer(t(lang, "charge_choose_from_buttons"))
        return
    
    if message.text not in CHARGE_PRESET_PACKAGES:
        await message.answer(t(lang, "charge_choose_from_buttons"))
        return
    await state.update_data(package_label=message.text)
    pkg = CHARGE_PRESET_PACKAGES[message.text]
    price = pkg['price']
    gb = pkg.get('gb')
    days = pkg.get('days')
    
    # Get charge type and remaining traffic info
    data = await state.get_data()
    charge_type = data.get('charge_type', 'normal')
    remaining_gb = data.get('remaining_gb', 0)
    
    # Build summary based on charge type (bilingual)
    if lang == "fa":
        if charge_type == 'booking':
            summary_lines = ['📅 خلاصه رزرو پلن:\n']
            summary_lines.append('🔸 نوع: رزرو (تمدید خودکار)')
        elif charge_type == 'normal_5gb_limit':
            summary_lines = ['⚡️ خلاصه شارژ (حد 5GB):\n']
            summary_lines.append('🔸 نوع: شارژ فوری با حد انتقال')
            summary_lines.append(f'🔸 انتقال: 5GB (از {remaining_gb:.1f}GB موجود)')
        else:
            summary_lines = ['⚡️ خلاصه شارژ:\n']
            summary_lines.append('🔸 نوع: شارژ عادی')
        
        if gb:
            summary_lines.append(f'🔹 حجم: {gb} گیگابایت')
        if days:
            summary_lines.append(f'🔹 اعتبار زمانی: {days} روز')
        summary_lines.append(f'💵 مبلغ: {price:,} تومان')
        
        if charge_type == 'booking':
            summary_lines.append('\n📋 این پلن زمانی اعمال می‌شود که:')
            summary_lines.append('• ترافیک کمتر از 5% باشد')
            summary_lines.append('• یا کمتر از 3 روز تا انقضا باشد')
        elif charge_type == 'normal_5gb_limit':
            summary_lines.append('\n⚠️ تنها 5GB از ترافیک فعلی انتقال داده می‌شود')
        
        summary_lines.append('\nبرای ادامه و ارسال رسید، گزینه تایید را بزنید.')
    else:
        if charge_type == 'booking':
            summary_lines = ['📅 Plan Booking Summary:\n']
            summary_lines.append('🔸 Type: Booking (auto-renewal)')
        elif charge_type == 'normal_5gb_limit':
            summary_lines = ['⚡️ Charge Summary (5GB limit):\n']
            summary_lines.append('🔸 Type: Immediate charge with transfer limit')
            summary_lines.append(f'🔸 Transfer: 5GB (from {remaining_gb:.1f}GB available)')
        else:
            summary_lines = ['⚡️ Charge Summary:\n']
            summary_lines.append('🔸 Type: Normal charge')
        
        if gb:
            summary_lines.append(f'🔹 Traffic: {gb}GB')
        if days:
            summary_lines.append(f'🔹 Duration: {days} days')
        summary_lines.append(f'💵 Price: {price:,} Toman')
        
        if charge_type == 'booking':
            summary_lines.append('\n📋 This plan will be applied when:')
            summary_lines.append('• Traffic drops below 5%')
            summary_lines.append('• Or less than 3 days until expiry')
        elif charge_type == 'normal_5gb_limit':
            summary_lines.append('\n⚠️ Only 5GB of current traffic will be transferred')
        
        summary_lines.append('\nTo continue and send receipt, tap Confirm.')
    
    from aiogram.types import KeyboardButton, ReplyKeyboardMarkup
    confirm_kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text=t(lang, "charge_confirm"))], [KeyboardButton(text=t(lang, "btn_back"))]], resize_keyboard=True)
    await state.set_state(ChargeState.confirmation)
    await message.answer('\n'.join(summary_lines), reply_markup=confirm_kb)


@router.message(ChargeState.package, text_matches("btn_back"))
async def back_from_package(message: Message, state: FSMContext, session: AsyncSession):
    """Step back from package selection to the previous logical step."""
    lang = await _get_lang(message.chat.id, session)
    data = await state.get_data()
    # If user had to choose between traffic options, return there
    if data.get('charge_type') in {'booking', 'normal_5gb_limit'} or (data.get('remaining_gb') or 0) > 5:
        await state.set_state(ChargeState.traffic_check)
        await message.answer(t(lang, "charge_back_step"), reply_markup=_build_traffic_options_keyboard(lang))
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
        await message.answer(t(lang, "charge_back_to_services"), reply_markup=_build_subscription_keyboard(subs, lang))
    else:
        await state.clear()
        await message.answer(t(lang, "charge_cancelled"), reply_markup=get_main_keyboard(message.chat.id, lang=lang))


@router.message(ChargeState.confirmation, text_matches("charge_confirm"))
async def confirm_charge(message: Message, state: FSMContext, session: AsyncSession):
    lang = await _get_lang(message.chat.id, session)

    # Wallet-credit option (same as the webapp charge flow). Only offered for
    # preset packages — custom/booking paths keep their own handling.
    data = await state.get_data()
    user = await crud.get_user(session, message.chat.id)
    pkg_label = data.get('package_label')
    if user and (user.credit or 0) > 0 and pkg_label in CHARGE_PRESET_PACKAGES:
        await state.set_state(ChargeState.ask_credit)
        credit_kb = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text=(f"✅ بله، {user.credit:,} تومان اعتبار را استفاده کن" if lang == "fa" else f"✅ Yes, use {user.credit:,} credit"))],
                [KeyboardButton(text=("خیر، برای بعد ذخیره کن" if lang == "fa" else "No, save for later"))],
            ],
            resize_keyboard=True,
            one_time_keyboard=True,
        )
        await message.answer(
            (f"شما **{user.credit:,} تومان اعتبار** دارید! آیا می‌خواهید آن را روی این شارژ استفاده کنید؟" if lang == "fa" else f"You have **{user.credit:,}** credit. Use it for this charge?"),
            reply_markup=credit_kb,
        )
        return

    await message.answer(
        _registered_text(lang),
        reply_markup=ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text=t(lang, "btn_back"))]], resize_keyboard=True),
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
            reply_markup=ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text=t(lang, "btn_back"))]], resize_keyboard=True),
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
        reply_markup=ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text=t(lang, "btn_back"))]], resize_keyboard=True),
        parse_mode="HTML"
    )
    await state.set_state(ChargeState.receipt)


@router.message(ChargeState.confirmation, text_matches("btn_back"))
async def cancel_confirm(message: Message, state: FSMContext, session: AsyncSession):
    lang = await _get_lang(message.chat.id, session)
    # Return to package selection to allow changing choice
    await state.set_state(ChargeState.package)
    await message.answer(t(lang, "charge_back_to_packages"), reply_markup=_build_package_keyboard(lang))


@router.message(ChargeState.confirmation)
async def confirmation_catch_all(message: Message, state: FSMContext, session: AsyncSession):
    """Catch any other message in confirmation state - allow /start to reset"""
    lang = await _get_lang(message.chat.id, session)
    
    # Allow /start to reset flow
    if message.text and message.text.startswith("/start"):
        await state.clear()
        return  # Let start handler handle it
    
    # Any other text - remind user to confirm or go back
    from aiogram.types import KeyboardButton, ReplyKeyboardMarkup
    confirm_kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=t(lang, "charge_confirm"))], [KeyboardButton(text=t(lang, "btn_back"))]],
        resize_keyboard=True
    )
    await message.answer(
        t(lang, "charge_confirm_or_back") if "charge_confirm_or_back" in dir(t) else 
        ("لطفاً تایید یا بازگشت را انتخاب کنید." if lang == "fa" else "Please choose confirm or back."),
        reply_markup=confirm_kb
    )

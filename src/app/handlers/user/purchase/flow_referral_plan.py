from aiogram import F
from aiogram.fsm.context import FSMContext
from aiogram.types import KeyboardButton, Message, ReplyKeyboardMarkup
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.settings import PLANS
from app.database import crud
from app.database.models import Referral
from app.keyboards.reply import get_main_keyboard
from app.utils.bot_i18n import normalize_lang, set_cached_lang, t, text_matches
from app.utils.validation import InputValidator, sanitize_user_input

from app.services.flows.pricing import (
    CUSTOM_MAX_GB,
    CUSTOM_MIN_GB,
    custom_plan_price,
    get_plan_info,
    plan_display_name,
)

from .common import (
    CUSTOM_PLAN_BTN_EN,
    CUSTOM_PLAN_BTN_FA,
    PurchaseState,
    _auto_renew_keyboard,
    _get_plan_keyboard_for_user,
    _lang_for,
    _name_keyboard,
    router,
)
from .summary import show_order_summary


@router.message(text_matches("btn_buy"))
async def start_purchase(message: Message, state: FSMContext, session: AsyncSession):
    """Entry point for purchase flow.

    If the user is already linked to a referrer (Referral.referee_id == user.id)
    we skip asking for an invitation code and jump straight to plan selection.
    """
    user = await crud.get_user(session, message.chat.id)
    lang = normalize_lang(getattr(user, "language", None)) if user else normalize_lang(getattr(message.from_user, "language_code", None))
    set_cached_lang(message.chat.id, lang)

    if user:
        result_ref = await session.execute(select(Referral).filter(Referral.referee_id == user.id))
        ref_row = result_ref.scalars().first()
        if ref_row:
            await state.update_data(referrer_id=ref_row.referrer_id)
            await state.set_state(PurchaseState.plan)
            plan_kb = await _get_plan_keyboard_for_user(session, message.chat.id, lang)
            await message.answer(
                ("لطفا یکی از پلن های زیر را انتخاب کنید:" if lang == "fa" else "Please choose a plan:"),
                reply_markup=plan_kb,
            )
            return

    # Otherwise ask for referral code as before
    await state.set_state(PurchaseState.referral_code)
    await message.answer(
        ("اگر کد دعوت دارید، آن را وارد کنید. در غیر این صورت، دکمه 'رد شدن' را بزنید." if lang == "fa" else "If you have an invite code, send it now. Otherwise tap 'Skip'."),
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text=("رد شدن" if lang == "fa" else "Skip"))],
                [KeyboardButton(text=t(lang, "btn_back"))],
            ],
            resize_keyboard=True,
            one_time_keyboard=True,
        ),
    )

@router.message(PurchaseState.referral_code)
async def process_referral_code(message: Message, state: FSMContext, session: AsyncSession):
    lang = await _lang_for(message, session)

    # Allow /start to reset flow
    if message.text and message.text.startswith("/start"):
        await state.clear()
        return  # Let start handler handle it

    if message.text in (t(lang, "btn_back"), "بازگشت🔙", "Back 🔙"):
        await state.clear()
        await message.answer(
            ("خرید لغو شد. به منوی اصلی بازگشتید." if lang == "fa" else "Purchase cancelled. Back to main menu."),
            reply_markup=get_main_keyboard(message.chat.id, lang=lang),
        )
        return

    if message.text not in (("رد شدن" if lang == "fa" else "Skip"), "رد شدن", "Skip"):
        # Validate referral code format
        if not InputValidator.validate_referral_code(message.text):
            await message.answer(
                "فرمت کد دعوت نامعتبر است. کد دعوت باید ۶ کاراکتر و شامل حروف بزرگ و اعداد باشد."
                if lang == "fa"
                else "Invalid invite code format. It must be 6 characters (A-Z and 0-9)."
            )
            return

        # Sanitize input
        sanitized_code = sanitize_user_input(message.text)

        referrer = await crud.get_user_by_referral_code(session, sanitized_code)
        if not referrer:
            await message.answer(
                "کد دعوت نامعتبر است. لطفا دوباره تلاش کنید یا روی 'رد شدن' کلیک کنید."
                if lang == "fa"
                else "Invalid invite code. Please try again or tap 'Skip'."
            )
            return
        if referrer.chat_id == message.chat.id:
            await message.answer("شما نمی توانید از کد دعوت خودتان استفاده کنید!" if lang == "fa" else "You can't use your own invite code!")
            return
        await state.update_data(referrer_id=referrer.id)
        await message.answer("✅ کد دعوت با موفقیت اعمال شد!" if lang == "fa" else "✅ Invite code applied!")
    else:
        # If user skipped entering code, but already registered via referral entry earlier, reuse it
        user = await crud.get_user(session, message.chat.id)
        if user:
            await session.refresh(user, attribute_names=["referral_entry"])
        if user and user.referral_entry:
            await state.update_data(referrer_id=user.referral_entry.referrer_id)

    await state.set_state(PurchaseState.plan)
    plan_kb = await _get_plan_keyboard_for_user(session, message.chat.id, lang)
    await message.answer(
        ("لطفا یکی از پلن های زیر را انتخاب کنید:" if lang == "fa" else "Please choose a plan:"),
        reply_markup=plan_kb,
    )

async def _continue_with_plan(message: Message, state: FSMContext, session: AsyncSession, plan_name: str):
    lang = await _lang_for(message, session)
    await state.update_data(plan=plan_name)
    data_prev = await state.get_data()
    if not data_prev.get('editing_plan_only'):
        # Clear previous name only in normal flow
        await state.update_data(name=None, marzban_username=None)
    await state.set_state(PurchaseState.auto_renew_choice)
    await message.answer(
        ("آیا می‌خواهید تمدید خودکار فعال باشد؟" if lang == "fa" else "Do you want to enable auto-renew?"),
        reply_markup=_auto_renew_keyboard(lang),
    )


@router.message(PurchaseState.plan, F.text.in_(PLANS.keys()))
async def process_plan(message: Message, state: FSMContext, session: AsyncSession):
    await _continue_with_plan(message, state, session, message.text)


_CUSTOM_BTNS = {CUSTOM_PLAN_BTN_FA, CUSTOM_PLAN_BTN_EN}
_FA_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")


def _custom_gb_prompt(lang: str) -> str:
    return (
        f"📦 پلن دلخواه\n\nچند گیگابایت می‌خواهید؟ یک عدد بین {CUSTOM_MIN_GB} تا {CUSTOM_MAX_GB} بفرستید:"
        if lang == "fa"
        else f"📦 Custom plan\n\nHow many GB? Send a number between {CUSTOM_MIN_GB} and {CUSTOM_MAX_GB}:"
    )


@router.message(PurchaseState.plan, F.text.in_(_CUSTOM_BTNS))
async def ask_custom_gb(message: Message, state: FSMContext, session: AsyncSession):
    lang = await _lang_for(message, session)
    await state.update_data(custom_for_renewal=False)
    await state.set_state(PurchaseState.custom_gb)
    await message.answer(
        _custom_gb_prompt(lang),
        reply_markup=ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text=t(lang, "btn_back"))]], resize_keyboard=True),
    )


@router.message(PurchaseState.renewal_template, F.text.in_(_CUSTOM_BTNS))
async def ask_custom_gb_renewal(message: Message, state: FSMContext, session: AsyncSession):
    lang = await _lang_for(message, session)
    await state.update_data(custom_for_renewal=True)
    await state.set_state(PurchaseState.custom_gb)
    await message.answer(
        _custom_gb_prompt(lang),
        reply_markup=ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text=t(lang, "btn_back"))]], resize_keyboard=True),
    )


@router.message(PurchaseState.custom_gb, text_matches("btn_back"))
async def back_from_custom_gb(message: Message, state: FSMContext, session: AsyncSession):
    lang = await _lang_for(message, session)
    data = await state.get_data()
    target = PurchaseState.renewal_template if data.get("custom_for_renewal") else PurchaseState.plan
    await state.set_state(target)
    plan_kb = await _get_plan_keyboard_for_user(session, message.chat.id, lang)
    await message.answer(
        ("لطفا یکی از پلن های زیر را انتخاب کنید:" if lang == "fa" else "Please choose a plan:"),
        reply_markup=plan_kb,
    )


@router.message(PurchaseState.custom_gb)
async def process_custom_gb(message: Message, state: FSMContext, session: AsyncSession):
    lang = await _lang_for(message, session)
    raw = (message.text or "").strip().translate(_FA_DIGITS)
    try:
        gb = int(raw)
    except ValueError:
        gb = -1
    if not (CUSTOM_MIN_GB <= gb <= CUSTOM_MAX_GB):
        await message.answer(
            (f"❌ عدد نامعتبر. یک عدد بین {CUSTOM_MIN_GB} تا {CUSTOM_MAX_GB} بفرستید (فقط رقم انگلیسی یا فارسی)." if lang == "fa"
             else f"❌ Invalid number. Send a number between {CUSTOM_MIN_GB} and {CUSTOM_MAX_GB}.")
        )
        return
    plan_name = f"custom:{gb}"
    price = custom_plan_price(gb)
    data = await state.get_data()
    await message.answer(
        (f"📦 {plan_display_name(plan_name, lang)}\n💵 قیمت: {price:,} تومان" if lang == "fa"
         else f"📦 {plan_display_name(plan_name, lang)}\n💵 Price: {price:,} Toman")
    )
    if data.get("custom_for_renewal"):
        await _continue_with_renewal(message, state, session, plan_name)
    else:
        await _continue_with_plan(message, state, session, plan_name)

@router.message(PurchaseState.auto_renew_choice, lambda m: (m.text or "").strip() in {"بدون تمدید خودکار", "No auto-renew"})
async def process_no_auto_renew(message: Message, state: FSMContext, session: AsyncSession):
    lang = await _lang_for(message, session)
    await state.update_data(auto_renewal=False)
    data = await state.get_data()
    if data.get('editing_plan_only') and data.get('marzban_username'):
        await state.update_data(editing_plan_only=False)  # reset flag
        # Skip name step, go straight to summary
        await show_order_summary(message, state, session)
    else:
        await state.set_state(PurchaseState.name)
        await message.answer(
            ("لطفا یک نام برای سرویس خود انتخاب کنید یا دکمه 'اتفاقی' را بزنید." if lang == "fa" else "Choose a service name, or tap 'Random'."),
            reply_markup=_name_keyboard(lang),
        )

@router.message(PurchaseState.auto_renew_choice, lambda m: (m.text or "").strip() in {"فعال‌سازی تمدید خودکار", "Enable auto-renew"})
async def process_yes_auto_renew(message: Message, state: FSMContext, session: AsyncSession):
    await state.update_data(auto_renewal=True)
    # renewal template selection uses plan keys; VIP users see VIP plans too
    plan_kb = await _get_plan_keyboard_for_user(session, message.chat.id, "fa")
    await state.set_state(PurchaseState.renewal_template)
    await message.answer(
        "لطفا پلن مورد نظر برای تمدید خودکار را انتخاب کنید:" if True else "Pick the plan for auto-renew:",
        reply_markup=plan_kb,
    )

@router.message(PurchaseState.renewal_template, F.text.in_(PLANS.keys()))
async def process_renewal_template(message: Message, state: FSMContext, session: AsyncSession):
    await _continue_with_renewal(message, state, session, message.text)


async def _continue_with_renewal(message: Message, state: FSMContext, session: AsyncSession, template_name: str):
    await state.update_data(renewal_template=template_name)
    data = await state.get_data()
    plan_info = get_plan_info(data['plan'])
    renewal_info = get_plan_info(template_name)
    total_price = plan_info['price'] + renewal_info['price']
    if data.get('editing_plan_only') and data.get('marzban_username'):
        await state.update_data(editing_plan_only=False)
        await show_order_summary(message, state, session)
    else:
        await state.set_state(PurchaseState.name)
        await message.answer(
            f"مجموع قیمت: {total_price:,} تومان\n\nلطفا یک نام برای سرویس خود انتخاب کنید یا دکمه 'اتفاقی' را بزنید.",
            reply_markup=ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text="اتفاقی")], [KeyboardButton(text="بازگشت🔙")]],
                resize_keyboard=True,
                one_time_keyboard=True,
            ),
        )

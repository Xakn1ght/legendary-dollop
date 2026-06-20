from __future__ import annotations

from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import KeyboardButton, Message, ReplyKeyboardMarkup
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import CHARGE_PLANS_BUTTON_COLUMNS, PLANS_BUTTON_COLUMNS
from app.database import crud
from app.keyboards.reply import get_main_keyboard
from app.services.marzban import marzban_api
from app.shared.plan_ordering import get_ordered_charge_plans, get_ordered_plans
from app.utils.bot_i18n import get_cached_lang, normalize_lang, set_cached_lang, t

router = Router()

GB = 1024 * 1024 * 1024

def _persian_digits(text):
    """Convert Latin digits to Persian digits in the given text."""
    persian_map = str.maketrans('0123456789', '۰۱۲۳۴۵۶۷۸۹')
    return str(text).translate(persian_map)


def _build_persian_traffic_message(persian_gb_str):
    """Build the traffic warning message with all digits in Persian."""
    # persian_gb_str already has Persian digits, but we need to convert numbers in the message
    message = (
        f'📊 ترافیک باقیمانده: {persian_gb_str} گیگابایت\n\n'
        '⚠️ توجه: ترافیک باقی مانده فعلی بیش از ۵ گیگابایت است. برای اعمال شارژ جدید، یکی از گزینه‌ها را انتخاب کنید:\n\n'
        '🔹 شارژ فوری (۵ گیگابایت): تنها ۵ گیگ از حجم باقی مانده فعلی انتقال داده می‌شود و ترافیک اضافی حذف خواهد شد.\n'
        '🔹 رزرو پلن: پلن جدید خریداری و رزرو می‌شود؛ در زمان کاهش ترافیک به زیر ۵ گیگابایت و یا نزدیکی به پایان مدت اشتراک، به طور خودکار اعمال خواهد شد.\n\n'
        'لطفاً گزینه مورد نظر را از دکمه‌های زیر انتخاب کنید:'
    )
    return message


def _build_english_traffic_message(gb_str):
    """Build the traffic warning message in English."""
    return (
        f'📊 Remaining traffic: **{gb_str}GB**\n\n'
        '⚠️ Note: Your remaining traffic is over 5GB. To apply a new charge, choose one of the options:\n\n'
        '🔹 **Charge Now (5GB):** Only 5GB of your current remaining traffic will be transferred, and extra traffic will be removed.\n'
        '🔹 **Book Plan:** A new plan will be purchased and reserved; it will be applied automatically when traffic drops below 5GB or near expiry.\n\n'
        'Please choose an option from the buttons below:'
    )

class ChargeState(StatesGroup):
    subscription = State()
    traffic_check = State()
    package = State()
    booking_plan = State()
    booking_choice = State()
    buy_days_plan = State()
    confirmation = State()
    ask_credit = State()
    receipt = State()


async def _get_lang(chat_id: int, session: AsyncSession) -> str:
    """Get user language from cache or DB."""
    lang = get_cached_lang(chat_id)
    if lang:
        return lang
    user = await crud.get_user(session, chat_id)
    if user:
        lang = normalize_lang(getattr(user, "language", None))
        set_cached_lang(chat_id, lang)
        return lang
    return "fa"


def _build_subscription_keyboard(subscriptions, lang: str = "fa"):
    rows = []
    for sub in subscriptions:
        rows.append([KeyboardButton(text=sub.marzban_username)])
    rows.append([KeyboardButton(text=t(lang, "btn_back"))])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def _build_package_keyboard(lang: str = "fa"):
    rows = []
    keys = get_ordered_charge_plans()
    
    # Create a 2D list representing the button layout
    button_grid = []
    for i in range(0, len(keys), CHARGE_PLANS_BUTTON_COLUMNS):
        row = [KeyboardButton(text=keys[j]) for j in range(i, min(i + CHARGE_PLANS_BUTTON_COLUMNS, len(keys)))]
        button_grid.append(row)
        
    # Add back button
    button_grid.append([KeyboardButton(text=t(lang, "btn_back"))])
    
    return ReplyKeyboardMarkup(keyboard=button_grid, resize_keyboard=True)


def _build_traffic_options_keyboard(lang: str = "fa"):
    """Build keyboard for >5GB traffic options"""
    rows = [
        [KeyboardButton(text=t(lang, "charge_now"))],
        [KeyboardButton(text=t(lang, "book_plan"))],
        [KeyboardButton(text=t(lang, "btn_back"))]
    ]
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def _build_main_plan_keyboard(lang: str = "fa"):
    """Keyboard for selecting main subscription PLANS (for booking/renewal template)."""
    rows = []
    keys = get_ordered_plans()
    for i in range(0, len(keys), PLANS_BUTTON_COLUMNS):
        row = [KeyboardButton(text=keys[j]) for j in range(i, min(i + PLANS_BUTTON_COLUMNS, len(keys)))]
        rows.append(row)
    rows.append([KeyboardButton(text=t(lang, "btn_back"))])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


async def check_subscription_traffic(message: Message, state: FSMContext, session: AsyncSession, subscription):
    """Check if subscription has >5GB remaining and show appropriate options"""
    lang = await _get_lang(message.chat.id, session)
    
    # Get current traffic info from Marzban
    user_info = await marzban_api.get_user_info(subscription.marzban_username)
    if not user_info:
        await message.answer(t(lang, "charge_error_fetch"), reply_markup=get_main_keyboard(message.chat.id, lang=lang))
        await state.clear()
        return
    
    data_limit = user_info.get('data_limit', 0) or 0
    used_traffic = user_info.get('used_traffic', 0) or 0
    remaining_bytes = max(data_limit - used_traffic, 0)
    remaining_gb = remaining_bytes / GB
    
    # Convert to Persian digits for display (only for Farsi)
    gb_str = _persian_digits(f"{remaining_gb:.1f}") if lang == "fa" else f"{remaining_gb:.1f}"
    
    await state.update_data(
        remaining_gb=remaining_gb,
        subscription_username=subscription.marzban_username
    )
    
    if remaining_gb <= 5:
        # Normal charging flow
        await state.set_state(ChargeState.package)
        await message.answer(
            t(lang, "charge_remaining").format(gb=gb_str) + "\n\n" + t(lang, "charge_choose_package"),
            reply_markup=_build_package_keyboard(lang)
        )
    else:
        # Show options for >5GB
        await state.set_state(ChargeState.traffic_check)
        await message.answer(
            _build_persian_traffic_message(gb_str) if lang == "fa" else _build_english_traffic_message(gb_str),
            reply_markup=_build_traffic_options_keyboard(lang)
        )

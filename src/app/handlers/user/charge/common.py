from __future__ import annotations

from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import CHARGE_PLANS_BUTTON_COLUMNS, PLANS_BUTTON_COLUMNS
from app.database import crud
from app.handlers.user.flow_inline import ikb
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


async def _build_subscription_keyboard(state: FSMContext, subscriptions, lang: str = "fa") -> InlineKeyboardMarkup:
    rows = [[sub.marzban_username] for sub in subscriptions]
    rows.append([t(lang, "btn_back")])
    return await ikb(state, rows)


async def _is_vip_chat(session, chat_id: int) -> bool:
    try:
        user = await crud.get_user(session, chat_id)
        return bool(user and await crud.is_user_vip(session, user.id))
    except Exception:
        return False


async def _build_package_keyboard(state: FSMContext, lang: str = "fa", is_vip: bool = False) -> InlineKeyboardMarkup:
    from app.core.settings import CHARGE_PRESET_PACKAGES

    keys = get_ordered_charge_plans()
    # VIP-exclusive top-ups hidden for non-VIP users (flows/charge.py
    # enforces the same rule on the money path).
    keys = [k for k in keys if is_vip or not CHARGE_PRESET_PACKAGES.get(k, {}).get("vip_only")]
    button_grid = []
    for i in range(0, len(keys), CHARGE_PLANS_BUTTON_COLUMNS):
        button_grid.append(keys[i:i + CHARGE_PLANS_BUTTON_COLUMNS])
    button_grid.append([t(lang, "btn_back")])
    return await ikb(state, button_grid)


async def _build_traffic_options_keyboard(state: FSMContext, lang: str = "fa") -> InlineKeyboardMarkup:
    """Build keyboard for >5GB traffic options"""
    return await ikb(state, [
        [t(lang, "charge_now")],
        [t(lang, "book_plan")],
        [t(lang, "btn_back")],
    ])


async def _build_main_plan_keyboard(state: FSMContext, lang: str = "fa") -> InlineKeyboardMarkup:
    """Keyboard for selecting main subscription PLANS (for booking/renewal template)."""
    rows = []
    keys = get_ordered_plans()
    for i in range(0, len(keys), PLANS_BUTTON_COLUMNS):
        rows.append(keys[i:i + PLANS_BUTTON_COLUMNS])
    rows.append([t(lang, "btn_back")])
    return await ikb(state, rows)


async def _back_keyboard(state: FSMContext, lang: str = "fa") -> InlineKeyboardMarkup:
    return await ikb(state, [[t(lang, "btn_back")]])


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
            reply_markup=await _build_package_keyboard(state, lang, is_vip=await _is_vip_chat(session, message.chat.id))
        )
    else:
        # Show options for >5GB
        await state.set_state(ChargeState.traffic_check)
        await message.answer(
            _build_persian_traffic_message(gb_str) if lang == "fa" else _build_english_traffic_message(gb_str),
            reply_markup=await _build_traffic_options_keyboard(state, lang)
        )

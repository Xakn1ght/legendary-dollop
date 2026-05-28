from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, WebAppInfo
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import BOT_TOKEN, DASHBOARD_PUBLIC_BASE_URL, WEBAPP_SESSION_SECRET
from app.database import crud
from app.database.cached_crud import get_user_with_cache, invalidate_user_cache
from app.handlers.user.add_subscription import AddSubState
from app.handlers.user.charge import (
    ChargeState,
    back_from_package,
    cancel_confirm,
    cancel_receipt,
)

# Import states and specific back handlers where available
from app.handlers.user.purchase import (
    PurchaseState,
    _build_plan_keyboard,
    back_from_auto_renew_choice,
    back_from_renewal_template,
    cancel_from_plan,
    cancel_purchase_receipt,
    go_back_from_confirmation,
)
from app.keyboards.reply import KEYBOARD_MARKUP_MAIN, get_main_keyboard
from app.utils.bot_i18n import (
    get_cached_lang,
    guess_lang_from_telegram,
    normalize_lang,
    set_cached_lang,
    t,
    text_matches,
)
from app.utils.webapp_verify import create_one_time_token

router = Router()

def _extract_state_name(state_value) -> str | None:
    if not state_value:
        return None
    # aiogram may return State object; our PersistentStorage may return State as well
    text = str(state_value)
    if text.startswith("<State '") and text.endswith("'>"):
        return text[8:-2]
    return text


@router.message(text_matches("btn_back"))
async def back_to_main(message: Message, state: FSMContext, session: AsyncSession):
    """State-aware back navigation; falls back to main menu."""
    # Get user to check if admin
    user = await get_user_with_cache(session, message.chat.id)
    is_admin = user.is_admin if user else False
    lang = normalize_lang(getattr(user, "language", None) or get_cached_lang(message.chat.id))
    set_cached_lang(message.chat.id, lang)
    
    current = await state.get_state()
    name = _extract_state_name(current)

    # Purchase flow
    if name and name.startswith('PurchaseState:'):
        step = name.split(':', 1)[1]
        if step == 'plan':
            await cancel_from_plan(message, state, session)
            return
        if step == 'auto_renew_choice':
            await back_from_auto_renew_choice(message, state, session)
            return
        if step == 'renewal_template':
            await back_from_renewal_template(message, state, session)
            return
        if step == 'name':
            # Return to plan selection
            await state.set_state(PurchaseState.plan)
            await message.answer(
                ("لطفا یکی از پلن های زیر را انتخاب کنید:" if lang == "fa" else "Please choose a plan:"),
                reply_markup=_build_plan_keyboard(),
            )
            return
        if step == 'confirmation':
            await go_back_from_confirmation(message, state, session)
            return
        if step == 'receipt':
            await cancel_purchase_receipt(message, state, session)
            return
        # Handle other purchase states - clear and return to main
        if step in ('referral_code', 'ask_discount', 'ask_credit', 'edit_choice'):
            await state.clear()
            await message.answer(
                ('خرید لغو شد. به منوی اصلی بازگشتید.' if lang == "fa" else 'Purchase cancelled. Back to main menu.'),
                reply_markup=get_main_keyboard(message.chat.id, is_admin=is_admin, lang=lang),
            )
            return

    # Charge flow
    if name and name.startswith('ChargeState:'):
        step = name.split(':', 1)[1]
        if step == 'package':
            await back_from_package(message, state, session)
            return
        if step == 'confirmation':
            await cancel_confirm(message, state, session)
            return
        if step == 'receipt':
            await cancel_receipt(message, state, session)
            return
        if step in ('subscription', 'traffic_check', 'booking_plan', 'booking_choice', 'buy_days_plan'):
            await state.clear()
            await message.answer(
                ('عملیات لغو شد.' if lang == "fa" else "Cancelled."),
                reply_markup=get_main_keyboard(message.chat.id, is_admin=is_admin, lang=lang),
            )
            return

    # Add subscription
    if name and name.startswith('AddSubState:'):
        await state.clear()
        await message.answer(
            ('عملیات لغو شد.' if lang == "fa" else "Cancelled."),
            reply_markup=get_main_keyboard(message.chat.id, is_admin=is_admin, lang=lang),
        )
        return

    # Default fallback: go to main
    await state.clear()
    await message.answer(
        'به منوی اصلی بازگشتید.' if lang == "fa" else "Back to main menu.",
        reply_markup=get_main_keyboard(message.chat.id, is_admin=is_admin, lang=lang),
    )


def _build_support_webapp_url(user_chat_id: int) -> str:
    """
    Bot-side Support must be WebApp-only:
    - issue a short-lived URL token (more leak-prone than cookies)
    - send the user to the dashboard support page
    """
    session_secret = WEBAPP_SESSION_SECRET or BOT_TOKEN
    auth_token = create_one_time_token(user_chat_id, session_secret, ttl_seconds=15 * 60)  # 15 minutes
    return f"{DASHBOARD_PUBLIC_BASE_URL}/webapp/dashboard/support.html?auth={auth_token}"


@router.message(Command("support"))
@router.message(text_matches("btn_support"))
async def open_support_webapp(message: Message, state: FSMContext, session: AsyncSession):
    """
    Replace bot-based support with a WebApp deep-link.
    This keeps the bot simple and ensures all support happens in the webapp UI.
    """
    # Clear any active flow state (avoid users getting "stuck" in old FSM states)
    try:
        await state.clear()
    except Exception:
        pass

    user = await get_user_with_cache(session, message.chat.id)
    lang = normalize_lang(getattr(user, "language", None) or guess_lang_from_telegram(getattr(message.from_user, "language_code", None)))
    set_cached_lang(message.chat.id, lang)

    url = _build_support_webapp_url(message.chat.id)
    kb = InlineKeyboardBuilder()
    kb.button(text=t(lang, "open_support_btn"), web_app=WebAppInfo(url=url))
    kb.adjust(1)
    await message.answer(
        t(lang, "support_webapp_only"),
        reply_markup=kb.as_markup(),
    )


@router.message(Command("language"))
@router.message(text_matches("btn_language"))
async def choose_language(message: Message, session: AsyncSession):
    lang = get_cached_lang(message.chat.id) or guess_lang_from_telegram(getattr(message.from_user, "language_code", None))
    kb = InlineKeyboardBuilder()
    kb.button(text="فارسی 🇮🇷", callback_data="lang:set:fa")
    kb.button(text="English 🇬🇧", callback_data="lang:set:en")
    kb.adjust(2)
    await message.answer(t(lang, "choose_language"), reply_markup=kb.as_markup())


@router.callback_query(F.data.startswith("lang:set:"))
async def set_language_cb(callback: CallbackQuery, session: AsyncSession):
    try:
        lang = callback.data.split(":", 2)[2]
    except Exception:
        lang = "fa"
    lang = normalize_lang(lang)
    set_cached_lang(callback.from_user.id, lang)
    try:
        await crud.set_user_language(session, callback.from_user.id, lang)
    except Exception:
        pass
    # User rows are frequently read via `get_user_with_cache`; invalidate so language changes apply instantly.
    try:
        await invalidate_user_cache(callback.from_user.id)
    except Exception:
        pass
    try:
        await callback.message.answer(t(lang, "lang_set_ok"), reply_markup=get_main_keyboard(callback.from_user.id, lang=lang))
    except Exception:
        pass
    await callback.answer()

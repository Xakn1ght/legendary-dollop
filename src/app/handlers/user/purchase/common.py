from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import PLANS, PLANS_BUTTON_COLUMNS
from app.database import crud
from app.handlers.user.flow_inline import ikb
from app.shared.plan_ordering import get_ordered_plans
from app.utils.bot_i18n import normalize_lang, set_cached_lang, t

router = Router()


class PurchaseState(StatesGroup):
    referral_code = State()
    plan = State()
    custom_gb = State()
    auto_renew_choice = State()
    renewal_template = State()
    name = State()
    ask_discount = State()
    ask_coupon = State()
    ask_credit = State()
    confirmation = State()
    receipt = State()
    edit_choice = State()


CUSTOM_PLAN_BTN_FA = "📦 پلن دلخواه"
CUSTOM_PLAN_BTN_EN = "📦 Custom Plan"


async def _build_plan_keyboard(state: FSMContext, lang: str = "fa", is_vip: bool = False) -> InlineKeyboardMarkup:
    rows = []
    keys = get_ordered_plans()
    # Filter VIP-only plans based on user's VIP status
    available_keys = []
    for k in keys:
        plan = PLANS.get(k, {})
        if plan.get('vip_only', False) and not is_vip:
            continue  # Skip VIP-only plans for non-VIP users
        available_keys.append(k)

    for i in range(0, len(available_keys), PLANS_BUTTON_COLUMNS):
        rows.append(available_keys[i:i + PLANS_BUTTON_COLUMNS])
    rows.append([CUSTOM_PLAN_BTN_FA if lang == "fa" else CUSTOM_PLAN_BTN_EN])
    rows.append([t(lang, "btn_back")])
    return await ikb(state, rows)


async def _get_plan_keyboard_for_user(session, chat_id: int, state: FSMContext, lang: str = "fa") -> InlineKeyboardMarkup:
    """Get plan keyboard with VIP status check"""
    user = await crud.get_user(session, chat_id)
    is_vip = await crud.is_user_vip(session, user.id) if user else False
    return await _build_plan_keyboard(state, lang, is_vip)


async def _lang_for(message: Message, session: AsyncSession) -> str:
    """Best-effort language resolution for this user."""
    try:
        user = await crud.get_user(session, message.chat.id)
        lang = normalize_lang(getattr(user, "language", None)) if user else normalize_lang(getattr(message.from_user, "language_code", None))
        set_cached_lang(message.chat.id, lang)
        return lang
    except Exception:
        return normalize_lang(getattr(message.from_user, "language_code", None))


async def _auto_renew_keyboard(state: FSMContext, lang: str) -> InlineKeyboardMarkup:
    return await ikb(state, [
        [("فعال‌سازی تمدید خودکار" if lang == "fa" else "Enable auto-renew")],
        [("بدون تمدید خودکار" if lang == "fa" else "No auto-renew")],
        [t(lang, "btn_back")],
    ])


async def _name_keyboard(state: FSMContext, lang: str) -> InlineKeyboardMarkup:
    return await ikb(state, [
        [("اتفاقی" if lang == "fa" else "Random")],
        [t(lang, "btn_back")],
    ])


async def _back_keyboard(state: FSMContext, lang: str) -> InlineKeyboardMarkup:
    return await ikb(state, [[t(lang, "btn_back")]])


async def _confirm_keyboard(state: FSMContext, lang: str) -> InlineKeyboardMarkup:
    return await ikb(state, [
        [("تایید و پرداخت ✅" if lang == "fa" else "Confirm & Pay ✅")],
        [("ویرایش ✏️" if lang == "fa" else "Edit ✏️"), t(lang, "btn_back")],
    ])


# NOTE: orders are now created only at Confirm & Pay via
# app.services.flows.purchase.start_purchase_order; cancellation/refunds go through
# cancel_purchase_order. The old _cleanup_pending_subscription helper is gone.

from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import KeyboardButton, Message, ReplyKeyboardMarkup
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.settings import PLANS, PLANS_BUTTON_COLUMNS
from app.database import crud, models
from app.shared.plan_ordering import get_ordered_plans
from app.utils.bot_i18n import normalize_lang, set_cached_lang, t

router = Router()


class PurchaseState(StatesGroup):
    referral_code = State()
    plan = State()
    auto_renew_choice = State()
    renewal_template = State()
    name = State()
    ask_discount = State()
    ask_credit = State()
    confirmation = State()
    receipt = State()
    edit_choice = State()


def _build_plan_keyboard(lang: str = "fa", is_vip: bool = False):
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
        row = [KeyboardButton(text=available_keys[j]) for j in range(i, min(i + PLANS_BUTTON_COLUMNS, len(available_keys)))]
        rows.append(row)
    rows.append([KeyboardButton(text=t(lang, "btn_back"))])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


async def _get_plan_keyboard_for_user(session, chat_id: int, lang: str = "fa"):
    """Get plan keyboard with VIP status check"""
    user = await crud.get_user(session, chat_id)
    is_vip = await crud.is_user_vip(session, user.id) if user else False
    return _build_plan_keyboard(lang, is_vip)


async def _lang_for(message: Message, session: AsyncSession) -> str:
    """Best-effort language resolution for this user."""
    try:
        user = await crud.get_user(session, message.chat.id)
        lang = normalize_lang(getattr(user, "language", None)) if user else normalize_lang(getattr(message.from_user, "language_code", None))
        set_cached_lang(message.chat.id, lang)
        return lang
    except Exception:
        return normalize_lang(getattr(message.from_user, "language_code", None))


def _auto_renew_keyboard(lang: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=("فعال‌سازی تمدید خودکار" if lang == "fa" else "Enable auto-renew"))],
            [KeyboardButton(text=("بدون تمدید خودکار" if lang == "fa" else "No auto-renew"))],
            [KeyboardButton(text=t(lang, "btn_back"))],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def _name_keyboard(lang: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=("اتفاقی" if lang == "fa" else "Random"))],
            [KeyboardButton(text=t(lang, "btn_back"))],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def _confirm_keyboard(lang: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=("تایید و پرداخت ✅" if lang == "fa" else "Confirm & Pay ✅"))],
            [KeyboardButton(text=("ویرایش ✏️" if lang == "fa" else "Edit ✏️")), KeyboardButton(text=t(lang, "btn_back"))],
        ],
        resize_keyboard=True,
    )


async def _cleanup_pending_subscription(session: AsyncSession, state: FSMContext):
    """Delete the pending subscription row (no receipt) and clear sub_id from state."""
    data = await state.get_data()
    sub_id = data.get('sub_id')
    if not sub_id:
        return
    result = await session.execute(select(models.Subscription).filter(models.Subscription.id == sub_id))
    sub = result.scalars().first()
    if sub and sub.status == 'pending' and sub.receipt_message_id is None:
        await crud.delete_subscription(session, sub_id)
    # remove id from state
    await state.update_data(sub_id=None)

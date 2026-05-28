from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import crud
from app.handlers.admin.common import ADMIN_IDS
from app.utils.bot_i18n import guess_lang_from_telegram, normalize_lang, set_cached_lang, t
from app.utils.persian_utils import parse_float_persian

router = Router()

# ---------------------------
#  Reward settings FSM
# ---------------------------

class RewardStates(StatesGroup):
    waiting_traffic = State()
    waiting_days = State()
    waiting_credit = State()

async def _admin_lang(session: AsyncSession, tg_user) -> str:
    try:
        u = await crud.get_user(session, tg_user.id)
        lang = normalize_lang(getattr(u, "language", None)) if u else guess_lang_from_telegram(getattr(tg_user, "language_code", None))
        set_cached_lang(int(tg_user.id), lang)
        return lang
    except Exception:
        return guess_lang_from_telegram(getattr(tg_user, "language_code", None))


@router.message(F.text == '/rewards')
async def rewards_menu(message: Message, session: AsyncSession):
    """Display current reward percentages and options to modify them."""
    if message.from_user.id not in ADMIN_IDS:
        return

    cfg = await crud.get_reward_config(session)
    lang = await _admin_lang(session, message.from_user)

    text = t(lang, "admin_rewards_current").format(
        traffic=cfg.traffic_percent,
        days=cfg.days_percent,
        credit=cfg.credit_percent,
    )

    kb = InlineKeyboardBuilder()
    kb.button(text=t(lang, "admin_rewards_set_traf_btn"), callback_data="set_rw_traf")
    kb.button(text=t(lang, "admin_rewards_set_days_btn"), callback_data="set_rw_days")
    kb.button(text=t(lang, "admin_rewards_set_credit_btn"), callback_data="set_rw_credit")
    kb.adjust(1)

    await message.answer(text, reply_markup=kb.as_markup())


# ---------- Callback entry points to collect new values ----------

@router.callback_query(F.data == 'set_rw_traf')
async def set_traf_cb(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer()
        return
    lang = await _admin_lang(session, callback.from_user)
    await callback.message.answer(t(lang, "admin_rewards_prompt_traf"))
    await state.set_state(RewardStates.waiting_traffic)
    await callback.answer()


@router.callback_query(F.data == 'set_rw_days')
async def set_days_cb(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer()
        return
    lang = await _admin_lang(session, callback.from_user)
    await callback.message.answer(t(lang, "admin_rewards_prompt_days"))
    await state.set_state(RewardStates.waiting_days)
    await callback.answer()


@router.callback_query(F.data == 'set_rw_credit')
async def set_credit_cb(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer()
        return
    lang = await _admin_lang(session, callback.from_user)
    await callback.message.answer(t(lang, "admin_rewards_prompt_credit"))
    await state.set_state(RewardStates.waiting_credit)
    await callback.answer()


# ---------- State-specific message handlers ----------

@router.message(RewardStates.waiting_traffic)
async def traffic_input(message: Message, session: AsyncSession, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    try:
        val = parse_float_persian(message.text.strip())
        if val < 0:
            raise ValueError
    except ValueError:
        lang = await _admin_lang(session, message.from_user)
        await message.answer(t(lang, "invalid_number_try_again"))
        return

    await crud.update_reward_config(session, traffic_percent=val)
    lang = await _admin_lang(session, message.from_user)
    await message.answer(t(lang, "admin_rewards_set_traf_ok").format(val=val))
    await state.clear()


@router.message(RewardStates.waiting_days)
async def days_input(message: Message, session: AsyncSession, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    try:
        val = parse_float_persian(message.text.strip())
        if val < 0:
            raise ValueError
    except ValueError:
        lang = await _admin_lang(session, message.from_user)
        await message.answer(t(lang, "invalid_number_try_again"))
        return

    await crud.update_reward_config(session, days_percent=val)
    lang = await _admin_lang(session, message.from_user)
    await message.answer(t(lang, "admin_rewards_set_days_ok").format(val=val))
    await state.clear()


@router.message(RewardStates.waiting_credit)
async def credit_input(message: Message, session: AsyncSession, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    try:
        val = parse_float_persian(message.text.strip())
        if val < 0:
            raise ValueError
    except ValueError:
        lang = await _admin_lang(session, message.from_user)
        await message.answer(t(lang, "invalid_number_try_again"))
        return

    await crud.update_reward_config(session, credit_percent=val)
    lang = await _admin_lang(session, message.from_user)
    await message.answer(t(lang, "admin_rewards_set_credit_ok").format(val=val))
    await state.clear()

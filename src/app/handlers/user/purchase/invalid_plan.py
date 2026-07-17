from aiogram.dispatcher.event.bases import SkipHandler
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.utils.bot_i18n import variants

from .common import PurchaseState, _get_plan_keyboard_for_user, _lang_for, router

# Main-menu reply buttons that should ESCAPE the purchase flow instead of
# being eaten by this catch-all (Pasha 2026-07-14 screenshot: tapping
# «سرویس‌های من» twice while stuck in plan state just re-prompted "use the
# buttons below"). btn_buy is excluded — its stateless handler restarts the
# flow and is registered before this module anyway.
_MENU_ESCAPE_KEYS = (
    "btn_my_services", "btn_recharge", "btn_support", "btn_rewards",
    "btn_invite", "btn_add_service", "btn_guide", "btn_language",
)


def _menu_texts() -> set[str]:
    out: set[str] = set()
    for key in _MENU_ESCAPE_KEYS:
        out |= variants(key)
    return out


@router.message(PurchaseState.plan)
async def invalid_plan(message: Message, state: FSMContext, session: AsyncSession):
    """Catch-all for the plan step.

    IMPORTANT (2026-07-14): this handler registers BEFORE plan_exits.py
    (module import order in __init__), so in aiogram it shadows any later
    PurchaseState.plan handler — the Back tap looped forever re-sending the
    same keyboard. Back and menu escapes must therefore be handled HERE,
    not in a later module.
    """
    text = (message.text or "").strip()

    # Allow /start to reset flow
    if text.startswith("/start"):
        await state.clear()
        return  # Let start handler handle it

    lang = await _lang_for(message, session)

    # Back = cancel the purchase (plan selection is the first step; no order
    # row exists yet). Delegates to plan_exits.cancel_from_plan — lazy import,
    # so module registration order stays untouched.
    if text in {"بازگشت🔙", "Back 🔙"}:
        from .plan_exits import cancel_from_plan

        await cancel_from_plan(message, state, session)
        return

    # Main-menu button while stuck in plan state: abandon the flow and let the
    # normal stateless handler take the tap (raw_state was resolved before the
    # handlers ran, so later routers still see this update).
    if text in _menu_texts():
        await state.clear()
        raise SkipHandler()

    plan_kb = await _get_plan_keyboard_for_user(session, message.chat.id, state, lang)
    await message.answer(("لطفا از دکمه های زیر استفاده کنید." if lang == "fa" else "Please use the buttons below."), reply_markup=plan_kb)

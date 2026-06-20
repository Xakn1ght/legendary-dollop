from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import crud
from app.utils.bot_i18n import normalize_lang, set_cached_lang

from .common import PurchaseState, router
from .summary import show_order_summary


@router.message(PurchaseState.ask_credit)
async def process_credit_choice(message: Message, state: FSMContext, session: AsyncSession):
    # Allow /start to reset flow
    if message.text and message.text.startswith("/start"):
        await state.clear()
        return  # Let start handler handle it

    user = await crud.get_user(session, message.chat.id)
    lang = normalize_lang(getattr(user, "language", None)) if user else normalize_lang(getattr(message.from_user, "language_code", None))
    set_cached_lang(message.chat.id, lang)

    # Only record the choice — the actual deduction happens when the order is
    # created at confirmation (services/flows/purchase.start_purchase_order), and is
    # refunded automatically on cancel/deny.
    apply_credit = (message.text or "").startswith("✅ بله") or (message.text or "").startswith("✅ Yes")
    await state.update_data(apply_credit=apply_credit)
    await show_order_summary(message, state, session)

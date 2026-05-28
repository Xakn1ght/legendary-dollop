from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import PLANS
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
    data = await state.get_data()
    plan_info = PLANS[data['plan']]
    renewal_price = PLANS[data['renewal_template']]['price'] if data.get('renewal_template') else 0
    initial_price = plan_info['price'] + (renewal_price or 0)
    # Calculate discount if any
    used_discount_percents = data.get('used_discount_percents', [])
    total_discount_percent = sum(used_discount_percents)
    price_after_discount = initial_price
    if total_discount_percent > 0:
        discount_amount = int(initial_price * (total_discount_percent / 100))
        price_after_discount = initial_price - discount_amount
    user_credit = user.credit or 0
    credit_used = 0
    if (message.text or "").startswith("✅ بله") or (message.text or "").startswith("✅ Yes"):
        credit_used = min(user_credit, price_after_discount)
        if credit_used > 0:
            await crud.deduct_credit(session, user.id, credit_used)
        await state.update_data(apply_credit=True, credit_used=credit_used)
    else:
        await state.update_data(apply_credit=False, credit_used=0)
    await show_order_summary(message, state, session)

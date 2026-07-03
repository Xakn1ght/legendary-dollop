from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from .common import PurchaseState, _get_plan_keyboard_for_user, _lang_for, router


@router.message(PurchaseState.plan)
async def invalid_plan(message: Message, state: FSMContext, session: AsyncSession):
    # Allow /start to reset flow
    if message.text and message.text.startswith("/start"):
        await state.clear()
        return  # Let start handler handle it

    lang = await _lang_for(message, session)
    plan_kb = await _get_plan_keyboard_for_user(session, message.chat.id, state, lang)
    await message.answer(("لطفا از دکمه های زیر استفاده کنید." if lang == "fa" else "Please use the buttons below."), reply_markup=plan_kb)

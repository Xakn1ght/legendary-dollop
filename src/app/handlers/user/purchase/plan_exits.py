from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.keyboards.reply import get_main_keyboard

from .common import (
    PurchaseState,
    _auto_renew_keyboard,
    _get_plan_keyboard_for_user,
    _lang_for,
    router,
)


@router.message(PurchaseState.plan, lambda m: (m.text or "").strip() in {"بازگشت🔙", "Back 🔙"})
async def cancel_from_plan(message: Message, state: FSMContext, session: AsyncSession):
    """User chose to go back from plan selection – cancel purchase and return to main menu.

    No order row exists yet at this step (it is created at Confirm & Pay)."""
    await state.clear()
    lang = await _lang_for(message, session)
    await message.answer(
        ('خرید لغو شد. به منوی اصلی بازگشتید.' if lang == "fa" else 'Purchase cancelled. Back to main menu.'),
        reply_markup=get_main_keyboard(message.chat.id, lang=lang),
    )

@router.message(PurchaseState.auto_renew_choice, lambda m: (m.text or "").strip() in {"بازگشت🔙", "Back 🔙"})
async def back_from_auto_renew_choice(message: Message, state: FSMContext, session: AsyncSession):
    lang = await _lang_for(message, session)
    await state.set_state(PurchaseState.plan)
    plan_kb = await _get_plan_keyboard_for_user(session, message.chat.id, state, lang)
    await message.answer(("لطفا یکی از پلن های زیر را انتخاب کنید:" if lang == "fa" else "Please choose a plan:"), reply_markup=plan_kb)

@router.message(PurchaseState.renewal_template, lambda m: (m.text or "").strip() in {"بازگشت🔙", "Back 🔙"})
async def back_from_renewal_template(message: Message, state: FSMContext, session: AsyncSession):
    lang = await _lang_for(message, session)
    await state.set_state(PurchaseState.auto_renew_choice)
    await message.answer(("آیا می‌خواهید تمدید خودکار فعال باشد؟" if lang == "fa" else "Do you want to enable auto-renew?"), reply_markup=await _auto_renew_keyboard(state, lang))

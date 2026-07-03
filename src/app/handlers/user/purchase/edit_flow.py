from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.handlers.user.flow_inline import ikb
from app.utils.bot_i18n import t

from .common import (
    PurchaseState,
    _confirm_keyboard,
    _get_plan_keyboard_for_user,
    _lang_for,
    _name_keyboard,
    router,
)


@router.message(PurchaseState.confirmation, lambda m: (m.text or "").strip() in {"بازگشت🔙", "Back 🔙"})
async def go_back_from_confirmation(message: Message, state: FSMContext, session: AsyncSession):
    lang = await _lang_for(message, session)
    # Nothing to refund/clean up: the order row (and any credit/coupon/discount
    # consumption) is only created when the user taps Confirm & Pay.
    await state.set_state(PurchaseState.name)
    await message.answer(
        ("لطفا یک نام برای سرویس خود انتخاب کنید یا دکمه 'اتفاقی' را بزنید." if lang == "fa" else "Choose a service name, or tap 'Random'."),
        reply_markup=await _name_keyboard(state, lang),
    )

@router.message(PurchaseState.confirmation, lambda m: (m.text or "").strip() in {"ویرایش ✏️", "Edit ✏️"})
async def edit_from_confirmation(message: Message, state: FSMContext, session: AsyncSession):
    """Ask the user what they want to edit (name or plan)."""
    lang = await _lang_for(message, session)
    edit_markup = await ikb(state, [
        [("ویرایش نام ✏️" if lang == "fa" else "Edit name ✏️")],
        [("ویرایش پلن 📦" if lang == "fa" else "Edit plan 📦")],
        [t(lang, "btn_back")],
    ])
    await state.set_state(PurchaseState.edit_choice)
    await message.answer(("کدام مورد را می‌خواهید ویرایش کنید؟" if lang == "fa" else "What would you like to edit?"), reply_markup=edit_markup)

# -------- Edit choice handlers --------

@router.message(PurchaseState.edit_choice, lambda m: (m.text or "").strip() in {"ویرایش نام ✏️", "Edit name ✏️"})
async def edit_name_choice(message: Message, state: FSMContext, session: AsyncSession):
    # Go to name selection step
    await state.set_state(PurchaseState.name)
    lang = await _lang_for(message, session)
    await message.answer(t(lang, "purchase_choose_new_name"), reply_markup=await _name_keyboard(state, lang))


@router.message(PurchaseState.edit_choice, lambda m: (m.text or "").strip() in {"ویرایش پلن 📦", "Edit plan 📦"})
async def edit_plan_choice(message: Message, state: FSMContext, session: AsyncSession):
    # Go back to plan selection step
    await state.update_data(editing_plan_only=True)
    await state.set_state(PurchaseState.plan)
    lang = await _lang_for(message, session)
    plan_kb = await _get_plan_keyboard_for_user(session, message.chat.id, state, lang)
    await message.answer(t(lang, "purchase_choose_plan"), reply_markup=plan_kb)


@router.message(PurchaseState.edit_choice, lambda m: (m.text or "").strip() in {"بازگشت🔙", "Back 🔙"})
async def edit_choice_back(message: Message, state: FSMContext, session: AsyncSession):
    # Return to confirmation screen without changes
    await state.set_state(PurchaseState.confirmation)
    lang = await _lang_for(message, session)
    await message.answer(t(lang, "purchase_back_to_confirmation"), reply_markup=await _confirm_keyboard(state, lang))

from aiogram.fsm.context import FSMContext
from aiogram.types import KeyboardButton, Message, ReplyKeyboardMarkup
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import crud
from app.utils.bot_i18n import t

from .common import (
    PurchaseState,
    _cleanup_pending_subscription,
    _confirm_keyboard,
    _get_plan_keyboard_for_user,
    _lang_for,
    _name_keyboard,
    router,
)


@router.message(PurchaseState.confirmation, lambda m: (m.text or "").strip() in {"بازگشت🔙", "Back 🔙"})
async def go_back_from_confirmation(message: Message, state: FSMContext, session: AsyncSession):
    lang = await _lang_for(message, session)
    # Refund any deducted credit
    data_state = await state.get_data()
    credit_used = data_state.get('credit_used', 0)
    if credit_used:
        await crud.add_credit(session, message.chat.id, credit_used)
        await state.update_data(credit_used=0)
    # Delete pending subscription row as user goes back to name step
    await _cleanup_pending_subscription(session, state)

    await state.set_state(PurchaseState.name)
    await message.answer(
        ("لطفا یک نام برای سرویس خود انتخاب کنید یا دکمه 'اتفاقی' را بزنید." if lang == "fa" else "Choose a service name, or tap 'Random'."),
        reply_markup=_name_keyboard(lang),
    )

@router.message(PurchaseState.confirmation, lambda m: (m.text or "").strip() in {"ویرایش ✏️", "Edit ✏️"})
async def edit_from_confirmation(message: Message, state: FSMContext, session: AsyncSession):
    """Ask the user what they want to edit (name or plan)."""
    # Refund any deducted credit before editing so we recalculate later
    data_state = await state.get_data()
    credit_used = data_state.get('credit_used', 0)
    if credit_used:
        await crud.add_credit(session, message.chat.id, credit_used)
        await state.update_data(credit_used=0)

    lang = await _lang_for(message, session)
    edit_markup = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=("ویرایش نام ✏️" if lang == "fa" else "Edit name ✏️"))],
            [KeyboardButton(text=("ویرایش پلن 📦" if lang == "fa" else "Edit plan 📦"))],
            [KeyboardButton(text=t(lang, "btn_back"))],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )
    await state.set_state(PurchaseState.edit_choice)
    await message.answer(("کدام مورد را می‌خواهید ویرایش کنید؟" if lang == "fa" else "What would you like to edit?"), reply_markup=edit_markup)

# -------- Edit choice handlers --------

@router.message(PurchaseState.edit_choice, lambda m: (m.text or "").strip() in {"ویرایش نام ✏️", "Edit name ✏️"})
async def edit_name_choice(message: Message, state: FSMContext, session: AsyncSession):
    # Go to name selection step
    markup = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="اتفاقی"), KeyboardButton(text="Random")], [KeyboardButton(text="بازگشت🔙"), KeyboardButton(text="Back 🔙")]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )
    await state.set_state(PurchaseState.name)
    lang = await _lang_for(message, session)
    await message.answer(t(lang, "purchase_choose_new_name"), reply_markup=markup)


@router.message(PurchaseState.edit_choice, lambda m: (m.text or "").strip() in {"ویرایش پلن 📦", "Edit plan 📦"})
async def edit_plan_choice(message: Message, state: FSMContext, session: AsyncSession):
    # Go back to plan selection step
    await state.update_data(editing_plan_only=True)
    await state.set_state(PurchaseState.plan)
    lang = await _lang_for(message, session)
    plan_kb = await _get_plan_keyboard_for_user(session, message.chat.id, lang)
    await message.answer(t(lang, "purchase_choose_plan"), reply_markup=plan_kb)


@router.message(PurchaseState.edit_choice, lambda m: (m.text or "").strip() in {"بازگشت🔙", "Back 🔙"})
async def edit_choice_back(message: Message, state: FSMContext, session: AsyncSession):
    # Return to confirmation screen without changes
    await state.set_state(PurchaseState.confirmation)
    lang = await _lang_for(message, session)
    await message.answer(t(lang, "purchase_back_to_confirmation"), reply_markup=_confirm_keyboard(lang))

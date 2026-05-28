from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.core import settings
from app.shared.admin_access import ADMIN_IDS

from .menu import admin_settings_menu

router = Router()


class RenewalEditState(StatesGroup):
    waiting_percent = State()
    waiting_days = State()


@router.callback_query(F.data == "renewal_settings")
async def renewal_settings_menu(cb: CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS:
        return
    text = (
        "🔄 تنظیمات تمدید خودکار\n\n"
        f"٪ ترافیک برای رد تمدید: {settings.RENEWAL_TRAFFIC_SKIP_PERCENT}%\n"
        f"روز تا انقضا برای رد تمدید: {settings.RENEWAL_TIME_SKIP_DAYS} روز\n\n"
        "یک گزینه را انتخاب کنید:"
    )
    kb = InlineKeyboardBuilder()
    kb.button(text="✏️ تغییر درصد ترافیک", callback_data="edit_renewal_percent")
    kb.button(text="✏️ تغییر روز تا انقضا", callback_data="edit_renewal_days")
    kb.button(text="🔙 بازگشت", callback_data="close_settings")
    kb.adjust(1)
    await cb.message.edit_text(text, reply_markup=kb.as_markup())


@router.callback_query(F.data == "edit_renewal_percent")
async def edit_renewal_percent_start(cb: CallbackQuery, state: FSMContext):
    await state.set_state(RenewalEditState.waiting_percent)
    await cb.message.edit_text("درصد جدید برای رد تمدید را وارد کنید (عدد صحیح 1-100):")


@router.message(RenewalEditState.waiting_percent)
async def edit_renewal_percent_save(message: Message, state: FSMContext):
    try:
        value = int(message.text.strip())
        if not (1 <= value <= 100):
            raise ValueError
        settings.RENEWAL_TRAFFIC_SKIP_PERCENT = value
        await message.answer(f"✅ درصد ترافیک جدید: {value}%")
        await state.clear()
        await admin_settings_menu(message)
    except ValueError:
        await message.answer("مقدار نامعتبر است. یک عدد صحیح بین 1 تا 100 وارد کنید:")


@router.callback_query(F.data == "edit_renewal_days")
async def edit_renewal_days_start(cb: CallbackQuery, state: FSMContext):
    await state.set_state(RenewalEditState.waiting_days)
    await cb.message.edit_text("تعداد روز تا انقضا برای رد تمدید را وارد کنید (عدد صحیح 1-60):")


@router.message(RenewalEditState.waiting_days)
async def edit_renewal_days_save(message: Message, state: FSMContext):
    try:
        value = int(message.text.strip())
        if not (1 <= value <= 60):
            raise ValueError
        settings.RENEWAL_TIME_SKIP_DAYS = value
        await message.answer(f"✅ روز تا انقضا جدید: {value}")
        await state.clear()
        await admin_settings_menu(message)
    except ValueError:
        await message.answer("مقدار نامعتبر است. یک عدد صحیح بین 1 تا 60 وارد کنید:")

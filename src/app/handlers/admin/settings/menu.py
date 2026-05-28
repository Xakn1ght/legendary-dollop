from aiogram import F, Router
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.shared.admin_access import ADMIN_IDS
from app.utils.bot_i18n import t

from ._common import lang_for_tg_user

router = Router()


@router.message(F.text.in_(["تنظیمات⚙️", "تنظیمات"]))
async def admin_settings_menu(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return

    lang = lang_for_tg_user(message.from_user)
    kb = InlineKeyboardBuilder()
    kb.button(text=t(lang, "admin_settings_btn_manage_plans"), callback_data="plans_manage")
    kb.button(text=t(lang, "admin_settings_btn_manage_charges"), callback_data="packages_manage")
    kb.button(text=t(lang, "admin_settings_btn_renewal_settings"), callback_data="renewal_settings")
    kb.button(text=t(lang, "admin_settings_btn_day_plans"), callback_data="day_plans_manage")
    kb.button(text=t(lang, "admin_settings_btn_support_settings"), callback_data="support_settings")
    kb.button(text=t(lang, "admin_settings_btn_jobs_manage"), callback_data="jobs_manage")
    kb.button(text=t(lang, "admin_settings_btn_close"), callback_data="close_settings")
    kb.adjust(1)

    await message.answer(t(lang, "admin_settings_menu_title"), reply_markup=kb.as_markup())


@router.callback_query(F.data == "close_settings")
async def close_settings(cb: CallbackQuery):
    await cb.message.delete()
    await cb.answer()

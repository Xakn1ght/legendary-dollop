from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message, WebAppInfo
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.core.settings import DASHBOARD_PUBLIC_BASE_URL
from app.shared.admin_access import is_admin_user

router = Router()


def _admin_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="👑 باز کردن پنل ادمین", web_app=WebAppInfo(url=f"{DASHBOARD_PUBLIC_BASE_URL}/admin/"))
    kb.adjust(1)
    return kb.as_markup()


@router.message(Command("start"))
@router.message(Command("admin"))
@router.message(lambda m: bool(getattr(m, "text", "")) and m.text.strip() in ("/admin", "/start"))
async def open_admin_webapp(message: Message):
    """Admin WebApp entry: same behavior on main bot and isolated admin bot."""
    if not is_admin_user(message.from_user):
        return
    await message.answer(
        "پنل ادمین فقط از طریق وب‌اپ در دسترس است.\n"
        "برای ورود به پنل ادمین، روی دکمه زیر بزنید:",
        reply_markup=_admin_kb(),
    )

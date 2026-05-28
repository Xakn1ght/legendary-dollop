import os

from aiogram import F
from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.shared.admin_access import ADMIN_IDS
from app.utils.bot_i18n import t

from .common import _lang_for_tg_user, router


@router.callback_query(F.data == "system_logs")
async def system_logs(callback: CallbackQuery):
    """Show system logs interface"""
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer(t(_lang_for_tg_user(callback.from_user), "not_authorized"), show_alert=True)
        return

    kb = InlineKeyboardBuilder()
    kb.button(text="📄 لاگ‌های امروز", callback_data="logs_today")
    kb.button(text="🐛 لاگ‌های خطا", callback_data="logs_errors")
    kb.adjust(2)

    await callback.message.edit_text(
        "📋 **مدیریت لاگ‌ها**\n\nنوع لاگ مورد نظر را انتخاب کنید:",
        reply_markup=kb.as_markup(),
        parse_mode="Markdown",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("logs_"))
async def show_logs(callback: CallbackQuery):
    """Show specific log type"""
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer(t(_lang_for_tg_user(callback.from_user), "not_authorized"), show_alert=True)
        return

    log_type = callback.data.split("_")[1]

    try:
        if log_type == "today":
            log_content = get_recent_logs(hours=24)
            title = "📄 لاگ‌های امروز"
        elif log_type == "errors":
            log_content = get_error_logs()
            title = "🐛 لاگ‌های خطا"
        elif log_type == "database":
            log_content = get_database_logs()
            title = "🔍 لاگ‌های دیتابیس"
        elif log_type == "api":
            log_content = get_api_logs()
            title = "📡 لاگ‌های API"
        elif log_type == "users":
            log_content = get_user_logs()
            title = "👥 لاگ‌های کاربران"
        else:
            log_content = "نوع لاگ نامشخص"
            title = "❓ نامشخص"

        if len(log_content) > 3000:
            log_content = log_content[-3000:] + "\n\n... (فقط 3000 کاراکتر آخر نمایش داده شده)"

        log_text = f"{title}\n\n```\n{log_content}\n```"

    except Exception as e:
        log_text = f"❌ خطا در دریافت لاگ‌ها: {str(e)}"

    kb = InlineKeyboardBuilder()
    kb.button(text="🔄 بروزرسانی", callback_data=f"logs_{log_type}")
    kb.button(text="⬅️ بازگشت", callback_data="system_logs")
    kb.adjust(2)

    await callback.message.edit_text(
        log_text,
        reply_markup=kb.as_markup(),
        parse_mode="Markdown",
    )
    await callback.answer()


def get_recent_logs(hours=24):
    """Get recent log entries"""
    try:
        log_file = "/app/logs/app.log"
        if not os.path.exists(log_file):
            return "فایل لاگ یافت نشد"

        with open(log_file, encoding="utf-8") as f:
            lines = f.readlines()

        return "".join(lines[-50:]) if lines else "لاگی یافت نشد"
    except Exception as e:
        return f"خطا در خواندن لاگ: {str(e)}"


def get_error_logs():
    """Get error logs"""
    try:
        log_file = "/app/logs/errors.log"
        if not os.path.exists(log_file):
            return "فایل لاگ خطا یافت نشد"

        with open(log_file, encoding="utf-8") as f:
            content = f.read()

        return content if content else "خطایی یافت نشد"
    except Exception as e:
        return f"خطا در خواندن لاگ خطا: {str(e)}"


def get_database_logs():
    """Get database logs"""
    return "لاگ‌های دیتابیس - نیاز به پیکربندی"


def get_api_logs():
    """Get API logs"""
    return "لاگ‌های API - نیاز به پیکربندی"


def get_user_logs():
    """Get user activity logs"""
    return "لاگ‌های فعالیت کاربران - نیاز به پیکربندی"

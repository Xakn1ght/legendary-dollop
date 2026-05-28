import os
import subprocess
from datetime import datetime

from aiogram import F
from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Subscription, User
from app.shared.admin_access import ADMIN_IDS
from app.utils.bot_i18n import t

from .common import _lang_for_tg_user, router


@router.callback_query(F.data == "system_backup")
async def system_backup(callback: CallbackQuery, session: AsyncSession):
    """System backup management"""
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer(t(_lang_for_tg_user(callback.from_user), "not_authorized"), show_alert=True)
        return

    try:
        db_size_query = text("SELECT pg_size_pretty(pg_database_size(current_database()))")
        db_size_result = await session.execute(db_size_query)
        db_size = db_size_result.scalar() or "نامشخص"

        total_users = await session.scalar(select(func.count(User.id))) or 0
        total_subs = await session.scalar(select(func.count(Subscription.id))) or 0

        backup_dir = "/app/backups"
        last_backup = "هرگز"
        backup_count = 0

        if os.path.exists(backup_dir):
            backup_files = [f for f in os.listdir(backup_dir) if f.endswith(".sql")]
            backup_count = len(backup_files)
            if backup_files:
                backup_files.sort(key=lambda x: os.path.getctime(os.path.join(backup_dir, x)), reverse=True)
                last_backup_time = datetime.fromtimestamp(
                    os.path.getctime(os.path.join(backup_dir, backup_files[0]))
                )
                last_backup = last_backup_time.strftime("%Y-%m-%d %H:%M")

        backup_text = (
            "💾 **مدیریت پشتیبان‌گیری**\n\n"
            f"📊 **وضعیت دیتابیس:**\n"
            f"💿 اندازه دیتابیس: `{db_size}`\n"
            f"👥 کاربران: `{total_users:,}`\n"
            f"🛍 اشتراک‌ها: `{total_subs:,}`\n\n"
            f"📋 **پشتیبان‌ها:**\n"
            f"📁 تعداد فایل‌ها: `{backup_count}`\n"
            f"🕐 آخرین پشتیبان: `{last_backup}`\n\n"
            "عملیات پشتیبان‌گیری مورد نظر را انتخاب کنید:"
        )

    except Exception as e:
        backup_text = f"❌ خطا در دریافت اطلاعات پشتیبان‌گیری: {str(e)}"

    kb = InlineKeyboardBuilder()
    kb.button(text="💾 پشتیبان فوری", callback_data="create_backup")
    kb.adjust(2)

    await callback.message.edit_text(
        backup_text,
        reply_markup=kb.as_markup(),
        parse_mode="Markdown",
    )
    await callback.answer()


@router.callback_query(F.data == "create_backup")
async def create_backup(callback: CallbackQuery):
    """Create immediate backup"""
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer(t(_lang_for_tg_user(callback.from_user), "not_authorized"), show_alert=True)
        return

    await callback.answer("در حال ایجاد پشتیبان...")

    try:
        backup_dir = "/app/backups"
        os.makedirs(backup_dir, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = f"{backup_dir}/backup_{timestamp}.sql"

        result = subprocess.run(
            [
                "pg_dump",
                "-h",
                "localhost",
                "-U",
                "postgres",
                "-d",
                "your_db_name",
                "-f",
                backup_file,
            ],
            capture_output=True,
            text=True,
        )

        if result.returncode == 0:
            file_size = os.path.getsize(backup_file) / (1024 * 1024)

            await callback.message.edit_text(
                f"✅ **پشتیبان‌گیری موفق**\n\n"
                f"📁 فایل: `backup_{timestamp}.sql`\n"
                f"📊 اندازه: `{file_size:.2f} MB`\n"
                f"🕐 زمان: `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`\n\n"
                "پشتیبان با موفقیت ایجاد شد ✅",
                parse_mode="Markdown",
            )
        else:
            await callback.message.edit_text(
                f"❌ **خطا در پشتیبان‌گیری**\n\n" f"خطا: `{result.stderr}`",
                parse_mode="Markdown",
            )

    except Exception as e:
        await callback.message.edit_text(
            f"❌ **خطا در ایجاد پشتیبان**\n\n" f"جزئیات خطا: `{str(e)}`",
            parse_mode="Markdown",
        )

try:
    import psutil
except ImportError:
    psutil = None

from datetime import datetime

from aiogram import F
from aiogram.types import Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.shared.admin_access import ADMIN_IDS

from .common import router


@router.message(F.text.in_(["⚙️ سیستم", "سیستم"]))
async def system_management_menu(message: Message, session: AsyncSession):
    """Main system management interface"""
    if message.from_user.id not in ADMIN_IDS:
        return

    try:
        if psutil:
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage("/")

            boot_time = datetime.fromtimestamp(psutil.boot_time())
            uptime = datetime.now() - boot_time
            uptime_str = f"{uptime.days} روز، {uptime.seconds//3600} ساعت"

            try:
                db_size_query = text("SELECT pg_size_pretty(pg_database_size(current_database()))")
                db_size_result = await session.execute(db_size_query)
                db_size = db_size_result.scalar() or "نامشخص"
            except Exception:
                db_size = "نامشخص"

            system_health = (
                f"💾 CPU: `{cpu_percent:.1f}%`\n"
                f"🧠 RAM: `{memory.percent:.1f}%` (`{memory.used/1024**3:.1f}` / `{memory.total/1024**3:.1f}` GB)\n"
                f"💿 دیسک: `{disk.percent:.1f}%` (`{disk.used/1024**3:.1f}` / `{disk.total/1024**3:.1f}` GB)\n"
                f"🗄 دیتابیس: `{db_size}`\n"
                f"⏱ آپتایم: `{uptime_str}`"
            )

            health_status = (
                "🟢 عالی"
                if cpu_percent < 70 and memory.percent < 80 and disk.percent < 85
                else "🟡 هشدار"
                if cpu_percent < 90 and memory.percent < 95 and disk.percent < 95
                else "🔴 بحرانی"
            )
        else:
            try:
                db_size_query = text("SELECT pg_size_pretty(pg_database_size(current_database()))")
                db_size_result = await session.execute(db_size_query)
                db_size = db_size_result.scalar() or "نامشخص"
            except Exception:
                db_size = "نامشخص"

            system_health = (
                f"💾 CPU: نامشخص (psutil ناموجود)\n"
                f"🧠 RAM: نامشخص (psutil ناموجود)\n"
                f"💿 دیسک: نامشخص (psutil ناموجود)\n"
                f"🗄 دیتابیس: `{db_size}`\n"
                f"⏱ آپتایم: نامشخص (psutil ناموجود)"
            )
            health_status = "❓ محدود (psutil ناموجود)"

    except Exception as e:
        system_health = f"❌ خطا در دریافت اطلاعات سیستم: {str(e)}"
        health_status = "❓ نامشخص"

    stats_text = (
        "⚙️ **مدیریت سیستم**\n\n"
        f"🌡 **وضعیت سیستم:** {health_status}\n\n"
        f"📊 **منابع سیستم:**\n"
        f"{system_health}\n\n"
        "عملیات سیستمی مورد نظر را انتخاب کنید:"
    )

    kb = InlineKeyboardBuilder()
    kb.button(text="📋 لاگ‌های سیستم", callback_data="system_logs")
    kb.button(text="💾 پشتیبان‌گیری", callback_data="system_backup")
    kb.adjust(2)

    await message.answer(stats_text, reply_markup=kb.as_markup(), parse_mode="Markdown")

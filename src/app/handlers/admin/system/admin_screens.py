import os

try:
    import psutil
except ImportError:
    psutil = None

from aiogram import F
from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.shared.admin_access import ADMIN_IDS
from app.utils.bot_i18n import t

from .common import _lang_for_tg_user, router


@router.callback_query(F.data == "system_monitoring")
async def system_monitoring(callback: CallbackQuery, session: AsyncSession):
    """Real-time system monitoring"""
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer(t(_lang_for_tg_user(callback.from_user), "not_authorized"), show_alert=True)
        return

    try:
        if psutil:
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_count = psutil.cpu_count()

            memory = psutil.virtual_memory()
            swap = psutil.swap_memory()

            disk = psutil.disk_usage("/")
            disk_io = psutil.disk_io_counters()

            network = psutil.net_io_counters()

            processes = len(psutil.pids())

            try:
                db_connections_query = text("SELECT count(*) FROM pg_stat_activity")
                db_connections_result = await session.execute(db_connections_query)
                db_connections = db_connections_result.scalar() or 0
            except Exception:
                db_connections = "نامشخص"

            monitoring_text = (
                "📊 **مانیتورینگ سیستم**\n\n"
                f"🖥 **CPU:**\n"
                f"• استفاده: `{cpu_percent:.1f}%`\n"
                f"• هسته‌ها: `{cpu_count}` عدد\n\n"
                f"🧠 **حافظه:**\n"
                f"• RAM: `{memory.percent:.1f}%` (`{memory.used/1024**3:.1f}` / `{memory.total/1024**3:.1f}` GB)\n"
                f"• Swap: `{swap.percent:.1f}%` (`{swap.used/1024**3:.1f}` / `{swap.total/1024**3:.1f}` GB)\n\n"
                f"💿 **دیسک:**\n"
                f"• استفاده: `{disk.percent:.1f}%` (`{disk.used/1024**3:.1f}` / `{disk.total/1024**3:.1f}` GB)\n"
                f"• خواندن: `{disk_io.read_bytes/1024**3:.2f}` GB\n"
                f"• نوشتن: `{disk_io.write_bytes/1024**3:.2f}` GB\n\n"
                f"🌐 **شبکه:**\n"
                f"• دریافت: `{network.bytes_recv/1024**3:.2f}` GB\n"
                f"• ارسال: `{network.bytes_sent/1024**3:.2f}` GB\n\n"
                f"⚙️ **فرآیندها:**\n"
                f"• تعداد: `{processes}`\n"
                f"• اتصالات DB: `{db_connections}`"
            )
        else:
            try:
                db_connections_query = text("SELECT count(*) FROM pg_stat_activity")
                db_connections_result = await session.execute(db_connections_query)
                db_connections = db_connections_result.scalar() or 0
            except Exception:
                db_connections = "نامشخص"

            monitoring_text = (
                "📊 **مانیتورینگ سیستم**\n\n"
                "⚠️ **psutil ناموجود - اطلاعات محدود**\n\n"
                f"🗄 **دیتابیس:**\n"
                f"• اتصالات فعال: `{db_connections}`\n\n"
                "💡 **نکته:** برای مانیتورینگ کامل سیستم، نصب psutil ضروری است:\n"
                "`pip install psutil`"
            )

    except Exception as e:
        monitoring_text = f"❌ خطا در دریافت اطلاعات مانیتورینگ: {str(e)}"

    kb = InlineKeyboardBuilder()
    kb.button(text="🔄 بروزرسانی", callback_data="system_monitoring")
    kb.adjust(2)

    await callback.message.edit_text(
        monitoring_text,
        reply_markup=kb.as_markup(),
        parse_mode="Markdown",
    )
    await callback.answer()


@router.callback_query(F.data == "bot_configuration")
async def bot_configuration(callback: CallbackQuery):
    """Bot configuration management"""
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer(t(_lang_for_tg_user(callback.from_user), "not_authorized"), show_alert=True)
        return

    try:
        config_info = (
            "🔧 **تنظیمات ربات**\n\n"
            "⚙️ **تنظیمات فعلی:**\n"
            f"• محیط: `{'Production' if os.getenv('ENVIRONMENT') == 'prod' else 'Development'}`\n"
            f"• دیباگ: `{'فعال' if os.getenv('DEBUG') == 'true' else 'غیرفعال'}`\n"
            f"• لاگ سطح: `{os.getenv('LOG_LEVEL', 'INFO')}`\n\n"
            "📊 **عملکرد ربات:**\n"
            f"• حالت polling: `{'فعال' if True else 'غیرفعال'}`\n"
            f"• تایم‌اوت: `30` ثانیه\n"
            f"• حداکثر اتصالات همزمان: `40`\n\n"
            "عملیات تنظیماتی مورد نظر را انتخاب کنید:"
        )
    except Exception as e:
        config_info = f"❌ خطا در دریافت تنظیمات: {str(e)}"

    kb = InlineKeyboardBuilder()
    kb.adjust(2)

    await callback.message.edit_text(
        config_info,
        reply_markup=kb.as_markup(),
        parse_mode="Markdown",
    )
    await callback.answer()


@router.callback_query(F.data == "maintenance_operations")
async def maintenance_operations(callback: CallbackQuery):
    """System maintenance operations"""
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer(t(_lang_for_tg_user(callback.from_user), "not_authorized"), show_alert=True)
        return

    maintenance_text = (
        "🔧 **عملیات تعمیر و نگهداری**\n\n"
        "⚠️ **توجه:** این عملیات بر روی عملکرد سیستم تأثیر می‌گذارند\n\n"
        "عملیات مورد نظر را انتخاب کنید:"
    )

    kb = InlineKeyboardBuilder()
    kb.adjust(2)

    await callback.message.edit_text(
        maintenance_text,
        reply_markup=kb.as_markup(),
        parse_mode="Markdown",
    )
    await callback.answer()

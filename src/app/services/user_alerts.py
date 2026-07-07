"""User-facing service alerts shared by the notify sweep and panel webhooks.

The 10-min low-data sweep (jobs/notifications.py) and the PasarGuard webhook
receiver (api/routes/webhooks/) can both decide to warn the same user. Every
send here is guarded by the SAME redis day-keys the sweep uses, so whichever
path fires first wins and the other stays silent.
"""
import logging
from datetime import datetime, timedelta

from app.core.redis_config import cache
from app.database import crud
from app.keyboards.inline import get_low_resource_keyboard, get_low_traffic_keyboard, get_renewal_keyboard


def _ttl_to_midnight() -> int:
    now = datetime.utcnow()
    nxt = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return int((nxt - now).total_seconds())


async def _once_per_day(kind: str, sub_id: int) -> bool:
    """True when this alert hasn't fired today (and marks it fired)."""
    key = f"notif:{kind}:{sub_id}:{datetime.utcnow().date().isoformat()}"
    try:
        if await cache.get(key):
            return False
        await cache.set(key, 1, ttl=_ttl_to_midnight())
    except Exception:
        pass  # redis down → prefer a possible duplicate over silence
    return True


async def send_finished_data_alert(bot, sub, *, auto_renew: bool) -> bool:
    user = sub.user
    if not user:
        return False
    kind = "finished_auto" if auto_renew else "finished"
    if not await _once_per_day(kind, sub.id):
        return False
    if auto_renew:
        text = (
            "❗️حجم اشتراک شما تمام شد!\n\n"
            f"برای سرویس با نام کاربری <code>{sub.marzban_username}</code> تمدید خودکار فعال است و به‌زودی انجام می‌گردد."
        )
        await bot.send_message(chat_id=user.chat_id, text=text, parse_mode="HTML")
    else:
        text = (
            "❗️حجم اشتراک شما تمام شد!\n\n"
            f"اشتراک با نام کاربری <code>{sub.marzban_username}</code> به اتمام رسیده است.\n\n"
            "برای تمدید و جلوگیری از حذف اشتراک از دکمه زیر استفاده کنید:"
        )
        await bot.send_message(
            chat_id=user.chat_id, text=text,
            reply_markup=get_renewal_keyboard(sub.marzban_username), parse_mode="HTML",
        )
    return True


async def send_low_traffic_alert(bot, sub, remaining_bytes: int, remaining_percent: float) -> bool:
    user = sub.user
    if not user:
        return False
    if not await _once_per_day("low_traffic", sub.id):
        return False
    remaining_gb = round(remaining_bytes / (1024 ** 3), 2)
    if sub.renewal_paid:
        text = (
            "⚠️ هشدار حجم کم!\n\n"
            f"حجم اشتراک <code>{sub.marzban_username}</code> رو به اتمام است.\n"
            f"باقی‌مانده: {remaining_gb} گیگابایت (~{remaining_percent:.1f}٪).\n\n"
            "تمدید خودکار فعال است و در زمان پایان سرویس اعمال می‌شود. در صورت نیاز می‌توانید همین حالا شارژ کنید."
        )
    else:
        text = (
            "⚠️ هشدار حجم کم!\n\n"
            f"حجم اشتراک با نام کاربری <code>{sub.marzban_username}</code> رو به اتمام است.\n"
            f"حجم باقی‌مانده: {remaining_gb} گیگابایت (~{remaining_percent:.1f}٪)\n\n"
            "برای شارژ یا تمدید، از دکمه زیر استفاده کنید."
        )
    await bot.send_message(
        chat_id=user.chat_id, text=text,
        reply_markup=get_low_traffic_keyboard(sub.marzban_username), parse_mode="HTML",
    )
    return True


async def send_expiry_soon_alert(bot, session, sub) -> bool:
    user = sub.user
    if not user:
        return False
    if not await _once_per_day("imminent_expiry", sub.id):
        return False
    text = (
        "⚠️ از زمان اشتراک با نام کاربری "
        f"<code>{sub.marzban_username}</code> کمتر از ۳ روز باقی مانده است. برای تمدید دکمه زیر را فشار دهید.\n\n"
        "✅ در صورت تمدید، بسته خریداری شده برای شما رزرو شده و به محض پایان سرویس فعلی به طور خودکار فعال می‌گردد."
    )
    await bot.send_message(
        chat_id=user.chat_id, text=text,
        reply_markup=get_low_resource_keyboard(sub.marzban_username), parse_mode="HTML",
    )
    try:
        await crud.set_imminent_expiry_notified(session, sub.id, True)
    except Exception:
        logging.debug("[ALERTS] could not persist imminent_expiry_notified", exc_info=True)
    return True


async def send_expired_alert(bot, session, sub) -> bool:
    user = sub.user
    if not user:
        return False
    if getattr(sub, "expired_notified", False):
        return False
    if not await _once_per_day("expired", sub.id):
        return False
    text = (
        f"❗️اشتراک شما با نام کاربری <code>{sub.marzban_username}</code> منقضی شد!\n\n"
        "برای تمدید و جلوگیری از حذف اشتراک از دکمه زیر استفاده کنید:"
    )
    await bot.send_message(
        chat_id=user.chat_id, text=text,
        reply_markup=get_renewal_keyboard(sub.marzban_username), parse_mode="HTML",
    )
    try:
        await crud.set_expired_notified(session, sub.id, True)
    except Exception:
        logging.debug("[ALERTS] could not persist expired_notified", exc_info=True)
    return True

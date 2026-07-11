import html
import json
from datetime import datetime as _dt
from pathlib import Path

from aiogram import F
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.jobs.renewal import (
    SKIP_RENEW_TIME_THRESHOLD,
    SKIP_RENEW_TRAFFIC_THRESHOLD_PERCENT,
    renewal_job,
)
from app.shared.admin_access import ADMIN_IDS
from app.utils.admin_bot_helper import get_user_bot
from app.utils.bot_i18n import t
from app.utils.health_check import get_health_summary, get_system_health

from .common import _lang_for_tg_user, router


_CLIENT_ERRORS_FILE = Path(__file__).resolve().parents[3] / "data" / "client_errors.jsonl"


@router.message(F.text.startswith("/errors"))
async def show_client_errors(message: Message):
    """Show the latest client-side JS errors reported by the Mini App.

    Usage: /errors [N]   (default 10, max 25)
    """
    if message.from_user.id not in ADMIN_IDS:
        return
    try:
        parts = (message.text or "").split()
        count = min(25, max(1, int(parts[1]))) if len(parts) > 1 else 10
    except Exception:
        count = 10

    try:
        lines = _CLIENT_ERRORS_FILE.read_text(encoding="utf-8").strip().splitlines()
    except FileNotFoundError:
        await message.answer("هیچ خطای کلاینتی ثبت نشده است.")
        return
    except Exception as e:
        await message.answer(f"خواندن فایل خطاها ممکن نشد: {e}")
        return

    if not lines:
        await message.answer("هیچ خطای کلاینتی ثبت نشده است.")
        return

    rows = []
    for line in lines[-count:]:
        try:
            ev = json.loads(line)
        except Exception:
            continue
        ts = _dt.fromtimestamp(int(ev.get("at", 0))).strftime("%m-%d %H:%M")
        kind = str(ev.get("kind", "?"))[:10]
        platform = str(ev.get("platform", "?"))[:8]
        page = html.escape(str(ev.get("page", ""))[:40])
        msg = html.escape(str(ev.get("msg", ""))[:160])
        rows.append(f"<b>{ts}</b> [{kind}/{platform}] {page}\n{msg}")

    total = len(lines)
    text = f"🧾 آخرین خطاهای کلاینت ({len(rows)} از {total}):\n\n" + "\n\n".join(rows)
    # Telegram message cap is 4096 chars.
    await message.answer(text[:4000])


@router.message(F.text == "/run_renewal")
async def run_renewal_now(message: Message):
    """Manually trigger the renewal job immediately (admin only)."""
    if message.from_user.id not in ADMIN_IDS:
        return
    user_bot = get_user_bot()
    if not user_bot:
        await message.answer("❌ BOT_TOKEN تنظیم نشده؛ نمی‌توان به کاربران پیام داد.")
        return
    try:
        await message.answer("⏱ اجرای فوری Job تمدید آغاز شد...")
        await renewal_job(user_bot)
        await message.answer("✅ Job تمدید اجرا شد. (نتایج در لاگ‌ها)")
    except Exception as e:
        await message.answer(f"❌ خطا در اجرای Job تمدید: {e}")


@router.message(F.text == "/renewal_preview")
async def renewal_preview(message: Message, session: AsyncSession):
    """Show subscriptions currently eligible for auto-renewal and why (admin only)."""
    if message.from_user.id not in ADMIN_IDS:
        return
    from app.database import crud as _crud
    from app.services.pasarguard import pasarguard_api as _api

    subs = await _crud.get_subscriptions_for_renewal(session)
    if not subs:
        await message.answer(
            "هیچ اشتراک واجد شرایطی یافت نشد (status=active, renewal_paid=True, renewal_applied=False)."
        )
        return
    now = _dt.utcnow()
    lines = []
    for s in subs[:50]:
        info = await _api.get_user_info(s.marzban_username)
        if not info:
            lines.append(f"{s.id}:{s.marzban_username} — no user info")
            continue
        expire_ts = info.get("expire")
        data_limit = info.get("data_limit", 0) or 0
        used = info.get("used_traffic", 0) or 0
        remaining = max(data_limit - used, 0)
        pct = (remaining / data_limit * 100) if data_limit > 0 else 0
        time_left = _dt.utcfromtimestamp(expire_ts) - now if expire_ts else None
        eligible = not (
            (time_left and time_left > SKIP_RENEW_TIME_THRESHOLD)
            and (pct > SKIP_RENEW_TRAFFIC_THRESHOLD_PERCENT)
        )
        lines.append(
            f"{s.id}:{s.marzban_username} — left {pct:.1f}% | time_left: {time_left} | eligible: {'✅' if eligible else '❌'}"
        )
    out = "\n".join(lines)
    if len(out) > 3500:
        out = out[:3500] + "\n..."
    await message.answer(out or "—")


@router.message(F.text == "/health")
async def system_health_command(message: Message):
    """Show concise system health summary (admin only)."""
    if message.from_user.id not in ADMIN_IDS:
        return
    try:
        await get_system_health()
        summary = get_health_summary()
        await message.answer(summary)
    except Exception as e:
        await message.answer(
            t(_lang_for_tg_user(message.from_user), "admin_system_health_failed").format(err=str(e))
        )

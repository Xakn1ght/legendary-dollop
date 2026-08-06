"""Admin-bot watchdog for the user bot + web server.

The admin bot runs as a separate process, so it can notice when the user
bot's web server stops answering and alert the admins on Telegram.

Policy: probe /health every 60s; alert after 2 consecutive failures
(one blip is ignored), re-alert every 30 minutes while still down, and
send a recovery message with total downtime when it comes back.
"""

import asyncio
import logging
import shutil
import time

import aiohttp

from app.core.settings.web_game import GAME_WEBAPP_PORT
from app.shared.admin_access import ADMIN_IDS

logger = logging.getLogger(__name__)

_HEALTH_URL = f"http://127.0.0.1:{GAME_WEBAPP_PORT}/health"
_PROBE_EVERY = 60
_FAILS_TO_ALERT = 2
_REALERT_EVERY = 30 * 60

# Disk watch: the classic silent killer — logs/backups fill the disk and
# Postgres stops writing. Alert at 90%, all-clear below 85%.
_DISK_PATH = "/"
_DISK_ALERT_PCT = 90
_DISK_CLEAR_PCT = 85
_DISK_REALERT_EVERY = 12 * 3600


async def _probe(session: aiohttp.ClientSession) -> str | None:
    """Return None when healthy, otherwise a short error description."""
    try:
        async with session.get(_HEALTH_URL, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            if resp.status == 200:
                return None
            return f"HTTP {resp.status}"
    except Exception as e:
        return type(e).__name__


async def _notify(bot, text: str) -> None:
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, text)
        except Exception as e:
            logger.warning("watchdog notify to %s failed: %s", admin_id, e)


def _disk_used_pct() -> int | None:
    try:
        usage = shutil.disk_usage(_DISK_PATH)
        return int(round(usage.used / usage.total * 100))
    except Exception:
        return None


async def service_watchdog(bot) -> None:
    fails = 0
    down_since: float | None = None
    last_alert = 0.0
    disk_high = False
    last_disk_alert = 0.0

    async with aiohttp.ClientSession() as session:
        while True:
            try:
                error = await _probe(session)
                now = time.time()

                if error is None:
                    if down_since is not None:
                        mins = max(1, int((now - down_since) / 60))
                        await _notify(bot, f"سرویس اصلی دوباره در دسترس است (قطعی: ~{mins} دقیقه)")
                        logger.info("watchdog: service recovered after ~%sm", mins)
                    fails = 0
                    down_since = None
                else:
                    fails += 1
                    if fails >= _FAILS_TO_ALERT:
                        if down_since is None:
                            down_since = now
                        if now - last_alert >= _REALERT_EVERY:
                            last_alert = now
                            await _notify(
                                bot,
                                "هشدار: ربات اصلی / داشبورد پاسخ نمی‌دهد!\n"
                                f"خطا: {error}\n"
                                "بررسی: systemctl status astrobyte-userbot",
                            )
                            logger.error("watchdog: service DOWN (%s)", error)

                # Disk watch (hysteresis: alert ≥90%, clear <85%)
                pct = _disk_used_pct()
                if pct is not None:
                    if pct >= _DISK_ALERT_PCT:
                        if now - last_disk_alert >= _DISK_REALERT_EVERY:
                            last_disk_alert = now
                            disk_high = True
                            await _notify(
                                bot,
                                f"هشدار فضای دیسک: {pct}٪ پر است!\n"
                                "بررسی: du -sh /root/5a06b8e65bdb/ASTROBYTE/{backups,logs}",
                            )
                            logger.error("watchdog: disk usage %s%%", pct)
                    elif disk_high and pct < _DISK_CLEAR_PCT:
                        disk_high = False
                        last_disk_alert = 0.0
                        await _notify(bot, f"فضای دیسک به حالت عادی برگشت ({pct}٪)")
            except Exception as e:
                logger.warning("watchdog loop error: %s", e)

            await asyncio.sleep(_PROBE_EVERY)

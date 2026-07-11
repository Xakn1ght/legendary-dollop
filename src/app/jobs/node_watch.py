"""Panel node watchdog.

Every run fetches the node list; when a node's connectivity flips (connected →
down or back), DMs every admin via the ADMIN bot. Last-known states are kept in
a small JSON file so restarts don't re-alert unchanged outages.

The job runs inside the user-bot process (its scheduler), but admin traffic
must NEVER flow through the user bot — alerts go out on the admin bot client.
"""
import json

from app.core.paths import data_path
from app.services.pasarguard import pasarguard_api
from app.shared.admin_access import ADMIN_IDS
from app.utils.admin_bot_helper import get_admin_bot
from app.utils.logger import bot_logger

_STATE_FILE = data_path("node_watch.json")
_OK_STATUSES = {"connected", "healthy"}


def _load_state() -> dict:
    try:
        with open(_STATE_FILE, encoding="utf-8") as f:
            return json.load(f) or {}
    except Exception:
        return {}


def _save_state(state: dict) -> None:
    try:
        with open(_STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False)
    except Exception as e:
        bot_logger.warning(f"[NODES] could not persist watch state: {e}")


async def node_watch_job(bot) -> None:
    nodes = await pasarguard_api.get_nodes()
    if not isinstance(nodes, list) or not nodes:
        return  # unreachable panel is alerted through its own health checks

    prev = _load_state()
    state: dict = {}
    changes: list[str] = []
    for n in nodes:
        name = str(n.get("name") or f"node-{n.get('id')}")
        status = str(n.get("status") or "unknown").lower()
        # "disabled" is an admin's choice (PasarGuard keeps such nodes listed),
        # not an outage — don't alert on it, and forget its previous state.
        if status == "disabled":
            continue
        up = status in _OK_STATUSES
        state[name] = "up" if up else "down"
        was = prev.get(name)
        if was is not None and was != state[name]:
            if up:
                changes.append(f"✅ نود «{name}» دوباره وصل شد.")
            else:
                changes.append(f"🔴 نود «{name}» از دسترس خارج شد! (status: {status})")
        elif was is None and not up:
            changes.append(f"🔴 نود «{name}» down است (status: {status}).")

    _save_state(state)
    if not changes:
        return

    # `bot` (the scheduler's user bot) is deliberately unused for sending:
    # node status is admin-only and must arrive from the admin bot.
    admin_bot = get_admin_bot()
    if not admin_bot:
        bot_logger.warning("[NODES] ADMIN_BOT_TOKEN not set — node alert skipped (never sent via user bot)")
        return

    text = "🛰 <b>وضعیت نودها</b>\n\n" + "\n".join(changes)
    for admin_id in ADMIN_IDS:
        try:
            await admin_bot.send_message(admin_id, text, parse_mode="HTML")
        except Exception:
            pass
    bot_logger.info(f"[NODES] status change alert sent: {changes}")

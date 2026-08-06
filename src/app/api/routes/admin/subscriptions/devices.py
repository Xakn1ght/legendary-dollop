"""Admin: read-only device + client-app view for one subscription.

Companion to the manual hwid_limit cap (see hwid_limit.py): before capping a
suspected link-sharer the admin can now see what the panel actually knows —
the registered HWID devices (Hiddify-family clients only; others never report
one) and the recent subscription/config fetches with their client user-agents,
which cover the non-HWID clients. Read-only: per-device delete/reset stays in
the panel UI (the API key deliberately has hwids.delete off).
"""
from aiohttp import web

from app.services.pasarguard import pasarguard_api

_SUB_UPDATES_SHOWN = 5


async def handle_admin_subscription_devices(request: web.Request):
    """GET /api/admin/subscriptions/{username}/devices"""
    username = request.match_info.get("username", "").strip()
    if not username or len(username) > 100:
        return web.json_response({"ok": False, "error": "invalid_username"}, status=400)

    try:
        # HWID endpoints are keyed by panel user id, not username (5.1.0).
        info = await pasarguard_api.get_user_info(username)
        if not isinstance(info, dict) or not info.get("id"):
            return web.json_response({"ok": False, "error": "user_not_found"}, status=404)

        devices = []
        hwid_data = await pasarguard_api.get_user_hwid_devices(int(info["id"]))
        for d in (hwid_data or {}).get("hwids") or []:
            if not isinstance(d, dict):
                continue
            devices.append({
                "id": d.get("id"),
                "hwid": d.get("hwid"),
                "device_os": d.get("device_os"),
                "os_version": d.get("os_version"),
                "device_model": d.get("device_model"),
                "first_seen": d.get("created_at"),
                "last_seen": d.get("last_used_at"),
            })

        # Recent config fetches (client app + time; IPs deliberately not sent
        # to the UI — nothing renders them and they'd sit in devtools).
        fetches = []
        sub_data = await pasarguard_api.get_user_sub_updates(username, limit=_SUB_UPDATES_SHOWN)
        for u in (sub_data or {}).get("updates") or []:
            if not isinstance(u, dict):
                continue
            fetches.append({
                "at": u.get("created_at"),
                "user_agent": u.get("user_agent"),
            })

        return web.json_response({
            "ok": True,
            "username": username,
            "hwid_limit": info.get("hwid_limit"),
            "devices": devices,
            "device_count": (hwid_data or {}).get("count", len(devices)),
            # None (vs []) tells the UI the panel call itself failed
            "devices_available": hwid_data is not None,
            "recent_fetches": fetches,
            "fetch_count": (sub_data or {}).get("count", len(fetches)),
        })
    except Exception:
        import traceback

        traceback.print_exc()
        return web.json_response({"ok": False, "error": "server_error"}, status=500)

"""Admin: set a subscription's device cap (PasarGuard hwid_limit).

No plan-level enforcement anywhere — this is a purely manual admin control
(Pasha's call, 2026-07-07): 0 clears the cap, N caps concurrent devices for
that one panel user. Only Hiddify-family clients report HWIDs reliably, so
this is applied case-by-case (e.g. an obvious link-sharer), never in bulk.
"""
from aiohttp import web

from app.services.audit import record_audit
from app.services.pasarguard import pasarguard_api


async def handle_admin_set_hwid_limit(request: web.Request):
    username = request.match_info.get("username", "").strip()
    if not username:
        return web.json_response({"ok": False, "error": "invalid_username"}, status=400)
    try:
        body = await request.json()
        limit = int(body.get("limit", 0))
    except Exception:
        return web.json_response({"ok": False, "error": "invalid_json"}, status=400)
    if limit < 0 or limit > 50:
        return web.json_response({"ok": False, "error": "invalid_limit"}, status=400)

    ok = await pasarguard_api.update_user(username, {"hwid_limit": limit})
    if not ok:
        return web.json_response({"ok": False, "error": "panel_update_failed"}, status=502)
    await pasarguard_api.invalidate_user_info(username)

    await record_audit(
        request, "subscription.hwid_limit", target_type="subscription", target_id=username,
        summary=f"device cap set to {limit or 'unlimited'} for {username}",
    )
    return web.json_response({"ok": True, "username": username, "hwid_limit": limit})

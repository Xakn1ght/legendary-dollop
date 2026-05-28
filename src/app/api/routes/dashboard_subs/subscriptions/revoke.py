from app.api.deps import _extract_user_id_from_init, _verify_webapp_auth

from ..common import *  # noqa: F403


async def handle_dashboard_revoke(request: web.Request):
    try:
        sub_id = int(request.match_info.get("sub_id"))
    except (ValueError, TypeError):
        return web.json_response({"ok": False, "error": "invalid_sub_id", "message": "Subscription ID must be a valid number"}, status=400)

    try:
        data = await request.json()
    except Exception:
        data = {}
    user_chat_id, new_session_token = _verify_webapp_auth(request)
    if not user_chat_id:
        # Back-compat: allow legacy clients to pass init_data in JSON body.
        init_data = (data or {}).get("init_data", "") or ""
        if init_data and verify_init_data(init_data, BOT_TOKEN):
            user_chat_id = _extract_user_id_from_init(init_data)
            if user_chat_id:
                new_session_token = create_session_token(user_chat_id, WEBAPP_SESSION_SECRET or BOT_TOKEN, ttl_seconds=86400)
    if not user_chat_id:
        return web.json_response({"ok": False, "error": "unauthorized"}, status=403)

    async with AsyncSessionLocal() as session:
        user = await crud.get_user(session, user_chat_id)
        if not user:
            return web.json_response({"ok": False, "error": "not_registered"}, status=403)
        sub = await session.get(Subscription, sub_id)
        if not sub or sub.user_id != user.id:
            return web.json_response({"ok": False, "error": "not_found"}, status=404)
        ok = await marzban_api.revoke_user_subscription(sub.marzban_username)
        if not ok:
            return web.json_response({"ok": False, "error": "revoke_failed"}, status=500)
        # Refresh info and persist token if needed
        info = await marzban_api.get_user_info(sub.marzban_username)
        try:
            new_link = (info or {}).get("subscription_url")
            if new_link:
                import re
                m = re.search(r"/sub/([^/]+)/?", new_link)
                if m:
                    sub.sub_token = m.group(1)
                    await session.commit()
        except Exception:
            pass
        resp = web.json_response({"ok": True})
        if new_session_token:
            set_tma_session_cookie(resp, request, new_session_token, max_age=86400)
        return resp

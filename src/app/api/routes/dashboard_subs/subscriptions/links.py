from app.api.deps import _verify_webapp_auth

from ..common import *  # noqa: F403


async def handle_dashboard_links(request: web.Request):
    try:
        sub_id = int(request.match_info.get("sub_id"))
    except (ValueError, TypeError):
        return web.json_response({"ok": False, "error": "invalid_sub_id", "message": "Subscription ID must be a valid number"}, status=400)

    user_chat_id, new_session_token = _verify_webapp_auth(request)
    if not user_chat_id:
        return web.json_response({"ok": False, "error": "unauthorized"}, status=403)

    async with AsyncSessionLocal() as session:
        user = await crud.get_user(session, user_chat_id)
        if not user:
            return web.json_response({"ok": False, "error": "not_registered"}, status=403)
        sub = await session.get(Subscription, sub_id)
        if not sub or sub.user_id != user.id:
            return web.json_response({"ok": False, "error": "not_found"}, status=404)

        info = await pasarguard_api.get_fast_user_info(sub.marzban_username, getattr(sub, 'sub_token', None))
        links = (info or {}).get("links") or []
        resp = web.json_response({"ok": True, "links": links})
        if new_session_token:
            set_tma_session_cookie(resp, request, new_session_token, max_age=86400)
        return resp

from app.api.deps import _extract_user_id_from_init, _verify_webapp_auth
from app.services.flows.errors import FlowError
from app.services.flows.subs import revoke_subscription

from ..common import *  # noqa: F403

# Ownership failures report not_found so the API doesn't leak which ids exist.
_ERROR_STATUS = {"not_found": 404, "unauthorized": 404, "revoke_failed": 500}
_ERROR_CODES = {"unauthorized": "not_found"}


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
                user_chat_id = int(user_chat_id)
                new_session_token = create_session_token(user_chat_id, WEBAPP_SESSION_SECRET or BOT_TOKEN, ttl_seconds=86400)
    if not user_chat_id:
        return web.json_response({"ok": False, "error": "unauthorized"}, status=403)

    async with AsyncSessionLocal() as session:
        user = await crud.get_user(session, user_chat_id)
        if not user:
            return web.json_response({"ok": False, "error": "not_registered"}, status=403)
        try:
            await revoke_subscription(session, user, sub_id)
        except FlowError as e:
            return web.json_response(
                {"ok": False, "error": _ERROR_CODES.get(e.code, e.code)},
                status=_ERROR_STATUS.get(e.code, 400),
            )

        resp = web.json_response({"ok": True})
        if new_session_token:
            set_tma_session_cookie(resp, request, new_session_token, max_age=86400)
        return resp

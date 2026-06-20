from app.api.deps import _verify_webapp_auth
from app.services.flows.errors import FlowError
from app.services.flows.subs import add_subscription_by_link

from ..common import *  # noqa: F403

_ERROR_STATUS = {
    "disallowed_domain": 400,
    "invalid_subscription_url": 400,
    "subscription_url_required": 400,
    "cannot_resolve_username": 400,
    "marzban_account_not_found": 400,
}


async def handle_dashboard_add_sub(request: web.Request):
    user_chat_id, new_session_token = _verify_webapp_auth(request)
    if not user_chat_id:
        return web.json_response({"ok": False, "error": "unauthorized"}, status=403)

    try:
        data = await request.json()
    except Exception:
        return web.json_response({"ok": False, "error": "invalid_json"}, status=400)

    # Validate input using Pydantic schema
    validated, error = validate_request(AddSubscriptionRequest, data)
    if error:
        return web.json_response(error, status=400)

    async with AsyncSessionLocal() as session:
        user = await crud.get_user(session, user_chat_id)
        if not user:
            return web.json_response({"ok": False, "error": "not_registered"}, status=403)

        try:
            result = await add_subscription_by_link(
                session,
                user,
                url=(validated.url or "").strip() or None,
                token=(validated.token or "").strip() or None,
                username=(validated.username or "").strip() or None,
            )
        except FlowError as e:
            return web.json_response(
                {"ok": False, "error": e.code, "message": str(e)},
                status=_ERROR_STATUS.get(e.code, 400),
            )

        resp = web.json_response(
            {"ok": True, "subscription_id": result.subscription.id, "created": result.created}
        )
        if new_session_token:
            set_tma_session_cookie(resp, request, new_session_token, max_age=86400)
        return resp

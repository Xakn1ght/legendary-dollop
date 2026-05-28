import traceback

from aiohttp import web

from app.api.deps import _verify_webapp_auth, set_tma_session_cookie
from app.database import crud, notifications_crud
from app.database.models import AsyncSessionLocal


async def handle_dashboard_notification_clear_history(request: web.Request):
    """Clear all notifications for user"""
    user_chat_id, new_session_token = _verify_webapp_auth(request)
    if not user_chat_id:
        return web.json_response({"ok": False, "error": "unauthorized"}, status=403)

    try:
        async with AsyncSessionLocal() as session:
            user = await crud.get_user(session, user_chat_id)
            if not user:
                return web.json_response({"ok": False, "error": "user_not_found"}, status=404)

            deleted_count = await notifications_crud.delete_read_notifications(session, user.id)

            resp = web.json_response(
                {
                    "ok": True,
                    "deleted_count": deleted_count,
                }
            )
            if new_session_token:
                set_tma_session_cookie(resp, request, new_session_token, max_age=86400)
            return resp
    except Exception:
        traceback.print_exc()
        return web.json_response({"ok": False, "error": "server_error"}, status=500)

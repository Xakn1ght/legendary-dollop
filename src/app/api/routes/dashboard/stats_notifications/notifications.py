import traceback

from aiohttp import web

from app.api.deps import _verify_webapp_auth, set_tma_session_cookie
from app.api.schemas import DashboardMarkNotificationReadRequest, validate_request
from app.database import crud, notifications_crud
from app.database.models import AsyncSessionLocal


async def handle_dashboard_notifications(request: web.Request):
    """Get user notifications"""
    user_chat_id, new_session_token = _verify_webapp_auth(request)
    if not user_chat_id:
        return web.json_response({"ok": False, "error": "unauthorized"}, status=403)

    try:
        async with AsyncSessionLocal() as session:
            user = await crud.get_user(session, user_chat_id)
            if not user:
                return web.json_response({"ok": False, "error": "user_not_found"}, status=404)

            notifs = await notifications_crud.get_user_notifications(session, user.id, limit=50)
            unread_count = await notifications_crud.get_unread_count(session, user.id)

            notifs_data = []
            for n in notifs:
                notifs_data.append(
                    {
                        "id": n.id,
                        "type": n.type,
                        "title": n.title,
                        "message": n.message,
                        "ticket_id": n.ticket_id,
                        "read": n.read,
                        "created_at": n.created_at.isoformat() if n.created_at else None,
                    }
                )

            resp = web.json_response(
                {
                    "ok": True,
                    "notifications": notifs_data,
                    "unread_count": unread_count,
                }
            )
            if new_session_token:
                set_tma_session_cookie(resp, request, new_session_token, max_age=86400)
            return resp
    except Exception:
        traceback.print_exc()
        return web.json_response({"ok": False, "error": "server_error"}, status=500)


async def handle_dashboard_notification_unread_count(request: web.Request):
    """Get just the unread count (lightweight)"""
    user_chat_id, new_session_token = _verify_webapp_auth(request)
    if not user_chat_id:
        return web.json_response({"ok": False, "error": "unauthorized"}, status=403)

    try:
        async with AsyncSessionLocal() as session:
            user = await crud.get_user(session, user_chat_id)
            if not user:
                return web.json_response({"ok": False, "error": "user_not_found"}, status=404)

            unread_count = await notifications_crud.get_unread_count(session, user.id)

            resp = web.json_response(
                {
                    "ok": True,
                    "unread_count": unread_count,
                }
            )
            if new_session_token:
                set_tma_session_cookie(resp, request, new_session_token, max_age=86400)
            return resp
    except Exception:
        return web.json_response({"ok": False, "error": "server_error"}, status=500)


async def handle_dashboard_notification_mark_read(request: web.Request):
    """Mark notification(s) as read"""
    user_chat_id, new_session_token = _verify_webapp_auth(request)
    if not user_chat_id:
        return web.json_response({"ok": False, "error": "unauthorized"}, status=403)

    try:
        data = await request.json()
    except Exception:
        data = {}

    validated, error = validate_request(DashboardMarkNotificationReadRequest, data)
    if error:
        return web.json_response(error, status=400)

    notification_id = validated.notification_id

    try:
        async with AsyncSessionLocal() as session:
            user = await crud.get_user(session, user_chat_id)
            if not user:
                return web.json_response({"ok": False, "error": "user_not_found"}, status=404)

            if notification_id:
                success = await notifications_crud.mark_notification_as_read(session, notification_id, user.id)
            else:
                success = await notifications_crud.mark_all_notifications_as_read(session, user.id)

            resp = web.json_response({"ok": success})
            if new_session_token:
                set_tma_session_cookie(resp, request, new_session_token, max_age=86400)
            return resp
    except Exception:
        return web.json_response({"ok": False, "error": "server_error"}, status=500)

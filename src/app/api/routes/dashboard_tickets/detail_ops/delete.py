import traceback
from datetime import datetime

from aiohttp import web
from sqlalchemy.future import select

from app.api.deps import _verify_webapp_auth, set_tma_session_cookie
from app.database.models import AsyncSessionLocal, Ticket, User


async def handle_dashboard_tickets_delete(request: web.Request):
    """Soft delete ticket (hide from user)"""
    try:
        ticket_id = int(request.match_info["ticket_id"])
    except (ValueError, KeyError):
        return web.json_response({"ok": False, "error": "invalid_ticket_id"}, status=400)

    user_chat_id, new_session_token = _verify_webapp_auth(request)
    if not user_chat_id:
        return web.json_response({"ok": False, "error": "unauthorized"}, status=403)

    try:
        async with AsyncSessionLocal() as session:
            user = await session.execute(select(User).where(User.chat_id == user_chat_id))
            user = user.scalar_one_or_none()
            if not user:
                return web.json_response({"ok": False, "error": "user_not_found"}, status=404)

            ticket = await session.get(Ticket, ticket_id)
            if not ticket or ticket.user_id != user.id:
                return web.json_response({"ok": False, "error": "ticket_not_found"}, status=404)

            ticket.hidden_from_user = True
            ticket.hidden_at = datetime.utcnow()
            # The user walked away — don't leave the ticket looking actionable
            # in the admin panel's pending queue.
            if ticket.status not in ("closed", "archived"):
                ticket.status = "closed"
            await session.commit()

            try:
                from app.api.routes.admin_ws import broadcast_ticket_list_update

                await broadcast_ticket_list_update()
            except Exception:
                pass

            resp = web.json_response({"ok": True})
            if new_session_token:
                set_tma_session_cookie(resp, request, new_session_token, max_age=86400)
            return resp
    except Exception:
        traceback.print_exc()
        return web.json_response({"ok": False, "error": "server_error"}, status=500)

import traceback
from datetime import datetime

from aiohttp import web
from sqlalchemy.future import select

from app.api.deps import _verify_webapp_auth, set_tma_session_cookie
from app.api.routes.dashboard_tickets.common import broadcast_ticket_update
from app.api.schemas import TicketReplyRequest, validate_request
from app.database.models import AsyncSessionLocal, Ticket, TicketMessage, User


async def handle_dashboard_tickets_reply(request: web.Request):
    """Reply to ticket"""
    try:
        ticket_id = int(request.match_info["ticket_id"])
    except (ValueError, KeyError):
        return web.json_response({"ok": False, "error": "invalid_ticket_id"}, status=400)

    user_chat_id, new_session_token = _verify_webapp_auth(request)
    if not user_chat_id:
        return web.json_response({"ok": False, "error": "unauthorized"}, status=403)

    try:
        data = await request.json()
    except Exception:
        return web.json_response({"ok": False, "error": "invalid_json"}, status=400)

    validated, error = validate_request(TicketReplyRequest, data)
    if error:
        return web.json_response(error, status=400)

    message = validated.message

    try:
        async with AsyncSessionLocal() as session:
            user = await session.execute(select(User).where(User.chat_id == user_chat_id))
            user = user.scalar_one_or_none()
            if not user:
                return web.json_response({"ok": False, "error": "user_not_found"}, status=404)

            ticket = await session.get(Ticket, ticket_id)
            if not ticket or ticket.user_id != user.id:
                return web.json_response({"ok": False, "error": "ticket_not_found"}, status=404)

            if ticket.status in ("closed", "archived"):
                return web.json_response({"ok": False, "error": "ticket_closed"}, status=400)

            new_msg = TicketMessage(
                ticket_id=ticket_id,
                sender="user",
                content_type="text",
                text=message,
                read_by_user=True,
                created_at=datetime.utcnow(),
            )
            session.add(new_msg)

            ticket.updated_at = datetime.utcnow()

            await session.commit()

            try:
                await broadcast_ticket_update(
                    ticket_id,
                    "new_message",
                    {
                        "sender": "user",
                        "text": message,
                        "created_at": new_msg.created_at.isoformat(),
                    },
                    ticket_user_id=user_chat_id,
                )
            except Exception:
                pass

            resp = web.json_response({"ok": True, "message": "Reply sent successfully"})
            if new_session_token:
                set_tma_session_cookie(resp, request, new_session_token, max_age=86400)
            return resp
    except Exception:
        traceback.print_exc()
        return web.json_response({"ok": False, "error": "server_error"}, status=500)

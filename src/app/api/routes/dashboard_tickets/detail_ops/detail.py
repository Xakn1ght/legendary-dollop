import traceback

from aiohttp import web
from sqlalchemy.future import select

from app.api.deps import _verify_webapp_auth, set_tma_session_cookie
from app.database.models import AsyncSessionLocal, Ticket, TicketMessage, User


async def handle_dashboard_tickets_detail(request: web.Request):
    """Get ticket details with messages"""
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

            msg_stmt = (
                select(TicketMessage)
                .where(TicketMessage.ticket_id == ticket_id)
                .order_by(TicketMessage.created_at.asc())
            )
            msg_result = await session.execute(msg_stmt)
            messages = msg_result.scalars().all()

            for m in messages:
                if m.sender == "admin" and not getattr(m, "read_by_user", True):
                    m.read_by_user = True
            await session.commit()

            messages_data = [
                {
                    "id": msg.id,
                    "message": msg.text or "",
                    "from_admin": msg.sender == "admin",
                    "content_type": msg.content_type or "text",
                    "file_name": msg.file_name if msg.content_type == "photo" else None,
                    "created_at": msg.created_at.isoformat() if msg.created_at else None,
                }
                for msg in messages
            ]

            ticket_data = {
                "id": ticket.id,
                "user_ticket_number": ticket.user_ticket_number,
                "category": ticket.category,
                "status": ticket.status,
                "priority": ticket.priority,
                "created_at": ticket.created_at.isoformat() if ticket.created_at else None,
                "messages": messages_data,
            }

            resp = web.json_response({"ok": True, "ticket": ticket_data})
            if new_session_token:
                set_tma_session_cookie(resp, request, new_session_token, max_age=86400)
            return resp
    except Exception:
        traceback.print_exc()
        return web.json_response({"ok": False, "error": "server_error"}, status=500)

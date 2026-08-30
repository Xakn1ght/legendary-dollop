import traceback
from datetime import datetime, timedelta

from aiohttp import web
from sqlalchemy import func
from sqlalchemy.future import select

from app.api.deps import _verify_webapp_auth, set_tma_session_cookie
from app.api.routes.dashboard_tickets.common import broadcast_ticket_list_update, broadcast_user_ticket_list_update
from app.api.schemas import TicketCreateRequest, validate_request
from app.database.models import AsyncSessionLocal, Ticket, TicketMessage, User

# Anti-spam caps (per user). Open = anything not closed/archived and still
# visible to the user; the daily cap counts hidden ones too so delete+recreate
# can't be used to spam the admin inbox.
MAX_OPEN_TICKETS = 3
MAX_TICKETS_PER_DAY = 10


async def handle_dashboard_tickets_create(request: web.Request):
    """Create new ticket"""
    user_chat_id, new_session_token = _verify_webapp_auth(request)
    if not user_chat_id:
        return web.json_response({"ok": False, "error": "unauthorized"}, status=403)

    try:
        data = await request.json()
    except Exception:
        return web.json_response({"ok": False, "error": "invalid_json"}, status=400)

    validated, error = validate_request(TicketCreateRequest, data)
    if error:
        return web.json_response(error, status=400)

    category = validated.category
    message = validated.message
    subscription_id = validated.subscription_id

    try:
        async with AsyncSessionLocal() as session:
            user = await session.execute(select(User).where(User.chat_id == user_chat_id))
            user = user.scalar_one_or_none()
            if not user:
                return web.json_response({"ok": False, "error": "user_not_found"}, status=404)

            open_count = await session.scalar(
                select(func.count(Ticket.id)).where(
                    Ticket.user_id == user.id,
                    Ticket.status.notin_(("closed", "archived")),
                    Ticket.hidden_from_user.is_(False),
                )
            ) or 0
            if open_count >= MAX_OPEN_TICKETS:
                return web.json_response(
                    {"ok": False, "error": "too_many_open_tickets", "limit": MAX_OPEN_TICKETS},
                    status=429,
                )

            day_count = await session.scalar(
                select(func.count(Ticket.id)).where(
                    Ticket.user_id == user.id,
                    Ticket.created_at >= datetime.utcnow() - timedelta(hours=24),
                )
            ) or 0
            if day_count >= MAX_TICKETS_PER_DAY:
                return web.json_response(
                    {"ok": False, "error": "daily_ticket_limit", "limit": MAX_TICKETS_PER_DAY},
                    status=429,
                )

            max_ticket_number = await session.scalar(
                select(func.max(Ticket.user_ticket_number)).where(Ticket.user_id == user.id)
            ) or 0
            next_ticket_number = max_ticket_number + 1

            new_ticket = Ticket(
                user_id=user.id,
                category=category,
                status="pending",
                # VIP customers jump the queue — the admin inbox pins and
                # badges high-priority tickets.
                priority="high" if bool(getattr(user, "is_vip", False)) else "normal",
                subscription_id=subscription_id,
                user_ticket_number=next_ticket_number,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            session.add(new_ticket)
            await session.flush()

            first_message = TicketMessage(
                ticket_id=new_ticket.id,
                sender="user",
                content_type="text",
                text=message,
                created_at=datetime.utcnow(),
            )
            session.add(first_message)

            await session.commit()

            # The assistant may answer the first message straight away; every
            # gate (switch, human present, escalation words, rate limit) lives
            # in the service, and it stays silent unless all of them pass.
            try:
                from app.services.support_assist import maybe_answer_ticket
                await maybe_answer_ticket(session, new_ticket, user, message)
            except Exception:
                pass

            try:
                await broadcast_ticket_list_update()
            except Exception:
                pass

            try:
                await broadcast_user_ticket_list_update(user_chat_id)
            except Exception:
                pass

            resp = web.json_response(
                {
                    "ok": True,
                    "ticket_id": new_ticket.id,
                    "user_ticket_number": new_ticket.user_ticket_number,
                    "message": "Ticket created successfully",
                }
            )
            if new_session_token:
                set_tma_session_cookie(resp, request, new_session_token, max_age=86400)
            return resp
    except Exception:
        traceback.print_exc()
        return web.json_response({"ok": False, "error": "server_error"}, status=500)

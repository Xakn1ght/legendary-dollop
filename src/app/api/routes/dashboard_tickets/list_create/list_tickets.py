import traceback

from aiohttp import web
from sqlalchemy import func
from sqlalchemy.future import select

from app.api.deps import _verify_webapp_auth, set_tma_session_cookie
from app.database.models import AsyncSessionLocal, Subscription, Ticket, TicketMessage, User


async def handle_dashboard_tickets_list(request: web.Request):
    """Get user's tickets"""
    user_chat_id, new_session_token = _verify_webapp_auth(request)
    if not user_chat_id:
        return web.json_response({"ok": False, "error": "unauthorized"}, status=403)

    try:
        async with AsyncSessionLocal() as session:
            user = await session.execute(select(User).where(User.chat_id == user_chat_id))
            user = user.scalar_one_or_none()
            if not user:
                return web.json_response({"ok": False, "error": "user_not_found"}, status=404)

            stmt = (
                select(Ticket)
                .where(Ticket.user_id == user.id)
                .where(Ticket.hidden_from_user == False)
                .order_by(func.coalesce(Ticket.updated_at, Ticket.created_at).desc())
            )
            result = await session.execute(stmt)
            tickets = result.scalars().all()

            tickets_data = []
            for ticket in tickets:
                last_msg_stmt = (
                    select(TicketMessage)
                    .where(TicketMessage.ticket_id == ticket.id)
                    .order_by(TicketMessage.created_at.desc())
                    .limit(1)
                )
                last_msg_result = await session.execute(last_msg_stmt)
                last_msg = last_msg_result.scalar_one_or_none()

                subscription_username = None
                if ticket.subscription_id:
                    sub_stmt = select(Subscription).where(Subscription.id == ticket.subscription_id)
                    sub_result = await session.execute(sub_stmt)
                    sub = sub_result.scalar_one_or_none()
                    if sub:
                        subscription_username = sub.marzban_username

                unread_count = (
                    await session.scalar(
                        select(func.count(TicketMessage.id)).where(
                            TicketMessage.ticket_id == ticket.id,
                            TicketMessage.sender == "admin",
                            TicketMessage.read_by_user == False,
                        )
                    )
                    or 0
                )

                tickets_data.append(
                    {
                        "id": ticket.id,
                        "user_ticket_number": ticket.user_ticket_number,
                        "category": ticket.category,
                        "status": ticket.status,
                        "priority": ticket.priority,
                        "subscription_id": ticket.subscription_id,
                        "subscription_username": subscription_username,
                        "created_at": ticket.created_at.isoformat() if ticket.created_at else None,
                        "updated_at": ticket.updated_at.isoformat() if ticket.updated_at else None,
                        "last_message": last_msg.text[:100] if last_msg and last_msg.text else "No messages",
                        "unread_count": unread_count,
                    }
                )

            resp = web.json_response({"ok": True, "tickets": tickets_data})
            if new_session_token:
                set_tma_session_cookie(resp, request, new_session_token, max_age=86400)
            return resp
    except Exception:
        traceback.print_exc()
        return web.json_response({"ok": False, "error": "server_error"}, status=500)

from ..common import *  # noqa: F403


async def handle_admin_ticket_detail(request: web.Request):
    try:
        ticket_id = int(request.match_info['ticket_id'])
    except (ValueError, KeyError):
        return web.json_response({"ok": False, "error": "invalid_ticket_id"}, status=400)
    try:
        async with AsyncSessionLocal() as session:
            ticket = await session.get(Ticket, ticket_id)
            if not ticket:
                return web.json_response({"ok": False, "error": "not_found"}, status=404)
            
            # Get user
            user = await session.get(User, ticket.user_id)
            user_name = user.full_name if user else f"User #{ticket.user_id}"
            
            # Get messages
            msgs_result = await session.execute(
                select(TicketMessage)
                .where(TicketMessage.ticket_id == ticket_id)
                .order_by(TicketMessage.created_at.asc())
            )
            msgs = msgs_result.scalars().all()
            
            # Mark messages as read by admin
            for m in msgs:
                if m.sender == 'user' and not m.read_by_admin:
                    m.read_by_admin = True
            await session.commit()
            
            # Get subscription info
            subscription_username = None
            if ticket.subscription_id:
                sub = await session.get(Subscription, ticket.subscription_id)
                if sub:
                    subscription_username = sub.marzban_username
            
            return web.json_response({
                "ok": True,
                "ticket": {
                    "id": ticket.id,
                    "user_id": ticket.user_id,
                    "user_name": user_name,
                    "subject": ticket.category or "No subject",
                    "category": ticket.category,
                    "status": ticket.status,
                    "priority": ticket.priority,
                    "subscription_username": subscription_username,
                    "user": {
                        "id": user.id if user else None,
                        "full_name": user.full_name if user else "Unknown",
                        "username": user.username if user else None
                    },
                    "messages": [{
                        "id": m.id,
                        "sender": m.sender,
                        "from_admin": m.sender == 'admin',
                        "message": m.text,
                        "text": m.text,
                        "created_at": m.created_at.isoformat()
                    } for m in msgs]
                }
            })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return web.json_response({"ok": False, "error": "server_error"}, status=500)

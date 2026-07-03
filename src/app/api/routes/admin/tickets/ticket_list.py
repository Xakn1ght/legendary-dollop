from ..common import *  # noqa: F403


async def handle_admin_tickets(request: web.Request):
    try:
        status_filter = request.query.get('status', 'all')
        
        async with AsyncSessionLocal() as session:
            stmt = select(Ticket).order_by(Ticket.updated_at.desc())
            if status_filter != 'all':
                stmt = stmt.where(Ticket.status == status_filter)
                
            result = await session.execute(stmt)
            tickets = result.scalars().all()
            
            tickets_data = []
            for t in tickets:
                # Get user info
                user = await session.get(User, t.user_id)
                user_name = user.full_name if user else f"User #{t.user_id}"
                user_deleted = user is None
                
                # Get subscription username if linked
                sub_username = None
                if t.subscription_id:
                    sub = await session.get(Subscription, t.subscription_id)
                    if sub:
                        sub_username = sub.marzban_username
                
                # Get last message preview
                last_msg_stmt = select(TicketMessage).where(
                    TicketMessage.ticket_id == t.id
                ).order_by(TicketMessage.created_at.desc()).limit(1)
                last_msg_result = await session.execute(last_msg_stmt)
                last_msg = last_msg_result.scalar_one_or_none()
                
                # Count unread messages (from user, not admin)
                unread_count = await session.scalar(
                    select(func.count(TicketMessage.id)).where(
                        TicketMessage.ticket_id == t.id,
                        TicketMessage.sender == 'user',
                        TicketMessage.read_by_admin == False
                    )
                ) or 0
                
                tickets_data.append({
                    "id": t.id,
                    "user_id": t.user_id,
                    "user_name": user_name,
                    "user_deleted": user_deleted,
                    "subject": t.category or "No subject",
                    "category": t.category,
                    "status": t.status,
                    "priority": t.priority,
                    "subscription_username": sub_username,
                    "last_message": (
                        "\U0001f4f7 Photo" if last_msg is not None and last_msg.content_type == "photo"
                        else last_msg.text[:50] + "..." if last_msg and last_msg.text and len(last_msg.text) > 50
                        else (last_msg.text if last_msg else "No messages yet")
                    ),
                    "unread_count": unread_count,
                    "created_at": t.created_at.isoformat(),
                    "updated_at": t.updated_at.isoformat()
                })
                
            return web.json_response({"ok": True, "tickets": tickets_data})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return web.json_response({"ok": False, "error": "server_error"}, status=500)

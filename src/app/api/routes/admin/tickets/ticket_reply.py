from ..common import *  # noqa: F403
from .notify import notify_user_after_admin_message


async def handle_admin_ticket_reply(request: web.Request):
    try:
        ticket_id = int(request.match_info['ticket_id'])
    except (ValueError, KeyError):
        return web.json_response({"ok": False, "error": "invalid_ticket_id"}, status=400)
    
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"ok": False, "error": "invalid_json"}, status=400)
    
    # Validate input using Pydantic schema
    validated, error = validate_request(AdminTicketReplyRequest, data)
    if error:
        return web.json_response(error, status=400)
    
    message = validated.message
    
    try:
        async with AsyncSessionLocal() as session:
            ticket = await session.get(Ticket, ticket_id)
            if not ticket:
                return web.json_response({"ok": False, "error": "not_found"}, status=404)

            # Enforce ticket state: no replies to closed/archived tickets
            if ticket.status in ('closed', 'archived'):
                return web.json_response({"ok": False, "error": "ticket_closed"}, status=400)
            
            # Add message
            new_msg = TicketMessage(
                ticket_id=ticket_id,
                sender='admin',
                content_type='text',
                text=message,
                # User hasn't read this message yet
                read_by_user=False,
                created_at=datetime.utcnow()
            )
            
            session.add(new_msg)
            
            # Update status if needed
            status_changed = False
            if ticket.status == 'pending':
                ticket.status = 'open'
                status_changed = True
            ticket.updated_at = datetime.utcnow()
            
            await session.commit()

            await notify_user_after_admin_message(
                request,
                session,
                ticket,
                {
                    'sender': 'admin',
                    'text': message,
                    'created_at': new_msg.created_at.isoformat(),
                },
                status_changed,
            )

            return web.json_response({"ok": True})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return web.json_response({"ok": False, "error": "server_error"}, status=500)

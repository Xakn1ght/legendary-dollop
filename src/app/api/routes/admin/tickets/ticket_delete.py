from ..common import *  # noqa: F403


async def handle_admin_ticket_delete(request: web.Request):
    """Permanently delete a ticket"""
    try:
        ticket_id = int(request.match_info['ticket_id'])
    except (ValueError, KeyError):
        return web.json_response({"ok": False, "error": "invalid_ticket_id"}, status=400)
    
    try:
        async with AsyncSessionLocal() as session:
            # Delete ticket messages first (foreign key constraint)
            await session.execute(
                delete(TicketMessage).where(TicketMessage.ticket_id == ticket_id)
            )
            
            # Delete ticket
            await session.execute(
                delete(Ticket).where(Ticket.id == ticket_id)
            )
            
            await session.commit()
            
            return web.json_response({"ok": True})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return web.json_response({"ok": False, "error": "server_error"}, status=500)

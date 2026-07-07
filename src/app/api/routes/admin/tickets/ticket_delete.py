import shutil

from app.api.routes.dashboard_tickets.detail_ops.photo import UPLOAD_ROOT

from ..common import *  # noqa: F403


async def handle_admin_ticket_delete(request: web.Request):
    """Permanently delete a ticket"""
    try:
        ticket_id = int(request.match_info['ticket_id'])
    except (ValueError, KeyError):
        return web.json_response({"ok": False, "error": "invalid_ticket_id"}, status=400)
    
    try:
        async with AsyncSessionLocal() as session:
            # Clear notifications referencing this ticket first — Notification
            # has a ticket_id FK, so a close/reply notification blocked the
            # delete with an IntegrityError 500 (audit fix).
            await session.execute(
                delete(Notification).where(Notification.ticket_id == ticket_id)
            )

            # Delete ticket messages (foreign key constraint)
            await session.execute(
                delete(TicketMessage).where(TicketMessage.ticket_id == ticket_id)
            )

            # Delete ticket
            await session.execute(
                delete(Ticket).where(Ticket.id == ticket_id)
            )

            await session.commit()

        # Remove the ticket's uploaded photos too — leaving them on disk let an
        # admin who kept a URL still fetch attachments of a deleted ticket
        # (orphaned-blob exposure flagged in the support security review).
        try:
            updir = (UPLOAD_ROOT / str(ticket_id)).resolve()
            if updir.parent == UPLOAD_ROOT.resolve() and updir.is_dir():
                shutil.rmtree(updir, ignore_errors=True)
        except Exception:
            pass

        return web.json_response({"ok": True})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return web.json_response({"ok": False, "error": "server_error"}, status=500)

"""Admin side of ticket photo attachments: upload into a ticket + serve any
ticket's photos to an authenticated admin (auth enforced by admin_auth_middleware
on /api/admin). Storage layout shared with the dashboard side."""

import secrets

from app.api.routes.dashboard_tickets.detail_ops.photo import (
    _SAFE_NAME,
    _UPLOAD_SERVE_HEADERS,
    MAX_PHOTO_BYTES,
    UPLOAD_ROOT,
)
from app.utils.image_security import ImageRejected, sanitize_image

from ..common import *  # noqa: F403
from .notify import notify_user_after_admin_message


async def handle_admin_ticket_photo_upload(request: web.Request):
    """POST multipart field 'photo' — admin attaches an image to a ticket."""
    try:
        ticket_id = int(request.match_info["ticket_id"])
    except (ValueError, KeyError):
        return web.json_response({"ok": False, "error": "invalid_ticket_id"}, status=400)

    try:
        reader = await request.multipart()
        field = await reader.next()
        while field is not None and field.name != "photo":
            field = await reader.next()
        if field is None:
            return web.json_response({"ok": False, "error": "no_photo"}, status=400)

        data = bytearray()
        while True:
            chunk = await field.read_chunk(64 * 1024)
            if not chunk:
                break
            data.extend(chunk)
            if len(data) > MAX_PHOTO_BYTES:
                return web.json_response({"ok": False, "error": "photo_too_large"}, status=413)
    except Exception:
        return web.json_response({"ok": False, "error": "invalid_upload"}, status=400)

    try:
        clean, ext, mime = sanitize_image(bytes(data), MAX_PHOTO_BYTES)
    except ImageRejected:
        return web.json_response({"ok": False, "error": "unsupported_image"}, status=400)

    try:
        async with AsyncSessionLocal() as session:
            ticket = await session.get(Ticket, ticket_id)
            if not ticket:
                return web.json_response({"ok": False, "error": "not_found"}, status=404)
            if ticket.status in ("closed", "archived"):
                return web.json_response({"ok": False, "error": "ticket_closed"}, status=400)

            fname = f"{secrets.token_hex(16)}.{ext}"
            dest_dir = UPLOAD_ROOT / str(ticket_id)
            dest_dir.mkdir(parents=True, exist_ok=True)
            (dest_dir / fname).write_bytes(clean)

            new_msg = TicketMessage(
                ticket_id=ticket_id,
                sender="admin",
                content_type="photo",
                text=None,
                file_name=fname,
                file_size=len(clean),
                file_mime_type=mime,
                read_by_user=False,
                created_at=datetime.utcnow(),
            )
            session.add(new_msg)

            status_changed = False
            if ticket.status == "pending":
                ticket.status = "open"
                status_changed = True
            ticket.updated_at = datetime.utcnow()
            await session.commit()

            await notify_user_after_admin_message(
                request,
                session,
                ticket,
                {
                    "sender": "admin",
                    "text": "",
                    "content_type": "photo",
                    "file_name": fname,
                    "created_at": new_msg.created_at.isoformat(),
                },
                status_changed,
            )

            return web.json_response({"ok": True, "file_name": fname, "created_at": new_msg.created_at.isoformat()})
    except Exception:
        import traceback

        traceback.print_exc()
        return web.json_response({"ok": False, "error": "server_error"}, status=500)


async def handle_admin_ticket_photo_get(request: web.Request):
    """Serve a ticket photo to an authenticated admin."""
    try:
        ticket_id = int(request.match_info["ticket_id"])
    except (ValueError, KeyError):
        return web.json_response({"ok": False, "error": "invalid_ticket_id"}, status=400)
    fname = request.match_info.get("file_name", "")
    if not _SAFE_NAME.match(fname):
        return web.json_response({"ok": False, "error": "not_found"}, status=404)

    path = UPLOAD_ROOT / str(ticket_id) / fname
    if not path.is_file():
        return web.json_response({"ok": False, "error": "not_found"}, status=404)
    return web.FileResponse(path, headers=_UPLOAD_SERVE_HEADERS)

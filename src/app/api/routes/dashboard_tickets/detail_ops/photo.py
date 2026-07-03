"""Photo attachments for support tickets (dashboard side).

Files live on disk under ``src/app/data/ticket_uploads/<ticket_id>/`` with a
random hex name; the ``TicketMessage`` row stores it in ``file_name`` with
``content_type='photo'``. Serving goes through the same webapp auth + ticket
ownership check as the detail endpoint — never through static file routes.
"""
import re
import secrets
import traceback
from datetime import datetime
from pathlib import Path

from aiohttp import web
from sqlalchemy.future import select

from app.api.deps import _verify_webapp_auth, set_tma_session_cookie
from app.api.routes.dashboard_tickets.common import broadcast_ticket_update
from app.database.models import AsyncSessionLocal, Ticket, TicketMessage, User

UPLOAD_ROOT = Path(__file__).resolve().parents[4] / "data" / "ticket_uploads"
MAX_PHOTO_BYTES = 8 * 1024 * 1024  # nginx caps the request at 12M
_SAFE_NAME = re.compile(r"^[a-f0-9]{32}\.(jpg|png|webp)\Z")  # \Z: '$' would accept a trailing newline (%0A)

# magic bytes -> extension/mime
def sniff_image(head: bytes):
    if head.startswith(b"\xff\xd8\xff"):
        return "jpg", "image/jpeg"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png", "image/png"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "webp", "image/webp"
    return None, None


async def _load_owned_ticket(session, user_chat_id: int, ticket_id: int):
    user = (await session.execute(select(User).where(User.chat_id == user_chat_id))).scalar_one_or_none()
    if not user:
        return None, None
    ticket = await session.get(Ticket, ticket_id)
    if not ticket or ticket.user_id != user.id:
        return user, None
    return user, ticket


async def handle_dashboard_ticket_photo_upload(request: web.Request):
    """POST multipart field 'photo' — attach an image to an open ticket."""
    try:
        ticket_id = int(request.match_info["ticket_id"])
    except (ValueError, KeyError):
        return web.json_response({"ok": False, "error": "invalid_ticket_id"}, status=400)

    user_chat_id, new_session_token = _verify_webapp_auth(request)
    if not user_chat_id:
        return web.json_response({"ok": False, "error": "unauthorized"}, status=403)

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

    ext, mime = sniff_image(bytes(data[:16]))
    if not ext or len(data) < 100:
        return web.json_response({"ok": False, "error": "unsupported_image"}, status=400)

    try:
        async with AsyncSessionLocal() as session:
            _user, ticket = await _load_owned_ticket(session, user_chat_id, ticket_id)
            if not ticket:
                return web.json_response({"ok": False, "error": "ticket_not_found"}, status=404)
            if ticket.status in ("closed", "archived"):
                return web.json_response({"ok": False, "error": "ticket_closed"}, status=400)

            fname = f"{secrets.token_hex(16)}.{ext}"
            dest_dir = UPLOAD_ROOT / str(ticket_id)
            dest_dir.mkdir(parents=True, exist_ok=True)
            (dest_dir / fname).write_bytes(bytes(data))

            new_msg = TicketMessage(
                ticket_id=ticket_id,
                sender="user",
                content_type="photo",
                text=None,
                file_name=fname,
                file_size=len(data),
                file_mime_type=mime,
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
                        "text": "",
                        "content_type": "photo",
                        "file_name": fname,
                        "created_at": new_msg.created_at.isoformat(),
                    },
                    ticket_user_id=user_chat_id,
                )
            except Exception:
                pass

            resp = web.json_response({"ok": True, "file_name": fname, "created_at": new_msg.created_at.isoformat()})
            if new_session_token:
                set_tma_session_cookie(resp, request, new_session_token, max_age=86400)
            return resp
    except Exception:
        traceback.print_exc()
        return web.json_response({"ok": False, "error": "server_error"}, status=500)


async def handle_dashboard_ticket_photo_get(request: web.Request):
    """Serve a ticket photo to its owner."""
    try:
        ticket_id = int(request.match_info["ticket_id"])
    except (ValueError, KeyError):
        return web.json_response({"ok": False, "error": "invalid_ticket_id"}, status=400)
    fname = request.match_info.get("file_name", "")
    if not _SAFE_NAME.match(fname):
        return web.json_response({"ok": False, "error": "not_found"}, status=404)

    user_chat_id, _ = _verify_webapp_auth(request)
    if not user_chat_id:
        return web.json_response({"ok": False, "error": "unauthorized"}, status=403)

    try:
        async with AsyncSessionLocal() as session:
            _user, ticket = await _load_owned_ticket(session, user_chat_id, ticket_id)
            if not ticket:
                return web.json_response({"ok": False, "error": "not_found"}, status=404)
    except Exception:
        traceback.print_exc()
        return web.json_response({"ok": False, "error": "server_error"}, status=500)

    path = UPLOAD_ROOT / str(ticket_id) / fname
    if not path.is_file():
        return web.json_response({"ok": False, "error": "not_found"}, status=404)
    return web.FileResponse(path, headers={"Cache-Control": "private, max-age=86400"})

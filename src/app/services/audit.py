"""Admin audit trail writer.

Usage from any /api/admin route:

    from app.services.audit import record_audit
    await record_audit(request, "charge.approve", target_type="charge",
                       target_id=charge_id, summary=f"approved {amount:,} toman")

Fire-and-forget: uses its own session and swallows every error — an audit
failure must never break the admin action it describes.
"""
import json

from app.database.models import AdminAuditLog, AsyncSessionLocal
from app.utils.logger import bot_logger


def _session_identity(request) -> tuple[str | None, str | None, str | None]:
    """(admin_chat_id, admin_name, ip) from the middleware-stashed session."""
    chat_id = name = ip = None
    try:
        sess = request.get("admin_session") if hasattr(request, "get") else None
        if isinstance(sess, dict):
            chat_id = str(sess.get("chat_id") or "") or None
            name = str(sess.get("username") or sess.get("name") or "") or None
    except Exception:
        pass
    try:
        from app.utils.admin_ip_whitelist import get_client_ip

        ip = get_client_ip(request)
    except Exception:
        ip = None
    return chat_id, name, ip


async def record_audit(
    request,
    action: str,
    *,
    target_type: str | None = None,
    target_id=None,
    summary: str | None = None,
    detail: dict | None = None,
) -> None:
    try:
        chat_id, name, ip = _session_identity(request)
        async with AsyncSessionLocal() as session:
            session.add(
                AdminAuditLog(
                    admin_chat_id=chat_id,
                    admin_name=name,
                    ip=ip,
                    action=action[:64],
                    target_type=(target_type or None),
                    target_id=str(target_id) if target_id is not None else None,
                    summary=(summary or "")[:300] or None,
                    detail=json.dumps(detail, ensure_ascii=False) if detail else None,
                )
            )
            await session.commit()
    except Exception as e:  # never break the caller
        try:
            bot_logger.warning(f"[AUDIT] write failed for {action}: {e}")
        except Exception:
            pass

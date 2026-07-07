from aiohttp import web
from sqlalchemy import desc, func, or_
from sqlalchemy.future import select

from app.database.models import AdminAuditLog, AsyncSessionLocal


async def handle_admin_audit_list(request: web.Request):
    """GET /api/admin/audit?page=&limit=&action=&q= — newest first."""
    try:
        try:
            page = max(1, int(request.query.get("page", 1)))
            limit = min(200, max(1, int(request.query.get("limit", 50))))
        except (TypeError, ValueError):
            page, limit = 1, 50
        action = (request.query.get("action") or "").strip()
        q = (request.query.get("q") or "").strip()

        async with AsyncSessionLocal() as session:
            stmt = select(AdminAuditLog)
            if action:
                stmt = stmt.filter(AdminAuditLog.action.like(f"{action}%"))
            if q:
                like = f"%{q}%"
                stmt = stmt.filter(or_(
                    AdminAuditLog.summary.ilike(like),
                    AdminAuditLog.target_id.ilike(like),
                    AdminAuditLog.admin_name.ilike(like),
                ))
            total = (await session.execute(
                select(func.count()).select_from(stmt.subquery())
            )).scalar() or 0
            rows = (await session.execute(
                stmt.order_by(desc(AdminAuditLog.id)).offset((page - 1) * limit).limit(limit)
            )).scalars().all()

            return web.json_response({
                "ok": True,
                "total": int(total),
                "page": page,
                "limit": limit,
                "entries": [
                    {
                        "id": r.id,
                        "action": r.action,
                        "target_type": r.target_type,
                        "target_id": r.target_id,
                        "summary": r.summary,
                        "admin_name": r.admin_name,
                        "admin_chat_id": r.admin_chat_id,
                        "ip": r.ip,
                        "created_at": r.created_at.isoformat() if r.created_at else None,
                    }
                    for r in rows
                ],
            })
    except Exception:
        import traceback

        traceback.print_exc()
        return web.json_response({"ok": False, "error": "server_error"}, status=500)

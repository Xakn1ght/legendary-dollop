from aiohttp import web
from sqlalchemy import text

from app.api.routes.admin_db.common import (
    _is_dangerous_sql_enabled,
    _is_sql_runner_enabled,
    _sql_disabled_response,
)
from app.database.models import AsyncSessionLocal
from app.services.audit import record_audit


async def handle_admin_db_exec(request: web.Request):
    if not _is_sql_runner_enabled():
        await record_audit(request, "db.sql_blocked", target_type="endpoint", target_id="db/exec",
                           summary="SQL runner disabled (ADMIN_DB_SQL_ENABLED off)")
        return _sql_disabled_response()

    if not _is_dangerous_sql_enabled():
        return web.json_response({"ok": False, "error": "write_disabled"}, status=403)

    if (request.headers.get("X-Admin-Dangerous") or "").strip().upper() != "YES":
        return web.json_response({"ok": False, "error": "danger_header_required"}, status=400)

    try:
        payload = await request.json()
    except Exception:
        return web.json_response({"ok": False, "error": "invalid_json"}, status=400)

    sql = (payload.get("sql") if isinstance(payload, dict) else "") or ""
    sql = str(sql).strip()
    if not sql or len(sql) > 20_000:
        return web.json_response({"ok": False, "error": "invalid_sql"}, status=400)
    if ";" in sql:
        return web.json_response({"ok": False, "error": "no_semicolons"}, status=400)

    async with AsyncSessionLocal() as session:
        dialect = session.bind.dialect.name if session.bind else "unknown"
        try:
            try:
                if dialect == "postgresql":
                    await session.execute(text("SET LOCAL statement_timeout = 7000"))
            except Exception:
                pass

            result = await session.execute(text(sql))
            await session.commit()
            rowcount = int(getattr(result, "rowcount", -1) or -1)
            return web.json_response({"ok": True, "dialect": dialect, "rowcount": rowcount})
        except Exception as e:
            try:
                await session.rollback()
            except Exception:
                pass
            return web.json_response({"ok": False, "error": "exec_failed", "detail": str(e)[:400]}, status=400)

from aiohttp import web
from sqlalchemy import text

from app.api.routes.admin_db.common import _is_read_only_sql, _json_safe
from app.database.models import AsyncSessionLocal


async def handle_admin_db_query(request: web.Request):
    try:
        payload = await request.json()
    except Exception:
        return web.json_response({"ok": False, "error": "invalid_json"}, status=400)

    sql = (payload.get("sql") if isinstance(payload, dict) else "") or ""
    sql = str(sql)
    if len(sql) > 20_000:
        return web.json_response({"ok": False, "error": "sql_too_large"}, status=400)

    if not _is_read_only_sql(sql):
        return web.json_response({"ok": False, "error": "read_only_only"}, status=400)

    max_rows = 500
    async with AsyncSessionLocal() as session:
        dialect = session.bind.dialect.name if session.bind else "unknown"

        try:
            if dialect == "postgresql":
                await session.execute(text("SET LOCAL statement_timeout = 7000"))
        except Exception:
            pass

        try:
            result = await session.execute(text(sql))
            rows = result.fetchall()
            cols = list(result.keys())
            if len(rows) > max_rows:
                rows = rows[:max_rows]
            data = [[_json_safe(v) for v in r] for r in rows]
            return web.json_response(
                {"ok": True, "dialect": dialect, "columns": cols, "rows": data, "truncated": len(data) >= max_rows}
            )
        except Exception as e:
            return web.json_response({"ok": False, "error": "query_failed", "detail": str(e)[:400]}, status=400)

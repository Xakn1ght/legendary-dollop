from aiohttp import web
from sqlalchemy import text

from app.api.routes.admin_db.common import _validate_table_name
from app.database.models import AsyncSessionLocal


async def handle_admin_db_table_rows(request: web.Request):
    table_raw = request.match_info.get("table", "")
    try:
        table, schema = _validate_table_name(table_raw)
    except ValueError as e:
        return web.json_response({"ok": False, "error": str(e)}, status=400)

    try:
        limit = int(request.query.get("limit") or "200")
        offset = int(request.query.get("offset") or "0")
    except ValueError:
        return web.json_response({"ok": False, "error": "invalid_pagination"}, status=400)

    limit = max(1, min(limit, 200))
    offset = max(0, offset)

    async with AsyncSessionLocal() as session:
        dialect = session.bind.dialect.name if session.bind else "unknown"
        qualified = f"{schema}.{table}" if schema else table

        try:
            if dialect == "postgresql":
                await session.execute(text("SET LOCAL statement_timeout = 5000"))
        except Exception:
            pass

        stmt = text(f"SELECT * FROM {qualified} LIMIT :limit OFFSET :offset")
        result = await session.execute(stmt, {"limit": limit, "offset": offset})
        rows = result.fetchall()
        cols = list(result.keys())
        data = [list(r) for r in rows]
        return web.json_response(
            {"ok": True, "dialect": dialect, "columns": cols, "rows": data, "limit": limit, "offset": offset}
        )

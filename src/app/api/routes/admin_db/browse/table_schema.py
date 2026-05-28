from aiohttp import web
from sqlalchemy import text

from app.api.routes.admin_db.common import _validate_table_name
from app.database.models import AsyncSessionLocal


async def handle_admin_db_table_schema(request: web.Request):
    table_raw = request.match_info.get("table", "")
    try:
        table, schema = _validate_table_name(table_raw)
    except ValueError as e:
        return web.json_response({"ok": False, "error": str(e)}, status=400)

    async with AsyncSessionLocal() as session:
        dialect = session.bind.dialect.name if session.bind else "unknown"
        cols: list[dict] = []

        if dialect == "postgresql":
            stmt = text(
                """
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_schema = :schema
                  AND table_name = :table
                ORDER BY ordinal_position
                """
            )
            schema_name = schema or "public"
            rows = (await session.execute(stmt, {"schema": schema_name, "table": table})).fetchall()
            cols = [{"name": r[0], "type": r[1], "nullable": (r[2] == "YES")} for r in rows]
        else:
            rows = (await session.execute(text(f"PRAGMA table_info({table})"))).fetchall()
            cols = [{"name": r[1], "type": r[2], "nullable": (r[3] == 0), "pk": bool(r[5])} for r in rows]

        return web.json_response({"ok": True, "dialect": dialect, "table": table_raw, "columns": cols})

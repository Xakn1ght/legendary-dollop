from aiohttp import web
from sqlalchemy import text

from app.database.models import AsyncSessionLocal


async def handle_admin_db_tables(request: web.Request):
    q = (request.query.get("q") or "").strip().lower()
    limit = 300
    async with AsyncSessionLocal() as session:
        dialect = session.bind.dialect.name if session.bind else "unknown"
        tables: list[str] = []

        if dialect == "postgresql":
            stmt = text(
                """
                SELECT table_schema, table_name
                FROM information_schema.tables
                WHERE table_type='BASE TABLE'
                  AND table_schema NOT IN ('pg_catalog','information_schema')
                ORDER BY table_schema, table_name
                LIMIT :limit
                """
            )
            rows = (await session.execute(stmt, {"limit": limit})).fetchall()
            for schema, table in rows:
                full = f"{schema}.{table}" if schema else str(table)
                if q and q not in full.lower():
                    continue
                tables.append(full)
        else:
            stmt = text(
                """
                SELECT name
                FROM sqlite_master
                WHERE type='table'
                  AND name NOT LIKE 'sqlite_%'
                ORDER BY name
                LIMIT :limit
                """
            )
            rows = (await session.execute(stmt, {"limit": limit})).fetchall()
            for (name,) in rows:
                full = str(name)
                if q and q not in full.lower():
                    continue
                tables.append(full)

        return web.json_response({"ok": True, "dialect": dialect, "tables": tables})

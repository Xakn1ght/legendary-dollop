from aiohttp import web

from app.api.routes.admin_db.common import _is_dangerous_sql_enabled


async def handle_admin_db_capabilities(request: web.Request):
    return web.json_response(
        {
            "ok": True,
            "capabilities": {
                "allow_write": _is_dangerous_sql_enabled(),
                "max_rows_table": 200,
                "max_rows_query": 500,
            },
        }
    )

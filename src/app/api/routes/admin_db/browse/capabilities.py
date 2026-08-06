from aiohttp import web

from app.api.routes.admin_db.common import _is_dangerous_sql_enabled, _is_sql_runner_enabled


async def handle_admin_db_capabilities(request: web.Request):
    allow_sql = _is_sql_runner_enabled()
    return web.json_response(
        {
            "ok": True,
            "capabilities": {
                # Free-text SQL runner (query + exec). Off by default; the UI
                # hides the whole SQL section when false.
                "allow_sql": allow_sql,
                # Writes need the runner on AND the separate dangerous-SQL flag.
                "allow_write": allow_sql and _is_dangerous_sql_enabled(),
                "max_rows_table": 200,
                "max_rows_query": 500,
            },
        }
    )

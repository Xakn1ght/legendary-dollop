import time

from aiohttp import web
from sqlalchemy import text

from app.database.models import AsyncSessionLocal


async def _timed(coro):
    t0 = time.monotonic()
    try:
        await coro
        return True, int((time.monotonic() - t0) * 1000), None
    except Exception as e:
        return False, int((time.monotonic() - t0) * 1000), str(e)[:120]


async def handle_admin_system_health(request: web.Request):
    """GET /api/admin/system-health — DB / Redis / Marzban reachability plus the
    last run of every scheduled job and the SMS auto-approve arm state."""
    try:
        out: dict = {"ok": True}

        async def db_ping():
            async with AsyncSessionLocal() as session:
                await session.execute(text("SELECT 1"))

        ok, ms, err = await _timed(db_ping())
        out["db"] = {"ok": ok, "latency_ms": ms, "error": err}

        try:
            from app.core.redis_config import redis_client

            if redis_client is not None:
                ok, ms, err = await _timed(redis_client.ping())
                out["redis"] = {"ok": ok, "latency_ms": ms, "error": err}
            else:
                out["redis"] = {"ok": False, "latency_ms": 0, "error": "not_initialised"}
        except Exception as e:
            out["redis"] = {"ok": False, "latency_ms": 0, "error": str(e)[:120]}

        try:
            from app.services.marzban import marzban_api

            t0 = time.monotonic()
            stats = await marzban_api.get_system_stats()
            ms = int((time.monotonic() - t0) * 1000)
            if stats:
                out["marzban"] = {
                    "ok": True, "latency_ms": ms,
                    "version": stats.get("version"),
                    "total_users": stats.get("total_user"),
                    "users_active": stats.get("users_active"),
                    "incoming_bandwidth": stats.get("incoming_bandwidth"),
                    "outgoing_bandwidth": stats.get("outgoing_bandwidth"),
                }
            else:
                out["marzban"] = {"ok": False, "latency_ms": ms, "error": "no_response"}
        except Exception as e:
            out["marzban"] = {"ok": False, "latency_ms": 0, "error": str(e)[:120]}

        try:
            from app.core.settings import JOB_SCHEDULES
            from app.services.job_status import get_job_statuses

            runs = get_job_statuses()
            jobs = []
            for name in JOB_SCHEDULES:
                r = runs.get(name) or {}
                jobs.append({
                    "name": name,
                    "last_run_at": r.get("last_run_at"),
                    "ok": r.get("ok"),
                    "duration_ms": r.get("duration_ms"),
                })
            out["jobs"] = jobs
        except Exception:
            out["jobs"] = []

        try:
            from app.services.sms_ingest import sms_enabled

            out["sms_auto_approve"] = {"enabled": bool(sms_enabled())}
        except Exception:
            out["sms_auto_approve"] = {"enabled": False}

        return web.json_response(out)
    except Exception:
        import traceback

        traceback.print_exc()
        return web.json_response({"ok": False, "error": "server_error"}, status=500)

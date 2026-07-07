from aiohttp import web

from app.services.marzban import marzban_api

_OK_STATUSES = {"connected", "healthy"}


async def handle_admin_nodes(request: web.Request):
    """GET /api/admin/nodes — Marzban nodes with status + per-node user spread."""
    try:
        nodes = await marzban_api.get_nodes()
        if not isinstance(nodes, list):
            nodes = []
        # Live per-node cpu/mem/bandwidth (PasarGuard; keyed by node id as str).
        realtime = await marzban_api.get_nodes_realtime_stats()

        out = []
        for n in nodes:
            status = str(n.get("status") or "unknown").lower()
            rt = realtime.get(str(n.get("id"))) or {}
            out.append({
                "id": n.get("id"),
                "name": n.get("name"),
                "address": n.get("address"),
                "port": n.get("port"),
                "status": status,
                "up": status in _OK_STATUSES,
                "xray_version": n.get("xray_version"),
                "usage_coefficient": n.get("usage_coefficient"),
                "message": n.get("message"),
                "cpu_usage": rt.get("cpu_usage"),
                "mem_used": rt.get("mem_used"),
                "mem_total": rt.get("mem_total"),
                "down_speed": rt.get("incoming_bandwidth_speed"),
                "up_speed": rt.get("outgoing_bandwidth_speed"),
                "uptime": rt.get("uptime"),
            })

        system = None
        try:
            stats = await marzban_api.get_system_stats()
            if stats:
                system = {
                    "version": stats.get("version"),
                    "total_user": stats.get("total_user"),
                    "users_active": stats.get("users_active"),
                    "incoming_bandwidth": stats.get("incoming_bandwidth"),
                    "outgoing_bandwidth": stats.get("outgoing_bandwidth"),
                    "incoming_bandwidth_speed": stats.get("incoming_bandwidth_speed"),
                    "outgoing_bandwidth_speed": stats.get("outgoing_bandwidth_speed"),
                }
        except Exception:
            system = None

        return web.json_response({"ok": True, "nodes": out, "system": system})
    except Exception:
        import traceback

        traceback.print_exc()
        return web.json_response({"ok": False, "error": "server_error"}, status=500)

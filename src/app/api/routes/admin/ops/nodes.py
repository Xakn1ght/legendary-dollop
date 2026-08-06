from aiohttp import web

from app.services.audit import record_audit
from app.services.node_seen import stamp_and_get
from app.services.pasarguard import pasarguard_api

_OK_STATUSES = {"connected", "healthy"}


async def handle_admin_nodes(request: web.Request):
    """GET /api/admin/nodes — PasarGuard nodes with status + live stats.

    2026-07-21 enrichment: per-node core/node versions, lifetime up/down
    totals (top-level on the 5.1.0 node object), and a locally-tracked
    last-seen stamp so disconnected/disabled nodes show more than an IP.
    """
    try:
        nodes = await pasarguard_api.get_nodes()
        if not isinstance(nodes, list):
            nodes = []
        # Live per-node cpu/mem/bandwidth (PasarGuard; keyed by node id as str).
        realtime = await pasarguard_api.get_nodes_realtime_stats()
        last_seen = stamp_and_get(nodes)

        out = []
        for n in nodes:
            status = str(n.get("status") or "unknown").lower()
            rt = realtime.get(str(n.get("id"))) or {}
            seen = last_seen.get(str(n.get("id"))) or {}
            out.append({
                "id": n.get("id"),
                "name": n.get("name"),
                "address": n.get("address"),
                "port": n.get("port"),
                "status": status,
                "up": status in _OK_STATUSES,
                "xray_version": n.get("xray_version"),
                "core_version": n.get("core_version"),
                "node_version": n.get("node_version"),
                "usage_coefficient": n.get("usage_coefficient"),
                "message": n.get("message"),
                "cpu_usage": rt.get("cpu_usage"),
                "mem_used": rt.get("mem_used"),
                "mem_total": rt.get("mem_total"),
                "down_speed": rt.get("incoming_bandwidth_speed"),
                "up_speed": rt.get("outgoing_bandwidth_speed"),
                "uptime": rt.get("uptime"),
                "lifetime_uplink": n.get("lifetime_uplink"),
                "lifetime_downlink": n.get("lifetime_downlink"),
                # epoch seconds of the last time WE observed it connected;
                # null = never seen up since this tracker deployed
                "last_seen": seen.get("ts"),
            })

        system = None
        try:
            stats = await pasarguard_api.get_system_stats()
            if stats:
                # NOTE: the classic *_bandwidth_speed keys are gone from the
                # 5.1.0 SystemStats schema (were always None here) — dropped.
                system = {
                    "version": stats.get("version"),
                    "total_user": stats.get("total_user"),
                    "users_active": stats.get("users_active"),
                    "online_users": stats.get("online_users"),
                    "incoming_bandwidth": stats.get("incoming_bandwidth"),
                    "outgoing_bandwidth": stats.get("outgoing_bandwidth"),
                }
        except Exception:
            system = None

        return web.json_response({"ok": True, "nodes": out, "system": system})
    except Exception:
        import traceback

        traceback.print_exc()
        return web.json_response({"ok": False, "error": "server_error"}, status=500)


async def handle_admin_node_reconnect(request: web.Request):
    """POST /api/admin/nodes/{node_id}/reconnect — panel-side node reconnect.

    The panel answers 200 {} even for nonexistent ids (probed live 2026-07-21),
    so the id is validated against the node list first; unknown ids 404 here
    instead of silently "succeeding". Audited as node.reconnect.
    """
    try:
        node_id = int(request.match_info.get("node_id", ""))
    except (TypeError, ValueError):
        return web.json_response({"ok": False, "error": "invalid_node_id"}, status=400)

    try:
        nodes = await pasarguard_api.get_nodes()
        node = next((n for n in nodes if isinstance(n, dict) and n.get("id") == node_id), None)
        if node is None:
            return web.json_response({"ok": False, "error": "node_not_found"}, status=404)

        name = str(node.get("name") or f"node-{node_id}")
        ok = await pasarguard_api.reconnect_node(node_id)
        if not ok:
            return web.json_response({"ok": False, "error": "panel_reconnect_failed"}, status=502)

        await record_audit(
            request, "node.reconnect", target_type="node", target_id=node_id,
            summary=f"reconnect requested for node {name}",
            detail={"status_before": str(node.get("status") or "unknown")},
        )
        return web.json_response({"ok": True, "id": node_id, "name": name})
    except Exception:
        import traceback

        traceback.print_exc()
        return web.json_response({"ok": False, "error": "server_error"}, status=500)

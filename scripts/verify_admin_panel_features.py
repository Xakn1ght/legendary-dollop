"""Post-deploy verification for the three new admin features.

1. Route registration: the three new paths exist in the aiohttp route table.
2. Devices handler: real panel round-trip (read-only GETs) via mocked request.
3. Online-series handler: real panel round-trip + cache write (read-only).
4. Reconnect handler: nonexistent-id guard (404 BEFORE any panel reconnect
   call) and invalid-id 400. NEVER invoked with a real node id here.

Never prints secrets or full usernames.
"""
import asyncio
import json
import sys

from aiohttp import web
from aiohttp.test_utils import make_mocked_request


def mask(s, keep=3):
    s = str(s or "")
    return (s[:keep] + "***") if len(s) > keep else "***"


async def main():
    from app.api.route_registry.admin_api.register import register_admin_api_routes
    from app.api.routes.admin import (
        handle_admin_analytics_online,
        handle_admin_node_reconnect,
        handle_admin_nodes,
        handle_admin_subscription_devices,
    )
    from app.services.pasarguard import pasarguard_api

    # 1) route table
    app = web.Application()
    register_admin_api_routes(app)
    routes = {(r.method, r.resource.canonical) for r in app.router.routes() if r.resource}
    for m, p in [
        ("GET", "/api/admin/subscriptions/{username}/devices"),
        ("POST", "/api/admin/nodes/{node_id}/reconnect"),
        ("GET", "/api/admin/analytics/online"),
    ]:
        assert (m, p) in routes, f"route missing: {m} {p}"
    print("route table: all 3 new routes registered")

    # helper: run a handler with a mocked (already-authed-in-real-life) request
    async def call(handler, method, path, match_info=None, query_string=""):
        req = make_mocked_request(method, path + ("?" + query_string if query_string else ""))
        if match_info:
            req._match_info = match_info  # aiohttp test util: inject match_info
        resp = await handler(req)
        return resp.status, json.loads(resp.body.decode())

    # 2) devices — pick a real username from the panel list (read-only)
    data = await pasarguard_api.get_all_users(offset=0, limit=1)
    uname = (data.get("users") or [{}])[0].get("username") or ""
    assert uname, "no panel user available for the probe"
    st, body = await call(handle_admin_subscription_devices, "GET",
                          f"/api/admin/subscriptions/{uname}/devices", {"username": uname})
    print(f"devices handler ({mask(uname)}): status={st} ok={body.get('ok')} "
          f"devices_available={body.get('devices_available')} device_count={body.get('device_count')} "
          f"fetches={len(body.get('recent_fetches') or [])}")
    assert st == 200 and body.get("ok") is True
    # unknown user -> 404
    st2, body2 = await call(handle_admin_subscription_devices, "GET",
                            "/api/admin/subscriptions/zz_no_such_user_zz/devices",
                            {"username": "zz_no_such_user_zz"})
    print(f"devices handler (unknown user): status={st2} error={body2.get('error')}")
    assert st2 == 404

    # 3) nodes list enrichment fields present
    st3, body3 = await call(handle_admin_nodes, "GET", "/api/admin/nodes")
    assert st3 == 200 and body3.get("ok")
    n0 = (body3.get("nodes") or [{}])[0]
    need = {"core_version", "node_version", "lifetime_uplink", "lifetime_downlink", "last_seen"}
    assert need.issubset(n0.keys()), f"missing enrichment keys: {need - set(n0.keys())}"
    ups = [n for n in body3["nodes"] if n.get("up")]
    downs = [n for n in body3["nodes"] if not n.get("up")]
    print(f"nodes handler: {len(body3['nodes'])} nodes; sample up node versions="
          f"{(ups[0].get('xray_version'), ups[0].get('node_version')) if ups else None} "
          f"lifetime_down={ups[0].get('lifetime_downlink') if ups else None}; "
          f"down-node last_seen={'set' if downs and downs[0].get('last_seen') else ('n/a' if not downs else None)}")
    print(f"system block: online_users={body3.get('system', {}).get('online_users')}")

    # 4) online series (panel call ~13s cold; cached after)
    st4, body4 = await call(handle_admin_analytics_online, "GET",
                            "/api/admin/analytics/online", query_string="hours=24")
    assert st4 == 200 and body4.get("ok"), f"online series failed: {st4} {body4}"
    print(f"online handler: points={len(body4.get('series') or [])} peak={body4.get('peak')} "
          f"unique={body4.get('unique_in_window')} cached={body4.get('cached')}")
    st5, body5 = await call(handle_admin_analytics_online, "GET",
                            "/api/admin/analytics/online", query_string="hours=24")
    print(f"online handler (2nd call): cached={body5.get('cached')}")
    assert body5.get("cached") is True, "Redis cache did not engage"

    # 5) reconnect guards only — NEVER a real node id
    st6, body6 = await call(handle_admin_node_reconnect, "POST",
                            "/api/admin/nodes/9999999/reconnect", {"node_id": "9999999"})
    print(f"reconnect handler (nonexistent id): status={st6} error={body6.get('error')}")
    assert st6 == 404 and body6.get("error") == "node_not_found"
    st7, body7 = await call(handle_admin_node_reconnect, "POST",
                            "/api/admin/nodes/abc/reconnect", {"node_id": "abc"})
    print(f"reconnect handler (invalid id): status={st7} error={body7.get('error')}")
    assert st7 == 400

    await pasarguard_api.close()
    print("ALL VERIFICATIONS PASSED")


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

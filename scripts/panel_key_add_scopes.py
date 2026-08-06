"""One-time: add hwids.read + nodes.reconnect to the astrobyte-app panel API key.

Context (2026-07-21): the key was created scoped to exactly what the integration
called at the time (users CRUD, templates read, nodes read+stats, system read).
The HWID device viewer needs hwids.read; the Servers-page Reconnect action needs
nodes.reconnect. This PATCHes ONLY those two flags via the owner-admin bearer
account, then re-verifies every pre-existing scope through the API key itself.

Never prints tokens, keys, or passwords. The only mutation is the key PATCH;
the reconnect scope check uses a nonexistent node id so no live node is touched.

Run:  set -a; . config/.env; set +a; PYTHONPATH=src .venv/bin/python scripts/panel_key_add_scopes.py
"""
import asyncio
import copy
import json
import os
import sys

import aiohttp

BASE = os.environ["PASARGUARD_BASE_URL"].rstrip("/")
USER = os.environ["PASARGUARD_USERNAME"]
PASS = os.environ["PASARGUARD_PASSWORD"]
KEY = os.environ["PASARGUARD_API_KEY"]


async def main():
    to = aiohttp.ClientTimeout(total=30)
    async with aiohttp.ClientSession(timeout=to) as s:
        # 1) bearer login (owner admin)
        async with s.post(f"{BASE}/api/admin/token", data={"username": USER, "password": PASS}) as r:
            assert r.status == 200, f"login failed: {r.status}"
            bearer = {"Authorization": f"Bearer {(await r.json())['access_token']}"}
        print("bearer login: 200")

        # 2) find our key
        async with s.get(f"{BASE}/api/api_keys", headers=bearer) as r:
            assert r.status == 200, f"list keys: {r.status}"
            keys = (await r.json()).get("api_keys") or []
        ours = [k for k in keys if k.get("name") == "astrobyte-app" and not k.get("revoked_at")]
        assert len(ours) == 1, f"expected exactly one active astrobyte-app key, got {len(ours)}"
        kid = ours[0]["id"]
        print(f"key found: id={kid} status={ours[0].get('status')}")

        # 3) read current permissions and patch ONLY the two new flags
        async with s.get(f"{BASE}/api/api_key/{kid}", headers=bearer) as r:
            assert r.status == 200, f"get key: {r.status}"
            cur = await r.json()
        perms = copy.deepcopy(cur.get("permissions") or {})
        print("current scopes:", json.dumps({
            "users": bool(perms.get("users")), "templates": bool(perms.get("templates")),
            "nodes": (perms.get("nodes") or {}), "system": (perms.get("system") or {}),
            "hwids": (perms.get("hwids") or None),
        }))
        hw = dict(perms.get("hwids") or {})
        hw["read"] = True
        hw.setdefault("delete", False)
        perms["hwids"] = hw
        nd = dict(perms.get("nodes") or {})
        nd["reconnect"] = True
        perms["nodes"] = nd

        async with s.patch(f"{BASE}/api/api_key/{kid}", headers=bearer, json={"permissions": perms}) as r:
            body = await r.text()
            print("PATCH permissions:", r.status)
            assert r.status == 200, f"patch failed: {r.status} {body[:200]}"
            new = json.loads(body)
        got = new.get("permissions") or {}
        print("post-patch hwids:", got.get("hwids"), "| nodes.reconnect:", (got.get("nodes") or {}).get("reconnect"))

        # 4) verify THROUGH the API key: old scopes intact + new ones live
        kh = {"X-Api-Key": KEY}
        checks = [
            ("GET", "/api/system", None),
            ("GET", "/api/nodes", None),
            ("GET", "/api/users", {"limit": 1}),
            ("GET", "/api/user_templates", None),
        ]
        for m, p, q in checks:
            async with s.request(m, f"{BASE}{p}", headers=kh, params=q) as r:
                print(f"key {m} {p} ->", r.status)
                assert r.status == 200, f"scope regression on {p}: {r.status}"

        # hwids.read now live (find a real user id first)
        async with s.get(f"{BASE}/api/users", headers=kh, params={"limit": 1}) as r:
            uid = ((await r.json()).get("users") or [{}])[0].get("id")
        async with s.get(f"{BASE}/api/user/{uid}/hwids", headers=kh) as r:
            body = await r.text()
            print("key GET /api/user/{id}/hwids ->", r.status,
                  ("count=" + str(json.loads(body).get("count"))) if r.status == 200 else body[:120])
            assert r.status == 200

        # nodes.reconnect scope check WITHOUT touching a live node: nonexistent id.
        # 403 = scope missing; 404/422 = scope OK, node lookup failed (harmless).
        async with s.post(f"{BASE}/api/node/9999999/reconnect", headers=kh) as r:
            body = await r.text()
            print("key POST /api/node/9999999/reconnect ->", r.status, body[:120])
            assert r.status != 403, "reconnect scope still denied"

        print("ALL OK")


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

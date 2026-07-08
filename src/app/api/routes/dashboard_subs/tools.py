import re
import secrets

from aiohttp import ClientSession, ClientTimeout, web

from app.api.deps import _verify_webapp_auth

from .common import *  # noqa: F403
from .geo_client import (
    _skip_geo_lookup,
    client_ip_from_request,
    lookup_client_geo,
    lookup_client_geo_for_ip,
)

# Speed-test payload: random bytes so no proxy/CDN layer can transparently
# compress it (zeros compress ~1000:1 and would fake gigabit readings).
# Generated once, lazily, and sliced per request.
_SPEED_BLOB_MAX = 8 * 1024 * 1024
_speed_blob_cache: bytes | None = None


def _speed_blob() -> bytes:
    global _speed_blob_cache
    if _speed_blob_cache is None:
        _speed_blob_cache = secrets.token_bytes(_SPEED_BLOB_MAX)
    return _speed_blob_cache


async def handle_dashboard_ping(request: web.Request):
    return web.json_response({"ok": True}, headers={"Cache-Control": "no-store"})


async def handle_dashboard_speed_dl(request: web.Request):
    # Auth-gated: up to 8MB per hit is too expensive to serve anonymously.
    user_chat_id, _ = _verify_webapp_auth(request)
    if not user_chat_id:
        return web.json_response({"ok": False, "error": "unauthorized"}, status=403)
    try:
        size = int(request.query.get('bytes', '2000000'))
    except Exception:
        size = 2000000
    size = max(10000, min(size, _SPEED_BLOB_MAX))  # 10KB .. 8MB
    return web.Response(
        body=_speed_blob()[:size],
        content_type='application/octet-stream',
        headers={"Cache-Control": "no-store"},
    )


async def handle_dashboard_speed_ul(request: web.Request):
    user_chat_id, _ = _verify_webapp_auth(request)
    if not user_chat_id:
        return web.json_response({"ok": False, "error": "unauthorized"}, status=403)
    try:
        _ = await request.read()  # discard
    except Exception:
        pass
    return web.json_response({"ok": True}, headers={"Cache-Control": "no-store"})


async def handle_dashboard_detect_country(request: web.Request):
    ip = client_ip_from_request(request)
    if not ip or _skip_geo_lookup(ip):
        qip = lookup_client_geo_for_ip((request.query.get("ip") or "").strip())
        if qip:
            ip = qip
    empty = {
        "ok": True,
        "ip": ip,
        "country": None,
        "country_code": None,
        "label": None,
    }
    if not ip:
        return web.json_response(empty)

    geo = await lookup_client_geo(ip)
    if not geo:
        return web.json_response({**empty, "ip": ip})

    return web.json_response(
        {
            "ok": True,
            "ip": ip,
            "country": geo.get("country") or geo.get("label"),
            "country_code": geo.get("country_code"),
            "label": geo.get("label"),
        }
    )


async def handle_dashboard_flag(request: web.Request):
    code = (request.match_info.get("code") or "").strip().lower()
    if not re.fullmatch(r"[a-z]{2}", code):
        raise web.HTTPNotFound()
    url = f"https://flagcdn.com/w40/{code}.png"
    try:
        async with ClientSession() as session:
            async with session.get(url, timeout=ClientTimeout(total=8)) as resp:
                if resp.status != 200:
                    raise web.HTTPNotFound()
                body = await resp.read()
                if len(body) > 500_000:
                    raise web.HTTPNotFound()
                return web.Response(
                    body=body,
                    content_type=resp.headers.get("Content-Type") or "image/png",
                    headers={"Cache-Control": "public, max-age=86400"},
                )
    except web.HTTPNotFound:
        raise
    except Exception:
        raise web.HTTPNotFound()

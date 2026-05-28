import re

from aiohttp import ClientSession, ClientTimeout

from .common import *  # noqa: F403
from .geo_client import (
    _skip_geo_lookup,
    client_ip_from_request,
    lookup_client_geo,
    lookup_client_geo_for_ip,
)


async def handle_dashboard_ping(request: web.Request):
    return web.json_response({"ok": True})


async def handle_dashboard_speed_dl(request: web.Request):
    try:
        size = int(request.query.get('bytes', '200000'))
    except Exception:
        size = 200000
    size = max(10000, min(size, 800000))  # 10KB .. 800KB
    data = b"0" * size
    return web.Response(body=data, content_type='application/octet-stream')


async def handle_dashboard_speed_ul(request: web.Request):
    try:
        _ = await request.read()  # discard
    except Exception:
        pass
    return web.json_response({"ok": True})


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

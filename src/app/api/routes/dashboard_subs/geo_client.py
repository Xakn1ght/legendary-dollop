"""Resolve client IP and country label for dashboard (server-side only)."""

from __future__ import annotations

import ipaddress
from urllib.parse import quote

from aiohttp import ClientSession, ClientTimeout, web

_LOCAL_IPS = frozenset({"127.0.0.1", "::1", "localhost"})


def client_ip_from_request(request: web.Request) -> str | None:
    h = request.headers
    for raw in (
        h.get("CF-Connecting-IP"),
        h.get("True-Client-IP"),
        h.get("X-Real-IP"),
    ):
        v = (raw or "").strip()
        if v:
            return v.split(",")[0].strip()

    forwarded = (h.get("X-Forwarded-For") or "").strip()
    if forwarded:
        return forwarded.split(",")[0].strip()

    remote = (request.remote or "").strip()
    return remote or None


def _skip_geo_lookup(ip: str | None) -> bool:
    s = (ip or "").strip().lower()
    return not s or s in _LOCAL_IPS


def lookup_client_geo_for_ip(raw: str) -> str | None:
    s = (raw or "").strip().split("%")[0].strip()
    if not s or s.lower() in _LOCAL_IPS:
        return None
    try:
        addr = ipaddress.ip_address(s)
        if addr.is_private or addr.is_loopback or addr.is_reserved or addr.is_link_local:
            return None
    except ValueError:
        return None
    return s


def _norm_geo_label(city: str | None, region: str | None, country: str | None) -> str | None:
    ctry = (country or "").strip()
    city = (city or "").strip()
    region = (region or "").strip()
    if city and ctry and city.lower() != ctry.lower():
        return f"{city}, {ctry}"
    if region and ctry and region.lower() != ctry.lower() and not city:
        return f"{region}, {ctry}"
    if ctry:
        return ctry
    if city:
        return city
    if region:
        return region
    return None


def _geo_result(country: str | None, code: str | None, city: str | None, region: str | None) -> dict | None:
    country = (country or "").strip() or None
    code = (code or "").strip() or None
    city = (city or "").strip() or None
    region = (region or "").strip() or None
    label = _norm_geo_label(city, region, country)
    if not label:
        return None
    return {"country": country, "country_code": code, "label": label}


async def _lookup_ipapi_co(client_ip: str) -> dict | None:
    q = quote(client_ip.strip("[]"), safe=":.")
    url = f"https://ipapi.co/{q}/json/"
    try:
        async with ClientSession() as session:
            async with session.get(url, timeout=ClientTimeout(total=5)) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()
                if data.get("error"):
                    return None
                return _geo_result(
                    data.get("country_name") or data.get("country"),
                    data.get("country_code"),
                    data.get("city"),
                    data.get("region"),
                )
    except Exception:
        return None


async def _lookup_ip_api(client_ip: str) -> dict | None:
    q = quote(client_ip.strip("[]"), safe=":.")
    url = (
        f"http://ip-api.com/json/{q}"
        "?fields=status,message,country,countryCode,city,regionName"
    )
    try:
        async with ClientSession() as session:
            async with session.get(url, timeout=ClientTimeout(total=5)) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()
                if data.get("status") != "success":
                    return None
                return _geo_result(
                    data.get("country"),
                    data.get("countryCode"),
                    data.get("city"),
                    data.get("regionName"),
                )
    except Exception:
        return None


async def lookup_client_geo(client_ip: str) -> dict | None:
    if _skip_geo_lookup(client_ip):
        return None
    for lookup in (_lookup_ip_api, _lookup_ipapi_co):
        geo = await lookup(client_ip)
        if geo:
            return geo
    return None


async def geo_for_request(request: web.Request) -> dict | None:
    ip = client_ip_from_request(request)
    if not ip or _skip_geo_lookup(ip):
        return None
    geo = await lookup_client_geo(ip)
    if not geo:
        return None
    return {"ip": ip, **geo}

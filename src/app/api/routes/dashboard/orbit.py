"""Add-to-Orbit: mint a single-use add link for the user's subscription.

The Orbit app (owner's v2rayNG build) claims tokens from the loopback-only
mint service in /opt/orbit-add/ (public /internal/mint is 404 by design —
only this server-to-server call with the shared secret can mint). The secret
stays in /opt/orbit-add/orbit-add.env; we read it at first use, never log it,
and never accept a sub URL from the client.
"""

import logging
import os
import re
from pathlib import Path

import aiohttp
from aiohttp import web

from app.api.deps import _verify_webapp_auth, set_tma_session_cookie
from app.database import crud
from app.database.models import AsyncSessionLocal, Subscription
from app.services.marzban import marzban_api

logger = logging.getLogger(__name__)

ORBIT_ENV_FILE = os.environ.get("ORBIT_ADD_ENV_FILE", "/opt/orbit-add/orbit-add.env")
ORBIT_MINT_URL = os.environ.get("ORBIT_MINT_URL", "http://127.0.0.1:8092/internal/mint")

_secret_cache: str | None = None


def _mint_secret() -> str:
    """ORBIT_MINT_SECRET from the orbit-add env file (cached)."""
    global _secret_cache
    if _secret_cache is not None:
        return _secret_cache
    secret = ""
    try:
        for line in Path(ORBIT_ENV_FILE).read_text(encoding="utf-8").splitlines():
            if line.startswith("ORBIT_MINT_SECRET="):
                secret = line.split("=", 1)[1].strip().strip('"').strip("'")
                break
    except OSError as e:
        logger.warning("orbit-add env file unreadable: %s", e)
    _secret_cache = secret
    return secret


async def handle_dashboard_orbit_add_link(request: web.Request):
    """POST {subscription_id?} → {ok, add_url} for the user's own subscription."""
    user_chat_id, new_session_token = _verify_webapp_auth(request)
    if not user_chat_id:
        return web.json_response({"ok": False, "error": "unauthorized"}, status=403)

    secret = _mint_secret()
    if not secret:
        return web.json_response({"ok": False, "error": "orbit_unavailable"}, status=503)

    try:
        body = await request.json()
    except Exception:
        body = {}
    want_sub_id = body.get("subscription_id")

    async with AsyncSessionLocal() as session:
        user = await crud.get_user(session, user_chat_id)
        if not user:
            return web.json_response({"ok": False, "error": "not_registered"}, status=403)

        sub = None
        if want_sub_id is not None:
            try:
                sub = await session.get(Subscription, int(want_sub_id))
            except (TypeError, ValueError):
                sub = None
            if not sub or sub.user_id != user.id:
                return web.json_response({"ok": False, "error": "not_found"}, status=404)
        else:
            subs = await crud.get_user_subscriptions(session, user.id)
            active = [s for s in subs if (s.status or "").lower() == "active" and s.marzban_username]
            sub = active[0] if active else (subs[0] if subs else None)
        if not sub:
            return web.json_response({"ok": False, "error": "no_subscription"}, status=404)

        display_name = sub.marzban_username or (user.full_name or "My subscription")

        # Resolve the public sub URL + expiry server-side (never from the client).
        info = None
        try:
            info = await marzban_api.get_fast_user_info(sub.marzban_username, getattr(sub, "sub_token", None))
        except Exception:
            info = None
        from app.core.settings import SUBLINK

        _base = SUBLINK.rstrip("/")
        if not _base.startswith(("http://", "https://")):
            _base = "https://" + _base
        _raw = (info or {}).get("subscription_url")
        token = getattr(sub, "sub_token", None)
        if _raw and re.match(r"^https?://", _raw):
            sub_url = _raw
        elif token:
            # PasarGuard /sub/{token}/info has no subscription_url, so info gives a
            # RELATIVE "/sub/{token}". Host it on the public SUBLINK domain rather
            # than the broken "https://sub/{token}" the old concat produced.
            sub_url = f"{_base}/{token}"
        else:
            sub_url = None
        if not sub_url:
            return web.json_response({"ok": False, "error": "no_sub_url"}, status=404)

        expires_ms = None
        try:
            exp = (info or {}).get("expire")
            if exp:
                expires_ms = int(exp) * 1000
        except Exception:
            expires_ms = None

    # Embedded add link: the subscription travels inside the link so the Orbit app
    # resolves it on-device (no Cloudflare claim round-trip, which some ISPs SNI-block).
    # base64url(JSON) payload; the app imports the sub straight from its own host.
    import base64 as _b64
    import json as _json
    _payload = _b64.urlsafe_b64encode(
        _json.dumps({"u": sub_url, "n": display_name, "e": expires_ms}, separators=(",", ":")).encode()
    ).decode().rstrip("=")
    add_url = f"https://game1.astrobytech.com/o/{_payload}"

    resp = web.json_response({"ok": True, "add_url": add_url})
    if new_session_token:
        set_tma_session_cookie(resp, request, new_session_token, max_age=86400)
    return resp

from app.api.deps import _verify_webapp_auth

from ..common import *  # noqa: F403


async def handle_dashboard_add_sub(request: web.Request):
    user_chat_id, new_session_token = _verify_webapp_auth(request)
    if not user_chat_id:
        return web.json_response({"ok": False, "error": "unauthorized"}, status=403)

    try:
        data = await request.json()
    except Exception:
        return web.json_response({"ok": False, "error": "invalid_json"}, status=400)
    
    # Validate input using Pydantic schema
    validated, error = validate_request(AddSubscriptionRequest, data)
    if error:
        return web.json_response(error, status=400)
    
    supplied_url = (validated.url or "").strip()
    supplied_username = (validated.username or "").strip()
    supplied_token = (validated.token or "").strip()

    def _normalize_b64_url(s: str) -> str:
        v = (s or "").strip().replace(" ", "").replace("\n", "").replace("\r", "").replace("\t", "")
        v = v.replace("-", "+").replace("_", "/")
        pad = (-len(v)) % 4
        return v + ("=" * pad)

    def _decode_b64_safe(s: str) -> str:
        try:
            return base64.b64decode(_normalize_b64_url(s)).decode("utf-8", "ignore")
        except Exception:
            return ""

    def _ensure_url_scheme(u: str) -> str:
        uu = (u or "").strip()
        if not uu:
            return uu
        if uu.startswith("http://") or uu.startswith("https://"):
            return uu
        return "https://" + uu.lstrip("/")

    def _host_allowed(host: str | None) -> bool:
        if not host:
            return False
        h = host.lower().strip(".")
        for allowed in (DASHBOARD_SUBSCRIPTION_ALLOWED_DOMAINS or []):
            a = (allowed or "").lower().strip(".")
            if not a:
                continue
            if h == a or h.endswith("." + a):
                return True
        return False

    def _extract_token_from_subscription_link(raw: str) -> str:
        """
        Extract token from a subscription URL like:
          https://example.com/sub/<token>
        Accepts either a raw URL, or a base64-encoded URL.
        """
        if not raw:
            return ""
        candidate = raw.strip()
        decoded = _decode_b64_safe(candidate)
        if decoded and ("/sub/" in decoded or decoded.startswith("http")):
            candidate = decoded.strip()
        candidate = _ensure_url_scheme(candidate)
        parsed = urlparse(candidate)
        # Domain restriction
        if DASHBOARD_SUBSCRIPTION_DOMAIN_ENFORCE and not _host_allowed(parsed.hostname):
            return "__DOMAIN_NOT_ALLOWED__"
        import re
        m = re.search(r"/sub/([^/]+)/?", parsed.path or "")
        return (m.group(1) if m else "") or ""

    if DASHBOARD_SUBSCRIPTION_DOMAIN_ENFORCE and not supplied_url:
        return web.json_response(
            {
                "ok": False,
                "error": "subscription_url_required",
                "message": "Subscription link is required",
            },
            status=400,
        )

    if supplied_url:
        extracted = _extract_token_from_subscription_link(supplied_url)
        if extracted == "__DOMAIN_NOT_ALLOWED__":
            allowed = ", ".join(DASHBOARD_SUBSCRIPTION_ALLOWED_DOMAINS or []) or "astrobytetech.com"
            return web.json_response(
                {
                    "ok": False,
                    "error": "disallowed_domain",
                    "message": f"Subscription link domain is not allowed. Allowed domains: {allowed}",
                },
                status=400,
            )
        if not extracted:
            return web.json_response(
                {
                    "ok": False,
                    "error": "invalid_subscription_url",
                    "message": "Invalid subscription link",
                },
                status=400,
            )
        supplied_token = extracted

    # Resolve username/token via Marzban when token provided
    token_val = None
    username_val = supplied_username or None
    if supplied_token:
        token_val = supplied_token
        try:
            info = await marzban_api.get_subscription_info(token_val)
            if info and not username_val:
                username_val = info.get("username")
        except Exception:
            pass

    if not username_val:
        return web.json_response({"ok": False, "error": "cannot_resolve_username"}, status=400)

    async with AsyncSessionLocal() as session:
        # Ensure user exists
        user = await crud.get_user(session, user_chat_id)
        if not user:
            return web.json_response({"ok": False, "error": "not_registered"}, status=403)

        # Check if subscription already exists
        from sqlalchemy import select
        existing = await session.execute(select(Subscription).filter(Subscription.marzban_username == username_val))
        sub = existing.scalars().first()
        created = False
        if not sub:
            sub = Subscription(user_id=user.id, marzban_username=username_val, status="active")
            if token_val:
                sub.sub_token = token_val
            session.add(sub)
            await session.commit()
            await session.refresh(sub)
            created = True
        else:
            # Link existing to this user if not already owned by anyone (or link table)
            if sub.user_id != user.id:
                await crud.add_subscription_link(session, user.id, sub.id)
        # Respond
        resp = web.json_response({"ok": True, "subscription_id": sub.id, "created": created})
        if new_session_token:
            set_tma_session_cookie(resp, request, new_session_token, max_age=86400)
        return resp


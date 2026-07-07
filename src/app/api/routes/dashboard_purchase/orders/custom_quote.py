from aiohttp import web

from app.api.deps import _verify_webapp_auth, set_tma_session_cookie
from app.services.flows.pricing import (
    CUSTOM_MAX_GB,
    CUSTOM_MIN_GB,
    custom_plan_price,
    get_plan_info,
)


async def handle_custom_plan_quote(request: web.Request):
    """Price a build-your-own plan: GET ?gb=<n> → {price, days, plan_name}.

    GET ?gb=all → the full price table (index 0 = CUSTOM_MIN_GB) so the client
    slider can show exact server prices instantly with zero per-tick requests.
    """
    user_chat_id, new_session_token = _verify_webapp_auth(request)
    if not user_chat_id:
        return web.json_response({"ok": False, "error": "unauthorized"}, status=403)

    raw_gb = request.query.get("gb", "")
    if raw_gb == "all":
        info = get_plan_info(f"custom:{CUSTOM_MIN_GB}") or {}
        resp = web.json_response(
            {
                "ok": True,
                "min": CUSTOM_MIN_GB,
                "max": CUSTOM_MAX_GB,
                "days": info.get("days"),
                "prices": [custom_plan_price(g) for g in range(CUSTOM_MIN_GB, CUSTOM_MAX_GB + 1)],
            }
        )
        resp.headers["Cache-Control"] = "private, max-age=600"
        if new_session_token:
            set_tma_session_cookie(resp, request, new_session_token, max_age=86400)
        return resp

    try:
        gb = int(raw_gb)
    except ValueError:
        return web.json_response({"ok": False, "error": "invalid_gb"}, status=400)
    if not (CUSTOM_MIN_GB <= gb <= CUSTOM_MAX_GB):
        return web.json_response(
            {"ok": False, "error": "out_of_range", "min": CUSTOM_MIN_GB, "max": CUSTOM_MAX_GB}, status=400
        )

    plan_name = f"custom:{gb}"
    info = get_plan_info(plan_name) or {}
    resp = web.json_response(
        {
            "ok": True,
            "plan_name": plan_name,
            "gb": gb,
            "price": custom_plan_price(gb),
            "days": info.get("days"),
            "min": CUSTOM_MIN_GB,
            "max": CUSTOM_MAX_GB,
        }
    )
    if new_session_token:
        set_tma_session_cookie(resp, request, new_session_token, max_age=86400)
    return resp

import traceback

from aiohttp import web
from sqlalchemy import and_
from sqlalchemy.future import select

from app.api.deps import _verify_webapp_auth, set_tma_session_cookie
from app.api.routes.dashboard.common import _normalize_sub_id
from app.api.schemas import DashboardPreferencesPatchRequest, validate_request
from app.database import crud
from app.database.models import AsyncSessionLocal, Subscription


async def handle_dashboard_preferences_get(request: web.Request):
    """Get per-user dashboard preferences (sync across devices)."""
    user_chat_id, new_session_token = _verify_webapp_auth(request)
    if not user_chat_id:
        return web.json_response({"ok": False, "error": "unauthorized"}, status=403)

    try:
        async with AsyncSessionLocal() as session:
            user = await crud.get_user(session, user_chat_id)
            if not user:
                return web.json_response({"ok": False, "error": "user_not_found"}, status=404)

            prefs = await crud.get_dashboard_prefs(session, user_chat_id)
            prefs = dict(prefs or {})
            prefs["lang"] = user.language or prefs.get("lang") or "en"

            resp = web.json_response({"ok": True, "prefs": prefs})
            if new_session_token:
                set_tma_session_cookie(resp, request, new_session_token, max_age=86400)
            return resp
    except Exception:
        traceback.print_exc()
        return web.json_response({"ok": False, "error": "server_error"}, status=500)


async def handle_dashboard_preferences_patch(request: web.Request):
    """Update per-user dashboard preferences (merge/patch)."""
    user_chat_id, new_session_token = _verify_webapp_auth(request)
    if not user_chat_id:
        return web.json_response({"ok": False, "error": "unauthorized"}, status=403)

    try:
        data = await request.json()
    except Exception:
        data = {}

    validated, error = validate_request(DashboardPreferencesPatchRequest, data)
    if error:
        return web.json_response(error, status=400)

    patch: dict = {}
    if validated.theme is not None:
        patch["theme"] = validated.theme
    if validated.lang is not None:
        patch["lang"] = validated.lang
    if validated.current_sub_id is not None:
        patch["current_sub_id"] = _normalize_sub_id(validated.current_sub_id)
    if validated.default_sub_id is not None:
        patch["default_sub_id"] = _normalize_sub_id(validated.default_sub_id)
    if validated.auto_claim is not None:
        patch["auto_claim"] = bool(validated.auto_claim)
    if getattr(validated, "voucher_auto_sub_id", None) is not None:
        patch["voucher_auto_sub_id"] = _normalize_sub_id(getattr(validated, "voucher_auto_sub_id", None))
    if getattr(validated, "accent", None) is not None:
        patch["accent"] = validated.accent
    if getattr(validated, "welcome_shown", None) is not None:
        patch["welcome_shown"] = bool(validated.welcome_shown)

    try:
        async with AsyncSessionLocal() as session:
            user = await crud.get_user(session, user_chat_id)
            if not user:
                return web.json_response({"ok": False, "error": "user_not_found"}, status=404)

            if "auto_claim" in patch and patch.get("auto_claim") is True:
                try:
                    is_vip = await crud.is_user_vip(session, user.id)
                except Exception:
                    is_vip = False
                if not is_vip:
                    return web.json_response({"ok": False, "error": "vip_required"}, status=403)

            if "voucher_auto_sub_id" in patch:
                try:
                    is_vip = await crud.is_user_vip(session, user.id)
                except Exception:
                    is_vip = False
                if not is_vip and patch.get("voucher_auto_sub_id") is not None:
                    return web.json_response({"ok": False, "error": "vip_required"}, status=403)

            for key in ("current_sub_id", "default_sub_id", "voucher_auto_sub_id"):
                if key not in patch:
                    continue
                sid = patch.get(key)
                if sid is None:
                    continue
                try:
                    q = await session.execute(
                        select(Subscription).where(and_(Subscription.id == int(sid), Subscription.user_id == user.id))
                    )
                    sub_obj = q.scalars().first()
                    ok = bool(sub_obj)
                    if not ok:
                        patch[key] = None
                    elif key == "voucher_auto_sub_id":
                        try:
                            if str(getattr(sub_obj, "status", "")).lower() != "active":
                                patch[key] = None
                            if not getattr(sub_obj, "marzban_username", None):
                                patch[key] = None
                        except Exception:
                            patch[key] = None
                except Exception:
                    patch[key] = None

            prefs = await crud.update_dashboard_prefs(session, user_chat_id, patch)
            prefs = dict(prefs or {})
            prefs["lang"] = user.language or prefs.get("lang") or "en"

            resp = web.json_response({"ok": True, "prefs": prefs})
            if new_session_token:
                set_tma_session_cookie(resp, request, new_session_token, max_age=86400)
            return resp
    except Exception:
        traceback.print_exc()
        return web.json_response({"ok": False, "error": "server_error"}, status=500)

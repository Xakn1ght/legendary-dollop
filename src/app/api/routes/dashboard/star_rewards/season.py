import json
import logging
import traceback
from datetime import datetime

from aiohttp import web

from app.api.deps import _verify_webapp_auth, set_tma_session_cookie
from app.core.rewards_config import STAR_SEASON_MILESTONES
from app.database import crud
from app.database.models import AsyncSessionLocal

logger = logging.getLogger(__name__)


def _parse_payload(raw) -> dict:
    if isinstance(raw, dict):
        return raw
    try:
        return json.loads(raw or "{}")
    except Exception:
        return {}


async def handle_dashboard_season(request: web.Request):
    """Star Season dashboard: season stars, the milestone ladder, and the coupon wallet.

    Read-only mirror of the bot reward menu (handlers/user/rewards/menu.py). Stars are
    referral-only and seasonal; coupon labels are rendered client-side from coupon_type
    + payload so the webapp keeps its own fa/en i18n.
    """
    user_chat_id, new_session_token = _verify_webapp_auth(request)
    if not user_chat_id:
        return web.json_response({"ok": False, "error": "unauthorized"}, status=403)

    try:
        async with AsyncSessionLocal() as session:
            user = await crud.get_user(session, user_chat_id)
            if not user:
                return web.json_response({"ok": False, "error": "user_not_found"}, status=404)

            season, season_stars = await crud.get_season_progress(session, user.id)
            coupons = await crud.get_active_coupons(session, user.id)
            now = datetime.utcnow()

            ladder = []
            for stars in sorted(STAR_SEASON_MILESTONES):
                info = STAR_SEASON_MILESTONES[stars]
                item = {
                    "stars": stars,
                    "name": info.get("name", ""),
                    "coupon_type": info.get("coupon_type", ""),
                    "payload": info.get("payload", {}),
                    "reached": season_stars >= stars,
                }
                # Milestone cosmetics (40★/50★): lets the webapp show badge art.
                if info.get("badge"):
                    item["badge"] = info["badge"]
                if info.get("theme"):
                    item["theme"] = info["theme"]
                if info.get("extra_coupons"):
                    item["extra_coupons"] = info["extra_coupons"]
                ladder.append(item)

            next_ms = next((m for m in sorted(STAR_SEASON_MILESTONES) if m > season_stars), None)
            next_milestone = (
                {"stars": next_ms, "name": STAR_SEASON_MILESTONES[next_ms].get("name", "")}
                if next_ms is not None
                else None
            )

            coupon_items = []
            for c in coupons:
                exp = getattr(c, "expires_at", None)
                days_left = max(0, (exp - now).days) if exp else None
                coupon_items.append(
                    {
                        "id": int(getattr(c, "id", 0) or 0),
                        "coupon_type": str(getattr(c, "coupon_type", "") or ""),
                        "payload": _parse_payload(getattr(c, "payload", None)),
                        "milestone_stars": int(getattr(c, "milestone_stars", 0) or 0),
                        "created_at": c.created_at.isoformat() if getattr(c, "created_at", None) else None,
                        "expires_at": exp.isoformat() if exp else None,
                        "days_left": days_left,
                    }
                )

            season_ends = getattr(season, "ends_at", None)
            season_info = {
                "name": str(getattr(season, "name", "") or ""),
                "ends_at": season_ends.isoformat() if season_ends else None,
                "days_left": max(0, (season_ends - now).days) if season_ends else None,
            }

            resp = web.json_response(
                {
                    "ok": True,
                    "season": season_info,
                    "season_stars": int(season_stars or 0),
                    "next_milestone": next_milestone,
                    "ladder": ladder,
                    "coupons": coupon_items,
                }
            )
            if new_session_token:
                set_tma_session_cookie(resp, request, new_session_token, max_age=86400)
            return resp
    except Exception as e:
        traceback.print_exc()
        logger.error(f"Error fetching season rewards: {e}")
        return web.json_response({"ok": False, "error": "server_error"}, status=500)

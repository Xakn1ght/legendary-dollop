import logging
import traceback
from datetime import datetime

from aiohttp import web

from app.api.deps import _verify_webapp_auth, set_tma_session_cookie
from app.api.routes.dashboard.common import _parse_tier_reward_value
from app.database import crud
from app.database.models import AsyncSessionLocal

logger = logging.getLogger(__name__)


async def handle_dashboard_star_claims(request: web.Request):
    """Return unclaimed star tier claims for current user (current Jalali season)."""
    user_chat_id, new_session_token = _verify_webapp_auth(request)
    if not user_chat_id:
        return web.json_response({"ok": False, "error": "unauthorized"}, status=403)

    try:
        async with AsyncSessionLocal() as session:
            user = await crud.get_user(session, user_chat_id)
            if not user:
                return web.json_response({"ok": False, "error": "user_not_found"}, status=404)

            claims = await crud.get_user_unclaimed_rewards(session, user.id)
            now = datetime.utcnow()
            out = []
            for c in claims or []:
                tier = getattr(c, "tier", None)
                if not tier:
                    continue
                parsed = _parse_tier_reward_value(getattr(tier, "reward_value", "") or "")
                needs_sub = int(parsed.get("traffic_gb") or 0) > 0
                out.append(
                    {
                        "id": int(getattr(c, "id", 0) or 0),
                        "tier_id": int(getattr(c, "tier_id", 0) or 0),
                        "status": str(getattr(c, "status", "") or ""),
                        "expires_at": (getattr(c, "expires_at", None) or now).isoformat(),
                        "tier": {
                            "id": int(getattr(tier, "id", 0) or 0),
                            "threshold": int(getattr(tier, "star_threshold", 0) or 0),
                            "title": str(getattr(tier, "title", "") or ""),
                            "description": str(getattr(tier, "description", "") or ""),
                            "reward_type": str(getattr(tier, "reward_type", "") or ""),
                            "reward": parsed,
                            "needs_subscription": bool(needs_sub),
                        },
                    }
                )

            resp = web.json_response({"ok": True, "claims": out})
            if new_session_token:
                set_tma_session_cookie(resp, request, new_session_token, max_age=86400)
            return resp
    except Exception as e:
        traceback.print_exc()
        logger.error(f"Error fetching star claims: {e}")
        return web.json_response({"ok": False, "error": "server_error"}, status=500)

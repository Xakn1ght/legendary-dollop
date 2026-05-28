import logging
import traceback

from aiohttp import web

from app.api.deps import _verify_webapp_auth, set_tma_session_cookie
from app.api.routes.dashboard.common import _parse_tier_reward_value
from app.database import crud
from app.database.models import AsyncSessionLocal

logger = logging.getLogger(__name__)


async def handle_dashboard_star_tiers(request: web.Request):
    """Return star tier ladder for the webapp Rewards page."""
    user_chat_id, new_session_token = _verify_webapp_auth(request)
    if not user_chat_id:
        return web.json_response({"ok": False, "error": "unauthorized"}, status=403)

    try:
        async with AsyncSessionLocal() as session:
            user = await crud.get_user(session, user_chat_id)
            if not user:
                return web.json_response({"ok": False, "error": "user_not_found"}, status=404)

            tiers = await crud.get_all_star_reward_tiers(session, active_only=True)
            items = []
            for t in tiers or []:
                parsed = _parse_tier_reward_value(getattr(t, "reward_value", "") or "")
                needs_sub = int(parsed.get("traffic_gb") or 0) > 0
                items.append(
                    {
                        "id": int(getattr(t, "id", 0) or 0),
                        "threshold": int(getattr(t, "star_threshold", 0) or 0),
                        "title": str(getattr(t, "title", "") or ""),
                        "description": str(getattr(t, "description", "") or ""),
                        "reward_type": str(getattr(t, "reward_type", "") or ""),
                        "reward": parsed,
                        "needs_subscription": bool(needs_sub),
                    }
                )

            resp = web.json_response(
                {
                    "ok": True,
                    "user": {"stars": int(getattr(user, "stars", 0) or 0)},
                    "tiers": items,
                }
            )
            if new_session_token:
                set_tma_session_cookie(resp, request, new_session_token, max_age=86400)
            return resp
    except Exception as e:
        traceback.print_exc()
        logger.error(f"Error fetching star tiers: {e}")
        return web.json_response({"ok": False, "error": "server_error"}, status=500)

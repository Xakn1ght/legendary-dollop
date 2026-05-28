import logging
import traceback

from aiohttp import web

from app.api.deps import _verify_webapp_auth, set_tma_session_cookie
from app.database import crud
from app.database.models import AsyncSessionLocal

logger = logging.getLogger(__name__)


async def handle_dashboard_rewards_summary(request: web.Request):
    """Small rewards summary for the Rewards page (stars/pieces/streak/game availability)."""
    user_chat_id, new_session_token = _verify_webapp_auth(request)
    if not user_chat_id:
        return web.json_response({"ok": False, "error": "unauthorized"}, status=403)

    try:
        async with AsyncSessionLocal() as session:
            user = await crud.get_user(session, user_chat_id)
            if not user:
                return web.json_response({"ok": False, "error": "user_not_found"}, status=404)

            can_play = {"allowed": True, "best_score": 0}
            try:
                can_play = await crud.can_play_daily_game(session, user.id)
            except Exception:
                pass

            pieces_per_star = 0
            monthly_cap = 0
            monthly_stars = 0
            current_pieces = 0
            progress = 0

            cfg = await crud.get_reward_config(session)
            traffic_pct = float(getattr(cfg, "traffic_percent", 0) or 0)
            days_pct = float(getattr(cfg, "days_percent", 0) or 0)
            credit_pct = float(getattr(cfg, "credit_percent", 0) or 0)

            resp = web.json_response(
                {
                    "ok": True,
                    "user": {
                        "stars": int(getattr(user, "stars", 0) or 0),
                        "credit": int(getattr(user, "credit", 0) or 0),
                        "subscription_credit": int(getattr(user, "subscription_credit", 0) or 0),
                        "streak": int(getattr(user, "login_streak", 0) or 0),
                        "loyalty_points": 0,
                    },
                    "arcade": {
                        "can_play_today": bool(can_play.get("allowed", False)),
                        "best_score_today": int(can_play.get("best_score", 0) or 0),
                        "pieces": {
                            "total": current_pieces,
                            "progress": progress,
                            "per_star": pieces_per_star,
                        },
                        "monthly_stars": {
                            "earned": monthly_stars,
                            "cap": monthly_cap,
                            "remaining": max(monthly_cap - monthly_stars, 0),
                            "cap_reached": bool(monthly_stars >= monthly_cap),
                        },
                    },
                    "referral_reward_options": {
                        "traffic_percent": round(traffic_pct, 1),
                        "days_percent": round(days_pct, 1),
                        "credit_percent": round(credit_pct, 1),
                        "stars_per_referral": 1,
                    },
                }
            )
            if new_session_token:
                resp.set_cookie(
                    "tma_session",
                    new_session_token,
                    max_age=86400,
                    httponly=True,
                    secure=True,
                    samesite="Lax",
                    path="/",
                )
            return resp
    except Exception as e:
        traceback.print_exc()
        logger.error(f"Error fetching rewards summary: {e}")
        return web.json_response({"ok": False, "error": "server_error"}, status=500)

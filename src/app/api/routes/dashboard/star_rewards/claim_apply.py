import logging
import traceback
from datetime import datetime, timedelta

from aiohttp import web

from app.api.deps import _verify_webapp_auth, set_tma_session_cookie
from app.api.routes.dashboard.common import _parse_tier_reward_value
from app.database import crud
from app.database.models import AsyncSessionLocal, StarRewardTier
from app.services.marzban import marzban_api

logger = logging.getLogger(__name__)


async def handle_dashboard_star_claim_apply(request: web.Request):
    """Claim a star tier reward from the webapp.

    Body: { subscription_id?: int }
    """
    user_chat_id, new_session_token = _verify_webapp_auth(request)
    if not user_chat_id:
        return web.json_response({"ok": False, "error": "unauthorized"}, status=403)

    claim_id = request.match_info.get("claim_id")
    try:
        claim_id_int = int(str(claim_id))
    except Exception:
        return web.json_response({"ok": False, "error": "invalid_claim_id"}, status=400)

    try:
        data = await request.json()
    except Exception:
        data = {}

    sub_id = data.get("subscription_id")
    try:
        sub_id_int = int(sub_id) if sub_id is not None else None
    except Exception:
        sub_id_int = None

    try:
        async with AsyncSessionLocal() as session:
            user = await crud.get_user(session, user_chat_id)
            if not user:
                return web.json_response({"ok": False, "error": "user_not_found"}, status=404)

            claim = await crud.get_user_star_reward_claim_by_id(session, claim_id_int)
            if not claim or int(getattr(claim, "user_id", 0) or 0) != int(user.id):
                return web.json_response({"ok": False, "error": "not_found"}, status=404)

            now = datetime.utcnow()
            if str(getattr(claim, "status", "")) != "offered" or (getattr(claim, "expires_at", now) <= now):
                return web.json_response({"ok": False, "error": "not_claimable"}, status=400)

            tier: StarRewardTier | None = getattr(claim, "tier", None)
            if not tier:
                tier = await session.get(StarRewardTier, int(getattr(claim, "tier_id", 0) or 0))
            if not tier:
                return web.json_response({"ok": False, "error": "tier_not_found"}, status=404)

            if str(getattr(tier, "reward_type", "")) != "bundle":
                return web.json_response({"ok": False, "error": "unsupported_reward_type"}, status=400)

            parsed = _parse_tier_reward_value(getattr(tier, "reward_value", "") or "")
            credit_amt = int(parsed.get("credit") or 0)
            sub_credit_amt = int(parsed.get("sub_credit") or 0)
            discount_pct = int(parsed.get("discount") or 0)
            traffic_gb = int(parsed.get("traffic_gb") or 0)

            applied_to = None
            if traffic_gb > 0:
                active_subs = await crud.get_user_active_subscriptions(session, user.id)
                active_subs = list(active_subs or [])
                if not active_subs:
                    return web.json_response({"ok": False, "error": "no_active_subscription"}, status=400)

                target_sub = None
                if len(active_subs) == 1:
                    target_sub = active_subs[0]
                else:
                    if not sub_id_int:
                        return web.json_response({"ok": False, "error": "choose_subscription"}, status=400)
                    target_sub = next((s for s in active_subs if int(getattr(s, "id", 0) or 0) == sub_id_int), None)
                    if not target_sub:
                        return web.json_response({"ok": False, "error": "invalid_subscription"}, status=400)

                info = await marzban_api.get_user_info(target_sub.marzban_username)
                if not info:
                    return web.json_response({"ok": False, "error": "marzban_user_not_found"}, status=502)
                add_bytes = int(traffic_gb) * 1024**3
                patch = {"data_limit": int(info.get("data_limit") or 0) + add_bytes}
                ok = await marzban_api.update_user(target_sub.marzban_username, patch)
                if not ok:
                    return web.json_response({"ok": False, "error": "marzban_update_failed"}, status=502)
                applied_to = str(getattr(target_sub, "marzban_username", "") or "")
                await crud.add_reward_history(
                    session,
                    user.id,
                    "traffic",
                    int(traffic_gb),
                    "star_tier",
                    int(getattr(tier, "id", 0) or 0),
                    notes=f"Applied to {applied_to}",
                )

            if credit_amt > 0:
                await crud.add_credit(session, user.id, credit_amt)
                await crud.add_reward_history(session, user.id, "credit", credit_amt, "star_tier", int(getattr(tier, "id", 0) or 0))

            if sub_credit_amt > 0:
                await crud.add_subscription_credit(session, user.id, sub_credit_amt, "star_tier", notes="Tier reward (webapp)")

            if discount_pct > 0:
                exp = datetime.utcnow() + timedelta(days=60)
                await crud.add_user_discount(session, user.id, discount_pct, exp, source=str(getattr(tier, "title", "") or "star_tier"))
                await crud.add_reward_history(
                    session, user.id, "discount_percent", discount_pct, "star_tier", int(getattr(tier, "id", 0) or 0), notes="Tier reward (webapp)"
                )

            claim.status = "claimed"
            claim.claimed_at = datetime.utcnow()
            try:
                claim.chosen_reward_type = "bundle"
            except Exception:
                pass
            await session.commit()

            resp = web.json_response(
                {
                    "ok": True,
                    "claim_id": int(getattr(claim, "id", 0) or 0),
                    "tier_id": int(getattr(tier, "id", 0) or 0),
                    "applied_to": applied_to,
                }
            )
            if new_session_token:
                set_tma_session_cookie(resp, request, new_session_token, max_age=86400)
            return resp
    except Exception as e:
        traceback.print_exc()
        logger.error(f"Error claiming star tier: {e}")
        return web.json_response({"ok": False, "error": "server_error"}, status=500)

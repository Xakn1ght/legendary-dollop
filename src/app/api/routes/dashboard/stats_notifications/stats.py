from aiohttp import web

from app.api.deps import _verify_webapp_auth, set_tma_session_cookie
from app.database import crud
from app.database.models import AsyncSessionLocal


async def handle_dashboard_stats(request: web.Request):
    user_chat_id, new_session_token = _verify_webapp_auth(request)
    if not user_chat_id:
        return web.json_response({"ok": False, "error": "unauthorized"}, status=403)

    async with AsyncSessionLocal() as session:
        user = await crud.get_user(session, user_chat_id)
        if not user:
            return web.json_response({"ok": False, "error": "not_registered"}, status=403)

        active_subs = await crud.get_user_subscriptions(session, user.id)
        active_count = len([s for s in active_subs if s.status == "active"])

        rewards = await crud.get_user_reward_history(session, user.id, limit=5)
        recent_rewards = [
            {
                "type": r.reward_type,
                "amount": r.amount,
                "date": r.created_at.isoformat(),
            }
            for r in rewards
        ]

        data = {
            "credit": user.credit,
            "stars": user.stars,
            "level": user.level,
            "xp": 0,
            "active_services": active_count,
            "recent_rewards": recent_rewards,
        }

        resp = web.json_response({"ok": True, "stats": data})
        if new_session_token:
            set_tma_session_cookie(resp, request, new_session_token, max_age=86400)
        return resp

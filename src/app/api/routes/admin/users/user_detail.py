from ..common import *  # noqa: F403


async def handle_admin_user_detail(request: web.Request):
    try:
        user_id = int(request.match_info['user_id'])
    except (ValueError, KeyError):
        return web.json_response({"ok": False, "error": "invalid_user_id"}, status=400)
    try:
        async with AsyncSessionLocal() as session:
            user = await session.get(User, user_id)
            if not user:
                return web.json_response({"ok": False, "error": "not_found"}, status=404)
            
            subs = await crud.get_user_subscriptions(session, user.id)
            # NB: expiry lives in Marzban, not the DB — the old `s.expire_date`
            # attribute never existed and 500'd this endpoint for any user
            # that owned a subscription.
            subs_data = [{
                "id": s.id,
                "username": s.marzban_username,
                "status": s.status,
                "plan_name": s.plan_name,
                "created_at": s.created_at.isoformat() if s.created_at else None,
            } for s in subs]
            
            return web.json_response({
                "ok": True,
                "user": {
                    "id": user.id,
                    "chat_id": user.chat_id,
                    "username": user.username,
                    "full_name": user.full_name,
                    "credit": user.credit,
                    "stars": user.stars,
                    "banned": user.banned,
                    "is_vip": bool(getattr(user, "is_vip", False)),
                    "vip_until": user.vip_until.isoformat() if getattr(user, "vip_until", None) else None,
                    "created_at": user.created_at.isoformat() if user.created_at else None,
                    "subscriptions": subs_data
                }
            })
    except Exception as e:
        return web.json_response({"ok": False, "error": "server_error"}, status=500)

from app.api.deps import _verify_webapp_auth

from ..common import *  # noqa: F403
from ..common import _is_dashboard_visible_subscription


async def handle_dashboard_list_subs(request: web.Request):
    user_chat_id, new_session_token = _verify_webapp_auth(request)
    if not user_chat_id:
        return web.json_response({"ok": False, "error": "unauthorized"}, status=403)

    async with AsyncSessionLocal() as session:
        user = await crud.get_user(session, user_chat_id)
        if not user:
            return web.json_response({"ok": True, "subscriptions": []})
        subs = await crud.get_user_subscriptions(session, user.id)
        subs = [s for s in subs if _is_dashboard_visible_subscription(s)]

        results = []
        tokens_persisted = False
        for s in subs:
            info = None
            try:
                info = await pasarguard_api.get_fast_user_info(s.marzban_username, getattr(s, 'sub_token', None))
            except Exception:
                info = None
            # Normalize
            used = (info or {}).get('used_traffic')
            limit = (info or {}).get('data_limit')
            expire = (info or {}).get('expire')
            status = (info or {}).get('status') or s.status
            # Determine share-link token
            token = getattr(s, 'sub_token', None)
            if not token:
                try:
                    sub_url_candidate = (info or {}).get('subscription_url')
                    if sub_url_candidate:
                        import re
                        m = re.search(r"/sub/([^/]+)/?", sub_url_candidate)
                        if m:
                            token = m.group(1)
                            # Persist so future reads ride the share-link fast path.
                            s.sub_token = token
                            tokens_persisted = True
                except Exception:
                    token = None
            # Build public subscription URL using configured SUBLINK host
            public_url = None
            if token:
                base = SUBLINK.rstrip('/')
                if not base.startswith('http://') and not base.startswith('https://'):
                    base = 'https://' + base
                public_url = f"{base}/{token}"
            results.append({
                "id": s.id,
                "name": s.marzban_username,
                "marzban_username": s.marzban_username,
                "username": s.marzban_username,
                "plan_name": getattr(s, 'plan_name', None),
                "status": status,
                "used_traffic": used,
                "data_limit": limit,
                "expire": expire,
                "subscription_token": token,
                "subscription_url": public_url,
            })

        if tokens_persisted:
            try:
                await session.commit()
            except Exception:
                pass

        resp = web.json_response({"ok": True, "subscriptions": results})
        if new_session_token:
            set_tma_session_cookie(resp, request, new_session_token, max_age=86400)
        return resp


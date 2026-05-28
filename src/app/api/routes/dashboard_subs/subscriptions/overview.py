from app.api.deps import _verify_webapp_auth
from app.utils.admin_bot_helper import resolve_user_bot

from ..common import *  # noqa: F403
from ..common import _is_dashboard_visible_subscription
from ..geo_client import geo_for_request


async def handle_dashboard_overview(request: web.Request):
    """Return a primary subscription overview for the user."""
    user_chat_id, new_session_token = _verify_webapp_auth(request)
    if not user_chat_id:
        return web.json_response({"ok": False, "error": "unauthorized"}, status=403)

    try:
        preferred_id = request.query.get("sub_id")
        preferred_id = int(preferred_id) if preferred_id else None
    except Exception:
        preferred_id = None

    async with AsyncSessionLocal() as session:
        user = await crud.get_user(session, user_chat_id)
        if not user:
            return web.json_response({"ok": True, "subscription": None, "user": None})
        
        # Check VIP status
        is_vip = await crud.is_user_vip(session, user.id)
        
        # Get bot username for deep links
        bot_username = "AstroByteBot"  # Default fallback
        try:
            bot = resolve_user_bot(request.app.get('bot'))
            if bot and hasattr(bot, '_me') and bot._me:
                bot_username = bot._me.username
        except Exception:
            pass
        
        # Prepare user data
        user_data = {
            "id": user.id,
            "chat_id": user.chat_id,
            "username": user.username,
            "full_name": user.full_name,
            "category": user.category,
            "credit": user.credit,
            "level": user.level,
            "experience_points": user.experience_points,
            "loyalty_points": user.loyalty_points,
            "referral_code": user.referral_code,
            "created_at": user.created_at.isoformat() if user.created_at else None,
            "is_vip": is_vip,
            "vip_until": user.vip_until.isoformat() if user.vip_until else None,
            "bot_username": bot_username,
        }
        
        subs = await crud.get_user_subscriptions(session, user.id)
        subs = [s for s in subs if _is_dashboard_visible_subscription(s)]
        if not subs:
            return web.json_response({"ok": True, "subscription": None, "user": user_data})

        sub = None
        if preferred_id:
            sub = next((s for s in subs if s.id == preferred_id), None)
        if not sub:
            active = [s for s in subs if (s.status or '').lower() == 'active']
            sub = active[0] if active else subs[0]

        info = None
        try:
            info = await marzban_api.get_fast_user_info(sub.marzban_username, getattr(sub, 'sub_token', None))
        except Exception:
            info = None

        # Compute public URL and token
        token = getattr(sub, 'sub_token', None)
        if not token:
            try:
                sub_url_candidate = (info or {}).get('subscription_url')
                if sub_url_candidate:
                    import re
                    m = re.search(r"/sub/([^/]+)/?", sub_url_candidate)
                    if m:
                        token = m.group(1)
            except Exception:
                token = None
        public_url = None
        if token:
            base = SUBLINK.rstrip('/')
            if not base.startswith('http://') and not base.startswith('https://'):
                base = 'https://' + base
            public_url = f"{base}/{token}"

        # Guess location from the last 7 days of usage by node name
        location_guess = None
        try:
            usage_list = await marzban_api.get_user_usage(sub.marzban_username, days=7)
            if usage_list:
                totals = {}
                for item in usage_list:
                    node = item.get('node_name') or ''
                    country = map_inbound_to_country(node)
                    used = int(item.get('used_traffic') or 0)
                    totals[country] = totals.get(country, 0) + used
                if totals:
                    # Choose country with max usage
                    location_guess = max(totals.items(), key=lambda kv: kv[1])[0]
        except Exception:
            location_guess = None

        result = {
            "id": sub.id,
            "username": sub.marzban_username,
            "status": (info or {}).get('status') or sub.status,
            "used_traffic": (info or {}).get('used_traffic'),
            "data_limit": (info or {}).get('data_limit'),
            "expire": (info or {}).get('expire'),
            "subscription_token": token,
            "subscription_url": public_url,
            "location_guess": location_guess,
        }

        client_geo = await geo_for_request(request)
        resp = web.json_response(
            {"ok": True, "subscription": result, "user": user_data, "client_geo": client_geo}
        )
        if new_session_token:
            set_tma_session_cookie(resp, request, new_session_token, max_age=86400)
        return resp

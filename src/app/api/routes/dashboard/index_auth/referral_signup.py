from app.api.deps import _extract_user_id_from_init, _verify_webapp_auth
from app.utils.admin_bot_helper import resolve_user_bot

from ..common import *  # noqa: F403


async def handle_dashboard_submit_referral(request: web.Request):
    """
    Submit referral code from webapp to register user.
    Body: { referral_code: str, language: str (optional) }
    """
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"ok": False, "error": "invalid_json"}, status=400)
    
    referral_code = data.get("referral_code", "").strip().upper()
    language = data.get("language", "fa")
    
    if not referral_code:
        return web.json_response({"ok": False, "error": "missing_code"}, status=400)
    
    # Validate format
    import re
    if not re.match(r'^[A-Z0-9]{6}$', referral_code):
        return web.json_response({"ok": False, "error": "invalid_format"}, status=400)
    
    # Get user_id from init_data (required for registration)
    init_data = request.headers.get("X-Telegram-Init", "") or request.query.get("init_data", "")
    user_id = _extract_user_id_from_init(init_data)
    if not user_id:
        # Try to get from auth token
        user_id, _ = _verify_webapp_auth(request)
    
    if not user_id:
        return web.json_response({"ok": False, "error": "unauthorized"}, status=403)
    
    async with AsyncSessionLocal() as session:
        # Check if user already exists
        user = await crud.get_user(session, user_id)
        if user:
            return web.json_response({"ok": False, "error": "already_registered"}, status=400)
        
        # Find referrer
        referrer = await crud.get_user_by_referral_code(session, referral_code)
        if not referrer:
            return web.json_response({"ok": False, "error": "invalid_code"}, status=400)
        
        if referrer.chat_id == user_id:
            return web.json_response({"ok": False, "error": "own_code"}, status=400)
        
        # Extract user info from init_data
        import urllib.parse
        user_data_from_init = {}
        try:
            if init_data:
                parsed = urllib.parse.parse_qs(init_data)
                if 'user' in parsed:
                    import json
                    user_json = json.loads(parsed['user'][0])
                    user_data_from_init = {
                        'username': user_json.get('username'),
                        'full_name': (user_json.get('first_name', '') + ' ' + user_json.get('last_name', '')).strip() or 'User',
                        'language': language
                    }
        except Exception:
            pass
        
        if not user_data_from_init.get('full_name'):
            user_data_from_init['full_name'] = 'User'
        
        # Create user
        from app.database.cached_crud import create_user_cached
        user = await create_user_cached(
            session,
            user_id,
            user_data_from_init.get('username'),
            user_data_from_init.get('full_name'),
            language=user_data_from_init.get('language', 'fa')
        )
        
        # Create referral link
        await crud.create_referral(session, referrer_id=referrer.id, referee_id=user.id)
        
        # Notify referrer via Telegram
        try:
            bot = resolve_user_bot(request.app.get('bot'))
            if bot:
                from html import escape as _esc

                from app.utils.bot_i18n import t as _t
                from app.utils.premium_emoji import send_premium

                referrer_lang = getattr(referrer, 'language', 'fa') or 'fa'
                new_user_name = user.full_name or user.username or str(user.chat_id)
                notify_msg = _t(referrer_lang, "referral_new_user_dm").format(name=_esc(str(new_user_name)))
                await send_premium(bot, referrer.chat_id, notify_msg)
        except Exception as e:
            logger.warning(f"Could not notify referrer {referrer.id} about new referral: {e}")
        
        # Create session token
        token = create_session_token(user_id, WEBAPP_SESSION_SECRET or BOT_TOKEN)
        
        resp = web.json_response({
            "ok": True,
            "token": token,
            "user": {
                "id": user.id,
                "chat_id": user.chat_id,
                "username": user.username,
                "full_name": user.full_name,
                "referral_code": user.referral_code
            }
        })
        set_tma_session_cookie(resp, request, token, max_age=86400)
        return resp

from app.api.deps import _extract_user_id_from_init

from ..common import *  # noqa: F403


async def handle_dashboard_login(request: web.Request):
    """
    Login endpoint for dashboard.
    Takes init_data, verifies it, creates session token.
    """
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"ok": False, "error": "invalid_json"}, status=400)
    
    # Validate input using Pydantic schema
    validated, error = validate_request(DashboardLoginRequest, data)
    if error:
        return web.json_response(error, status=400)
    
    init_data = validated.init_data

    init_ok = False
    if BOT_TOKEN and verify_init_data(init_data, BOT_TOKEN):
        init_ok = True
    elif ADMIN_BOT_TOKEN and verify_init_data(init_data, ADMIN_BOT_TOKEN):
        init_ok = True
    if not init_ok:
        return web.json_response({"ok": False, "error": "bad_signature"}, status=403)
    
    user_id = _extract_user_id_from_init(init_data)
    if not user_id:
        return web.json_response({"ok": False, "error": "no_user_id"}, status=400)
    
    # Extract user info from init_data for auto-creation
    import urllib.parse
    user_data_from_init = {}
    try:
        parsed = urllib.parse.parse_qs(init_data)
        if 'user' in parsed:
            import json
            user_json = json.loads(parsed['user'][0])
            user_data_from_init = {
                'username': user_json.get('username'),
                'full_name': user_json.get('first_name', '') + ' ' + user_json.get('last_name', '').strip(),
                'language': user_json.get('language_code', 'fa')[:2] if user_json.get('language_code') else 'fa'
            }
    except Exception:
        pass
    
    # Create session
    token = create_session_token(user_id, WEBAPP_SESSION_SECRET or BOT_TOKEN)
    
    # Get user info
    async with AsyncSessionLocal() as session:
        user = await crud.get_user(session, user_id)
        
        # Auto-create OG users if they don't exist
        if not user:
            from app.handlers.user.start import _is_og_user
            is_og = _is_og_user(user_id, user_data_from_init.get('username'))
            
            if is_og:
                # Create OG user automatically
                from app.database.cached_crud import create_user_cached
                user = await create_user_cached(
                    session, 
                    user_id, 
                    user_data_from_init.get('username'),
                    user_data_from_init.get('full_name', 'User'),
                    language=user_data_from_init.get('language', 'fa')
                )
            else:
                # Not OG and not registered - must use /start first
                return web.json_response({"ok": False, "error": "not_registered"}, status=403)
        
        user_data = {
            "id": user.id,
            "chat_id": user.chat_id,
            "username": user.username,
            "full_name": user.full_name,
            "credit": user.credit,
            "stars": user.stars,
            "level": user.level,
            "is_admin": user.is_admin
        }
    
    resp = web.json_response({"ok": True, "token": token, "user": user_data})
    set_tma_session_cookie(resp, request, token, max_age=86400)
    return resp

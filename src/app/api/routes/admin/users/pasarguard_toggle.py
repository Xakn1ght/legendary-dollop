from ..common import *  # noqa: F403


async def handle_admin_toggle_user(request: web.Request):
    username = request.match_info.get('username', '').strip()
    if not username or len(username) > 100:
        return web.json_response({"ok": False, "error": "invalid_username"}, status=400)
    
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"ok": False, "error": "invalid_json"}, status=400)
    
    # Validate input using Pydantic schema
    validated, error = validate_request(AdminToggleUserStatusRequest, data)
    if error:
        return web.json_response(error, status=400)
    
    try:
        success = await pasarguard_api.toggle_user_status(username, validated.status)
        if success:
             return web.json_response({"ok": True})
        else:
             return web.json_response({"ok": False, "error": "pasarguard_error"}, status=500)
    except Exception as e:
        return web.json_response({"ok": False, "error": "server_error"}, status=500)

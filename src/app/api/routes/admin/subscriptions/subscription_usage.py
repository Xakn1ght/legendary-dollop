from ..common import *  # noqa: F403


async def handle_admin_subscription_usage(request: web.Request):
    """Get usage stats for a user from Marzban"""
    username = request.match_info.get('username', '').strip()
    if not username or len(username) > 100:
        return web.json_response({"ok": False, "error": "invalid_username"}, status=400)
    
    try:
        usages = await marzban_api.get_user_usage(username)
        return web.json_response({"ok": True, "usages": usages or []})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return web.json_response({"ok": False, "error": "server_error"}, status=500)

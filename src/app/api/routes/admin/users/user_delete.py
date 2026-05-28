from ..common import *  # noqa: F403


async def handle_admin_user_delete(request: web.Request):
    try:
        user_id = int(request.match_info['user_id'])
    except (ValueError, KeyError):
        return web.json_response({"ok": False, "error": "invalid_user_id"}, status=400)
    try:
        async with AsyncSessionLocal() as session:
            # This is a hard delete - be careful!
            user = await session.get(User, user_id)
            if not user:
                return web.json_response({"ok": False, "error": "not_found"}, status=404)
            
            # Delete associated data first if needed or rely on cascade
            await session.delete(user)
            await session.commit()
            return web.json_response({"ok": True})
    except Exception as e:
        return web.json_response({"ok": False, "error": "server_error"}, status=500)

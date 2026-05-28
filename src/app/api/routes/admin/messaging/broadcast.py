from app.utils.admin_bot_helper import resolve_user_bot

from ..common import *  # noqa: F403


async def handle_admin_broadcast(request: web.Request):
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"ok": False, "error": "invalid_json"}, status=400)
    
    # Validate input using Pydantic schema
    validated, error = validate_request(AdminBroadcastRequest, data)
    if error:
        return web.json_response(error, status=400)
    
    message = validated.message
            
    try:
        # Logic to broadcast via bot
        # This usually requires access to the bot instance
        bot = resolve_user_bot(request.app.get("bot"))
        if not bot:
             return web.json_response({"ok": False, "error": "bot_not_available"}, status=500)
             
        # Start broadcast task (simplified)
        # In production, queue this
        async with AsyncSessionLocal() as session:
             users = await session.scalars(select(User.chat_id))
             count = 0
             for chat_id in users:
                 try:
                     await bot.send_message(chat_id, message)
                     count += 1
                 except Exception:
                     pass
        
        return web.json_response({"ok": True, "sent_count": count})
    except Exception as e:
        return web.json_response({"ok": False, "error": "server_error"}, status=500)

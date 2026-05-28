from app.utils.admin_bot_helper import resolve_user_bot

from ..common import *  # noqa: F403


async def handle_admin_send_notification(request: web.Request):
    """Send notification to users (webapp/bot)"""
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"ok": False, "error": "invalid_json"}, status=400)
    
    # Validate input using Pydantic schema
    validated, error = validate_request(AdminSendNotificationRequest, data)
    if error:
        return web.json_response(error, status=400)
    
    title = validated.title
    message = validated.message
    target = validated.target
    send_to_webapp = validated.send_to_webapp
    send_to_bot = validated.send_to_bot
    user_ids = validated.user_ids or []
    
    try:
        async with AsyncSessionLocal() as session:
            count = 0
            if target == 'all':
                # Send to all users
                count = await notifications_crud.send_notification_to_all_users(
                    db=session,
                    title=title,
                    message=message,
                    sent_to_webapp=send_to_webapp,
                    sent_to_bot=send_to_bot
                )
            else:  # target == 'specific' (already validated by schema)
                # Send to specific users
                count = await notifications_crud.send_general_notification_to_users(
                    db=session,
                    user_ids=user_ids,
                    title=title,
                    message=message,
                    sent_to_webapp=send_to_webapp,
                    sent_to_bot=send_to_bot
                )
            
            # If bot notifications enabled, send them now
            if send_to_bot:
                bot = resolve_user_bot(request.app.get("bot"))
                if bot:
                    try:
                        bot_sent = await notifications_crud.process_pending_bot_notifications(
                            db=session,
                            bot=bot,
                        )
                        print(f"[NOTIF] Sent {bot_sent} bot notifications")
                    except Exception as e:
                        print(f"[NOTIF] Error sending bot notifications: {e}")
            
            return web.json_response({
                "ok": True,
                "count": count,
                "message": f"Notification sent to {count} users"
            })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return web.json_response({"ok": False, "error": "server_error"}, status=500)

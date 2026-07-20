from app.core.notification_catalog import NotificationType
from app.services.notify import notify

from ..common import *  # noqa: F403

import logging

logger = logging.getLogger(__name__)


async def handle_admin_send_notification(request: web.Request):
    """Send an admin broadcast to users through the notify() single write path.

    Each recipient gets one row (type `general`) and, when the admin picked
    "also send to bot", an immediately-stamped DM via dm_override. The old
    process_pending_bot_notifications sweep is gone from this path: it scanned
    ALL sent_to_bot rows with bot_message_sent=False, so a bot-enabled
    broadcast could replay stale rows from unrelated events.
    """
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
            if target == 'all':
                result = await session.execute(select(User.id))
                recipient_ids = [row[0] for row in result.all()]
            else:  # target == 'specific' (already validated by schema)
                recipient_ids = user_ids

            count = 0
            dm_sent = 0
            for uid in recipient_ids:
                notification = await notify(
                    session, uid, NotificationType.GENERAL,
                    {"title": title, "body": message},
                    dm_override=bool(send_to_bot),
                )
                if not send_to_webapp:
                    # Telegram-only broadcast: keep the row out of the dashboard
                    # center, as before.
                    notification.sent_to_webapp = False
                if notification.bot_message_sent:
                    dm_sent += 1
                count += 1
            await session.commit()

            if send_to_bot:
                logger.info(f"[NOTIF] Sent {dm_sent} bot notifications")

            return web.json_response({
                "ok": True,
                "count": count,
                "message": f"Notification sent to {count} users"
            })
    except Exception:
        import traceback
        traceback.print_exc()
        return web.json_response({"ok": False, "error": "server_error"}, status=500)

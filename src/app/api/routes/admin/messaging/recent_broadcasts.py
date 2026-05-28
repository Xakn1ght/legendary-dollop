from ..common import *  # noqa: F403


async def handle_admin_recent_broadcasts(request: web.Request):
    """Get recent broadcast notifications"""
    try:
        async with AsyncSessionLocal() as session:
            # Get notifications of type 'general' grouped by title+message
            # (to avoid duplicates for multi-user broadcasts)
            result = await session.execute(
                select(
                    Notification.title,
                    Notification.message,
                    Notification.sent_to_webapp,
                    Notification.sent_to_bot,
                    func.max(Notification.created_at).label('last_sent'),
                    func.count(Notification.id).label('recipient_count')
                ).where(
                    Notification.type == 'general'
                ).group_by(
                    Notification.title,
                    Notification.message,
                    Notification.sent_to_webapp,
                    Notification.sent_to_bot
                ).order_by(
                    func.max(Notification.created_at).desc()
                ).limit(10)
            )
            
            broadcasts = []
            for row in result:
                broadcasts.append({
                    "title": row.title,
                    "message": row.message,
                    "sent_to_webapp": row.sent_to_webapp,
                    "sent_to_bot": row.sent_to_bot,
                    "last_sent": row.last_sent.isoformat() if row.last_sent else None,
                    "recipient_count": row.recipient_count
                })
            
            return web.json_response({
                "ok": True,
                "broadcasts": broadcasts
            })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return web.json_response({"ok": False, "error": "server_error"}, status=500)

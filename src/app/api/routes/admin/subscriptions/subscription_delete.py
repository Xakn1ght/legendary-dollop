from app.core.notification_catalog import NotificationType
from app.services.notify import notify

from ..common import *  # noqa: F403


async def handle_admin_subscription_delete(request: web.Request):
    """Delete a user from PasarGuard"""
    username = request.match_info.get('username', '').strip()
    if not username or len(username) > 100:
        return web.json_response({"ok": False, "error": "invalid_username"}, status=400)
    
    try:
        # First find the user to notify before deleting
        user_to_notify = None
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Subscription).where(Subscription.marzban_username == username)
            )
            sub = result.scalar_one_or_none()
            if sub and sub.user_id:
                user_to_notify = await session.get(User, sub.user_id)
        
        success = await pasarguard_api.delete_user(username)
        if success:
            # Notification row + policy DM through the single write path (the
            # old ad-hoc plain DM duplicated the row content and is gone).
            if user_to_notify:
                async with AsyncSessionLocal() as session:
                    await notify(
                        session, user_to_notify.id, NotificationType.SUBSCRIPTION_DELETED,
                        {"service_name": username},
                    )
            
            from app.services.audit import record_audit

            await record_audit(
                request, "subscription.delete", target_type="subscription", target_id=username,
                summary=f"deleted panel user {username}",
            )
            return web.json_response({"ok": True, "message": "deleted"})
        else:
            return web.json_response({"ok": False, "error": "delete_failed"}, status=500)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return web.json_response({"ok": False, "error": "server_error"}, status=500)

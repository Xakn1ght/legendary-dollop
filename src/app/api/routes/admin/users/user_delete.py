from sqlalchemy.exc import IntegrityError

from ..common import *  # noqa: F403


async def handle_admin_user_delete(request: web.Request):
    try:
        user_id = int(request.match_info['user_id'])
    except (ValueError, KeyError):
        return web.json_response({"ok": False, "error": "invalid_user_id"}, status=400)
    try:
        async with AsyncSessionLocal() as session:
            user = await session.get(User, user_id)
            if not user:
                return web.json_response({"ok": False, "error": "not_found"}, status=404)

            # Clear non-financial owned rows that have no ON DELETE CASCADE
            # (notifications) so a plain user with only notifications deletes
            # cleanly instead of raising a raw 500 (audit fix).
            await session.execute(delete(Notification).where(Notification.user_id == user_id))

            try:
                await session.delete(user)
                await session.commit()
            except IntegrityError:
                # User still has financial/relational history (subscriptions,
                # receipts, VIP/charge orders, referrals). Refuse rather than
                # silently 500 or wipe money records; the admin should handle
                # those explicitly. Ban is the safe alternative.
                await session.rollback()
                return web.json_response(
                    {"ok": False, "error": "has_related_records",
                     "message": "User has subscriptions/orders/history; ban instead of delete."},
                    status=409,
                )

            from app.services.audit import record_audit

            await record_audit(
                request, "user.delete", target_type="user", target_id=user_id,
                summary="deleted user account",
            )
            return web.json_response({"ok": True})
    except Exception:
        return web.json_response({"ok": False, "error": "server_error"}, status=500)

from app.core.notification_catalog import NotificationType
from app.services.notify import notify
from app.utils.bot_i18n import normalize_lang

from ..common import *  # noqa: F403


async def handle_admin_user_update(request: web.Request):
    try:
        user_id = int(request.match_info['user_id'])
    except (ValueError, KeyError):
        return web.json_response({"ok": False, "error": "invalid_user_id"}, status=400)
    
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"ok": False, "error": "invalid_json"}, status=400)
    
    # Validate input using Pydantic schema
    validated, error = validate_request(AdminUserUpdateRequest, data)
    if error:
        return web.json_response(error, status=400)
    
    try:
        async with AsyncSessionLocal() as session:
            user = await session.get(User, user_id)
            if not user:
                return web.json_response({"ok": False, "error": "not_found"}, status=404)
            
            old_credit = user.credit
            old_banned = user.banned
            
            if validated.credit is not None:
                user.credit = validated.credit
            if validated.stars is not None:
                user.stars = validated.stars
            if validated.banned is not None:
                user.banned = validated.banned
            
            # Notifications for significant changes go through the notify()
            # single write path (row + policy DM; the old ad-hoc plain DMs
            # duplicated the row content and are gone).
            lang = normalize_lang(getattr(user, "language", None))

            # Credit change notification
            if validated.credit is not None and validated.credit != old_credit:
                credit_diff = validated.credit - old_credit
                await notify(
                    session, user.id, NotificationType.CREDIT_CHANGE,
                    {"delta": f"{credit_diff:+,}", "balance": f"{validated.credit:,}"},
                )

            # Ban/unban notification
            if validated.banned is not None and validated.banned != old_banned:
                if lang == "en":
                    status_word = "suspended" if validated.banned else "reactivated"
                else:
                    status_word = "مسدود" if validated.banned else "فعال"
                await notify(
                    session, user.id, NotificationType.ACCOUNT_STATUS,
                    {"status": status_word},
                )

            await session.commit()

            from app.services.audit import record_audit

            bits = []
            if validated.credit is not None and validated.credit != old_credit:
                bits.append(f"credit {old_credit:,}→{validated.credit:,}")
            if validated.banned is not None and validated.banned != old_banned:
                bits.append("BANNED" if validated.banned else "unbanned")
            if validated.stars is not None:
                bits.append(f"stars={validated.stars}")
            if bits:
                await record_audit(
                    request, "user.update", target_type="user", target_id=user_id,
                    summary=", ".join(bits),
                )
            return web.json_response({"ok": True})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return web.json_response({"ok": False, "error": "server_error"}, status=500)

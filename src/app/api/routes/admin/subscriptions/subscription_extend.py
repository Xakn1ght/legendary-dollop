from app.core.notification_catalog import NotificationType
from app.services.notify import notify
from app.utils.bot_i18n import normalize_lang

from ..common import *  # noqa: F403


async def handle_admin_subscription_extend(request: web.Request):
    """Extend or set a subscription's days/traffic/expiry"""
    username = request.match_info.get('username', '').strip()
    if not username or len(username) > 100:
        return web.json_response({"ok": False, "error": "invalid_username"}, status=400)
    
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"ok": False, "error": "invalid_json"}, status=400)
    if not isinstance(data, dict):
        return web.json_response({"ok": False, "error": "invalid_payload"}, status=400)

    # int() on unvalidated body (e.g. {"days": "abc"} or a JSON array) raised an
    # uncaught ValueError/TypeError → raw 500 (audit fix).
    try:
        days = int(data.get('days', 0) or 0)
        traffic_gb = int(data.get('traffic_gb', 0) or 0)
    except (ValueError, TypeError):
        return web.json_response({"ok": False, "error": "invalid_values"}, status=400)
    traffic_mode = str(data.get('traffic_mode', 'add')).lower()
    days_mode = str(data.get('days_mode', 'add')).lower()
    expire_at_raw = data.get('expire_at')  # epoch seconds or ISO string from UI
    
    if days < 0 or traffic_gb < 0:
        return web.json_response({"ok": False, "error": "invalid_values"}, status=400)
    
    if traffic_mode not in ('add', 'set', 'reset') or days_mode not in ('add', 'set'):
        return web.json_response({"ok": False, "error": "invalid_mode"}, status=400)
    
    try:
        # Get current user info from PasarGuard
        user_info = await pasarguard_api.get_user_info(username)
        if not user_info:
            return web.json_response({"ok": False, "error": "user_not_found"}, status=404)
        
        # Calculate new values
        current_expire = user_info.get('expire')
        current_limit = user_info.get('data_limit', 0) or 0
        
        update_data = {}
        
        # Expiry handling: explicit timestamp wins, otherwise days logic
        expire_ts = None
        if expire_at_raw:
            try:
                if isinstance(expire_at_raw, (int, float)):
                    expire_ts = int(expire_at_raw)
                elif isinstance(expire_at_raw, str):
                    from datetime import datetime, timezone
                    # Attempt ISO parse; treat naive as UTC
                    parsed = datetime.fromisoformat(expire_at_raw.replace('Z', '+00:00'))
                    if parsed.tzinfo is None:
                        parsed = parsed.replace(tzinfo=timezone.utc)
                    expire_ts = int(parsed.timestamp())
            except Exception:
                return web.json_response({"ok": False, "error": "invalid_expire_at"}, status=400)
        
        if expire_ts:
            update_data['expire'] = expire_ts
        elif days > 0:
            from datetime import datetime, timedelta, timezone
            base_dt = datetime.now(timezone.utc) if days_mode == 'set' or not current_expire else datetime.fromtimestamp(current_expire, tz=timezone.utc)
            new_expire_dt = base_dt + timedelta(days=days)
            update_data['expire'] = int(new_expire_dt.timestamp())
        
        # Traffic handling: add / set (convert GB to bytes) / reset (usage → 0).
        # 'reset' zeroes used traffic via PasarGuard's POST /reset while keeping the
        # current limit + expire (or the new expire computed above).
        if traffic_mode == 'reset':
            reset_expire = update_data.get('expire', current_expire or 0)
            success = await pasarguard_api.reset_user_traffic_bytes(username, int(current_limit or 0), int(reset_expire or 0))
            if not success:
                return web.json_response({"ok": False, "error": "panel_update_failed"}, status=500)
            update_data.pop('expire', None)  # already applied inside the reset call
        elif traffic_gb > 0 or (traffic_mode == 'set' and traffic_gb >= 0):
            if traffic_mode == 'set':
                new_limit = traffic_gb * 1024**3
            else:
                new_limit = current_limit + (traffic_gb * 1024**3)
            update_data['data_limit'] = new_limit

        if update_data:
            success = await pasarguard_api.update_user(username, update_data)
            if not success:
                return web.json_response({"ok": False, "error": "panel_update_failed"}, status=500)
            
            # Notification row + policy DM through the single write path (the
            # old ad-hoc plain DM duplicated the row content and is gone).
            async with AsyncSessionLocal() as session:
                # Find subscription and user
                result = await session.execute(
                    select(Subscription).where(Subscription.marzban_username == username)
                )
                sub = result.scalar_one_or_none()
                
                if sub and sub.user_id:
                    user = await session.get(User, sub.user_id)
                    if user:
                        # Language-matched summary of what was added
                        changes = []
                        if normalize_lang(getattr(user, "language", None)) == "en":
                            if days > 0:
                                changes.append(f"+{days} days")
                            if traffic_gb > 0:
                                changes.append(f"+{traffic_gb} GB")
                            changes_text = " and ".join(changes) if changes else "settings updated"
                        else:
                            if days > 0:
                                changes.append(f"+{days} روز")
                            if traffic_gb > 0:
                                changes.append(f"+{traffic_gb} GB ترافیک")
                            changes_text = " و ".join(changes) if changes else "تنظیمات بروزرسانی شد"

                        await notify(
                            session, user.id, NotificationType.SUBSCRIPTION_EXTENDED,
                            {"service_name": username, "changes": changes_text},
                        )
        
        if not update_data and traffic_mode != 'reset':
            return web.json_response({"ok": True, "message": "no_changes"})

        from app.services.audit import record_audit

        await record_audit(
            request, "subscription.extend", target_type="subscription", target_id=username,
            summary=f"+{days}d +{traffic_gb}GB mode={traffic_mode}",
        )
        return web.json_response({"ok": True, "message": "extended"})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return web.json_response({"ok": False, "error": "server_error"}, status=500)

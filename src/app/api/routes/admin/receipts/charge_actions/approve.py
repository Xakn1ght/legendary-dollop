from datetime import datetime

from aiohttp import web

from app.database import crud, notifications_crud
from app.database.models import AsyncSessionLocal
from app.services.marzban import marzban_api
from app.utils.admin_bot_helper import resolve_user_bot
from app.utils.bot_i18n import normalize_lang

try:
    from app.api.routes.admin_ws import broadcast_admin_event
except ImportError:

    async def broadcast_admin_event(*args, **kwargs):
        return


GB = 1024 * 1024 * 1024


async def handle_admin_approve_charge(request: web.Request):
    """Approve a pending charge request"""
    try:
        charge_id = int(request.match_info["charge_id"])
    except (ValueError, KeyError):
        return web.json_response({"ok": False, "error": "invalid_charge_id"}, status=400)
    try:
        user_bot = resolve_user_bot(request.app.get("bot"))

        async with AsyncSessionLocal() as session:
            charge_req = await crud.get_charge_request(session, charge_id)
            if not charge_req or charge_req.status != "pending":
                return web.json_response({"ok": False, "error": "not_found_or_processed"}, status=404)

            await session.refresh(charge_req, attribute_names=["subscription", "user"])
            sub = charge_req.subscription
            user = charge_req.user

            if not sub or not sub.marzban_username:
                return web.json_response({"ok": False, "error": "invalid_subscription"}, status=400)
            if not user:
                return web.json_response({"ok": False, "error": "user_not_found"}, status=404)

            user_info = await marzban_api.get_user_info(sub.marzban_username)
            if not user_info:
                return web.json_response({"ok": False, "error": "marzban_fetch_failed"}, status=500)

            now_ts = datetime.utcnow().timestamp()
            expire_ts = user_info.get("expire", 0) or 0
            data_limit_current = user_info.get("data_limit", 0) or 0
            used_traffic = user_info.get("used_traffic", 0) or 0

            remaining_bytes_current = max(data_limit_current - used_traffic, 0)
            expired = bool(expire_ts and expire_ts < now_ts)
            traffic_exhausted = remaining_bytes_current == 0
            subscription_ended = expired or traffic_exhausted

            new_expire_ts = expire_ts or 0
            reset_usage = False

            carry_bytes = 0
            lost_bytes = 0
            reset_at = None

            add_days_only = bool(charge_req.extra_days) and not (charge_req.traffic_bytes and charge_req.traffic_bytes > 0)
            is_5gb_limit_charge = getattr(charge_req, "charge_type", "normal") == "normal_5gb_limit"

            if add_days_only:
                base = now_ts if expired else (expire_ts or now_ts)
                new_expire_ts = int(base + charge_req.extra_days * 24 * 3600)
                data_limit_after = data_limit_current
            elif subscription_ended:
                data_limit_after = data_limit_current
                if charge_req.traffic_bytes and charge_req.traffic_bytes > 0:
                    data_limit_after = int(charge_req.traffic_bytes)
                    reset_usage = True
                if charge_req.extra_days:
                    base = now_ts if expired else (expire_ts or now_ts)
                    new_expire_ts = int(base + charge_req.extra_days * 24 * 3600)
            else:
                remaining = remaining_bytes_current
                if is_5gb_limit_charge:
                    carry_bytes = min(remaining, 5 * GB)
                    lost_bytes = max(0, remaining - 5 * GB)
                    data_limit_after = carry_bytes + (charge_req.traffic_bytes or 0)
                    reset_usage = True
                    if charge_req.extra_days:
                        new_expire_ts = int(now_ts + charge_req.extra_days * 24 * 3600)
                elif remaining <= 5 * GB:
                    carry_bytes = remaining if (charge_req.traffic_bytes and charge_req.traffic_bytes > 0) else 0
                    data_limit_after = carry_bytes + (charge_req.traffic_bytes or 0)
                    reset_usage = True
                    if charge_req.extra_days:
                        new_expire_ts = int((expire_ts or now_ts) + charge_req.extra_days * 24 * 3600)
                else:
                    carry_bytes = min(remaining, 5 * GB) if (charge_req.traffic_bytes and charge_req.traffic_bytes > 0) else 0
                    lost_bytes = max(0, remaining - 5 * GB)
                    data_limit_after = carry_bytes + (charge_req.traffic_bytes or 0)
                    reset_usage = True
                    if charge_req.extra_days:
                        new_expire_ts = int((expire_ts or now_ts) + charge_req.extra_days * 24 * 3600)

            if reset_usage:
                ok = await marzban_api.reset_user_traffic_bytes(
                    sub.marzban_username,
                    new_data_limit_bytes=int(data_limit_after or 0),
                    new_expire_ts=int(new_expire_ts or 0),
                )
                if not ok:
                    return web.json_response({"ok": False, "error": "marzban_reset_update_failed"}, status=500)
            else:
                session_http = await marzban_api._get_session()
                headers = await marzban_api._get_headers()
                url = f"{marzban_api.base_url}/api/user/{sub.marzban_username}"
                patch_body = {
                    "data_limit": int(data_limit_after or 0),
                    "expire": int(new_expire_ts or 0),
                    "status": "active",
                    "data_limit_reset_strategy": "no_reset",
                }
                async with session_http.put(url, headers=headers, json=patch_body) as resp:
                    if resp.status not in (200, 204):
                        return web.json_response({"ok": False, "error": "marzban_update_failed"}, status=500)

            await crud.set_subscription_carry_over(session, sub.id, carry_bytes, reset_at)
            await crud.update_charge_request_status(session, charge_id, "approved")
            await session.commit()

            if user_bot and user:
                try:
                    traffic_gb = (charge_req.traffic_bytes or 0) / (1024 * 1024 * 1024)
                    msg = f"✅ شارژ شما تایید شد!\n\n"
                    msg += f"📦 سرویس: {sub.marzban_username}\n"
                    if charge_req.traffic_bytes:
                        msg += f"📊 حجم اضافه شده: {traffic_gb:.1f} GB\n"
                    if charge_req.extra_days:
                        msg += f"📅 روز اضافه شده: {charge_req.extra_days} روز\n"
                    if carry_bytes:
                        msg += f"🔹 انتقال از دوره قبل: {(carry_bytes / GB):.1f} GB\n"
                    if lost_bytes and lost_bytes > 0 and is_5gb_limit_charge:
                        msg += f"⚠️ {lost_bytes/GB:.1f} GB بیش از حد 5GB حذف شد.\n"
                    await user_bot.send_message(user.chat_id, msg)
                except Exception:
                    pass

            try:
                if user:
                    traffic_gb = (charge_req.traffic_bytes or 0) / GB
                    user_lang = normalize_lang(getattr(user, "language", None)) or "fa"

                    if user_lang == "fa":
                        title = "شارژ تایید شد"
                        message = (
                            f"شارژ شما تایید شد!\n\n"
                            f"سرویس: {sub.marzban_username}\n"
                            f"حجم اضافه شده: {traffic_gb:.0f} گیگابایت"
                            + (f"\nروز اضافه شده: {charge_req.extra_days} روز" if charge_req.extra_days else "")
                            + (f"\nحجم منتقل شده: {(carry_bytes / GB):.1f} گیگابایت" if carry_bytes else "")
                        )
                    else:
                        title = "Charge approved"
                        message = (
                            f"Your charge has been approved!\n\n"
                            f"Service: {sub.marzban_username}\n"
                            f"Added: {traffic_gb:.0f}GB"
                            + (f"\nExtra days: {charge_req.extra_days} days" if charge_req.extra_days else "")
                            + (f"\nCarried over: {(carry_bytes / GB):.1f}GB" if carry_bytes else "")
                        )
                    await notifications_crud.create_notification(
                        session,
                        user_id=user.id,
                        type="charge_approved",
                        title=title,
                        message=message,
                        sent_to_webapp=True,
                        sent_to_bot=False,
                    )
            except Exception:
                pass

            try:
                await broadcast_admin_event("receipts_updated", {"order_id": charge_id, "type": "charge"})
            except Exception:
                pass

            return web.json_response({"ok": True, "message": "approved"})
    except Exception:
        import traceback

        traceback.print_exc()
        return web.json_response({"ok": False, "error": "server_error"}, status=500)

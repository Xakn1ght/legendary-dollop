from aiohttp import web

from app.database import crud, notifications_crud
from app.database.models import AsyncSessionLocal
from app.utils.admin_bot_helper import resolve_user_bot

try:
    from app.api.routes.admin_ws import broadcast_admin_event
except ImportError:

    async def broadcast_admin_event(*args, **kwargs):
        return


async def handle_admin_deny_charge(request: web.Request):
    """Deny a pending charge request"""
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
            user = charge_req.user
            sub = charge_req.subscription

            if hasattr(charge_req, "credit_used") and charge_req.credit_used and charge_req.credit_used > 0:
                if user:
                    user.credit = (user.credit or 0) + charge_req.credit_used

            await crud.update_charge_request_status(session, charge_id, "denied")
            await session.commit()

            if user_bot and user:
                try:
                    msg = f"❌ متاسفانه درخواست شارژ شما رد شد.\n\n"
                    msg += f"📦 سرویس: {sub.marzban_username if sub else 'نامشخص'}\n"
                    msg += "لطفاً با پشتیبانی تماس بگیرید."
                    await user_bot.send_message(user.chat_id, msg)
                except Exception:
                    pass

            try:
                if user:
                    await notifications_crud.create_notification(
                        session,
                        user_id=user.id,
                        type="charge_denied",
                        title="Charge denied",
                        message=f"❌ Your charge request for {sub.marzban_username if sub else 'your service'} was denied.",
                        sent_to_webapp=True,
                        sent_to_bot=False,
                    )
            except Exception:
                pass

            try:
                await broadcast_admin_event("receipts_updated", {"order_id": charge_id, "type": "charge"})
            except Exception:
                pass

            return web.json_response({"ok": True, "message": "denied"})
    except Exception:
        import traceback

        traceback.print_exc()
        return web.json_response({"ok": False, "error": "server_error"}, status=500)

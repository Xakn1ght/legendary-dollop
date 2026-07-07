from aiohttp import web

from app.database import crud, notifications_crud
from app.database.models import AsyncSessionLocal
from app.services.flows.charge import deny_charge
from app.services.flows.errors import FlowError
from app.utils.admin_bot_helper import resolve_user_bot

try:
    from app.api.routes.admin_ws import broadcast_admin_event
except ImportError:

    async def broadcast_admin_event(*args, **kwargs):
        return


async def handle_admin_deny_charge(request: web.Request):
    """Deny a pending charge request (refunds any reserved credit)."""
    try:
        charge_id = int(request.match_info["charge_id"])
    except (ValueError, KeyError):
        return web.json_response({"ok": False, "error": "invalid_charge_id"}, status=400)
    try:
        user_bot = resolve_user_bot(request.app.get("bot"))

        async with AsyncSessionLocal() as session:
            try:
                result = await deny_charge(session, charge_id)
            except FlowError:
                return web.json_response({"ok": False, "error": "not_found_or_processed"}, status=404)

            user = await crud.get_user_by_id(session, result.user_id)

            if user_bot and user:
                try:
                    msg = "❌ متاسفانه درخواست شارژ شما رد شد.\n\n"
                    msg += f"📦 سرویس: {result.service_name or 'نامشخص'}\n"
                    if result.credit_refunded > 0:
                        msg += f"💰 بازگشت اعتبار: {result.credit_refunded:,} تومان\n"
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
                        message=f"❌ Your charge request for {result.service_name or 'your service'} was denied.",
                        sent_to_webapp=True,
                        sent_to_bot=False,
                    )
            except Exception:
                pass

            try:
                await broadcast_admin_event("receipts_updated", {"order_id": charge_id, "type": "charge"})
            except Exception:
                pass

            from app.services.audit import record_audit

            await record_audit(
                request, "charge.deny", target_type="charge", target_id=charge_id,
                summary=f"denied charge (refund {result.credit_refunded:,} toman credit)",
            )
            return web.json_response({"ok": True, "message": "denied"})
    except Exception:
        import traceback

        traceback.print_exc()
        return web.json_response({"ok": False, "error": "server_error"}, status=500)

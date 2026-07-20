from aiohttp import web

from app.core.notification_catalog import NotificationType, charge_denied_ctx
from app.database import crud
from app.database.models import AsyncSessionLocal
from app.services.flows.charge import deny_charge
from app.services.flows.errors import FlowError
from app.services.notify import notify
from app.utils.bot_i18n import normalize_lang

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
        async with AsyncSessionLocal() as session:
            try:
                result = await deny_charge(session, charge_id)
            except FlowError:
                return web.json_response({"ok": False, "error": "not_found_or_processed"}, status=404)

            user = await crud.get_user_by_id(session, result.user_id)

            # Notification row + policy DM through the single write path (the
            # old ad-hoc plain DM duplicated the row content and is gone).
            try:
                if user:
                    ctx = charge_denied_ctx(
                        normalize_lang(getattr(user, "language", None)),
                        service_name=result.service_name,
                        credit_refunded=result.credit_refunded,
                    )
                    await notify(session, user.id, NotificationType.CHARGE_DENIED, ctx)
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

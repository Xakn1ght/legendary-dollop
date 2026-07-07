from aiohttp import web

from app.database.models import AsyncSessionLocal
from app.services.flows.charge import approve_charge
from app.services.flows.errors import FlowError
from app.utils.admin_bot_helper import resolve_user_bot

try:
    from app.api.routes.admin_ws import broadcast_admin_event
except ImportError:

    async def broadcast_admin_event(*args, **kwargs):
        return


_ERROR_STATUS = {
    "not_found_or_handled": 404,
    "user_missing": 404,
    "marzban_fetch_failed": 500,
    "marzban_reset_failed": 500,
    "marzban_update_failed": 500,
}


async def handle_admin_approve_charge(request: web.Request):
    """Approve a pending charge request (shared flows.charge.approve_charge:
    carry-over math, active-subscription check, referral rewards, renewal intent)."""
    try:
        charge_id = int(request.match_info["charge_id"])
    except (ValueError, KeyError):
        return web.json_response({"ok": False, "error": "invalid_charge_id"}, status=400)
    try:
        user_bot = resolve_user_bot(request.app.get("bot"))

        async with AsyncSessionLocal() as session:
            try:
                await approve_charge(session, charge_id, user_bot=user_bot)
            except FlowError as e:
                return web.json_response(
                    {"ok": False, "error": e.code}, status=_ERROR_STATUS.get(e.code, 400)
                )

            try:
                await broadcast_admin_event("receipts_updated", {"order_id": charge_id, "type": "charge"})
            except Exception:
                pass

            from app.services.audit import record_audit

            await record_audit(
                request, "charge.approve", target_type="charge", target_id=charge_id,
                summary="approved charge request",
            )
            return web.json_response({"ok": True, "message": "approved"})
    except Exception:
        import traceback

        traceback.print_exc()
        return web.json_response({"ok": False, "error": "server_error"}, status=500)

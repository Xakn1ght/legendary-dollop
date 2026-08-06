"""Admin panel cash-out decisions (parity with the bot's financial/cashout flow).

Approve marks the request paid — the admin confirms the card transfer happened.
The panel path carries no payout photo; the confirmation DM is text-only
(the bot flow can still attach a receipt photo).
"""
from aiohttp import web

from app.database import crud, notifications_crud
from app.database.models import AsyncSessionLocal
from app.services.audit import _session_identity, record_audit
from app.services.flows.cashout import approve_cashout, deny_cashout
from app.services.flows.errors import FlowError
from app.utils.admin_bot_helper import resolve_user_bot

try:
    from app.api.routes.admin_ws import broadcast_admin_event
except ImportError:

    async def broadcast_admin_event(*args, **kwargs):
        return


def _admin_chat_id(request) -> int | None:
    chat_id, _, _ = _session_identity(request)
    try:
        return int(chat_id) if chat_id else None
    except (TypeError, ValueError):
        return None


async def handle_admin_approve_cashout(request: web.Request):
    """POST /api/admin/cashouts/{cashout_id}/approve — mark a withdrawal paid."""
    try:
        cashout_id = int(request.match_info["cashout_id"])
    except (ValueError, KeyError):
        return web.json_response({"ok": False, "error": "invalid_cashout_id"}, status=400)
    try:
        user_bot = resolve_user_bot(request.app.get("bot"))

        async with AsyncSessionLocal() as session:
            try:
                req = await approve_cashout(
                    session,
                    cashout_id,
                    processed_by=_admin_chat_id(request),
                    admin_note="Paid via admin panel",
                )
            except FlowError as e:
                return web.json_response({"ok": False, "error": e.code}, status=404)

            user = await crud.get_user_by_id(session, req.user_id)

            if user_bot and user:
                try:
                    await user_bot.send_message(
                        user.chat_id,
                        f"درخواست برداشت شما پرداخت شد.\n\nکد: #{req.id}\nمبلغ: {req.amount:,} تومان",
                    )
                except Exception:
                    pass

            if user:
                try:
                    await notifications_crud.create_notification(
                        session,
                        user_id=user.id,
                        type="cashout_paid",
                        title="برداشت پرداخت شد",
                        message=f"درخواست برداشت #{req.id} به مبلغ {req.amount:,} تومان پرداخت شد.",
                        sent_to_webapp=True,
                        sent_to_bot=False,
                    )
                except Exception:
                    pass

            try:
                await broadcast_admin_event("receipts_updated", {"order_id": cashout_id, "type": "cashout"})
            except Exception:
                pass

            await record_audit(
                request, "cashout.approve", target_type="cashout", target_id=cashout_id,
                summary=f"paid {req.amount:,} toman to user #{req.user_id} ({req.destination or '-'})",
            )
            return web.json_response({"ok": True, "message": "approved"})
    except Exception:
        import traceback

        traceback.print_exc()
        return web.json_response({"ok": False, "error": "server_error"}, status=500)


async def handle_admin_deny_cashout(request: web.Request):
    """POST /api/admin/cashouts/{cashout_id}/deny — refund the reserved amount."""
    try:
        cashout_id = int(request.match_info["cashout_id"])
    except (ValueError, KeyError):
        return web.json_response({"ok": False, "error": "invalid_cashout_id"}, status=400)
    try:
        user_bot = resolve_user_bot(request.app.get("bot"))

        async with AsyncSessionLocal() as session:
            try:
                req = await deny_cashout(
                    session,
                    cashout_id,
                    processed_by=_admin_chat_id(request),
                    admin_note="Denied via admin panel",
                )
            except FlowError as e:
                return web.json_response({"ok": False, "error": e.code}, status=404)

            user = await crud.get_user_by_id(session, req.user_id)

            if user_bot and user:
                try:
                    await user_bot.send_message(
                        user.chat_id,
                        f"درخواست برداشت شما با کد #{req.id} رد شد.\n"
                        f"مبلغ {req.amount:,} تومان به کیف پول شما بازگردانده شد.",
                    )
                except Exception:
                    pass

            if user:
                try:
                    await notifications_crud.create_notification(
                        session,
                        user_id=user.id,
                        type="cashout_denied",
                        title="برداشت رد شد",
                        message=(
                            f"درخواست برداشت #{req.id} رد شد و مبلغ {req.amount:,} تومان "
                            "به کیف پول شما بازگشت."
                        ),
                        sent_to_webapp=True,
                        sent_to_bot=False,
                    )
                except Exception:
                    pass

            try:
                await broadcast_admin_event("receipts_updated", {"order_id": cashout_id, "type": "cashout"})
            except Exception:
                pass

            await record_audit(
                request, "cashout.deny", target_type="cashout", target_id=cashout_id,
                summary=f"denied cash-out (refund {req.amount:,} toman cashback)",
            )
            return web.json_response({"ok": True, "message": "denied"})
    except Exception:
        import traceback

        traceback.print_exc()
        return web.json_response({"ok": False, "error": "server_error"}, status=500)

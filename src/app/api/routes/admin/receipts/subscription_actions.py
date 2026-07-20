from app.core.notification_catalog import NotificationType, purchase_denied_ctx
from app.services.audit import record_audit
from app.services.notify import notify
from app.utils.bot_i18n import normalize_lang

from ..common import *  # noqa: F403


async def handle_admin_approve_receipt(request: web.Request):
    """Approve a pending subscription receipt"""
    try:
        sub_id = int(request.match_info['sub_id'])
    except (ValueError, KeyError):
        return web.json_response({"ok": False, "error": "invalid_sub_id"}, status=400)
    try:
        from app.utils.admin_bot_helper import resolve_user_bot

        bot = resolve_user_bot(request.app.get("bot"))
        if not bot:
            return web.json_response({"ok": False, "error": "bot_not_available"}, status=500)

        async with AsyncSessionLocal() as session:
            from app.handlers.admin.subscription import process_approved_subscription
            
            # Get subscription info for notification
            sub = await session.get(Subscription, sub_id)
            if not sub:
                return web.json_response({"ok": False, "error": "not_found"}, status=404)

            # Idempotency: if already processed, do not re-run activation/send link again
            if sub.status != 'pending':
                return web.json_response({"ok": True, "message": "already_processed"})

            user_id = sub.user_id if sub else None
            plan_name = sub.plan_name if sub else None
            service_name = sub.marzban_username if sub else None

            from app.services.audit import _session_identity
            _, panel_admin, _ = _session_identity(request)
            success = await process_approved_subscription(
                sub_id, session, bot, approved_by=(panel_admin or "پنل ادمین"),
            )
            
            if success:
                # Dashboard notification row; DM suppressed because
                # process_approved_subscription already sent the rich link DM.
                if user_id:
                    try:
                        await notify(
                            session, user_id, NotificationType.PURCHASE_APPROVED,
                            {"service_name": service_name or "-", "plan_name": plan_name or "-"},
                            dm_override=False,
                        )
                    except Exception:
                        pass

                # Notify other admin UIs to update instantly (remove this receipt from lists)
                try:
                    await broadcast_admin_event('receipts_updated', {'order_id': sub_id})
                except Exception:
                    pass

                await record_audit(
                    request, "receipt.approve", target_type="subscription", target_id=sub_id,
                    summary=f"approved {plan_name or '?'} for user #{user_id} ({service_name or '-'})",
                )
                return web.json_response({"ok": True, "message": "approved"})
            else:
                return web.json_response({"ok": False, "error": "activation_failed"}, status=500)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return web.json_response({"ok": False, "error": "server_error"}, status=500)


async def handle_admin_deny_receipt(request: web.Request):
    """Deny a pending subscription receipt"""
    try:
        sub_id = int(request.match_info['sub_id'])
    except (ValueError, KeyError):
        return web.json_response({"ok": False, "error": "invalid_sub_id"}, status=400)
    try:
        from app.utils.admin_bot_helper import get_admin_bot

        async with AsyncSessionLocal() as session:
            from app.services.flows.errors import FlowError
            from app.services.flows.purchase import deny_purchase_order

            try:
                result = await deny_purchase_order(session, sub_id)
            except FlowError as e:
                status = 404 if e.code == "not_found" else 400
                return web.json_response({"ok": False, "error": e.code}, status=status)

            user = await session.get(User, result.user_id)
            credit_refunded = result.credit_refunded
            discounts_restored = result.discounts_restored

            # Notification row + policy DM through the single write path (the
            # old ad-hoc plain DM duplicated the row content and is gone).
            if result.user_id:
                try:
                    ctx = purchase_denied_ctx(
                        normalize_lang(getattr(user, "language", None)),
                        service_name=result.service_name,
                        plan_name=result.plan_name,
                        credit_refunded=credit_refunded,
                        discounts_restored=discounts_restored,
                        coupon_restored=result.coupon_restored,
                    )
                    await notify(session, result.user_id, NotificationType.PURCHASE_DENIED, ctx)
                except Exception:
                    pass
            
            # Refresh in-bot admin pending requests list (messages live on admin bot)
            admin_bot = get_admin_bot()
            if admin_bot:
                try:
                    from app.handlers.admin.common import ADMIN_IDS, _send_pending_requests

                    for admin_id in ADMIN_IDS:
                        await _send_pending_requests(admin_bot, session, admin_id)
                except Exception:
                    pass

            # Notify other admin UIs to update instantly
            try:
                await broadcast_admin_event('receipts_updated', {'order_id': sub_id})
            except Exception:
                pass

            await record_audit(
                request, "receipt.deny", target_type="subscription", target_id=sub_id,
                summary=f"denied order (refund {credit_refunded:,} toman credit)",
            )
            return web.json_response({"ok": True, "message": "denied"})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return web.json_response({"ok": False, "error": "server_error"}, status=500)

from sqlalchemy import update as _sql_update

from app.core.notification_catalog import NotificationType, vip_duration_text
from app.services.audit import record_audit
from app.services.notify import notify

from ..common import *  # noqa: F403

import logging

logger = logging.getLogger(__name__)


async def _claim_vip_order(session, order_id: int) -> bool:
    """Atomic pending → processing claim so two concurrent approve/deny taps
    can't both proceed. Returns False when the order was already taken."""
    res = await session.execute(
        _sql_update(VipOrder)
        .where(VipOrder.id == order_id, VipOrder.status == 'pending')
        .values(status='processing')
    )
    await session.commit()
    return (res.rowcount or 0) > 0


async def _unclaim_vip_order(session, order_id: int) -> None:
    try:
        await session.execute(
            _sql_update(VipOrder)
            .where(VipOrder.id == order_id, VipOrder.status == 'processing')
            .values(status='pending')
        )
        await session.commit()
    except Exception:
        logger.exception(f"[VIP] could not release claim on order {order_id}")


async def _unclaim_vip_order_fresh(order_id: int) -> None:
    """Release a claim from a NEW session — safe to call from the outer except
    after the request's `async with` session has already closed/failed."""
    try:
        async with AsyncSessionLocal() as s:
            await _unclaim_vip_order(s, order_id)
    except Exception:
        logger.exception(f"[VIP] could not release claim (fresh) on order {order_id}")


async def handle_admin_approve_vip_order(request: web.Request):
    """Approve a pending VIP order"""
    try:
        order_id = int(request.match_info['order_id'])
    except (ValueError, KeyError):
        return web.json_response({"ok": False, "error": "invalid_order_id"}, status=400)
    
    try:
        async with AsyncSessionLocal() as session:
            if not await _claim_vip_order(session, order_id):
                vip_order = await session.get(VipOrder, order_id)
                if not vip_order:
                    return web.json_response({"ok": False, "error": "not_found"}, status=404)
                return web.json_response({"ok": True, "message": "already_processed"})

            vip_order = await session.get(VipOrder, order_id)
            user = await session.get(User, vip_order.user_id)
            if not user:
                await _unclaim_vip_order(session, order_id)
                return web.json_response({"ok": False, "error": "user_not_found"}, status=404)
            
            # Set VIP status on user
            from datetime import timedelta
            user.is_vip = True
            if vip_order.days and vip_order.days > 0:
                # If user already has VIP, extend from current expiry
                if user.vip_until and user.vip_until > datetime.utcnow():
                    user.vip_until = user.vip_until + timedelta(days=vip_order.days)
                else:
                    user.vip_until = datetime.utcnow() + timedelta(days=vip_order.days)
                duration_text = f"{vip_order.days} روز"
            else:
                # Lifetime VIP
                user.vip_until = None
                duration_text = "دائمی"
            
            # Mark order as approved
            vip_order.status = 'approved'

            # Notification row + policy DM through the single write path (the
            # old ad-hoc plain DM duplicated the row content and is gone).
            await notify(
                session, user.id, NotificationType.VIP_GRANTED,
                {"duration": vip_duration_text(getattr(user, "language", None), vip_order.days)},
            )

            await session.commit()
            
            # Broadcast to admin UIs
            try:
                await broadcast_admin_event('receipts_updated', {'order_id': order_id, 'type': 'vip'})
            except Exception:
                pass

            await record_audit(
                request, "vip.approve", target_type="vip", target_id=order_id,
                summary=f"VIP {duration_text} for user {user.chat_id} ({vip_order.price:,} toman)",
            )
            return web.json_response({"ok": True, "message": "approved"})
    except Exception:
        import traceback
        traceback.print_exc()
        # never leave the order wedged in 'processing'
        try:
            await _unclaim_vip_order_fresh(int(request.match_info['order_id']))
        except Exception:
            pass
        return web.json_response({"ok": False, "error": "server_error"}, status=500)


async def handle_admin_deny_vip_order(request: web.Request):
    """Deny a pending VIP order"""
    try:
        order_id = int(request.match_info['order_id'])
    except (ValueError, KeyError):
        return web.json_response({"ok": False, "error": "invalid_order_id"}, status=400)
    
    try:
        async with AsyncSessionLocal() as session:
            if not await _claim_vip_order(session, order_id):
                vip_order = await session.get(VipOrder, order_id)
                if not vip_order:
                    return web.json_response({"ok": False, "error": "not_found"}, status=404)
                return web.json_response({"ok": False, "error": "already_processed"}, status=400)

            vip_order = await session.get(VipOrder, order_id)
            user = await session.get(User, vip_order.user_id)
            
            # Mark order as denied
            vip_order.status = 'denied'

            # Notification row + policy DM through the single write path (the
            # old ad-hoc plain DM duplicated the row content and is gone).
            if user:
                await notify(session, user.id, NotificationType.VIP_DENIED, {})

            await session.commit()
            
            # Broadcast to admin UIs
            try:
                await broadcast_admin_event('receipts_updated', {'order_id': order_id, 'type': 'vip'})
            except Exception:
                pass

            await record_audit(
                request, "vip.deny", target_type="vip", target_id=order_id,
                summary=f"denied VIP order ({vip_order.price:,} toman)",
            )
            return web.json_response({"ok": True, "message": "denied"})
    except Exception:
        import traceback
        traceback.print_exc()
        try:
            await _unclaim_vip_order_fresh(int(request.match_info['order_id']))
        except Exception:
            pass
        return web.json_response({"ok": False, "error": "server_error"}, status=500)

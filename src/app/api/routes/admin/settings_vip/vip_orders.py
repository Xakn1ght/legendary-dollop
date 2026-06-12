from app.utils.admin_bot_helper import resolve_user_bot

from ..common import *  # noqa: F403

import logging

logger = logging.getLogger(__name__)


async def handle_admin_approve_vip_order(request: web.Request):
    """Approve a pending VIP order"""
    try:
        order_id = int(request.match_info['order_id'])
    except (ValueError, KeyError):
        return web.json_response({"ok": False, "error": "invalid_order_id"}, status=400)
    
    try:
        async with AsyncSessionLocal() as session:
            vip_order = await session.get(VipOrder, order_id)
            if not vip_order:
                return web.json_response({"ok": False, "error": "not_found"}, status=404)
            
            if vip_order.status != 'pending':
                return web.json_response({"ok": True, "message": "already_processed"})
            
            user = await session.get(User, vip_order.user_id)
            if not user:
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
            
            # Create notification
            await notifications_crud.create_notification(
                db=session,
                user_id=user.id,
                type='vip_granted',
                title='تبریک! VIP فعال شد',
                message=f'اشتراک VIP شما فعال شد ({duration_text}). از مزایای ویژه لذت ببرید!',
                sent_to_webapp=True,
                sent_to_bot=True
            )
            
            await session.commit()
            
            # Send Telegram notification
            bot = resolve_user_bot(request.app.get('bot'))
            if bot and user.chat_id:
                try:
                    vip_msg = (
                        f"*تبریک! VIP فعال شد*\n\n"
                        f"اشتراک VIP شما با موفقیت فعال شد.\n"
                        f"مدت: {duration_text}\n\n"
                        f"از مزایای ویژه VIP لذت ببرید!"
                    )
                    await bot.send_message(chat_id=user.chat_id, text=vip_msg, parse_mode='Markdown')
                except Exception as e:
                    logger.warning(f"[VIP] Failed to send VIP notification: {e}")
            
            # Broadcast to admin UIs
            try:
                await broadcast_admin_event('receipts_updated', {'order_id': order_id, 'type': 'vip'})
            except Exception:
                pass
            
            return web.json_response({"ok": True, "message": "approved"})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return web.json_response({"ok": False, "error": "server_error"}, status=500)


async def handle_admin_deny_vip_order(request: web.Request):
    """Deny a pending VIP order"""
    try:
        order_id = int(request.match_info['order_id'])
    except (ValueError, KeyError):
        return web.json_response({"ok": False, "error": "invalid_order_id"}, status=400)
    
    try:
        async with AsyncSessionLocal() as session:
            vip_order = await session.get(VipOrder, order_id)
            if not vip_order:
                return web.json_response({"ok": False, "error": "not_found"}, status=404)
            
            if vip_order.status != 'pending':
                return web.json_response({"ok": False, "error": "already_processed"}, status=400)
            
            user = await session.get(User, vip_order.user_id)
            
            # Mark order as denied
            vip_order.status = 'denied'
            
            # Create notification for user
            if user:
                await notifications_crud.create_notification(
                    db=session,
                    user_id=user.id,
                    type='vip_denied',
                    title='❌ درخواست VIP رد شد',
                    message='درخواست خرید VIP شما رد شد. برای اطلاعات بیشتر با پشتیبانی تماس بگیرید.',
                    sent_to_webapp=True,
                    sent_to_bot=True
                )
            
            await session.commit()
            
            # Send Telegram notification
            bot = resolve_user_bot(request.app.get('bot'))
            if bot and user and user.chat_id:
                try:
                    msg = "❌ *درخواست VIP رد شد*\n\nدرخواست خرید VIP شما رد شد.\nبرای اطلاعات بیشتر با پشتیبانی تماس بگیرید."
                    await bot.send_message(chat_id=user.chat_id, text=msg, parse_mode='Markdown')
                except Exception:
                    pass
            
            # Broadcast to admin UIs
            try:
                await broadcast_admin_event('receipts_updated', {'order_id': order_id, 'type': 'vip'})
            except Exception:
                pass
            
            return web.json_response({"ok": True, "message": "denied"})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return web.json_response({"ok": False, "error": "server_error"}, status=500)

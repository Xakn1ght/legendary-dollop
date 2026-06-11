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
            
            success = await process_approved_subscription(sub_id, session, bot)
            
            if success:
                # Create dashboard notification
                if user_id:
                    try:
                        notif_msg = f'سرویس "{service_name}" ({plan_name}) با موفقیت فعال شد.' if service_name else f'سرویس {plan_name or "شما"} با موفقیت فعال شد.'
                        notif_msg += ' از داشبورد می‌توانید اطلاعات اتصال را مشاهده کنید.'
                        await notifications_crud.create_notification(
                            db=session,
                            user_id=user_id,
                            type='purchase_approved',
                            title='سرویس فعال شد',
                            message=notif_msg,
                            sent_to_webapp=True,
                            sent_to_bot=False
                        )
                    except Exception:
                        pass

                # Notify other admin UIs to update instantly (remove this receipt from lists)
                try:
                    await broadcast_admin_event('receipts_updated', {'order_id': sub_id})
                except Exception:
                    pass
                
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
        from app.utils.admin_bot_helper import get_admin_bot, resolve_user_bot

        user_bot = resolve_user_bot(request.app.get("bot"))

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

            # Notify user via user bot (embedded aiohttp may not set request.app["bot"])
            if user_bot and user:
                try:
                    msg = "❌ درخواست سرویس شما توسط ادمین رد شد."
                    details = []
                    if credit_refunded > 0:
                        details.append(f"بازگشت اعتبار: {credit_refunded:,} تومان")
                    if discounts_restored:
                        details.append("تخفیف‌های استفاده‌شده به حساب شما بازگردانده شد.")
                    if result.coupon_restored:
                        details.append("کوپن استفاده‌شده به حساب شما بازگردانده شد.")
                    if details:
                        msg += "\n" + "\n".join(details)
                    await user_bot.send_message(user.chat_id, msg)
                except Exception:
                    pass

            # Create dashboard notification
            if result.user_id:
                try:
                    service_name = result.service_name
                    plan_name = result.plan_name
                    notif_msg = f'درخواست سرویس "{service_name}" ({plan_name}) رد شد.' if service_name else "درخواست خرید سرویس شما رد شد."
                    if credit_refunded > 0:
                        notif_msg += f" اعتبار {credit_refunded:,} تومان به حساب شما برگشت."
                    if discounts_restored:
                        notif_msg += " تخفیف‌های استفاده‌شده بازگردانده شد."
                    await notifications_crud.create_notification(
                        db=session,
                        user_id=result.user_id,
                        type='purchase_denied',
                        title='❌ درخواست رد شد',
                        message=notif_msg,
                        sent_to_webapp=True,
                        sent_to_bot=False
                    )
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
            
            return web.json_response({"ok": True, "message": "denied"})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return web.json_response({"ok": False, "error": "server_error"}, status=500)

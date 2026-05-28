from ..common import *  # noqa: F403


async def handle_admin_receipt_detail(request: web.Request):
    """Get a single pending receipt by subscription id (used for WS-first instant injection)."""
    try:
        sub_id = int(request.match_info['sub_id'])
    except (ValueError, KeyError):
        return web.json_response({"ok": False, "error": "invalid_sub_id"}, status=400)
    try:
        async with AsyncSessionLocal() as session:
            sub = await session.get(Subscription, sub_id)
            if not sub:
                return web.json_response({"ok": False, "error": "not_found"}, status=404)

            # Only receipts that require admin action
            if sub.status != 'pending' or sub.receipt_message_id is None:
                return web.json_response({"ok": False, "error": "not_pending"}, status=404)

            user = await session.get(User, sub.user_id)

            from app.core.settings import PLANS
            plan_info = PLANS.get(sub.plan_name, {})

            # Calculate original price (before discounts)
            original_price = plan_info.get("price", 0)
            if sub.renewal_paid and sub.renewal_template:
                renewal_plan_info = PLANS.get(sub.renewal_template, {})
                original_price += renewal_plan_info.get("price", 0)

            # Check if user is/was VIP (VIP discounts are automatic and not stored in applied_discount_ids)
            from app.core.settings import VIP_PURCHASE_DISCOUNT_ENABLED, VIP_PURCHASE_DISCOUNT_PERCENT
            is_vip = user.is_vip if user else False
            has_vip_discount = is_vip and VIP_PURCHASE_DISCOUNT_ENABLED and VIP_PURCHASE_DISCOUNT_PERCENT > 0
            
            # Check if any discounts were applied
            has_any_discount = bool(sub.applied_discount_ids) or has_vip_discount
            
            # Calculate discount amount
            discount_amount = 0
            if has_any_discount:
                # Calculate total discount percentage
                total_discount_percent = 0
                if has_vip_discount:
                    total_discount_percent += VIP_PURCHASE_DISCOUNT_PERCENT
                # Add other discounts if any
                if sub.applied_discount_ids and sub.applied_discount_ids.strip():
                    try:
                        from app.database.models import UserDiscount
                        discount_ids = [int(x.strip()) for x in sub.applied_discount_ids.split(',') if x.strip() and x.strip().isdigit()]
                        if discount_ids:
                            discount_result = await session.execute(
                                select(UserDiscount).where(UserDiscount.id.in_(discount_ids))
                            )
                            discounts = discount_result.scalars().all()
                            for d in discounts:
                                if d and d.percent:
                                    total_discount_percent += d.percent
                    except Exception as e:
                        # If discount lookup fails, continue without it
                        import logging
                        logging.warning(f"Failed to load discounts for subscription {sub.id}: {e}")
                        pass
                
                total_discount_percent = max(0, min(int(total_discount_percent), 90))
                if total_discount_percent > 0:
                    discount_amount = int(original_price * (total_discount_percent / 100))
            
            # Calculate price after discount
            price_after_discount = original_price - discount_amount
            
            # Calculate final paid price (after discount and credit)
            credit_used = sub.credit_used or 0
            total = price_after_discount - credit_used
            
            # Only show original_price if there was a discount
            if not has_any_discount or discount_amount == 0:
                original_price = None

            # Count notifications for this receipt
            notification_count = await session.scalar(
                select(func.count(Notification.id)).where(
                    and_(
                        Notification.user_id == user.id if user else None,
                        Notification.type == 'purchase_approved'
                    )
                )
            ) or 0
            
            receipt = {
                "id": sub.id,
                "user_id": user.id if user else None,
                "user_chat_id": user.chat_id if user else None,
                "user_name": user.full_name if user else "Unknown User",
                "username": user.username if user else None,
                "plan_name": sub.plan_name,
                "plan_gb": plan_info.get("gb", 0),
                "service_name": sub.marzban_username,
                "price": total,
                "original_price": original_price,
                "discount_amount": discount_amount,
                "credit_used": sub.credit_used or 0,
                "has_discounts": has_any_discount,
                "is_vip": is_vip,
                "auto_renewal": sub.renewal_paid,
                "renewal_plan": sub.renewal_template,
                "renewal_price": sub.renewal_price,
                "notification_count": notification_count,
                "is_web_receipt": sub.receipt_message_id == -1,
                "receipt_image_url": getattr(sub, "receipt_image_url", None),
                "receipt_message_id": sub.receipt_message_id if sub.receipt_message_id != -1 else None,
                "created_at": sub.created_at.isoformat() if sub.created_at else None,
            }
            return web.json_response({"ok": True, "receipt": receipt})
    except Exception:
        import traceback
        traceback.print_exc()
        return web.json_response({"ok": False, "error": "server_error"}, status=500)

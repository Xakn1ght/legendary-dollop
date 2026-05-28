from ..common import *  # noqa: F403


async def handle_admin_pending_receipts(request: web.Request):
    """Get pending subscription receipts and VIP orders for admin approval"""
    try:
        async with AsyncSessionLocal() as session:
            receipts_data = []
            
            # Get pending subscriptions with receipt_message_id set
            stmt = (
                select(Subscription)
                .where(Subscription.status == 'pending')
                .where(Subscription.receipt_message_id != None)
                .order_by(Subscription.created_at.desc())
            )
            result = await session.execute(stmt)
            pending_subs = result.scalars().all()
            
            for sub in pending_subs:
                try:
                    # Get user info
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
                        if sub.applied_discount_ids and str(sub.applied_discount_ids).strip():
                            try:
                                from app.database.models import UserDiscount
                                discount_ids = [int(x.strip()) for x in str(sub.applied_discount_ids).split(',') if x.strip() and x.strip().isdigit()]
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
                except Exception as e:
                    import logging
                    import traceback
                    logging.error(f"Error processing subscription {sub.id}: {e}")
                    traceback.print_exc()
                    # Fallback to simple calculation if discount calculation fails
                    original_price = plan_info.get("price", 0)
                    if sub.renewal_paid and sub.renewal_price:
                        original_price += sub.renewal_price
                    total = (sub.price or original_price) + (sub.renewal_price or 0) - (sub.credit_used or 0)
                    discount_amount = 0
                    has_any_discount = False
                    is_vip = user.is_vip if user else False
                
                # Count notifications for this receipt (purchase_approved type)
                from app.database.models import Notification
                notification_count = 0
                if user:
                    try:
                        notification_count = await session.scalar(
                            select(func.count(Notification.id)).where(
                                and_(
                                    Notification.user_id == user.id,
                                    Notification.type == 'purchase_approved'
                                )
                            )
                        ) or 0
                    except Exception:
                        notification_count = 0
                
                receipts_data.append({
                    "id": sub.id,
                    "type": "subscription",
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
                    "created_at": sub.created_at.isoformat() if sub.created_at else None
                })
            
            # Get pending VIP orders
            vip_stmt = (
                select(VipOrder)
                .where(VipOrder.status == 'pending')
                .order_by(VipOrder.created_at.desc())
            )
            vip_result = await session.execute(vip_stmt)
            pending_vip_orders = vip_result.scalars().all()
            
            from app.core.settings import VIP_PLANS
            for vip_order in pending_vip_orders:
                user = await session.get(User, vip_order.user_id)
                vip_plan = VIP_PLANS.get(vip_order.plan_id, {})
                
                receipts_data.append({
                    "id": vip_order.id,
                    "type": "vip",
                    "user_id": user.id if user else None,
                    "user_chat_id": user.chat_id if user else None,
                    "user_name": user.full_name if user else "Unknown User",
                    "username": user.username if user else None,
                    "plan_name": f"VIP {vip_plan.get('label', vip_order.plan_id)}",
                    "plan_gb": None,
                    "service_name": None,
                    "price": vip_order.price,
                    "credit_used": 0,
                    "has_discounts": False,
                    "auto_renewal": False,
                    "renewal_plan": None,
                    "is_web_receipt": True,
                    "receipt_image_url": vip_order.receipt_image_url,
                    "receipt_message_id": None,
                    "vip_days": vip_order.days,
                    "created_at": vip_order.created_at.isoformat() if vip_order.created_at else None
                })
            
            # Get pending charge requests
            charge_stmt = (
                select(ChargeRequest)
                .where(ChargeRequest.status == 'pending')
                .where(ChargeRequest.receipt_message_id != None)
                .order_by(ChargeRequest.created_at.desc())
            )
            charge_result = await session.execute(charge_stmt)
            pending_charges = charge_result.scalars().all()
            
            from app.core.settings import CHARGE_PRESET_PACKAGES, VIP_DISCOUNT_PERCENT
            for charge in pending_charges:
                user = await session.get(User, charge.user_id)
                sub = await session.get(Subscription, charge.subscription_id)
                
                # Check VIP status and discount
                is_vip = user.is_vip if user else False
                has_vip_discount = is_vip and VIP_DISCOUNT_PERCENT > 0
                
                # Calculate discount if VIP
                discount_amount = 0
                original_price = charge.price
                if has_vip_discount:
                    discount_amount = int(charge.price * (VIP_DISCOUNT_PERCENT / 100))
                    original_price = charge.price + discount_amount  # Show original before discount
                
                # Find package name
                traffic_gb = charge.traffic_bytes / (1024 * 1024 * 1024) if charge.traffic_bytes else 0
                package_name = f"{traffic_gb:.0f} GB" if traffic_gb > 0 else ""
                if charge.extra_days:
                    if package_name:
                        package_name += f" + {charge.extra_days} Days"
                    else:
                        package_name = f"{charge.extra_days} Days"
                
                receipts_data.append({
                    "id": charge.id,
                    "type": "charge",
                    "user_id": user.id if user else None,
                    "user_chat_id": user.chat_id if user else None,
                    "user_name": user.full_name if user else "Unknown User",
                    "username": user.username if user else None,
                    "plan_name": package_name,
                    "plan_gb": traffic_gb,
                    "service_name": sub.marzban_username if sub else None,
                    "price": charge.price,
                    "original_price": original_price if has_vip_discount else None,
                    "discount_amount": discount_amount,
                    "credit_used": 0,
                    "has_discounts": has_vip_discount,
                    "is_vip": is_vip,
                    "auto_renewal": False,
                    "renewal_plan": None,
                    "is_web_receipt": charge.receipt_message_id == -1,
                    "receipt_image_url": getattr(charge, "receipt_image_url", None),
                    "receipt_message_id": charge.receipt_message_id if charge.receipt_message_id != -1 else None,
                    "charge_traffic_bytes": charge.traffic_bytes,
                    "charge_extra_days": charge.extra_days,
                    "created_at": charge.created_at.isoformat() if charge.created_at else None
                })
            
            # Sort all by created_at descending
            receipts_data.sort(key=lambda x: x.get('created_at') or '', reverse=True)
            
            return web.json_response({
                "ok": True,
                "receipts": receipts_data,
                "count": len(receipts_data)
            })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return web.json_response({"ok": False, "error": "server_error"}, status=500)

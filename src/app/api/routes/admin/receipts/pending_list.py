from ..common import *  # noqa: F403


async def handle_admin_pending_receipts(request: web.Request):
    """Get pending subscription receipts and VIP orders for admin approval"""
    try:
        # Verify aid: last-4 of OUR payment card so the admin can check the
        # receipt was sent to the right destination. Imported inside the
        # handler because save_payment_settings() rebinds the module global.
        from app.core.settings import PAYMENT_CARD_NUMBER
        _card_digits = "".join(ch for ch in str(PAYMENT_CARD_NUMBER or "") if ch.isdigit())
        # the env fallback is "6037-xxxx-xxxx-xxxx" (4 digits) — never surface it
        payto_last4 = _card_digits[-4:] if len(_card_digits) >= 8 else None

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
            
            from app.services.flows.pricing import get_plan_info, plan_display_name

            # Buyer history (verify aid): approve/deny track record per unique
            # buyer, two aggregate queries total — never one per order.
            sub_uids = {s.user_id for s in pending_subs if s.user_id is not None}
            sub_hist = {}
            if sub_uids:
                hist_rows = await session.execute(
                    select(
                        Subscription.user_id,
                        # "approved-ish": anything that made it past payment review
                        func.count(Subscription.id).filter(
                            Subscription.status.not_in(("draft", "pending", "cancelled"))
                        ),
                        # denied purchase orders are deleted by deny_purchase_order,
                        # so in practice this bucket counts cancellations
                        func.count(Subscription.id).filter(
                            Subscription.status.in_(("denied", "cancelled"))
                        ),
                    )
                    .where(Subscription.user_id.in_(sub_uids))
                    .group_by(Subscription.user_id)
                )
                sub_hist = {row[0]: (int(row[1] or 0), int(row[2] or 0)) for row in hist_rows}

            for sub in pending_subs:
                # Invoice numbers come from the STORED order fields — the same
                # figures the admin-bot caption shows (receipt_captions.py) and
                # the SMS auto-approver matches on. Never re-derive them from
                # today's catalog/discount config: custom («custom:<gb>») and
                # «@Nm» renewal templates aren't PLANS keys (a 1.2M booking used
                # to vanish from the total), and percentages drift over time.
                user = None
                plan_info = {}
                try:
                    user = await session.get(User, sub.user_id)
                    plan_info = get_plan_info(sub.plan_name) or {}
                except Exception:
                    pass

                is_vip = user.is_vip if user else False

                plan_price = sub.price if sub.price is not None else int(plan_info.get("price", 0) or 0)
                renewal_price = int(sub.renewal_price or 0) if sub.renewal_paid else 0
                base_total = int(plan_price or 0) + renewal_price
                credit_used = int(sub.credit_used or 0)
                # paid_amount = final_price stamped at order time (after discounts
                # AND credit) — the exact figure that must appear on the receipt.
                if sub.paid_amount is not None:
                    paid_total = int(sub.paid_amount)
                else:
                    paid_total = max(base_total - credit_used, 0)
                discount_amount = max(base_total - credit_used - paid_total, 0)
                has_any_discount = discount_amount > 0 or bool(sub.applied_discount_ids) or bool(sub.applied_coupon_id)

                renewal_plan_label = None
                if sub.renewal_paid and sub.renewal_template:
                    try:
                        renewal_plan_label = plan_display_name(sub.renewal_template)
                    except Exception:
                        renewal_plan_label = str(sub.renewal_template)

                # Same label the bot caption shows: «@Nm» keys render as the
                # scaled total («۱۸۰ گیگ | ۳ ماهه»), custom keys as «N گیگ | سفارشی».
                try:
                    plan_label = plan_display_name(sub.plan_name)
                except Exception:
                    plan_label = sub.plan_name

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
                    "plan_name": plan_label,
                    "plan_gb": plan_info.get("gb", 0),
                    "service_name": sub.marzban_username,
                    "price": paid_total,
                    "plan_price": plan_price,
                    "base_total": base_total,
                    "original_price": base_total if has_any_discount else None,
                    "discount_amount": discount_amount,
                    "credit_used": credit_used,
                    "has_discounts": has_any_discount,
                    "is_vip": is_vip,
                    "auto_renewal": sub.renewal_paid,
                    "renewal_plan": renewal_plan_label,
                    "renewal_price": renewal_price or None,
                    "notification_count": notification_count,
                    "is_web_receipt": sub.receipt_message_id == -1,
                    "receipt_image_url": getattr(sub, "receipt_image_url", None),
                    "receipt_message_id": sub.receipt_message_id if sub.receipt_message_id != -1 else None,
                    "payto_last4": payto_last4,
                    "buyer_approved_count": (sub_hist.get(sub.user_id) or (0, 0))[0],
                    "buyer_denied_count": (sub_hist.get(sub.user_id) or (0, 0))[1],
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
                    "plan_price": vip_order.price,
                    "base_total": vip_order.price,
                    "credit_used": 0,
                    "has_discounts": False,
                    "auto_renewal": False,
                    "renewal_plan": None,
                    "is_web_receipt": True,
                    "receipt_image_url": vip_order.receipt_image_url,
                    "receipt_message_id": None,
                    "vip_days": vip_order.days,
                    "payto_last4": payto_last4,
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
            
            # second (and last) buyer-history aggregate: charge track record
            charge_uids = {c.user_id for c in pending_charges if c.user_id is not None}
            charge_hist = {}
            if charge_uids:
                hist_rows = await session.execute(
                    select(
                        ChargeRequest.user_id,
                        func.count(ChargeRequest.id).filter(ChargeRequest.status == "approved"),
                        func.count(ChargeRequest.id).filter(ChargeRequest.status == "denied"),
                    )
                    .where(ChargeRequest.user_id.in_(charge_uids))
                    .group_by(ChargeRequest.user_id)
                )
                charge_hist = {row[0]: (int(row[1] or 0), int(row[2] or 0)) for row in hist_rows}

            for charge in pending_charges:
                user = await session.get(User, charge.user_id)
                sub = await session.get(Subscription, charge.subscription_id)
                
                is_vip = user.is_vip if user else False
                
                # Find package name
                traffic_gb = charge.traffic_bytes / (1024 * 1024 * 1024) if charge.traffic_bytes else 0
                package_name = f"{traffic_gb:.0f} GB" if traffic_gb > 0 else ""
                if charge.extra_days:
                    if package_name:
                        package_name += f" + {charge.extra_days} Days"
                    else:
                        package_name = f"{charge.extra_days} Days"
                
                # What the user actually transferred: the flow stores the net on
                # paid_amount (price minus reserved credit). Never re-derive
                # discounts here with today's percentages — charges price through
                # PLANS server-side and the stored numbers are the truth.
                credit_used = int(charge.credit_used or 0)
                base_total = int(charge.price or 0)
                paid_total = charge.paid_amount if charge.paid_amount is not None else max(base_total - credit_used, 0)

                # Bookings carry the next plan on renewal_template — surface it
                # like the purchase auto-renewal line so the drawer reads the same.
                booking_plan = None
                if getattr(charge, "charge_type", "") == "booking" and charge.renewal_template:
                    try:
                        booking_plan = plan_display_name(charge.renewal_template)
                    except Exception:
                        booking_plan = str(charge.renewal_template)

                receipts_data.append({
                    "id": charge.id,
                    "type": "charge",
                    "charge_type": getattr(charge, "charge_type", None) or "normal",
                    "user_id": user.id if user else None,
                    "user_chat_id": user.chat_id if user else None,
                    "user_name": user.full_name if user else "Unknown User",
                    "username": user.username if user else None,
                    "plan_name": package_name or booking_plan or "Top-up",
                    "plan_gb": traffic_gb,
                    "service_name": sub.marzban_username if sub else None,
                    "price": paid_total,
                    "plan_price": base_total,
                    "base_total": base_total,
                    "original_price": None,
                    "discount_amount": 0,
                    "credit_used": credit_used,
                    "has_discounts": False,
                    "is_vip": is_vip,
                    "auto_renewal": bool(booking_plan),
                    "renewal_plan": booking_plan,
                    "is_web_receipt": charge.receipt_message_id == -1,
                    "receipt_image_url": getattr(charge, "receipt_image_url", None),
                    "receipt_message_id": charge.receipt_message_id if charge.receipt_message_id != -1 else None,
                    "charge_traffic_bytes": charge.traffic_bytes,
                    "charge_extra_days": charge.extra_days,
                    "payto_last4": payto_last4,
                    "buyer_approved_count": (charge_hist.get(charge.user_id) or (0, 0))[0],
                    "buyer_denied_count": (charge_hist.get(charge.user_id) or (0, 0))[1],
                    "created_at": charge.created_at.isoformat() if charge.created_at else None
                })
            
            # Pending cash-outs (wallet withdrawals) — money decisions belong in
            # the same queue as receipts so nothing waits invisible in the bot.
            pending_cashouts = await crud.list_cashout_requests(session, status="pending", limit=100)
            for co in pending_cashouts:
                user = await session.get(User, co.user_id)
                receipts_data.append({
                    "id": co.id,
                    "type": "cashout",
                    "user_id": user.id if user else None,
                    "user_chat_id": user.chat_id if user else None,
                    "user_name": user.full_name if user else "Unknown User",
                    "username": user.username if user else None,
                    "plan_name": "Wallet cash-out",
                    "plan_gb": None,
                    "service_name": None,
                    "cashout_destination": co.destination,
                    "price": co.amount,
                    "plan_price": co.amount,
                    "base_total": co.amount,
                    "original_price": None,
                    "discount_amount": 0,
                    "credit_used": 0,
                    "has_discounts": False,
                    "is_vip": user.is_vip if user else False,
                    "auto_renewal": False,
                    "renewal_plan": None,
                    "is_web_receipt": True,
                    "receipt_image_url": None,
                    "receipt_message_id": None,
                    "created_at": co.requested_at.isoformat() if co.requested_at else None
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

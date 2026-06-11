"""Single source of truth for purchase price math.

Both checkout surfaces (webapp ``dashboard_purchase/start_purchase`` and the bot
purchase FSM) must price an order through :func:`quote_purchase` so the displayed
summary, the credit cap, and the auto-approve threshold can never disagree.

Rules (canonical, from the webapp implementation):
- VIP discount applies only when ``VIP_PURCHASE_DISCOUNT_ENABLED`` and uses
  ``VIP_PURCHASE_DISCOUNT_PERCENT``.
- ``GLOBAL_PURCHASE_DISCOUNTS`` percentages stack on top.
- User discounts stack too; the combined percent is capped at 90.
- One reward coupon per purchase (discount_percent capped via core/coupons,
  free_gb adds bonus GB at provisioning, price unchanged).
- Credit is capped to the post-discount amount due.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.coupons import coupon_discount_amount
from app.core.settings import (
    GLOBAL_PURCHASE_DISCOUNTS,
    PLANS,
    VIP_PURCHASE_DISCOUNT_ENABLED,
    VIP_PURCHASE_DISCOUNT_PERCENT,
)
from app.database import crud
from app.services.flows.errors import FlowError

MAX_TOTAL_DISCOUNT_PERCENT = 90

# Coupon types spendable at checkout today (Phase 1). Other types must be rejected,
# never silently consumed.
SUPPORTED_COUPON_TYPES = ("discount_percent", "free_gb")


class QuoteError(FlowError):
    """Raised when an order can't be priced."""


@dataclass
class CouponEffect:
    id: int
    coupon_type: str
    discount_amount: int = 0
    free_gb: int = 0


@dataclass
class PurchaseQuote:
    plan_name: str
    renewal_plan: str | None
    base_total: int                 # plan price + renewal price
    plan_price: int
    renewal_price: int
    discount_percent: int           # VIP + global + user discounts, capped
    discount_amount: int            # money removed by percent discounts + coupon
    coupon: CouponEffect | None
    credit_used: int
    final_price: int
    applied_discount_ids: list[int] = field(default_factory=list)

    @property
    def coupon_free_gb(self) -> int:
        return self.coupon.free_gb if self.coupon else 0


async def quote_purchase(
    session: AsyncSession,
    user,
    *,
    plan_name: str,
    renewal_plan: str | None = None,
    discount_ids: list[int] | None = None,
    coupon_id: int | None = None,
    use_credit: bool = False,
) -> PurchaseQuote:
    """Price a purchase for ``user``. Pure computation — consumes nothing.

    Raises QuoteError(code) with codes: invalid_plan, invalid_renewal_plan,
    invalid_coupon, coupon_not_supported_yet.
    """
    if plan_name not in PLANS:
        raise QuoteError("invalid_plan", "Selected plan does not exist")
    if renewal_plan is not None and renewal_plan not in PLANS:
        raise QuoteError("invalid_renewal_plan", "Invalid renewal plan selected")

    plan_price = int(PLANS[plan_name].get("price") or 0)
    renewal_price = int(PLANS[renewal_plan].get("price") or 0) if renewal_plan else 0
    base_total = plan_price + renewal_price

    total_discount_percent = 0
    if await crud.is_user_vip(session, user.id) and VIP_PURCHASE_DISCOUNT_ENABLED and VIP_PURCHASE_DISCOUNT_PERCENT > 0:
        total_discount_percent += VIP_PURCHASE_DISCOUNT_PERCENT
    for item in GLOBAL_PURCHASE_DISCOUNTS or []:
        try:
            pct = int(item.get("percent") or 0)
        except Exception:
            pct = 0
        if pct > 0:
            total_discount_percent += pct

    applied_discount_ids: list[int] = []
    if discount_ids:
        active = await crud.get_active_user_discounts(session, user.id)
        for d in active:
            if d.id in discount_ids:
                total_discount_percent += d.percent
                applied_discount_ids.append(d.id)

    total_discount_percent = max(0, min(int(total_discount_percent), MAX_TOTAL_DISCOUNT_PERCENT))

    discount_amount = int(base_total * (total_discount_percent / 100)) if total_discount_percent > 0 else 0

    coupon_effect = None
    if coupon_id:
        coupon_effect = await _validate_coupon(session, user, coupon_id, base_total)

    if coupon_effect:
        discount_amount += coupon_effect.discount_amount
    if discount_amount > base_total:
        discount_amount = base_total

    price_after_discount = base_total - discount_amount

    credit_used = 0
    if use_credit and (user.credit or 0) > 0:
        credit_used = min(int(user.credit or 0), price_after_discount)

    return PurchaseQuote(
        plan_name=plan_name,
        renewal_plan=renewal_plan,
        base_total=base_total,
        plan_price=plan_price,
        renewal_price=renewal_price,
        discount_percent=total_discount_percent,
        discount_amount=discount_amount,
        coupon=coupon_effect,
        credit_used=credit_used,
        final_price=price_after_discount - credit_used,
        applied_discount_ids=applied_discount_ids,
    )


async def _validate_coupon(session: AsyncSession, user, coupon_id: int, base_total: int) -> CouponEffect:
    """Ownership / active / expiry / supported-type checks for a checkout coupon."""
    coupon = await crud.get_coupon_by_id(session, coupon_id)
    now = datetime.utcnow()
    if (
        not coupon
        or coupon.user_id != user.id
        or coupon.status != "active"
        or (coupon.expires_at and coupon.expires_at < now)
    ):
        raise QuoteError("invalid_coupon", "Coupon not available")

    try:
        payload = json.loads(coupon.payload or "{}")
    except Exception:
        payload = {}

    if coupon.coupon_type == "discount_percent":
        pct = int(payload.get("discount_percent") or 0)
        return CouponEffect(
            id=coupon.id,
            coupon_type=coupon.coupon_type,
            discount_amount=coupon_discount_amount(pct, base_total),
        )
    if coupon.coupon_type == "free_gb":
        return CouponEffect(
            id=coupon.id,
            coupon_type=coupon.coupon_type,
            free_gb=int(payload.get("gb") or 0),
        )
    # free_plan / free_autorenew / vip_pack / legend_pack are deferred-tier coupons —
    # reject so they're never silently consumed at checkout.
    raise QuoteError("coupon_not_supported_yet", "This coupon type is not yet redeemable at checkout.")

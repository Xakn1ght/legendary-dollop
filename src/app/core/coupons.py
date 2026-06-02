"""Shared coupon-at-checkout math, used by both the webapp purchase handler and the
bot purchase FSM so the two surfaces never diverge.

Phase 1 spendable types: discount_percent (percent off, capped to a ~100GB plan's
price) and free_gb (bonus GB on the provisioned plan). See rewards_config + the final
reward map for the rules.
"""
from app.core.rewards_config import DISCOUNT_COUPON_MAX_PLAN_GB
from app.core.settings import PLANS


def discount_price_cap() -> int:
    """Highest base-plan price at or below the coupon GB cap (the spec's 100GB cap on
    discount coupons). A percent coupon can't discount more than this — so it can't be
    applied to an arbitrarily large custom plan for outsized value."""
    prices = [
        int(p.get("price") or 0)
        for p in PLANS.values()
        if int(p.get("gb") or 0) <= DISCOUNT_COUPON_MAX_PLAN_GB
    ]
    return max(prices) if prices else 0


def coupon_discount_amount(discount_percent, total_price: int) -> int:
    """Money discounted by a percent coupon on an order whose pre-coupon total is
    `total_price`, applying the 100GB price cap."""
    try:
        pct = int(discount_percent or 0)
    except Exception:
        pct = 0
    if pct <= 0 or total_price <= 0:
        return 0
    cap = discount_price_cap()
    base = min(total_price, cap) if cap > 0 else total_price
    return int(base * (pct / 100))

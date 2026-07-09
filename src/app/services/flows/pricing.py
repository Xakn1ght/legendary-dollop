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
import re
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

# ── custom (build-your-own) plans ────────────────────────────────────────────
# plan_name format "custom:<gb>". Price math lives in app.core.pricing (the
# designed curve that hits every fixed-plan anchor exactly); this is just the
# plan-name plumbing around it.
from app.core.pricing import (  # noqa: E402
    CUSTOM_MAX_GB,
    CUSTOM_MIN_GB,
    PLAN_DURATION_DAYS,
    custom_gb_price,
    custom_price,
)

CUSTOM_PLAN_PREFIX = "custom:"


def parse_custom_plan(plan_name: str) -> int | None:
    """Return the GB for a "custom:<gb>" plan name, else None."""
    if not isinstance(plan_name, str) or not plan_name.startswith(CUSTOM_PLAN_PREFIX):
        return None
    try:
        gb = int(plan_name[len(CUSTOM_PLAN_PREFIX):])
    except ValueError:
        return None
    return gb if CUSTOM_MIN_GB <= gb <= CUSTOM_MAX_GB else None


def custom_plan_price(gb: int) -> int:
    try:
        return custom_gb_price(gb)
    except ValueError as e:
        raise QuoteError("invalid_plan", str(e))


# ── multi-month plans (2026-07-09) ───────────────────────────────────────────
# A plan can be bought for 1-3 months via a "@<n>m" name suffix
# ("۲۰ گیگ | یکماه@2m"): price / gb / days all scale linearly (a 2-month
# purchase = two monthly quotas prepaid). Catalog entries may set
# "min_months" (VIP-exclusive plans use 2 — they are NOT sold as 1-month);
# bare names resolve to the plan's minimum, so bot flows that send bare
# names stay correct without changes. Custom plans stay 1-month only.
MAX_PLAN_MONTHS = 3
_MONTHS_SUFFIX_RE = re.compile(r"^(?P<base>.+)@(?P<months>\d{1,2})m$")


def parse_plan_months(plan_name: str) -> tuple[str, int | None]:
    """Split "<base>@<n>m" → (base, n). Names without a suffix → (name, None)."""
    if isinstance(plan_name, str):
        m = _MONTHS_SUFFIX_RE.match(plan_name)
        if m:
            return m.group("base"), int(m.group("months"))
    return plan_name, None


def plan_min_months(plan_info: dict) -> int:
    try:
        return max(1, int(plan_info.get("min_months") or 1))
    except Exception:
        return 1


def get_plan_info(plan_name: str, plans: dict | None = None) -> dict | None:
    """PLANS lookup that also resolves "custom:<gb>" virtual plans and
    "@<n>m" multi-month variants.

    ``plans`` lets callers (and tests) supply their own catalog for the fixed
    lookup; custom pricing always interpolates from the live PLANS anchors.
    """
    catalog = plans if plans is not None else PLANS
    base_name, months = parse_plan_months(plan_name)

    base = None
    if base_name in catalog:
        base = dict(catalog[base_name])
    else:
        gb = parse_custom_plan(base_name)
        if gb is not None:
            if months is not None:
                return None  # custom plans are 1-month only (GB-only by design)
            base = {
                "price": custom_plan_price(gb),
                "gb": gb,
                "days": PLAN_DURATION_DAYS,
                "custom": True,
                "name_en": f"{gb} GB | Custom",
            }
    if base is None:
        return None

    min_months = plan_min_months(base)
    resolved_months = months if months is not None else min_months
    if resolved_months < min_months or resolved_months > MAX_PLAN_MONTHS:
        return None

    if resolved_months > 1:
        base["price"] = int(base.get("price") or 0) * resolved_months
        base["gb"] = int(base.get("gb") or 0) * resolved_months
        base["days"] = int(base.get("days") or PLAN_DURATION_DAYS) * resolved_months
    base["months"] = resolved_months
    return base


_FA_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")


def plan_display_name(plan_name: str, lang: str = "fa") -> str:
    """User-facing label; fixed plans keep their configured name.

    Multi-month variants read as «<plan> | ۲ ماهه» / "<plan> | 2 Months",
    with a stale «| یکماه» segment dropped from the base label.
    """
    base_name, months = parse_plan_months(plan_name)
    gb = parse_custom_plan(base_name)
    if gb is not None:
        return f"{gb} گیگ | سفارشی".translate(_FA_DIGITS) if lang == "fa" else f"{gb} GB | Custom"
    if not months or months <= 1:
        return plan_name
    label = base_name.replace("| یکماه", "").replace("  ", " ").strip()
    if lang == "fa":
        return f"{label} | {months} ماهه".translate(_FA_DIGITS)
    return f"{label} | {months} Months"

# Coupon types spendable at checkout. Other types must be rejected, never silently
# consumed. free_plan/free_autorenew are valued via the pricing curve and applied as a
# money discount (free_plan zeroes the plan up to its granted value; free_autorenew
# zeroes the selected renewal plan up to its granted value — no longer minted, but
# wallet coupons stay honored until expiry). vip_days is wallet-redeemed, never
# checkout-spent. vip_pack/legend_pack are retired.
SUPPORTED_COUPON_TYPES = (
    "discount_percent", "free_gb", "free_plan", "free_autorenew",
)


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
    plan_info = get_plan_info(plan_name)
    if not plan_info:
        # Distinguish "asked for a 1-month VIP package" from a garbage name —
        # the client shows a specific message for the former.
        base_name, months = parse_plan_months(plan_name)
        base = get_plan_info(base_name)
        if base and months is not None and months < plan_min_months(base):
            raise QuoteError("plan_min_months", "This plan is only sold as a 2-3 month package")
        raise QuoteError("invalid_plan", "Selected plan does not exist")
    renewal_info = get_plan_info(renewal_plan) if renewal_plan is not None else None
    if renewal_plan is not None and not renewal_info:
        raise QuoteError("invalid_renewal_plan", "Invalid renewal plan selected")

    plan_price = int(plan_info.get("price") or 0)
    renewal_price = int(renewal_info.get("price") or 0) if renewal_info else 0
    base_total = plan_price + renewal_price

    # VIP-exclusive plans: money-path enforcement lives HERE (both surfaces
    # quote through this function). Since 2026-07-09 they carry NO VIP percent
    # (Pasha killed the -20% offer on them — list price IS the price, and they
    # are only sold as 2-3 month packages via min_months). The VIP % still
    # applies to regular plans; an order touching any VIP-exclusive plan is
    # exempted wholesale to keep the math simple and un-gameable.
    is_vip_user = await crud.is_user_vip(session, user.id)
    vip_only_order = bool(plan_info.get("vip_only")) or bool(renewal_info and renewal_info.get("vip_only"))
    if vip_only_order and not is_vip_user:
        raise QuoteError("vip_only_plan", "This plan is exclusive to VIP members")

    total_discount_percent = 0
    if (
        is_vip_user
        and not vip_only_order
        and VIP_PURCHASE_DISCOUNT_ENABLED and VIP_PURCHASE_DISCOUNT_PERCENT > 0
    ):
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
        coupon_effect = await _validate_coupon(
            session, user, coupon_id, base_total,
            plan_price=plan_price, renewal_price=renewal_price,
        )

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


def _plan_value(gb: int, days: int) -> int:
    """Toman value of a (gb, days) plan via the pricing curve; 0 if out of range."""
    try:
        return int(custom_price(int(gb), int(days or PLAN_DURATION_DAYS)))
    except Exception:
        return 0


async def _validate_coupon(
    session: AsyncSession, user, coupon_id: int, base_total: int,
    *, plan_price: int = 0, renewal_price: int = 0,
) -> CouponEffect:
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
    if coupon.coupon_type == "free_plan":
        # Zero the plan up to the granted plan's value. On a bigger plan it's a partial
        # discount worth the granted plan; on the exact plan it's fully free.
        value = _plan_value(payload.get("plan_gb") or 0, payload.get("duration_days") or 0)
        discount = min(value, int(plan_price or 0))
        if discount <= 0:
            raise QuoteError("invalid_coupon", "Coupon not available")
        return CouponEffect(id=coupon.id, coupon_type=coupon.coupon_type, discount_amount=discount)
    if coupon.coupon_type == "free_autorenew":
        # Zero the selected renewal plan up to the granted value. Needs a renewal plan —
        # reject (un-consumed) if none chosen so the user can re-pick one.
        if int(renewal_price or 0) <= 0:
            raise QuoteError("coupon_needs_renewal", "Pick a renewal plan to use this coupon.")
        value = _plan_value(payload.get("max_plan_gb") or 0, payload.get("duration_days") or 0)
        discount = min(value, int(renewal_price or 0))
        if discount <= 0:
            raise QuoteError("invalid_coupon", "Coupon not available")
        return CouponEffect(id=coupon.id, coupon_type=coupon.coupon_type, discount_amount=discount)
    raise QuoteError("coupon_not_supported_yet", "This coupon type is not redeemable at checkout.")

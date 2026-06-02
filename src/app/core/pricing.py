"""Subscription pricing — base plans, custom GB, and custom days.

Single source of truth for price math. See
``docs/design-specs/specs/2026-05-31-final-reward-system-map.md`` §1.

Design rules:
- Base plans (fixed): 20→90k, 40→180k, 60→250k, 100→400k, 35 days.
- Custom GB curve is aligned so it hits the base-plan prices exactly at 20/40/60/100.
- Custom days use 35 days as the anchor; a *protective* 0.7 split keeps short
  windows only slightly cheaper (protects rebuy revenue) while longer windows still
  add absolute revenue.
- All prices are integer Tomans, rounded to the nearest 1,000.
"""

# Base plans (kept in sync with core/plans.json)
BASE_PLANS = {20: 90_000, 40: 180_000, 60: 250_000, 100: 400_000}
PLAN_DURATION_DAYS = 35

# Custom GB bounds
CUSTOM_MIN_GB = 1
CUSTOM_MAX_GB = 300

# Custom days bounds + pricing split (anchored at PLAN_DURATION_DAYS = ×1.0)
DAYS_MIN = 15
DAYS_MAX = 90
DAY_PRICE_BASE = 0.7   # fixed share (GB cost is mostly window-independent)
DAY_PRICE_SLOPE = 0.3  # time-scaling share (DAY_PRICE_BASE + DAY_PRICE_SLOPE == 1.0)


def round_price(amount: float) -> int:
    """Round any price to the nearest 1,000 Tomans."""
    return int(round(amount / 1000) * 1000)


def custom_gb_price(gb: int) -> int:
    """Price for a custom GB amount at the standard 35-day duration.

    Piecewise-linear curve that passes through every base-plan anchor:
    10=50k, 20=90k, 40=180k, 60=250k, 100=400k.
    """
    if gb < CUSTOM_MIN_GB or gb > CUSTOM_MAX_GB:
        raise ValueError(f"Custom GB must be between {CUSTOM_MIN_GB} and {CUSTOM_MAX_GB}")

    if gb <= 10:
        return round_price(gb * 5_000)                       # → 10 = 50k
    if gb <= 20:
        return round_price(50_000 + (gb - 10) * 4_000)       # → 20 = 90k
    if gb <= 40:
        return round_price(90_000 + (gb - 20) * 4_500)       # → 40 = 180k
    if gb <= 60:
        return round_price(180_000 + (gb - 40) * 3_500)      # → 60 = 250k
    if gb <= 100:
        return round_price(250_000 + (gb - 60) * 3_750)      # → 100 = 400k
    return round_price(400_000 + (gb - 100) * 4_000)         # → 300 = 1.2M


def day_factor(days: int) -> float:
    """Duration multiplier applied to the GB price. 35 days → 1.0."""
    return DAY_PRICE_BASE + DAY_PRICE_SLOPE * (days / PLAN_DURATION_DAYS)


def custom_price(gb: int, days: int = PLAN_DURATION_DAYS) -> int:
    """Price for a fully custom (GB, days) plan.

    Combines the GB curve with the protective day multiplier. Days outside
    [DAYS_MIN, DAYS_MAX] are rejected (no sub-15-day plans — anti-farm).
    """
    if days < DAYS_MIN or days > DAYS_MAX:
        raise ValueError(f"Custom days must be between {DAYS_MIN} and {DAYS_MAX}")
    return round_price(custom_gb_price(gb) * day_factor(days))

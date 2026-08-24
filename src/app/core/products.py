"""Virtual products that are NOT rows in the ``PLANS`` catalog.

Ported from the live sales bot during the merge (see ``MERGE_PLAN.md``). Three
products live here rather than in ``PLANS``:

- ``test``      free trial on the normal route
- ``pro_test``  free trial on the Pro / IR-Tun route
- ``pro:<gb>``  the Pro / IR-Tun route, priced per GB

They are deliberately kept OUT of ``PLANS`` for the same reason ``custom:<gb>``
is: ``PLANS`` is iterated raw by the Mini App plan grid, the charge grid, the
bot charge keyboards and ``core/coupons.py``. A free 250 MB entry and a
priceless per-GB entry would render as a broken tile in every one of them, and
the admin catalog editor only round-trips price/gb/days.

Instead ``flows.pricing.get_plan_info`` resolves these names, which is the
choke point every money path already goes through (``quote_purchase``,
``flows/charge.py``, ``services/nextplan.py``, ``jobs/renewal.py``).

Every product here carries a ``route``: ``"normal"`` or ``"pro"``. The route
decides which PasarGuard group the panel user is created in, and money paths
refuse to mix routes (you cannot top up a normal subscription with a Pro
package, or book a Pro renewal on a normal plan).
"""

from __future__ import annotations

ROUTE_NORMAL = "normal"
ROUTE_PRO = "pro"

# ── free trials ──────────────────────────────────────────────────────────────
# Both trials are the same size; they differ only in route and allowance.
FREE_TEST_GB = 0.25
FREE_TEST_DAYS = 10

TEST_PLAN = "test"
PRO_TEST_PLAN = "pro_test"
FREE_TEST_PLANS = (TEST_PLAN, PRO_TEST_PLAN)

# One normal trial a week, one Pro trial a month. Counted independently - a
# normal trial must never block a Pro trial or the other way round.
TEST_COOLDOWN_DAYS = 7
PRO_TEST_COOLDOWN_DAYS = 30

# ── Pro / IR-Tun ─────────────────────────────────────────────────────────────
PRO_PLAN_PREFIX = "pro:"
PRO_PLAN_DAYS = 35
PRO_MIN_GB = 1
PRO_MAX_GB = 300

# Toman per GB. The step down at 10 GB is DELIBERATE (Pasha, 2026-08-24): it
# pushes buyers past 10 GB, and the Pro route costs materially more to run, so
# small volumes carry a higher rate. Yes, this means 11 GB is cheaper in total
# than 10 GB. That is the intended nudge, not a bug - do not "fix" it.
PRO_RATE_SMALL = 7_000      # 1-10 GB
PRO_RATE_LARGE = 5_500      # 11 GB and up
PRO_RATE_BREAK_GB = 10


def pro_gb_price(gb: int) -> int:
    """Price in toman for a Pro / IR-Tun subscription of ``gb`` gigabytes."""
    gb = int(gb)
    if gb < PRO_MIN_GB or gb > PRO_MAX_GB:
        raise ValueError(f"Pro GB must be between {PRO_MIN_GB} and {PRO_MAX_GB}")
    rate = PRO_RATE_SMALL if gb <= PRO_RATE_BREAK_GB else PRO_RATE_LARGE
    return gb * rate


def parse_pro_plan(plan_name: str) -> int | None:
    """Return the GB for a ``pro:<gb>`` plan name, else None."""
    if not isinstance(plan_name, str) or not plan_name.startswith(PRO_PLAN_PREFIX):
        return None
    try:
        gb = int(plan_name[len(PRO_PLAN_PREFIX):])
    except ValueError:
        return None
    return gb if PRO_MIN_GB <= gb <= PRO_MAX_GB else None


def pro_plan_name(gb: int) -> str:
    return f"{PRO_PLAN_PREFIX}{int(gb)}"


def is_free_test_plan(plan_name: str) -> bool:
    return plan_name in FREE_TEST_PLANS


def test_cooldown_days(plan_name: str) -> int:
    return PRO_TEST_COOLDOWN_DAYS if plan_name == PRO_TEST_PLAN else TEST_COOLDOWN_DAYS


def resolve_virtual_product(plan_name: str) -> dict | None:
    """Resolve one of this module's product names to a plan-info dict.

    Returns None for anything else, so callers can fall through to ``PLANS``
    and ``custom:<gb>``. The shape matches what ``get_plan_info`` returns
    everywhere else: price / gb / days, plus ``route`` and (for trials)
    ``free``.
    """
    if plan_name == TEST_PLAN:
        return {
            "price": 0,
            "gb": FREE_TEST_GB,
            "days": FREE_TEST_DAYS,
            "free": True,
            "route": ROUTE_NORMAL,
            "name_en": "Free test",
        }
    if plan_name == PRO_TEST_PLAN:
        return {
            "price": 0,
            "gb": FREE_TEST_GB,
            "days": FREE_TEST_DAYS,
            "free": True,
            "route": ROUTE_PRO,
            "name_en": "Free Pro test",
        }
    gb = parse_pro_plan(plan_name)
    if gb is not None:
        return {
            "price": pro_gb_price(gb),
            "gb": gb,
            "days": PRO_PLAN_DAYS,
            "route": ROUTE_PRO,
            "name_en": f"{gb} GB | Pro",
        }
    return None


def plan_route(plan_info: dict | None) -> str:
    """Route of a resolved plan. Everything without one is the normal route."""
    if not plan_info:
        return ROUTE_NORMAL
    return plan_info.get("route") or ROUTE_NORMAL

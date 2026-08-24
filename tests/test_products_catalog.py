"""Virtual products: test, pro_test and pro:<gb> (app.core.products).

These three are deliberately NOT rows in PLANS - see the module docstring in
app/core/products.py. The most important assertion in this file is the last
one: PLANS must still contain exactly its catalog entries, because the Mini App
plan grid, the charge grid, the bot charge keyboards and core/coupons all
iterate it raw and would render a free 250 MB tile and a priceless Pro tile.

Run: PYTHONPATH=src python tests/test_products_catalog.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from app.core.products import (  # noqa: E402
    PRO_MAX_GB,
    PRO_TEST_PLAN,
    ROUTE_NORMAL,
    ROUTE_PRO,
    TEST_PLAN,
    parse_pro_plan,
    plan_route,
    pro_gb_price,
    resolve_virtual_product,
)
from app.services.flows.pricing import get_plan_info, plan_display_name  # noqa: E402


def test_pro_price_curve():
    # 7,000/GB up to 10 GB, 5,500/GB above.
    assert pro_gb_price(1) == 7_000
    assert pro_gb_price(10) == 70_000
    assert pro_gb_price(11) == 60_500
    assert pro_gb_price(15) == 82_500
    assert pro_gb_price(300) == 1_650_000
    # The step down at 10 GB is DELIBERATE (Pasha 2026-08-24) - it nudges
    # buyers past 10 GB. Pinned here so nobody "fixes" it into a monotonic
    # curve without reading the decision first.
    assert pro_gb_price(11) < pro_gb_price(10)
    print("pro price curve OK (11GB deliberately cheaper than 10GB)")


def test_pro_bounds():
    for bad in ("pro:0", f"pro:{PRO_MAX_GB + 1}", "pro:abc", "pro:", "pro:-5"):
        assert parse_pro_plan(bad) is None, bad
        assert get_plan_info(bad) is None, bad
    assert parse_pro_plan("pro:50") == 50
    for bad_gb in (0, PRO_MAX_GB + 1):
        try:
            pro_gb_price(bad_gb)
            raise AssertionError(f"pro_gb_price({bad_gb}) should raise")
        except ValueError:
            pass
    print("pro bounds OK")


def test_free_trials():
    for name, route in ((TEST_PLAN, ROUTE_NORMAL), (PRO_TEST_PLAN, ROUTE_PRO)):
        info = get_plan_info(name)
        assert info is not None, name
        assert info["price"] == 0 and info["gb"] == 0.25 and info["days"] == 10, info
        assert info["free"] is True and info["route"] == route, info
    print("free trials OK")


def test_months_suffix_rejected():
    # A trial has a fixed 10 days and Pro is sold by GB - "@Nm" has nothing to
    # scale, and accepting it would silently multiply a price.
    for name in ("test@2m", "pro_test@3m", "pro:20@2m", "pro:20@1m"):
        assert get_plan_info(name) is None, name
    print("@Nm rejected on virtual products OK")


def test_routes():
    assert plan_route(get_plan_info("pro:20")) == ROUTE_PRO
    assert plan_route(get_plan_info("pro_test")) == ROUTE_PRO
    assert plan_route(get_plan_info("test")) == ROUTE_NORMAL
    assert plan_route(get_plan_info("custom:50")) == ROUTE_NORMAL
    # An unresolvable historical plan name must read as the normal route -
    # every subscription predating the merge is normal.
    assert plan_route(get_plan_info("some retired plan")) == ROUTE_NORMAL
    assert plan_route(None) == ROUTE_NORMAL
    print("routes OK")


def test_display_names():
    # Without these the summary, receipt caption, admin card and delivery
    # message all print the raw string "pro:50".
    assert plan_display_name("pro:15", "en") == "15 GB | Pro"
    assert "پرو" in plan_display_name("pro:15", "fa")
    assert plan_display_name("test", "en") == "Free test"
    assert plan_display_name("pro_test", "en") == "Free Pro test"
    assert "pro:" not in plan_display_name("pro:15", "fa")
    print("display names OK")


def test_plans_catalog_untouched():
    from app.core.settings import PLANS
    for virtual in (TEST_PLAN, PRO_TEST_PLAN, "pro:20"):
        assert virtual not in PLANS, f"{virtual} leaked into PLANS"
    assert resolve_virtual_product("۲۰ گیگ | یکماه") is None
    # Every catalog row must still price normally.
    for name in PLANS:
        assert get_plan_info(name) is not None, name
    print(f"PLANS untouched OK ({len(PLANS)} catalog rows, no virtual products)")


if __name__ == "__main__":
    test_pro_price_curve()
    test_pro_bounds()
    test_free_trials()
    test_months_suffix_rejected()
    test_routes()
    test_display_names()
    test_plans_catalog_untouched()
    print("\nAll product catalog tests passed.")

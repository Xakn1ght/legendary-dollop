"""Tests for subscription pricing (base plans, custom GB, custom days).

Run with pytest, or directly:  python tests/test_pricing.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from app.core.pricing import (  # noqa: E402
    BASE_PLANS,
    custom_gb_price,
    custom_price,
    DAYS_MIN,
    DAYS_MAX,
)


def test_base_plan_prices():
    assert BASE_PLANS == {20: 90_000, 40: 180_000, 60: 250_000, 100: 400_000}


def test_custom_gb_hits_anchors():
    expected = {1: 5_000, 10: 50_000, 20: 90_000, 40: 180_000,
                60: 250_000, 80: 325_000, 100: 400_000, 150: 600_000,
                300: 1_200_000, 500: 2_000_000}  # 500 = VIP ceiling (2026-07-12)
    for gb, price in expected.items():
        assert custom_gb_price(gb) == price, f"{gb}GB → {custom_gb_price(gb)} != {price}"


def test_custom_gb_matches_base_plans():
    for gb, price in BASE_PLANS.items():
        assert custom_gb_price(gb) == price


def test_custom_gb_monotonic():
    prices = [custom_gb_price(g) for g in range(1, 501)]
    assert all(b >= a for a, b in zip(prices, prices[1:]))


def test_custom_gb_out_of_range():
    # Absolute ceiling is 500 (VIP). 301-500 are valid at the price level;
    # the 300-vs-500 gate is VIP enforcement in flows/pricing.py, not here.
    for bad in (0, 501, -5):
        try:
            custom_gb_price(bad)
            assert False, f"{bad} should raise"
        except ValueError:
            pass
    assert custom_gb_price(301) > 0 and custom_gb_price(500) == 2_000_000


def test_custom_days_protective():
    # 35d anchor = the GB price
    assert custom_price(100, 35) == 400_000
    # protective 0.7: short windows only modestly cheaper, long windows cost more
    assert custom_price(100, 15) == 331_000
    assert custom_price(100, 90) == 589_000
    assert custom_price(50, 60) == 261_000


def test_custom_days_bounds():
    for bad in (DAYS_MIN - 1, DAYS_MAX + 1, 7, 0):
        try:
            custom_price(50, bad)
            assert False, f"{bad} days should raise"
        except ValueError:
            pass


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"PASS {fn.__name__}")
    print(f"\nAll {len(fns)} pricing tests passed.")

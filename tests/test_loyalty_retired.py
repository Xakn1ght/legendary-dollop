"""Iron rule: loyalty points (play-earned) must not buy VPN value.

Locks that the loyalty shop retires its monetary item types (sub_credit, plan). Run:
    PYTHONPATH=src .venv/bin/python tests/test_loyalty_retired.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from app.handlers.user.rewards.loyalty_shop import LOYALTY_SHOP, RETIRED_LOYALTY_TYPES  # noqa: E402


def test_loyalty_monetary_types_retired():
    # The money-minting types are retired.
    assert {"sub_credit", "plan"} <= RETIRED_LOYALTY_TYPES
    # The catalog still contains such items, so the redemption guard is meaningful.
    types = {v["type"] for v in LOYALTY_SHOP.values()}
    assert "sub_credit" in types and "plan" in types


if __name__ == "__main__":
    test_loyalty_monetary_types_retired()
    print("PASS test_loyalty_retired")

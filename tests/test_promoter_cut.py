"""Tiered promoter cut: referrer store-credit % rises with active-referral count.

Run:  PYTHONPATH=src .venv/bin/python tests/test_promoter_cut.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from app.services.flows.cashout import promoter_credit_percent  # noqa: E402


def test_promoter_tiers():
    # PROMOTER_REFERRAL_CUT = {0: 0.05, 10: 0.10, 20: 0.12, 50: 0.15}
    # (2026-07-13: 5% under 10 actives, 10% under 20, then 12/15 as before)
    assert promoter_credit_percent(0) == 5.0
    assert promoter_credit_percent(9) == 5.0
    assert promoter_credit_percent(10) == 10.0
    assert promoter_credit_percent(19) == 10.0
    assert promoter_credit_percent(20) == 12.0
    assert promoter_credit_percent(49) == 12.0
    assert promoter_credit_percent(50) == 15.0
    assert promoter_credit_percent(999) == 15.0


if __name__ == "__main__":
    test_promoter_tiers()
    print("PASS test_promoter_cut")

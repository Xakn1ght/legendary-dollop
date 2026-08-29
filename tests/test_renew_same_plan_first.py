"""Renewing onto the same plan should be the first button, not a hunt.

The keyboard keeps the plan's OWN label rather than a "renew same plan"
wrapper, because that label is what the booking_plan handler matches on - so
this is a reorder, not a new button with a new handler and a new way to break.

Run: PYTHONPATH=src python tests/test_renew_same_plan_first.py
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from app.core.settings import PLANS  # noqa: E402
from app.handlers.user.charge.common import _build_main_plan_keyboard  # noqa: E402


class FakeState:
    """Only what the keyboard builder touches: FSM data + the ikb() bridge's
    own update_data call."""

    def __init__(self, data=None):
        self._data = dict(data or {})

    async def get_data(self):
        return dict(self._data)

    async def update_data(self, **kw):
        self._data.update(kw)
        return dict(self._data)


def labels(markup):
    return [b.text for row in markup.inline_keyboard for b in row]


async def main():
    keys = list(PLANS)
    assert len(keys) >= 2, "need at least two catalog plans to test ordering"
    target = keys[-1]  # deliberately the LAST one, so a no-op would fail

    # From FSM data - how every real call site supplies it.
    kb = await _build_main_plan_keyboard(FakeState({"current_plan": target}), "fa", is_vip=True)
    first = labels(kb)[0]
    assert first == target, f"current plan not first: {first!r} vs {target!r}"
    assert labels(kb).count(target) == 1, "current plan duplicated"
    print(f"current plan first OK ({target})")

    # No current plan: catalog order, nothing moved.
    kb2 = await _build_main_plan_keyboard(FakeState(), "fa", is_vip=True)
    plain = [x for x in labels(kb2) if x in PLANS]
    assert plain[0] != target or keys[0] == target, "ordering changed with no current_plan"
    assert set(plain) == set(keys), "plans lost or added"
    print("no current plan leaves catalog order OK")

    # A custom plan is not a catalog key: nothing matches, nothing moves.
    kb3 = await _build_main_plan_keyboard(FakeState({"current_plan": "custom:50"}), "fa", is_vip=True)
    assert [x for x in labels(kb3) if x in PLANS] == plain, "custom plan disturbed the order"
    print("custom current plan changes nothing OK")

    # Non-VIP must still not see VIP-only plans, even as their current plan.
    vip_only = [k for k in keys if PLANS[k].get("vip_only")]
    if vip_only:
        kb4 = await _build_main_plan_keyboard(
            FakeState({"current_plan": vip_only[0]}), "fa", is_vip=False
        )
        assert vip_only[0] not in labels(kb4), "VIP-only plan shown to a non-VIP user"
        print("VIP-only plan stays hidden for non-VIP OK")

    print("\nAll renew-same-plan tests passed.")


if __name__ == "__main__":
    asyncio.run(main())

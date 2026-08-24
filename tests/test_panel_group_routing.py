"""Pro / IR-Tun orders must reach the panel in their OWN group.

The failure this guards against is silent and expensive: PasarGuard templates
carry their own group, and add_user's template fast path triggers on any
whole-number GB - which every Pro order is. Without the guard a Pro customer
gets a working subscription link on the NORMAL route, having paid Pro rates,
and nothing errors.

Run: PYTHONPATH=src python tests/test_panel_group_routing.py
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from app.core.settings import PASARGUARD_IR_TUN_GROUP_ID, PASARGUARD_GROUP_IDS  # noqa: E402
from app.services import pasarguard as pg_mod  # noqa: E402
from app.services.flows.pricing import get_plan_info  # noqa: E402


class _Resp:
    status = 200

    def __init__(self, payload):
        self._payload = payload

    async def json(self):
        return self._payload

    async def text(self):
        return "{}"

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False


class _Session:
    """Captures the POST body add_user sends to the panel."""

    def __init__(self, sink):
        self.sink = sink

    def post(self, url, headers=None, json=None):
        self.sink.append(json)
        return _Resp({"username": (json or {}).get("username"), "subscription_url": "/sub/tok"})


class FakePanel(pg_mod.PasarGuardAPI if hasattr(pg_mod, "PasarGuardAPI") else object):
    """Real add_user, everything around it faked."""

    base_url = "http://fake"

    def __init__(self):
        self.posts = []
        self.template_calls = []

    async def invalidate_user_info(self, username):
        pass

    async def _get_session(self):
        return _Session(self.posts)

    async def _get_headers(self):
        return {}

    async def audit_templates(self):
        # A template exists for every whole-GB / whole-day shape, which is the
        # worst case: the fast path is always available if not suppressed.
        class _AnyMap(dict):
            def get(self, key, default=None):
                return {"id": 1, "name": "any"}
        return _AnyMap()

    async def _add_user_from_template(self, username, template_id):
        self.template_calls.append((username, template_id))
        return {"username": username, "subscription_url": "/sub/template"}

    add_user = pg_mod.PasarGuardAPI.add_user


async def _create(plan_name, username="qauser"):
    """Run the real provisioning path for a plan and report what the panel saw."""
    from app.database.repos.subscription import SubscriptionRepository

    panel = FakePanel()
    orig = pg_mod.pasarguard_api
    import app.database.repos.subscription as sub_mod
    orig_sub = sub_mod.pasarguard_api
    pg_mod.pasarguard_api = panel
    sub_mod.pasarguard_api = panel
    try:
        class _Sub:
            marzban_username = username
        info = get_plan_info(plan_name)
        assert info is not None, plan_name
        await SubscriptionRepository.create_subscription_on_pasarguard(_Sub(), info)
        return panel
    finally:
        pg_mod.pasarguard_api = orig
        sub_mod.pasarguard_api = orig_sub


async def test_pro_lands_in_the_ir_tun_group():
    panel = await _create("pro:20")
    assert not panel.template_calls, (
        "Pro order used the template fast path - it would land in the template's "
        f"group, not the IR-Tun one: {panel.template_calls}"
    )
    assert len(panel.posts) == 1, panel.posts
    body = panel.posts[0]
    assert body["group_ids"] == [PASARGUARD_IR_TUN_GROUP_ID], body["group_ids"]
    assert body["data_limit"] == 20 * 1024 ** 3, body["data_limit"]
    print(f"pro:20 -> group {body['group_ids']} via manual create OK")


async def test_pro_test_lands_in_the_ir_tun_group():
    panel = await _create("pro_test")
    assert not panel.template_calls, panel.template_calls
    body = panel.posts[0]
    assert body["group_ids"] == [PASARGUARD_IR_TUN_GROUP_ID], body["group_ids"]
    # 0.25 GB must reach the panel as an int, not 268435456.0
    assert isinstance(body["data_limit"], int), type(body["data_limit"])
    assert body["data_limit"] == int(0.25 * 1024 ** 3), body["data_limit"]
    print(f"pro_test -> group {body['group_ids']}, data_limit {body['data_limit']} (int) OK")


async def test_normal_plans_keep_the_template_fast_path():
    """The fast path is a real speed win on every ordinary purchase. Naming
    groups for normal orders too would have silently switched it off."""
    panel = await _create("۲۰ گیگ | یکماه")
    assert panel.template_calls, "normal order lost the template fast path"
    assert not panel.posts, panel.posts
    print("normal plan still uses the template fast path OK")


async def test_free_normal_test_stays_in_the_normal_group():
    panel = await _create("test")
    # 0.25 GB is not a whole number, so the fast path never applied here.
    body = panel.posts[0]
    assert body["group_ids"] == list(PASARGUARD_GROUP_IDS), body["group_ids"]
    assert isinstance(body["data_limit"], int), type(body["data_limit"])
    print(f"test -> group {body['group_ids']} OK")


async def main():
    await test_pro_lands_in_the_ir_tun_group()
    await test_pro_test_lands_in_the_ir_tun_group()
    await test_normal_plans_keep_the_template_fast_path()
    await test_free_normal_test_stays_in_the_normal_group()
    print("\nAll panel group routing tests passed.")


if __name__ == "__main__":
    asyncio.run(main())

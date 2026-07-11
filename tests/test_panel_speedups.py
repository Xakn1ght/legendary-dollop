"""PasarGuard panel speed-up tests (2026-07-10).

Covers the optimization layer added around the panel client:
- v3 share-token parsing (panel user id embedded in the link)
- template audit filtering (group match required; dud templates skipped)
- template-based creation chosen only for exactly-matching plain plans,
  with transparent manual fallback (custom shapes, on_hold, template failure)
- revoke response reuse (no follow-up get_user_info when the panel returns
  the updated user object)
- add-by-link v3 fast path: one by-id call replaces share-info + admin-info,
  and a stale/revoked v3 token falls back safely

Run: PYTHONPATH=src python tests/test_panel_speedups.py
"""
import asyncio
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from app.database import crud  # noqa: E402
from app.database.models import Base, User  # noqa: E402
from app.services import pasarguard as pasarguard_mod  # noqa: E402
from app.services.flows import subs as subs_mod  # noqa: E402
from app.services.flows.errors import FlowError  # noqa: E402
from app.services.flows.subs import add_subscription_by_link, revoke_subscription  # noqa: E402
from app.services.pasarguard import PasarGuardAPI, extract_v3_user_id  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

GB = 1024 ** 3
CHAT = 4242

# Real live-shape token: base64("v3,4139,1783718529") + hex signature tail.
V3_TOKEN = "djMsNDEzOSwxNzgzNzE4NTI52be546d852"


# ── pure parsing ─────────────────────────────────────────────────────────────────

def test_v3_token_extraction():
    assert extract_v3_user_id(V3_TOKEN) == 4139
    # single-digit id (different b64 alignment)
    import base64

    tok = base64.b64encode(b"v3,7,1700000000").decode().rstrip("=") + "aabbcc"
    assert extract_v3_user_id(tok) == 7
    # classic the panel tokens and garbage must parse to None
    assert extract_v3_user_id("tok-alice") is None
    assert extract_v3_user_id("") is None
    assert extract_v3_user_id(None) is None
    assert extract_v3_user_id("djMgarbagegarbage") is None
    print("PASS test_v3_token_extraction")


# ── template audit ───────────────────────────────────────────────────────────────

class _AuditResp:
    def __init__(self, status, payload):
        self.status = status
        self._payload = payload

    async def json(self):
        return self._payload

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False


class _AuditHttp:
    def __init__(self, payload):
        self.payload = payload

    def get(self, url, headers=None, params=None):
        return _AuditResp(200, self.payload)


async def _api_with_templates(payload):
    api = PasarGuardAPI()

    async def _sess():
        return _AuditHttp(payload)

    async def _hdrs():
        return {}

    api._get_session = _sess
    api._get_headers = _hdrs
    return api


async def test_audit_filters_unusable_templates():
    pasarguard_mod.PASARGUARD_GROUP_IDS = [1]
    payload = [
        # legacy template WITHOUT groups → would create a config-less dud; skip
        {"id": 2, "name": "20GB", "data_limit": 20 * GB, "expire_duration": 35 * 86400,
         "group_ids": [], "status": "active", "is_disabled": False},
        # right shape + right group → usable
        {"id": 13, "name": "AstroByte 20GB", "data_limit": 20 * GB, "expire_duration": 35 * 86400,
         "group_ids": [1], "status": "active", "is_disabled": False},
        # disabled → skip
        {"id": 14, "name": "AstroByte 40GB", "data_limit": 40 * GB, "expire_duration": 35 * 86400,
         "group_ids": [1], "status": "active", "is_disabled": True},
        # wrong group set → skip
        {"id": 15, "name": "OtherShop 60GB", "data_limit": 60 * GB, "expire_duration": 35 * 86400,
         "group_ids": [2], "status": "active", "is_disabled": False},
        # username prefix would mangle our service names → skip
        {"id": 16, "name": "Prefixy", "data_limit": 100 * GB, "expire_duration": 35 * 86400,
         "group_ids": [1], "status": "active", "is_disabled": False, "username_prefix": "shop_"},
    ]
    api = await _api_with_templates(payload)
    tmap = await api.audit_templates()
    assert set(tmap.keys()) == {(20 * GB, 35 * 86400)}, tmap.keys()
    assert tmap[(20 * GB, 35 * 86400)]["id"] == 13
    print("PASS test_audit_filters_unusable_templates")


async def test_audit_prefers_astrobyte_on_collision():
    pasarguard_mod.PASARGUARD_GROUP_IDS = [1]
    payload = [
        {"id": 30, "name": "AstroByte 20GB", "data_limit": 20 * GB, "expire_duration": 35 * 86400,
         "group_ids": [1], "status": "active", "is_disabled": False},
        {"id": 31, "name": "Generic 20GB", "data_limit": 20 * GB, "expire_duration": 35 * 86400,
         "group_ids": [1], "status": "active", "is_disabled": False},
    ]
    api = await _api_with_templates(payload)
    tmap = await api.audit_templates()
    assert tmap[(20 * GB, 35 * 86400)]["id"] == 30  # AstroByte name wins
    print("PASS test_audit_prefers_astrobyte_on_collision")


async def test_audit_failure_is_soft():
    api = PasarGuardAPI()

    async def _boom():
        raise RuntimeError("panel down")

    api._get_session = _boom
    tmap = await api.audit_templates()
    assert tmap == {}  # empty map, no exception → creation uses the manual path
    print("PASS test_audit_failure_is_soft")


# ── creation path selection ──────────────────────────────────────────────────────

async def _api_for_creation():
    """PasarGuardAPI with a seeded template map, recording which path ran."""
    api = PasarGuardAPI()
    api._template_map = {(20 * GB, 35 * 86400): {"id": 13, "name": "AstroByte 20GB"}}
    api._template_fetched_at = time.monotonic()
    api.log = {"template": [], "manual": [], "invalidated": []}

    async def _from_template(username, template_id):
        api.log["template"].append((username, template_id))
        return {"username": username, "subscription_url": "https://x/sub/tok", "expire": 1}

    async def _invalidate(username):
        api.log["invalidated"].append(username)

    class _ManualResp:
        status = 201

        def __init__(self, payload):
            self._p = payload

        async def json(self):
            return self._p

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

    class _ManualHttp:
        def __init__(self, log):
            self._log = log

        def post(self, url, headers=None, json=None):
            self._log["manual"].append(json)
            return _ManualResp({"username": json["username"], "subscription_url": "https://x/sub/m", "expire": 1})

    async def _sess():
        return _ManualHttp(api.log)

    async def _hdrs():
        return {}

    api._add_user_from_template = _from_template
    api.invalidate_user_info = _invalidate
    api._get_session = _sess
    api._get_headers = _hdrs
    return api


async def test_template_path_chosen_for_matching_plan():
    api = await _api_for_creation()
    result = await api.add_user("svc1", 20, 35)
    assert result and result["subscription_url"] == "https://x/sub/tok"
    assert api.log["template"] == [("svc1", 13)]
    assert api.log["manual"] == []  # manual creation never ran
    assert "svc1" in api.log["invalidated"]
    print("PASS test_template_path_chosen_for_matching_plan")


async def test_manual_path_for_unmatched_shapes():
    api = await _api_for_creation()

    # 30GB has no template (custom / coupon-bonus / multi-month shapes).
    result = await api.add_user("svc2", 30, 35)
    assert result and api.log["template"] == []
    assert len(api.log["manual"]) == 1
    body = api.log["manual"][0]
    assert body["data_limit"] == 30 * GB and body["username"] == "svc2"
    assert body["group_ids"] == list(pasarguard_mod.PASARGUARD_GROUP_IDS)

    # on_hold gift plans can't ride a template even when the size matches.
    api2 = await _api_for_creation()
    result = await api2.add_user("svc3", 20, 35, on_hold_days=35)
    assert result and api2.log["template"] == []
    assert api2.log["manual"][0]["status"] == "on_hold"
    print("PASS test_manual_path_for_unmatched_shapes")


async def test_template_failure_falls_back_to_manual():
    api = await _api_for_creation()

    async def _from_template_fail(username, template_id):
        api.log["template"].append((username, template_id))
        return None  # panel rejected / template vanished

    api._add_user_from_template = _from_template_fail
    result = await api.add_user("svc4", 20, 35)
    assert result and result["subscription_url"] == "https://x/sub/m"
    assert api.log["template"] == [("svc4", 13)]  # tried template first
    assert len(api.log["manual"]) == 1            # then fell back
    print("PASS test_template_failure_falls_back_to_manual")


# ── flows: revoke response reuse + v3 add-by-link ────────────────────────────────

class FakeMarzbanFlows:
    def __init__(self):
        self.by_id_calls = []
        self.sub_info_calls = []
        self.user_info_calls = []
        self.accounts = {
            "vthree": {
                "id": 4139,
                "username": "vthree",
                "subscription_url": f"https://panel.astrobyte.org/sub/{V3_TOKEN}",
            },
        }

    async def get_user_info_by_id(self, panel_user_id):
        self.by_id_calls.append(panel_user_id)
        for acc in self.accounts.values():
            if acc["id"] == panel_user_id:
                return dict(acc)
        return None

    async def get_subscription_info(self, token):
        self.sub_info_calls.append(token)
        for acc in self.accounts.values():
            if f"/sub/{token}" in acc["subscription_url"]:
                return {"username": acc["username"]}
        return None

    async def get_user_info(self, username):
        self.user_info_calls.append(username)
        return dict(self.accounts[username]) if username in self.accounts else None

    async def revoke_user_subscription(self, username):
        # PasarGuard shape: the updated user object comes back in the response.
        acc = self.accounts.get(username)
        if not acc:
            return False
        acc["subscription_url"] = f"https://panel.astrobyte.org/sub/rotated-{username}"
        return dict(acc)


async def _setup_flows():
    eng = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with eng.begin() as c:
        await c.run_sync(Base.metadata.create_all)
        await c.execute(
            text(
                "CREATE TABLE IF NOT EXISTS subscription_links ("
                "user_id INTEGER NOT NULL, subscription_id INTEGER NOT NULL, added_at TIMESTAMP, "
                "PRIMARY KEY (user_id, subscription_id))"
            )
        )
    Session = async_sessionmaker(eng, expire_on_commit=False)

    subs_mod.DASHBOARD_SUBSCRIPTION_ALLOWED_DOMAINS = ["astrobyte.org"]
    subs_mod.DASHBOARD_SUBSCRIPTION_DOMAIN_ENFORCE = True
    fake = FakeMarzbanFlows()
    subs_mod.pasarguard_api = fake

    async with Session() as db:
        db.add(User(id=1, chat_id=CHAT, referral_code="me"))
        await db.commit()
    return Session, fake


async def test_add_by_link_v3_single_roundtrip():
    Session, fake = await _setup_flows()
    async with Session() as db:
        user = await crud.get_user(db, CHAT)
        res = await add_subscription_by_link(
            db, user, url=f"https://panel.astrobyte.org/sub/{V3_TOKEN}"
        )
        assert res.created and res.subscription.marzban_username == "vthree"
        assert res.subscription.sub_token == V3_TOKEN
        # ONE by-id call did everything; neither legacy round-trip fired.
        assert fake.by_id_calls == [4139]
        assert fake.sub_info_calls == []
        assert fake.user_info_calls == []
    print("PASS test_add_by_link_v3_single_roundtrip")


async def test_add_by_link_stale_v3_token_rejected():
    """A v3 token whose id resolves but that is NOT the account's current token
    (revoked/forged link) must fail exactly like the classic path."""
    Session, fake = await _setup_flows()
    fake.accounts["vthree"]["subscription_url"] = "https://panel.astrobyte.org/sub/rotated-vthree"
    async with Session() as db:
        user = await crud.get_user(db, CHAT)
        try:
            await add_subscription_by_link(
                db, user, url=f"https://panel.astrobyte.org/sub/{V3_TOKEN}"
            )
            raise AssertionError("expected cannot_resolve_username")
        except FlowError as e:
            assert e.code == "cannot_resolve_username", e.code
        assert fake.by_id_calls == [4139]         # fast path tried
        assert fake.sub_info_calls == [V3_TOKEN]  # classic fallback also refused it
    print("PASS test_add_by_link_stale_v3_token_rejected")


async def test_add_by_link_classic_token_keeps_two_step():
    """Classic tokens keep the original validated two-step path unchanged."""
    Session, fake = await _setup_flows()
    fake.accounts["alice"] = {
        "id": 8, "username": "alice",
        "subscription_url": "https://panel.astrobyte.org/sub/tok-alice",
    }
    async with Session() as db:
        user = await crud.get_user(db, CHAT)
        res = await add_subscription_by_link(db, user, url="https://panel.astrobyte.org/sub/tok-alice")
        assert res.created and res.subscription.marzban_username == "alice"
        assert fake.by_id_calls == []  # not a v3 token
        assert fake.sub_info_calls == ["tok-alice"]
        assert fake.user_info_calls == ["alice"]  # existence still verified
    print("PASS test_add_by_link_classic_token_keeps_two_step")


async def test_revoke_reuses_response_object():
    Session, fake = await _setup_flows()
    async with Session() as db:
        user = await crud.get_user(db, CHAT)
        res = await add_subscription_by_link(
            db, user, url=f"https://panel.astrobyte.org/sub/{V3_TOKEN}"
        )
        fake.user_info_calls.clear()

        result = await revoke_subscription(db, user, res.subscription.id)
        assert result.new_token == "rotated-vthree"
        assert fake.user_info_calls == []  # NO follow-up fetch — response reused
        await db.refresh(res.subscription)
        assert res.subscription.sub_token == "rotated-vthree"
    print("PASS test_revoke_reuses_response_object")


async def main():
    test_v3_token_extraction()
    await test_audit_filters_unusable_templates()
    await test_audit_prefers_astrobyte_on_collision()
    await test_audit_failure_is_soft()
    await test_template_path_chosen_for_matching_plan()
    await test_manual_path_for_unmatched_shapes()
    await test_template_failure_falls_back_to_manual()
    await test_add_by_link_v3_single_roundtrip()
    await test_add_by_link_stale_v3_token_rejected()
    await test_add_by_link_classic_token_keeps_two_step()
    await test_revoke_reuses_response_object()
    print("\nAll panel speed-up tests passed.")


if __name__ == "__main__":
    asyncio.run(main())

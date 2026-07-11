"""Subscription flow-service tests (app.services.flows.subs) on in-memory SQLite.

Covers the Phase-2 divergences:
- domain allowlist enforced on every surface (was webapp-only)
- the the panel account must exist before a row is created (was bot-only)
- dedupe: re-adding your own sub is a no-op; someone else's sub links via the
  shared-account table; detached rows re-attach
- revoke requires ownership (the bot button used to skip the check entirely)
- remove-local detaches owners / unlinks shared users

Run: PYTHONPATH=src python tests/test_subs_service.py
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from app.database import crud  # noqa: E402
from app.database.models import Base, Subscription, User  # noqa: E402
from app.services.flows import subs as subs_mod  # noqa: E402
from app.services.flows.errors import FlowError  # noqa: E402
from app.services.flows.subs import (  # noqa: E402
    add_subscription_by_link,
    extract_token_from_link,
    remove_local_subscription,
    revoke_subscription,
)
from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

CHAT = 333


class FakePasarGuard:
    def __init__(self):
        self.accounts = {"alice": {"subscription_url": "https://panel.astrobyte.org/sub/tok-alice"}}
        self.tokens = {"tok-alice": {"username": "alice"}}
        self.revoked = []

    async def get_subscription_info(self, token):
        return self.tokens.get(token)

    async def get_user_info(self, username):
        return self.accounts.get(username)

    async def revoke_user_subscription(self, username):
        if username not in self.accounts:
            return False
        self.revoked.append(username)
        self.accounts[username] = {"subscription_url": f"https://panel.astrobyte.org/sub/new-{username}"}
        return True


async def _setup():
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
    fake = FakePasarGuard()
    subs_mod.pasarguard_api = fake

    async with Session() as db:
        db.add(User(id=1, chat_id=CHAT, referral_code="me"))
        db.add(User(id=2, chat_id=999, referral_code="other"))
        await db.commit()
    return Session, fake


async def test_link_parsing_and_domain_gate():
    await _setup()
    assert extract_token_from_link("https://panel.astrobyte.org/sub/tok-alice") == "tok-alice"
    # base64-encoded links are accepted too
    import base64

    b64 = base64.b64encode(b"https://panel.astrobyte.org/sub/tok-alice").decode()
    assert extract_token_from_link(b64) == "tok-alice"

    for bad, code in [
        ("https://evil.example.com/sub/tok-alice", "disallowed_domain"),
        ("https://panel.astrobyte.org/nope", "invalid_subscription_url"),
        ("", "invalid_subscription_url"),
    ]:
        try:
            extract_token_from_link(bad)
            raise AssertionError(f"expected {code}")
        except FlowError as e:
            assert e.code == code, (e.code, code)
    print("PASS test_link_parsing_and_domain_gate")


async def test_add_verifies_marzban_and_dedupes():
    Session, fake = await _setup()
    async with Session() as db:
        user = await crud.get_user(db, CHAT)

        res = await add_subscription_by_link(db, user, url="https://panel.astrobyte.org/sub/tok-alice")
        assert res.created and not res.linked
        assert res.subscription.marzban_username == "alice"
        assert res.subscription.sub_token == "tok-alice"
        assert res.subscription.status == "active" and res.subscription.price == 0

        # Re-adding your own subscription is a no-op.
        res2 = await add_subscription_by_link(db, user, url="https://panel.astrobyte.org/sub/tok-alice")
        assert not res2.created and not res2.linked and res2.subscription.id == res.subscription.id

        # Someone else adding it gets a shared link, not ownership.
        other = await crud.get_user(db, 999)
        res3 = await add_subscription_by_link(db, other, url="https://panel.astrobyte.org/sub/tok-alice")
        assert res3.linked and not res3.created
        await db.refresh(res.subscription)
        assert res.subscription.user_id == 1

        # An account that doesn't exist on the panel is refused (token resolves to a
        # username the panel then denies knowing).
        fake.tokens["tok-ghost"] = {"username": "ghost"}
        try:
            await add_subscription_by_link(db, user, url="https://panel.astrobyte.org/sub/tok-ghost")
            raise AssertionError("expected panel_account_not_found")
        except FlowError as e:
            assert e.code == "panel_account_not_found"

        # With enforcement on, a bare username is not accepted.
        try:
            await add_subscription_by_link(db, user, username="alice")
            raise AssertionError("expected subscription_url_required")
        except FlowError as e:
            assert e.code == "subscription_url_required"
    print("PASS test_add_verifies_marzban_and_dedupes")


async def test_remove_local_owner_and_linked():
    Session, fake = await _setup()
    async with Session() as db:
        user = await crud.get_user(db, CHAT)
        other = await crud.get_user(db, 999)

        res = await add_subscription_by_link(db, user, url="https://panel.astrobyte.org/sub/tok-alice")
        sub_id = res.subscription.id
        await add_subscription_by_link(db, other, url="https://panel.astrobyte.org/sub/tok-alice")

        # Linked (non-owner) user removes: the link row goes, ownership stays.
        await remove_local_subscription(db, other, sub_id)
        rows = (await db.execute(text("SELECT COUNT(*) FROM subscription_links"))).scalar()
        assert rows == 0
        sub = await db.get(Subscription, sub_id)
        assert sub.user_id == 1

        # A second removal by the same non-owner reports not_found.
        try:
            await remove_local_subscription(db, other, sub_id)
            raise AssertionError("expected not_found")
        except FlowError as e:
            assert e.code == "not_found"

        # Owner removes: the row is detached, then re-adding re-attaches it.
        await remove_local_subscription(db, user, sub_id)
        sub = await db.get(Subscription, sub_id)
        assert sub.user_id is None
        res2 = await add_subscription_by_link(db, user, url="https://panel.astrobyte.org/sub/tok-alice")
        assert not res2.created and res2.subscription.id == sub_id
        await db.refresh(sub)
        assert sub.user_id == 1
    print("PASS test_remove_local_owner_and_linked")


async def test_revoke_requires_ownership():
    Session, fake = await _setup()
    async with Session() as db:
        user = await crud.get_user(db, CHAT)
        other = await crud.get_user(db, 999)

        res = await add_subscription_by_link(db, user, url="https://panel.astrobyte.org/sub/tok-alice")
        sub_id = res.subscription.id

        # Non-owner can't rotate the link (the old bot button allowed this).
        try:
            await revoke_subscription(db, other, sub_id)
            raise AssertionError("expected unauthorized")
        except FlowError as e:
            assert e.code == "unauthorized"
        assert fake.revoked == []

        # Owner can; the new token is persisted on the row.
        result = await revoke_subscription(db, user, sub_id)
        assert fake.revoked == ["alice"]
        assert result.new_token == "new-alice"
        sub = await db.get(Subscription, sub_id)
        assert sub.sub_token == "new-alice"
    print("PASS test_revoke_requires_ownership")


async def main():
    await test_link_parsing_and_domain_gate()
    await test_add_verifies_marzban_and_dedupes()
    await test_remove_local_owner_and_linked()
    await test_revoke_requires_ownership()
    print("\nAll subs-service tests passed.")


if __name__ == "__main__":
    asyncio.run(main())

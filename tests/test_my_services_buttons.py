"""My-services detail card: link + keyboard rework (2026-07-13, Pasha).

Drives the REAL dispatcher with a fake Telegram session and a fake panel:
- the caption carries the full public https://astrobyte.org/sub/<token> link
  (the panel's relative "/sub/<token>" must never reach users);
- the card keyboard has the v2 layout incl. the native copy-link button and
  a back-to-list row;
- EVERY button on the card answers: charge, book-next-plan, buy-days,
  all-links, new-link (revoke), usage chart, refresh, report, back, plus
  reopening a card from the list (svc_).

Run: PYTHONPATH=src python tests/test_my_services_buttons.py
"""
import asyncio
import datetime
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from aiogram import Bot, Dispatcher  # noqa: E402
from aiogram.client.session.base import BaseSession  # noqa: E402
from aiogram.methods import (  # noqa: E402
    EditMessageCaption,
    EditMessageText,
    SendMessage,
    SendPhoto,
    TelegramMethod,
)
from aiogram.types import CallbackQuery, Chat, Message, Update  # noqa: E402
from aiogram.types import User as TgUser
from app.database.models import Base, Subscription, User  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

CHAT = 991
TOKEN = "aDZtam9uMHNfVEVTVFRPS0VO"
GB = 1024 ** 3

outbox: list[tuple[str, str]] = []  # (method, text/caption)


class DummySession(BaseSession):
    async def close(self):
        pass

    async def make_request(self, bot, method: TelegramMethod, timeout=None):
        name = type(method).__name__
        text = getattr(method, "text", None) or getattr(method, "caption", None) or ""
        outbox.append((name, str(text)))
        if isinstance(method, (SendMessage, SendPhoto)):
            return Message(message_id=len(outbox) + 100, date=datetime.datetime.now(),
                           chat=Chat(id=CHAT, type="private"), text=str(text) or None)
        if isinstance(method, (EditMessageText, EditMessageCaption)):
            return Message(message_id=500, date=datetime.datetime.now(),
                           chat=Chat(id=CHAT, type="private"), text=str(text) or None)
        return True

    async def stream_content(self, *a, **kw):  # pragma: no cover
        raise NotImplementedError
        yield


class FakePanel:
    """Just enough of PasarGuardAPI for the detail-card handlers."""

    def __init__(self):
        self.info = {
            "status": "active",
            "used_traffic": int(0.1 * GB),
            "data_limit": 25 * GB,
            "expire": int(time.time()) + 28 * 86400,
            "subscription_url": f"/sub/{TOKEN}",
            "links": ["vless://cfg1@host:443#DE-1", "vless://cfg2@host:443#NL-1"],
        }

    async def get_fast_user_info(self, username, token=None):
        return dict(self.info)

    async def get_user_info(self, username):
        return dict(self.info)

    async def get_user_usage(self, username, days=7):
        return [{"node_name": "de-node", "used_traffic": 2 * GB},
                {"node_name": "nl-node", "used_traffic": 1 * GB}]

    async def revoke_user_subscription(self, username):
        return {**self.info, "subscription_url": "/sub/NEWTOKEN123"}

    async def invalidate_user_info(self, username):
        return None

    async def with_next_plan_preserved(self, username, payload):
        return payload


async def _feed_callback(dp, bot, Session, data, update_id):
    async with Session() as db:
        user = TgUser(id=CHAT, is_bot=False, first_name="U")
        chat = Chat(id=CHAT, type="private")
        msg = Message(message_id=500, date=datetime.datetime.now(), chat=chat,
                      from_user=TgUser(id=42, is_bot=True, first_name="bot"), text="card")
        cb = CallbackQuery(id=f"cb{update_id}", from_user=user, chat_instance="ci",
                           message=msg, data=data)
        await dp.feed_update(bot, Update(update_id=update_id, callback_query=cb),
                             session=db, dispatcher=dp)


async def main():
    eng = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with eng.begin() as c:
        await c.run_sync(Base.metadata.create_all)
        # Shared-subscriptions link table is raw DDL in prod (indexes.py),
        # not an ORM model — the services list queries it directly.
        await c.exec_driver_sql(
            "CREATE TABLE subscription_links (user_id INTEGER, subscription_id INTEGER, added_at TIMESTAMP)"
        )
    Session = async_sessionmaker(eng, expire_on_commit=False)
    async with Session() as db:
        db.add(User(id=1, chat_id=CHAT, referral_code="me", credit=0, language="fa"))
        db.add(Subscription(id=10, user_id=1, marzban_username="m75n3f4n",
                            sub_token=TOKEN, plan_name="p50", status="active"))
        await db.commit()

    fake = FakePanel()
    # Every module that captured pasarguard_api at import time gets the fake.
    import app.handlers.user.charge.common as charge_common
    import app.handlers.user.my_services.handlers.charge_revoke as mod_cr
    import app.handlers.user.my_services.handlers.detail as mod_detail
    import app.handlers.user.my_services.handlers.links_usage as mod_links
    import app.services.flows.subs as flows_subs
    import app.services.pasarguard as pg
    for m in (mod_detail, mod_links, mod_cr, charge_common, flows_subs, pg):
        m.pasarguard_api = fake

    # 1) Card build: caption link + keyboard shape.
    from app.handlers.user.my_services.subscription_details import build_subscription_detail
    async with Session() as db:
        sub = await db.get(Subscription, 10)
    text, kb, _ = build_subscription_detail(sub, fake.info, generate_image=False)
    assert f"https://astrobyte.org/sub/{TOKEN}" in text, text
    assert "<code>/sub/" not in text, "relative link leaked into the caption"
    markup = kb.as_markup()
    datas = [b.callback_data for row in markup.inline_keyboard for b in row if b.callback_data]
    copies = [b.copy_text.text for row in markup.inline_keyboard for b in row if b.copy_text]
    expected = {"charge_10", "renew_m75n3f4n", "buydays_m75n3f4n", "link_10",
                "revoke_10", "usage_10", "refresh_10", "support_for_sub_10", "my_services_list"}
    assert expected == set(datas), set(datas) ^ expected
    assert copies == [f"https://astrobyte.org/sub/{TOKEN}"], copies
    print("PASS card: public https link + v2 keyboard + native copy button")

    # 2) Every button answers through the real dispatcher.
    bot = Bot(token="42:TEST-token", session=DummySession())
    dp = Dispatcher()
    from app.handlers.user.charge.common import router as charge_router
    from app.handlers.user.my_services.handlers.common import router as my_router
    dp.include_router(my_router)
    dp.include_router(charge_router)

    # Skip the heavy photo re-render inside svc_/refresh_ (1h cooldown gate).
    from app.handlers.user.my_services.handlers.common import _last_image_refresh
    _last_image_refresh[(CHAT, 10)] = time.time()

    checks = [
        ("svc_10", "کپی می‌شود", "reopen card"),
        ("charge_10", "ترافیک باقیمانده", "charge opens 5GB options"),
        # Months step is VIP-only (2026-07-14); this fixture user is non-VIP,
        # so the book button goes straight to the plan keyboard.
        ("renew_m75n3f4n", "پلن را انتخاب کنید", "book-next-plan plan step (non-VIP: no months)"),
        ("buydays_m75n3f4n", "زمانی", "buy-days plan list"),
        ("link_10", "vless://cfg1", "all links sent"),
        ("usage_10", "مصرف", "usage chart/caption"),
        ("refresh_10", "", "refresh answers"),
        ("support_for_sub_10", "دسته مشکل", "report problem opens categories"),
        ("revoke_10", "", "new link issued"),
        ("my_services_list", "انتخاب", "back to list"),
    ]
    uid = 100
    for data, marker, label in checks:
        outbox.clear()
        uid += 1
        await _feed_callback(dp, bot, Session, data, uid)
        assert outbox, f"{label}: no telegram call at all for {data}"
        blob = " | ".join(f"{m}:{t}" for m, t in outbox)
        if marker:
            assert marker in blob, f"{label}: expected «{marker}» in outbox → {blob[:400]}"
        # every button must at least ACK the callback or send/edit something
        kinds = {m for m, _ in outbox}
        assert kinds & {"AnswerCallbackQuery", "SendMessage", "EditMessageText",
                        "EditMessageCaption", "SendPhoto"}, f"{label}: {kinds}"
        print(f"PASS button {data} — {label}")

    await bot.session.close()
    print("\ntest_my_services_buttons: OK")


asyncio.run(main())

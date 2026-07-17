"""Webapp-open → bot-lock guard (2026-07-13, Pasha).

Drives WebappLockMiddleware directly with a fake Redis presence backend:
- Mini App open → a normal message is BLOCKED (handler never runs) and the
  user gets the "close the Mini App" notice.
- Mini App open → a callback is answered with an alert, handler blocked.
- /start and /cancel ALWAYS pass and CLEAR the lock (escape hatch).
- Mini App closed → everything passes through untouched.
- Redis error → FAIL-OPEN (handler runs).

Run: PYTHONPATH=src python tests/test_webapp_lock.py
"""
import asyncio
import datetime
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import app.services.webapp_presence as presence  # noqa: E402
from aiogram.types import Chat, Message, Update  # noqa: E402
from aiogram.types import User as TgUser
from app.utils.webapp_lock_middleware import WebappLockMiddleware  # noqa: E402

CHAT = 4242


class FakeCache:
    def __init__(self):
        self.store = {}
        self.fail = False

    async def set(self, key, value, ttl=None):
        if self.fail:
            raise RuntimeError("redis down")
        self.store[key] = value
        return True

    async def get(self, key):
        if self.fail:
            raise RuntimeError("redis down")
        return self.store.get(key)

    async def delete(self, key):
        if self.fail:
            raise RuntimeError("redis down")
        self.store.pop(key, None)
        return True


class FakeBot:
    def __init__(self):
        self.sent = []

    async def send_message(self, chat_id, text, **kw):
        self.sent.append((chat_id, text))


class FakeCb:
    def __init__(self, data):
        self.from_user = TgUser(id=CHAT, is_bot=False, first_name="U")
        self.data = data
        self.answers = []

    async def answer(self, text=None, show_alert=False, **kw):
        self.answers.append((text, show_alert))


def _msg_update(text):
    u = TgUser(id=CHAT, is_bot=False, first_name="U")
    m = Message(message_id=1, date=datetime.datetime.now(),
                chat=Chat(id=CHAT, type="private"), from_user=u, text=text)
    return Update(update_id=1, message=m)


async def main():
    fake = FakeCache()
    presence.cache = fake  # touch/clear/is_open all read this module-level cache

    mw = WebappLockMiddleware()
    ran = {"n": 0}

    async def handler(event, data):
        ran["n"] += 1
        return "HANDLED"

    bot = FakeBot()

    # Lock ON.
    await presence.touch(CHAT)
    assert await presence.is_open(CHAT) is True

    # 1) normal message blocked + notice sent
    ran["n"] = 0
    bot.sent.clear()
    res = await mw(handler, _msg_update("سلام"), {"bot": bot})
    assert ran["n"] == 0 and res is None, "message should be blocked"
    assert bot.sent and ("Mini App" in bot.sent[-1][1] or "مینی" in bot.sent[-1][1]), bot.sent
    print("PASS message blocked + close-app notice")

    # 2) notice is rate-limited (second immediate message: no 2nd DM)
    bot.sent.clear()
    await mw(handler, _msg_update("بازم سلام"), {"bot": bot})
    assert not bot.sent, "notice should be rate-limited"
    print("PASS notice rate-limited")

    # 3) callback answered with alert, blocked
    ran["n"] = 0
    cb = FakeCb("charge_10")
    # feed our FakeCb via a shim update object so .answer() is observable
    class ShimUpd:
        message = None
        edited_message = None
        inline_query = None
        def __init__(self, cbobj): self.callback_query = cbobj
    res = await mw(handler, ShimUpd(cb), {"bot": bot})
    assert ran["n"] == 0 and res is None
    assert cb.answers and cb.answers[-1][1] is True, cb.answers
    print("PASS callback blocked with alert")

    # 4) /start bypasses AND clears the lock
    ran["n"] = 0
    res = await mw(handler, _msg_update("/start"), {"bot": bot})
    assert res == "HANDLED" and ran["n"] == 1, "/start must pass"
    assert await presence.is_open(CHAT) is False, "/start must clear the lock"
    print("PASS /start bypasses and clears lock")

    # 5) closed → passes through
    ran["n"] = 0
    res = await mw(handler, _msg_update("hello"), {"bot": bot})
    assert res == "HANDLED" and ran["n"] == 1
    print("PASS unlocked passes through")

    # 6) Redis down → fail-open (lock cannot be read → bot works)
    await presence.touch(CHAT)  # would lock, but:
    fake.fail = True
    ran["n"] = 0
    res = await mw(handler, _msg_update("still working?"), {"bot": bot})
    assert res == "HANDLED" and ran["n"] == 1, "must fail-open when redis errors"
    fake.fail = False
    print("PASS fail-open on redis error")

    print("\ntest_webapp_lock: OK")


asyncio.run(main())

"""Regression: enabling auto-renew must show the renewal-plan keyboard.

Pasha's Jul-12 dead end (screenshot 18:52 + two "'str' object has no attribute
'get_data'" errors in bot_error.log): process_yes_auto_renew passed "fa" where
the FSMContext belongs, so building the keyboard crashed and the flow went
silent right after the "فعال‌سازی تمدید خودکار" tap.

Also pins the VIP-aware custom-GB bounds (300 regular / 500 VIP) on the
purchase custom-plan step.

Run: PYTHONPATH=src python tests/test_purchase_autorenew_kb.py
"""
import asyncio
import datetime
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from aiogram import Bot, Dispatcher  # noqa: E402
from aiogram.client.session.base import BaseSession  # noqa: E402
from aiogram.fsm.context import FSMContext  # noqa: E402
from aiogram.fsm.storage.base import StorageKey  # noqa: E402
from aiogram.fsm.storage.memory import MemoryStorage  # noqa: E402
from aiogram.methods import SendMessage, TelegramMethod  # noqa: E402
from aiogram.types import Chat, Message, Update  # noqa: E402
from aiogram.types import User as TgUser
from app.database.models import Base, User  # noqa: E402
from app.handlers.user.purchase.common import PurchaseState  # noqa: E402
from app.handlers.user.purchase.common import router as purchase_router  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

CHAT = 778
VIP_CHAT = 779
sent = []


class DummySession(BaseSession):
    async def close(self):
        pass

    async def make_request(self, bot, method: TelegramMethod, timeout=None):
        if isinstance(method, SendMessage):
            sent.append(method.text)
            return Message(
                message_id=len(sent), date=datetime.datetime.now(),
                chat=Chat(id=CHAT, type="private"), text=method.text,
            )
        return True

    async def stream_content(self, *a, **kw):  # pragma: no cover
        raise NotImplementedError
        yield


async def _feed(dp, bot, Session, chat_id, text, update_id):
    async with Session() as db:
        user = TgUser(id=chat_id, is_bot=False, first_name="U")
        chat = Chat(id=chat_id, type="private")
        msg = Message(
            message_id=update_id, date=datetime.datetime.now(), chat=chat,
            from_user=user, text=text,
        )
        await dp.feed_update(bot, Update(update_id=update_id, message=msg),
                             session=db, dispatcher=dp)


async def main():
    eng = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with eng.begin() as c:
        await c.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(eng, expire_on_commit=False)
    async with Session() as db:
        db.add(User(id=1, chat_id=CHAT, referral_code="a", credit=0, language="fa"))
        db.add(User(id=2, chat_id=VIP_CHAT, referral_code="b", credit=0, language="fa", is_vip=True))
        await db.commit()

    bot = Bot(token="42:TEST-token", session=DummySession())
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(purchase_router)

    # 1. Enabling auto-renew lands on the renewal-template step with a prompt
    #    (this used to crash before any reply).
    ctx = FSMContext(storage=dp.storage, key=StorageKey(bot_id=42, chat_id=CHAT, user_id=CHAT))
    await ctx.set_state(PurchaseState.auto_renew_choice)
    await ctx.set_data({"plan": "custom:40"})
    await _feed(dp, bot, Session, CHAT, "فعال‌سازی تمدید خودکار", 1)
    state_now = await ctx.get_state()
    assert state_now == PurchaseState.renewal_template.state, f"state: {state_now}"
    assert sent and "تمدید خودکار" in sent[-1], f"expected renewal prompt, got: {sent[-1] if sent else None}"
    print("PASS auto-renew tap shows the renewal plan keyboard")

    # 2. Custom-GB bounds: non-VIP capped at 300, VIP allowed to 500.
    sent.clear()
    await ctx.set_state(PurchaseState.custom_gb)
    await ctx.set_data({"custom_for_renewal": False})
    await _feed(dp, bot, Session, CHAT, "500", 2)
    assert sent and "نامعتبر" in sent[-1] and "۳۰۰" in sent[-1], f"non-vip 500 must be rejected with the 300 cap: {sent}"
    print("PASS non-vip capped at 300 (FA digits in message)")

    sent.clear()
    vctx = FSMContext(storage=dp.storage, key=StorageKey(bot_id=42, chat_id=VIP_CHAT, user_id=VIP_CHAT))
    await vctx.set_state(PurchaseState.custom_gb)
    await vctx.set_data({"custom_for_renewal": False})
    await _feed(dp, bot, Session, VIP_CHAT, "500", 3)
    assert sent and all("نامعتبر" not in s for s in sent), f"vip 500 must be accepted: {sent}"
    assert any("۵۰۰ گیگ" in s or "سفارشی" in s for s in sent), f"expected custom plan echo: {sent}"
    state_now = await vctx.get_state()
    assert state_now == PurchaseState.auto_renew_choice.state, f"vip should proceed to auto-renew choice: {state_now}"
    print("PASS vip accepted at 500 and flow continues")

    await bot.session.close()
    print("test_purchase_autorenew_kb: OK")


asyncio.run(main())

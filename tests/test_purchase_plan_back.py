"""Regression: Back on the purchase PLAN step must cancel the flow, and
main-menu buttons must escape it.

Until 2026-07-14 the plan-state catch-all (invalid_plan, registered before
plan_exits) shadowed the back handler, so every Back tap re-sent the same
"use the buttons below" + plans keyboard forever (Pasha screenshot, 11:34 PM
loop), and «سرویس‌های من» taps were eaten the same way.

Run: PYTHONPATH=src python tests/test_purchase_plan_back.py
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
from aiogram.types import Chat, Message, Update, User as TgUser  # noqa: E402
from app.database.models import Base, User  # noqa: E402
from app.handlers.user.purchase.common import PurchaseState  # noqa: E402
from app.handlers.user.purchase.common import router as purchase_router  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

CHAT = 778
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


async def _feed(dp, bot, Session, text, update_id):
    async with Session() as db:
        user = TgUser(id=CHAT, is_bot=False, first_name="U")
        chat = Chat(id=CHAT, type="private")
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
        db.add(User(id=1, chat_id=CHAT, referral_code="me", credit=0, language="fa"))
        await db.commit()

    bot = Bot(token="42:TEST-token", session=DummySession())
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(purchase_router)

    ctx = FSMContext(storage=dp.storage,
                     key=StorageKey(bot_id=42, chat_id=CHAT, user_id=CHAT))

    # 1. Back on the plan step cancels the purchase (state cleared, main menu),
    #    instead of looping "use the buttons below" forever.
    await ctx.set_state(PurchaseState.plan)
    await _feed(dp, bot, Session, "بازگشت🔙", 1)
    state_now = await ctx.get_state()
    assert state_now is None, f"state after back: {state_now}"
    assert sent and "لغو" in sent[-1], f"expected cancel message, got: {sent[-1] if sent else None}"
    assert all("از دکمه های زیر" not in s for s in sent), f"back looped the plans prompt: {sent}"
    print("PASS back cancels the plan step")

    # 2. A main-menu button escapes the flow: state cleared, catch-all stays
    #    silent (the real my-services handler lives in another router).
    sent.clear()
    await ctx.set_state(PurchaseState.plan)
    await _feed(dp, bot, Session, "🛍 سرویس‌های من", 2)
    state_now = await ctx.get_state()
    assert state_now is None, f"state after menu tap: {state_now}"
    assert all("از دکمه های زیر" not in s for s in sent), f"menu tap was eaten: {sent}"
    print("PASS menu button escapes the plan step")

    # 3. Garbage stays in-state and re-prompts (the catch-all's real job).
    sent.clear()
    await ctx.set_state(PurchaseState.plan)
    await _feed(dp, bot, Session, "blahblah", 3)
    state_now = await ctx.get_state()
    assert state_now == PurchaseState.plan.state, f"state after junk: {state_now}"
    assert sent and "از دکمه های زیر" in sent[-1], f"expected re-prompt, got: {sent}"
    print("PASS junk still re-prompts in-state")

    await bot.session.close()
    print("test_purchase_plan_back: OK")


asyncio.run(main())

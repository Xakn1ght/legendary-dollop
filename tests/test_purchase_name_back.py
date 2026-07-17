"""Regression: the Back button on the purchase NAME step must exit to plan
selection, not die on the safe-text validator.

The reply keyboard sends «بازگشت🔙» — the emoji fails validate_safe_text, and
until 2026-07-12 the back check ran AFTER that gate, so every Back tap got
"invalid service name" and the step was a dead end (found live-testing as
Pasanim). The fix checks the back button before validation.

Run: PYTHONPATH=src python tests/test_purchase_name_back.py
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

CHAT = 777
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
    await ctx.set_state(PurchaseState.name)
    await ctx.set_data({"plan": "۲۰ گیگ | یکماه", "auto_renewal": False})

    # 1. Back button (with the emoji, exactly what the keyboard sends) exits
    #    to plan selection instead of tripping the safe-text validator.
    await _feed(dp, bot, Session, "بازگشت🔙", 1)
    state_now = await ctx.get_state()
    assert state_now == PurchaseState.plan.state, f"state after back: {state_now}"
    assert sent and "پلن" in sent[-1], f"expected plan prompt, got: {sent[-1] if sent else None}"
    assert all("نامعتبر" not in s for s in sent), f"back tap was rejected as invalid: {sent}"
    print("PASS back button exits name step")

    # 2. The validator still guards real input: junk name is rejected in-state.
    sent.clear()
    await ctx.set_state(PurchaseState.name)
    await _feed(dp, bot, Session, "@@@///", 2)
    state_now = await ctx.get_state()
    assert state_now == PurchaseState.name.state, f"state after junk: {state_now}"
    assert sent and "نامعتبر" in sent[-1], f"expected invalid-name reply, got: {sent}"
    print("PASS junk name still rejected")

    await bot.session.close()
    print("test_purchase_name_back: OK")


asyncio.run(main())

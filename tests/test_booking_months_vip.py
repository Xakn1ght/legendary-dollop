"""Bot booking lane: the 1/2/3-months step is VIP-only (2026-07-14).

- non-VIP tapping «رزرو پلن» goes STRAIGHT to the plan keyboard
  (ChargeState.booking_plan), never seeing the months step
- VIP gets the months keyboard first (ChargeState.booking_months)

Run: PYTHONPATH=src python tests/test_booking_months_vip.py
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
from app.database.models import Base, Subscription, User  # noqa: E402
from app.handlers.user.charge.common import ChargeState  # noqa: E402
from app.handlers.user.charge.common import router as charge_router  # noqa: E402
from app.utils.bot_i18n import t  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

VIP_CHAT = 991
REG_CHAT = 992
sent = []


class DummySession(BaseSession):
    async def close(self):
        pass

    async def make_request(self, bot, method: TelegramMethod, timeout=None):
        if isinstance(method, SendMessage):
            sent.append(method.text)
            return Message(
                message_id=len(sent), date=datetime.datetime.now(),
                chat=Chat(id=method.chat_id, type="private"), text=method.text,
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
        db.add(User(id=1, chat_id=VIP_CHAT, referral_code="v", credit=0, is_vip=True, vip_until=None, language="fa"))
        db.add(User(id=2, chat_id=REG_CHAT, referral_code="r", credit=0, language="fa"))
        db.add(Subscription(id=10, user_id=1, marzban_username="vsvc", plan_name="p", status="active"))
        db.add(Subscription(id=20, user_id=2, marzban_username="rsvc", plan_name="p", status="active"))
        await db.commit()

    bot = Bot(token="42:TEST-token", session=DummySession())
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(charge_router)

    book_btn = t("fa", "book_plan")

    # non-VIP: months step skipped -> booking_plan + plan keyboard title
    ctx_reg = FSMContext(storage=dp.storage,
                         key=StorageKey(bot_id=42, chat_id=REG_CHAT, user_id=REG_CHAT))
    await ctx_reg.set_state(ChargeState.traffic_check)
    await ctx_reg.set_data({"subscription_id": 20, "remaining_gb": 8.0})
    await _feed(dp, bot, Session, REG_CHAT, book_btn, 1)
    state_now = await ctx_reg.get_state()
    assert state_now == ChargeState.booking_plan.state, f"non-VIP state: {state_now}"
    assert sent and sent[-1] == t("fa", "charge_booking_title"), f"non-VIP got: {sent[-1] if sent else None}"
    print("PASS non-VIP skips the months step")

    # VIP: months keyboard first
    sent.clear()
    ctx_vip = FSMContext(storage=dp.storage,
                         key=StorageKey(bot_id=42, chat_id=VIP_CHAT, user_id=VIP_CHAT))
    await ctx_vip.set_state(ChargeState.traffic_check)
    await ctx_vip.set_data({"subscription_id": 10, "remaining_gb": 8.0})
    await _feed(dp, bot, Session, VIP_CHAT, book_btn, 2)
    state_now = await ctx_vip.get_state()
    assert state_now == ChargeState.booking_months.state, f"VIP state: {state_now}"
    assert sent and sent[-1] == t("fa", "charge_booking_months_title"), f"VIP got: {sent[-1] if sent else None}"
    print("PASS VIP still gets the months step")

    # non-VIP back from the plan keyboard returns to the OPTIONS, not months
    sent.clear()
    await _feed(dp, bot, Session, REG_CHAT, t("fa", "btn_back"), 3)
    state_now = await ctx_reg.get_state()
    assert state_now == ChargeState.traffic_check.state, f"non-VIP back state: {state_now}"
    assert sent and sent[-1] == t("fa", "charge_back_step"), f"non-VIP back got: {sent[-1] if sent else None}"
    print("PASS non-VIP back returns to the options step")

    await bot.session.close()
    print("test_booking_months_vip: OK")


asyncio.run(main())

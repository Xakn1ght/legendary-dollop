"""The two-level purchase menu: Normal and Pro never share a screen.

Drives the real purchase router through a Dispatcher, the same way
test_inline_bridge.py does, and reads back the keyboard rows the user would
see. The rule under test came from the live sales bot, where a test locks it
in: a customer must not be able to buy a Pro plan believing it is a normal one.

Run: PYTHONPATH=src python tests/test_purchase_two_level_menu.py
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from aiogram import Bot, Dispatcher  # noqa: E402
from aiogram.client.session.base import BaseSession  # noqa: E402
from aiogram.fsm.storage.memory import MemoryStorage  # noqa: E402
from aiogram.methods import SendMessage, TelegramMethod  # noqa: E402
from aiogram.types import Chat, Message, Update, User as TgUser  # noqa: E402
from app.core.settings import PLANS  # noqa: E402
from app.database.models import Base, User  # noqa: E402
from app.handlers.user.purchase import router as purchase_router  # noqa: E402
from app.handlers.user.purchase.common import (  # noqa: E402
    CAT_NORMAL_BTN_FA,
    CAT_PRO_BTN_FA,
    CUSTOM_PLAN_BTN_FA,
    FREE_TEST_BTN_FA,
    PRO_BUY_BTN_FA,
    PRO_TEST_BTN_FA,
)
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

CHAT = 8080
sent = []


class DummySession(BaseSession):
    async def close(self):
        pass

    async def make_request(self, bot, method: TelegramMethod, timeout=None):
        if isinstance(method, SendMessage):
            sent.append(method)
            return Message(
                message_id=len(sent), date=0,
                chat=Chat(id=CHAT, type="private"), text=method.text,
            )
        return True

    async def stream_content(self, *a, **kw):
        raise NotImplementedError
        yield


def _rows(method) -> list[list[str]]:
    """The labels a user would see, recovered from the FSM-indexed keyboard."""
    kb = getattr(method, "reply_markup", None)
    if kb is None:
        return []
    return [[b.text for b in row] for row in kb.inline_keyboard]


def _flat(method) -> list[str]:
    return [b for row in _rows(method) for b in row]


async def _drive(dp, bot, text):
    sent.clear()
    upd = Update(
        update_id=len(sent) + 1,
        message=Message(
            message_id=999, date=0, text=text,
            chat=Chat(id=CHAT, type="private"),
            from_user=TgUser(id=CHAT, is_bot=False, first_name="P"),
        ),
    )
    await dp.feed_update(bot, upd)
    return sent[-1] if sent else None


async def main():
    eng = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with eng.begin() as c:
        await c.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(eng, expire_on_commit=False)
    async with Session() as db:
        db.add(User(id=1, chat_id=CHAT, referral_code="me", language="fa"))
        await db.commit()

    try:
        from app.core.redis_config import cache
        for tier in ("test", "pro_test"):
            await cache.delete(f"freetest:1:{tier}")
    except Exception:
        pass

    bot = Bot(token="42:TEST-token", session=DummySession())
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(purchase_router)

    db_session = Session()

    @dp.update.outer_middleware()
    async def inject(handler, event, data):
        data["session"] = db_session
        data["dispatcher"] = dp
        return await handler(event, data)

    # --- level 1 -------------------------------------------------------
    m = await _drive(dp, bot, "خرید سرویس")
    if m is None:
        m = await _drive(dp, bot, "💳 خرید سرویس")
    assert m is not None, "purchase entry did not answer"
    level1 = _flat(m)
    assert CAT_NORMAL_BTN_FA in level1, level1
    assert CAT_PRO_BTN_FA in level1, level1
    # No products at level 1 - it is a chooser, nothing else.
    assert not any(p in level1 for p in PLANS), level1
    assert CUSTOM_PLAN_BTN_FA not in level1, level1
    print(f"level 1 is a chooser only: {level1}")

    # --- level 2a: normal ----------------------------------------------
    m = await _drive(dp, bot, CAT_NORMAL_BTN_FA)
    normal = _flat(m)
    assert FREE_TEST_BTN_FA in normal, normal
    assert CUSTOM_PLAN_BTN_FA in normal, normal
    assert any(p in normal for p in PLANS), normal
    # The Pro family must be absent from this screen.
    assert PRO_BUY_BTN_FA not in normal, normal
    assert PRO_TEST_BTN_FA not in normal, normal
    print(f"level 2 normal has plans + free test, no Pro: {len(normal)} buttons")

    # Back from the plan list goes UP to level 1, it does not cancel.
    m = await _drive(dp, bot, "بازگشت🔙")
    back = _flat(m)
    assert CAT_NORMAL_BTN_FA in back and CAT_PRO_BTN_FA in back, back
    print("back from the plan list returns to level 1 OK")

    # --- level 2b: pro --------------------------------------------------
    m = await _drive(dp, bot, CAT_PRO_BTN_FA)
    pro = _flat(m)
    assert PRO_BUY_BTN_FA in pro, pro
    assert PRO_TEST_BTN_FA in pro, pro
    # The normal family must be absent from this screen.
    assert not any(p in pro for p in PLANS), pro
    assert CUSTOM_PLAN_BTN_FA not in pro, pro
    assert FREE_TEST_BTN_FA not in pro, pro
    print(f"level 2 pro has only Pro products: {pro}")

    # --- the two screens must not intersect -----------------------------
    overlap = (set(normal) & set(pro)) - {"بازگشت🔙"}
    assert not overlap, f"Normal and Pro share products: {overlap}"
    print("normal and pro share nothing but Back OK")

    # --- the Pro button opens a GB prompt --------------------------------
    m = await _drive(dp, bot, PRO_BUY_BTN_FA)
    assert m is not None and "گیگابایت" in (m.text or ""), m.text
    print("pro button opens the GB prompt OK")

    # --- a valid GB proceeds at the Pro price ----------------------------
    m = await _drive(dp, bot, "15")
    texts = " ".join(x.text or "" for x in sent)
    assert "۸۲,۵۰۰" in texts or "82,500" in texts, texts[:200]
    print("15 GB priced at 82,500 OK")

    await db_session.close()
    print("\nAll two-level purchase menu tests passed.")


if __name__ == "__main__":
    asyncio.run(main())

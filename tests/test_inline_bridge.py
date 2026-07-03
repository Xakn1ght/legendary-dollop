"""Inline-keyboard bridge test: a fkb:<gen>:<idx> callback tap must resolve its
label from FSM data and re-run the matching *text* handler with the same
kwargs (session etc.), and stale generations must be rejected.

Run: PYTHONPATH=src python tests/test_inline_bridge.py
"""
import asyncio
import sys

sys.path.insert(0, "src")

from aiogram import Bot, Dispatcher, F
from aiogram.client.session.base import BaseSession
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.methods import AnswerCallbackQuery, EditMessageReplyMarkup, TelegramMethod
from aiogram.types import CallbackQuery, Chat, Message, Update, User
from app.handlers.user.flow_inline import ikb, resolve_label
from app.handlers.user.flow_inline import router as bridge_router


class DummySession(BaseSession):
    """No-network session: every API call succeeds with a canned response."""

    async def close(self):
        pass

    async def make_request(self, bot, method: TelegramMethod, timeout=None):
        if isinstance(method, (AnswerCallbackQuery, EditMessageReplyMarkup)):
            return True
        raise AssertionError(f"unexpected API call: {type(method).__name__}")

    async def stream_content(self, *a, **kw):  # pragma: no cover
        raise NotImplementedError
        yield


class TestSG(StatesGroup):
    step = State()


captured = []


async def main():
    bot = Bot(token="42:TEST-token", session=DummySession())
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(bridge_router)

    from aiogram import Router
    test_router = Router()

    @test_router.message(TestSG.step, F.text == "PLAN A")
    async def on_plan(message: Message, state: FSMContext, session):
        captured.append((message.text, session, message.from_user.id))

    dp.include_router(test_router)

    # Prod injects `session` and `dispatcher` via update-level outer middlewares
    # (DbSessionMiddleware / DispatcherMiddleware in main.py); mimic that.
    @dp.update.outer_middleware()
    async def inject_session(handler, event, data):
        data["session"] = "SESSION_SENTINEL"
        data["dispatcher"] = dp
        return await handler(event, data)

    user = User(id=777, is_bot=False, first_name="U")
    chat = Chat(id=777, type="private")
    bot_user = User(id=42, is_bot=True, first_name="B")

    key_ctx = FSMContext(
        storage=dp.storage,
        key=__import__("aiogram.fsm.storage.base", fromlist=["StorageKey"]).StorageKey(
            bot_id=42, chat_id=777, user_id=777
        ),
    )
    await key_ctx.set_state(TestSG.step)
    markup = await ikb(key_ctx, [["PLAN A"], ["back"]])
    assert markup.inline_keyboard[0][0].callback_data == "fkb:1:0"
    assert markup.inline_keyboard[1][0].callback_data == "fkb:1:1"

    prompt = Message(message_id=5, date=0, chat=chat, from_user=bot_user, text="pick a plan")
    cbq = CallbackQuery(
        id="1", from_user=user, chat_instance="ci", data="fkb:1:0", message=prompt
    )
    await dp.feed_update(bot, Update(update_id=1, callback_query=cbq))

    assert captured == [("PLAN A", "SESSION_SENTINEL", 777)], captured

    # Stale generation: a newer keyboard expires the old one.
    await ikb(key_ctx, [["PLAN B"]])
    data = await key_ctx.get_data()
    assert resolve_label(data, "fkb:1:0") is None
    assert resolve_label(data, "fkb:2:0") == "PLAN B"
    assert resolve_label(data, "fkb:2:9") is None
    assert resolve_label(data, "garbage") is None

    # Tapping the stale button must NOT re-fire the handler.
    await key_ctx.set_state(TestSG.step)
    await dp.feed_update(bot, Update(update_id=2, callback_query=cbq))
    assert len(captured) == 1, captured

    await bot.session.close()
    print("inline bridge test OK")


asyncio.run(main())

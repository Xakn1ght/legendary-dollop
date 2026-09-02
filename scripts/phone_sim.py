"""Drive the REAL bot the way a phone does — synthetic taps, real everything else.

This is the closest thing to phone testing that runs unattended. It builds the
same Dispatcher `main.py` builds (same routers, same middlewares), points it at
the real database and Redis, and feeds it Telegram updates. Nothing reaches
Telegram: a no-network session records what the bot WOULD have sent, which is
what gets printed as a transcript.

What it catches: handler crashes, dead buttons, wrong prices, missing FSM
states, shadowed handlers, keyboards that lie. What it cannot catch: how it
looks on a real screen.

    PYTHONPATH=src .venv/bin/python scripts/phone_sim.py           # all scenarios
    PYTHONPATH=src .venv/bin/python scripts/phone_sim.py purchase  # one of them
"""
from __future__ import annotations

import asyncio
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.base import BaseSession
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.methods import (
    AnswerCallbackQuery,
    DeleteMessage,
    EditMessageCaption,
    EditMessageMedia,
    EditMessageReplyMarkup,
    EditMessageText,
    SendMessage,
    SendPhoto,
    TelegramMethod,
)
from aiogram.types import CallbackQuery, Update
from aiogram.types import Chat as TgChat
from aiogram.types import Message as TgMessage
from aiogram.types import User as TgUser

TEST_CHAT_ID = 999_000_111
INVITE_CODE = "PHYDZ4"        # a real existing customer's referral code        # a chat id no real customer can hold
_msg_id = [1000]


# ── the screen ──────────────────────────────────────────────────────────────
class Screen:
    """What the phone would be showing, plus everything it was told."""

    def __init__(self):
        self.text = ""
        self.buttons: list[str] = []          # flat labels, reply or inline
        self.callbacks: dict[str, str] = {}   # label -> callback_data
        self.alerts: list[str] = []
        self.sent: list[str] = []             # every message body, in order
        self.errors: list[str] = []
        self.slow: list[tuple] = []           # taps a thumb would notice
        self.last_ms = 0

    def show(self, title=""):
        head = f"  ┌─ {title} " + "─" * max(0, 58 - len(title))
        print(head)
        for line in (self.text or "(no text)").splitlines():
            print(f"  │ {line}")
        if self.buttons:
            print("  ├─ buttons " + "─" * 48)
            for b in self.buttons:
                cb = self.callbacks.get(b)
                print(f"  │ [{b}]" + (f"  -> {cb}" if cb else ""))
        if self.alerts:
            for a in self.alerts:
                print(f"  ├─ popup: {a}")
        print("  └" + "─" * 60)


screen = Screen()


def _collect_markup(markup):
    labels, cbs = [], {}
    rows = getattr(markup, "inline_keyboard", None) or getattr(markup, "keyboard", None) or []
    for row in rows:
        for btn in row:
            label = getattr(btn, "text", None)
            if not label:
                continue
            labels.append(label)
            data = getattr(btn, "callback_data", None)
            if data:
                cbs[label] = data
            elif getattr(btn, "web_app", None):
                cbs[label] = f"(webapp) {btn.web_app.url[:60]}"
    return labels, cbs


class RecordingSession(BaseSession):
    """No network. Records what the bot tried to send."""

    async def close(self):
        pass

    async def make_request(self, bot, method: TelegramMethod, timeout=None):
        if isinstance(method, (SendMessage, EditMessageText)):
            screen.text = method.text or ""
            screen.sent.append(screen.text)
            screen.buttons, screen.callbacks = _collect_markup(method.reply_markup)
            _msg_id[0] += 1
            return _fake_message(screen.text)
        if isinstance(method, SendPhoto):
            screen.text = (method.caption or "") + "\n[photo]"
            screen.sent.append(screen.text)
            screen.buttons, screen.callbacks = _collect_markup(method.reply_markup)
            _msg_id[0] += 1
            return _fake_message(screen.text)
        if isinstance(method, (EditMessageMedia, EditMessageCaption)):
            cap = getattr(getattr(method, "media", None), "caption", None) or getattr(method, "caption", "")
            screen.text = (cap or "") + "\n[photo]"
            screen.sent.append(screen.text)
            screen.buttons, screen.callbacks = _collect_markup(method.reply_markup)
            return _fake_message(screen.text)
        if isinstance(method, EditMessageReplyMarkup):
            screen.buttons, screen.callbacks = _collect_markup(method.reply_markup)
            return True
        if isinstance(method, AnswerCallbackQuery):
            if method.text:
                screen.alerts.append(method.text)
            return True
        if isinstance(method, DeleteMessage):
            return True
        return True

    async def stream_content(self, *a, **kw):  # pragma: no cover
        raise NotImplementedError
        yield


def _user():
    return TgUser(id=TEST_CHAT_ID, is_bot=False, first_name="QA", username="qa_phone",
                  language_code="fa")


def _chat():
    return TgChat(id=TEST_CHAT_ID, type="private")


def _fake_message(text):
    return TgMessage(message_id=_msg_id[0], date=datetime.now(), chat=_chat(),
                     from_user=_user(), text=text)


# ── the finger ──────────────────────────────────────────────────────────────
class Phone:
    def __init__(self, dp, bot):
        self.dp, self.bot = dp, bot

    async def _feed(self, update):
        import time as _t
        screen.alerts.clear()
        screen.sent.clear()
        t0 = _t.perf_counter()
        try:
            await self.dp.feed_update(self.bot, update)
        except Exception as exc:
            screen.errors.append(f"{type(exc).__name__}: {exc}")
            print(f"  !! HANDLER CRASHED: {type(exc).__name__}: {exc}")
        screen.last_ms = int((_t.perf_counter() - t0) * 1000)
        if screen.last_ms > 2000:
            print(f"  !! SLOW: that tap took {screen.last_ms/1000:.1f}s")
            screen.slow.append((getattr(screen, "_what", "?"), screen.last_ms))
        return screen

    async def type(self, text, title=None):
        """Type a message (or tap a reply-keyboard button, same thing)."""
        screen._what = title or f'typed "{text}"'
        _msg_id[0] += 1
        msg = TgMessage(message_id=_msg_id[0], date=datetime.now(), chat=_chat(),
                        from_user=_user(), text=text)
        await self._feed(Update(update_id=_msg_id[0], message=msg))
        screen.show(title or f'typed "{text}"')
        return screen

    async def tap(self, label, title=None):
        """Tap a button by its visible label — inline or reply keyboard."""
        data = screen.callbacks.get(label)
        if data is None:
            match = [b for b in screen.buttons if label in b]
            if not match:
                print(f"  !! NO SUCH BUTTON: {label!r}")
                print(f"     on screen: {screen.buttons}")
                screen.errors.append(f"missing button: {label}")
                return screen
            data = screen.callbacks.get(match[0])
            label = match[0]
        if data is None or data.startswith("(webapp)"):
            return await self.type(label, title or f'tapped "{label}"')
        screen._what = title or f'tapped "{label}"'
        _msg_id[0] += 1
        cb = CallbackQuery(
            id=str(_msg_id[0]), from_user=_user(), chat_instance="qa",
            data=data, message=_fake_message(screen.text))
        await self._feed(Update(update_id=_msg_id[0], callback_query=cb))
        screen.show(title or f'tapped "{label}" ({data})')
        return screen


# ── wiring ──────────────────────────────────────────────────────────────────
async def build_phone():
    from app.core.redis_config import init_redis
    from app.database.models import AsyncSessionLocal
    from app.handlers.user import (
        add_subscription,
        charge,
        common,
        flow_inline,
        my_services,
        purchase,
        referral,
        start,
        support,
        tutorials,
    )
    from app.handlers.user import game as game_router
    from app.handlers.user.rewards import challenges as challenges_router
    from app.handlers.user.rewards import router as rewards_router
    from app.handlers.user.rewards import star_levels as star_levels_router
    from app.utils.banned_user_middleware import BannedUserMiddleware
    from app.utils.error_middleware import (
        ErrorHandlingMiddleware,
        PerformanceMiddleware,
        ValidationMiddleware,
    )

    # These two are five-liners defined inside main.py; importing that module
    # would boot the whole bot, so they are copied rather than imported.
    class DbSessionMiddleware:
        def __init__(self, session_pool):
            self.session_pool = session_pool

        async def __call__(self, handler, event, data):
            async with self.session_pool() as session:
                data["session"] = session
                return await handler(event, data)

    class DispatcherMiddleware:
        def __init__(self, dp):
            self.dp = dp

        async def __call__(self, handler, event, data):
            data["dispatcher"] = self.dp
            return await handler(event, data)
    from app.utils.webapp_lock_middleware import WebappLockMiddleware

    await init_redis()

    bot = Bot(token="42:QA-token", session=RecordingSession(),
              default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())

    # Same middlewares as main.py, minus the rate limiter: a scripted run taps
    # far faster than a thumb and would trip it, which tells us nothing.
    dp.update.outer_middleware.register(DbSessionMiddleware(session_pool=AsyncSessionLocal))
    dp.update.outer_middleware.register(ErrorHandlingMiddleware())
    dp.update.outer_middleware.register(ValidationMiddleware())
    dp.update.outer_middleware.register(PerformanceMiddleware())
    dp.update.outer_middleware.register(BannedUserMiddleware())
    dp.update.outer_middleware.register(WebappLockMiddleware())
    dp.update.outer_middleware.register(DispatcherMiddleware(dp))
    dp["notification_queue"] = asyncio.Queue()

    for r in (start.router, flow_inline.router, purchase.router, referral.router,
              rewards_router, my_services.router, tutorials.router, charge.router,
              add_subscription.router, common.router, support.router,
              challenges_router.router, game_router.router, star_levels_router.router):
        dp.include_router(r)

    # Warm the render pool here too. The bot warms its own at startup; without
    # this the simulator would pay the 7s cold start itself and report a slow
    # step that no customer ever sees.
    try:
        from app.utils.render_manager import warm_up
        await warm_up()
    except Exception as exc:
        print(f"(render pool warm-up skipped: {type(exc).__name__})")

    return Phone(dp, bot), bot


# ── scenarios ───────────────────────────────────────────────────────────────
async def scenario_start(p: Phone):
    print("\n=== SCENARIO: first open ===")
    await p.type("/start")


async def scenario_purchase(p: Phone):
    print("\n=== SCENARIO: buy a plan ===")
    await p.type("/start")
    if "lang_fa" in screen.callbacks.values():
        await p.tap("فارسی")
    if "کد دعوت" in screen.text:
        # New customers hit the invite gate first. Use a real code, the way a
        # customer would after asking a friend for one.
        await p.type(INVITE_CODE, "entered an invite code")
    await p.type("/start", "main menu")
    for label in ("خرید", "خريد", "Buy"):
        if any(label in b for b in screen.buttons):
            await p.tap(label, "opened the shop")
            break
    else:
        print(f"  !! no buy button on the main menu: {screen.buttons}")
        return
    await p.tap("اشتراک معمولی", "normal plans")
    await p.tap("۲۰ گیگ", "picked a plan")
    await p.tap("بدون تمدید", "declined auto-renew")
    await p.type("qatest1", "typed a service name")
    await p.tap("تایید و پرداخت", "payment page")


async def _to_shop(p: Phone):
    await p.type("/start")
    if "lang_fa" in screen.callbacks.values():
        await p.tap("فارسی")
    if "کد دعوت" in screen.text:
        await p.type(INVITE_CODE)
    await p.type("/start")
    await p.tap("خرید", "shop")


async def scenario_freetest(p: Phone):
    """The free trial provisions for real: no name step, no receipt."""
    print("\n=== SCENARIO: free trial (creates a REAL panel account) ===")
    await _to_shop(p)
    await p.tap("اشتراک معمولی", "normal plans")
    if not any("تست رایگان" in b for b in screen.buttons):
        print("  !! no free-test button (already used, or hidden on cooldown)")
        return
    await p.tap("تست رایگان", "took the free trial")


async def scenario_pro(p: Phone):
    """Pro is sold per GB; check the price the bot quotes."""
    print("\n=== SCENARIO: Pro route ===")
    await _to_shop(p)
    await p.tap("اشتراک پرو", "pro menu")
    await p.tap("خرید اشتراک پرو", "pro gb prompt")
    await p.type("15", "asked for 15 GB")
    await p.tap("بدون تمدید", "declined auto-renew")
    await p.type("qapro1", "named it")


async def _to_menu(p: Phone):
    await p.type("/start")
    if "lang_fa" in screen.callbacks.values():
        await p.tap("فارسی")
    if "کد دعوت" in screen.text:
        await p.type(INVITE_CODE)
    await p.type("/start")


async def scenario_services(p: Phone):
    """My services -> open one -> links, usage, renew."""
    print("\n=== SCENARIO: my services ===")
    await _to_menu(p)
    await p.tap("سرویس‌های من", "service list")
    sub = next((b for b in screen.buttons if screen.callbacks.get(b, "").startswith("svc_")), None)
    if not sub:
        print(f"  !! no subscription button: {screen.buttons}")
        return
    await p.tap(sub, "opened a subscription")
    for want, title in (("همه لینک‌ها", "all links"), ("نمودار مصرف", "usage chart")):
        if any(want in b for b in screen.buttons):
            await p.tap(want, title)


async def scenario_renew(p: Phone):
    """Renewal: the plan the customer is already on must be first."""
    print("\n=== SCENARIO: renew / charge ===")
    await _to_menu(p)
    await p.tap("شارژ سرویس", "charge menu")
    sub = next((b for b in screen.buttons
                if screen.callbacks.get(b, "").startswith(("charge_", "svc_"))), None)
    if not sub:
        print(f"  !! nothing chargeable: {screen.buttons}")
        return
    await p.tap(sub, "picked a subscription to charge")


async def scenario_support(p: Phone):
    """Open a ticket and see whether the assistant answers."""
    print("\n=== SCENARIO: support ticket ===")
    await _to_menu(p)
    await p.tap("پشتیبانی", "support menu")


async def scenario_rewards(p: Phone):
    print("\n=== SCENARIO: rewards ===")
    await _to_menu(p)
    await p.tap("پاداش", "rewards")


async def scenario_referral(p: Phone):
    print("\n=== SCENARIO: referral ===")
    await _to_menu(p)
    await p.tap("کد دعوت", "referral")


SCENARIOS = {"start": scenario_start, "purchase": scenario_purchase,
             "freetest": scenario_freetest, "pro": scenario_pro,
             "services": scenario_services, "renew": scenario_renew,
             "support": scenario_support, "rewards": scenario_rewards,
             "referral": scenario_referral}


async def cleanup():
    """Remove everything this run created, including panel accounts."""
    from app.database.models import AsyncSessionLocal, Subscription, User
    from sqlalchemy import select
    async with AsyncSessionLocal() as s:
        user = (await s.execute(select(User).where(User.chat_id == TEST_CHAT_ID))).scalar_one_or_none()
        if not user:
            print("cleanup: no test user")
            return
        subs = (await s.execute(select(Subscription).where(Subscription.user_id == user.id))).scalars().all()
        for sub in subs:
            if sub.marzban_username:
                try:
                    from app.services.pasarguard import pasarguard_api
                    await pasarguard_api.delete_user(sub.marzban_username)
                    print(f"cleanup: deleted panel account {sub.marzban_username}")
                except Exception as exc:
                    print(f"cleanup: panel delete failed for {sub.marzban_username}: {exc}")
        # Delete the subscription rows too. Free-test eligibility is DERIVED
        # from this table, so removing them makes the next run repeatable
        # (the user row stays, which skips the invite gate).
        from sqlalchemy import text as _text
        for sub in subs:
            await s.execute(_text("DELETE FROM renewal_history WHERE subscription_id = :i"),
                            {"i": sub.id})
            await s.delete(sub)
        await s.commit()
        print(f"cleanup: removed {len(subs)} subscription(s); test user id={user.id} kept")


async def main():
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    p, bot = await build_phone()
    try:
        for name in (args or SCENARIOS):
            if name not in SCENARIOS:
                print(f"unknown scenario: {name}; have {list(SCENARIOS)}")
                continue
            await SCENARIOS[name](p)
        print()
        if screen.errors:
            print(f"{len(screen.errors)} PROBLEM(S):")
            for e in screen.errors:
                print(f"  - {e}")
        else:
            print("no crashes, no dead buttons")
        if screen.slow:
            print("\nSLOW STEPS (a thumb notices anything over ~1s):")
            for what, ms in screen.slow:
                print(f"  {ms/1000:5.1f}s  {what}")
    finally:
        await bot.session.close()
        if "--cleanup" in sys.argv:
            await cleanup()


if __name__ == "__main__":
    asyncio.run(main())

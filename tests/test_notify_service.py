"""Notification catalog + notify() single write path (rework phase 1).

- every catalog type renders fa+en from sample ctx: zero emojis, no unfilled
  placeholders, ctx placeholders all documented in ctx_doc
- render(): unknown lang falls back to fa; missing ctx raises with strict=True
  and falls back to the raw template on the production path
- notify(): dm=False writes the row without touching the bot resolver
- notify(): dm=True sends the DM through a stubbed bot and stamps
  bot_message_sent + bot_message_id
- DM failure: row survives, bot_message_sent stays False and sent_to_bot flips
  False (replay-proof: no later sweep can pick it up)
- get_unread_count is a real COUNT(*) (read rows and webapp-hidden rows excluded)
- to_payload(): computed category/icon/deeplink for known types, system/no
  deeplink fallback for unknown legacy types

Run: PYTHONPATH=src python tests/test_notify_service.py
"""
import asyncio
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import app.services.notify as notify_svc  # noqa: E402
from app.core.notification_catalog import (  # noqa: E402
    CATALOG,
    CATEGORIES,
    NotificationType,
    charge_denied_ctx,
    purchase_denied_ctx,
    render,
    template_placeholders,
)
from app.database.models import Base, Notification, User  # noqa: E402
from app.database.notifications_crud import (  # noqa: E402
    create_notification,
    get_unread_count,
    get_user_notifications,
    mark_notification_as_read,
)
from app.services.notify import notify, to_payload  # noqa: E402
from sqlalchemy import select  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

EMOJI_RE = re.compile(
    "["
    "\U0001F000-\U0001FAFF"  # pictographs, emoticons, transport, flags, supplemental
    "\u2300-\u23FF"          # misc technical (clocks, hourglasses)
    "\u2600-\u27BF"          # misc symbols + dingbats (warning, check, cross)
    "\u2B00-\u2BFF"          # arrows/stars block (star emoji)
    "\u203C\u2049\u20E3\uFE0F"
    "]"
)

# One sample value per documented ctx placeholder across the whole catalog.
SAMPLE_CTX = {
    "service_name": "astro_user_42",
    "plan_name": "پلن ۵۰ گیگ",
    "service_ref": " «astro_user_42» (پلن ۵۰ گیگ)",
    "details": " جزئیات نمونه.",
    "request_id": 17,
    "amount": "150,000",
    "duration": "۳۰ روز",
    "status": "فعال",
    "title": "عنوان نمونه",
    "body": "متن نمونه",
    "ticket_no": 5,
    "changes": "+۳۰ روز و +۱۰ GB",
    "delta": "+50,000",
    "balance": "175,000",
    "remaining_gb": "1.5",
    "percent": "12",
    "days_left": "۳",
}

LEFTOVER_PLACEHOLDER_RE = re.compile(r"\{[a-zA-Z_][a-zA-Z0-9_]*\}")


class StubBot:
    def __init__(self, fail: bool = False):
        self.fail = fail
        self.sent = []
        self.markups = []

    async def send_message(self, chat_id, text, **kwargs):
        if self.fail:
            raise RuntimeError("telegram unreachable (stub)")
        self.sent.append((chat_id, text))
        self.markups.append(kwargs.get("reply_markup"))

        class _Msg:
            message_id = 4242

        return _Msg()


def test_catalog_rendering():
    assert len(NotificationType) == 20, f"expected 20 types, got {len(NotificationType)}"
    for nt in NotificationType:
        entry = CATALOG[nt]
        assert entry.category in CATEGORIES, (nt, entry.category)
        assert entry.icon and not EMOJI_RE.search(entry.icon), (nt, entry.icon)

        placeholders = set()
        for tpl in (entry.title_fa, entry.title_en, entry.body_fa, entry.body_en):
            placeholders |= template_placeholders(tpl)
        assert placeholders == set(entry.ctx_doc.keys()), (
            f"{nt.value}: template placeholders {placeholders} != documented ctx {set(entry.ctx_doc)}"
        )
        missing_samples = placeholders - set(SAMPLE_CTX)
        assert not missing_samples, f"{nt.value}: no sample value for {missing_samples}"

        ctx = {k: SAMPLE_CTX[k] for k in placeholders}
        for lang in ("fa", "en"):
            title, body = render(nt, lang, ctx, strict=True)
            for text in (title, body):
                assert text.strip(), (nt, lang)
                hit = EMOJI_RE.search(text)
                assert not hit, f"{nt.value}/{lang} contains emoji {hit.group()!r}: {text!r}"
                left = LEFTOVER_PLACEHOLDER_RE.search(text)
                assert not left, f"{nt.value}/{lang} has unfilled placeholder {left.group()}: {text!r}"

        # deeplink templates may only reference ticket_id (filled from the row)
        if entry.deeplink:
            assert template_placeholders(entry.deeplink) <= {"ticket_id"}, (nt, entry.deeplink)
    print("PASS all 20 catalog types render fa+en: no emojis, no unfilled placeholders, ctx documented")

    fa = render(NotificationType.VIP_DENIED, "fa", {}, strict=True)
    assert render(NotificationType.VIP_DENIED, None, {}, strict=True) == fa
    assert render(NotificationType.VIP_DENIED, "de", {}, strict=True) == fa
    assert render(NotificationType.VIP_DENIED, "en", {}, strict=True) != fa
    print("PASS unknown/missing language falls back to fa")

    try:
        render(NotificationType.CASHOUT_PAID, "fa", {}, strict=True)
        raise AssertionError("expected KeyError for missing ctx in strict mode")
    except KeyError:
        pass
    title, body = render(NotificationType.CASHOUT_PAID, "fa", {})  # production path
    assert "{request_id}" in body, "non-strict render must fall back to the raw template"
    print("PASS missing ctx raises in strict mode, falls back to raw template otherwise")

    try:
        render("no_such_type", "fa", {})
        raise AssertionError("expected ValueError for unknown type")
    except ValueError:
        pass
    print("PASS unknown type rejected by render()")

    # shared ctx builders feed their templates completely, in both languages
    for lang in ("fa", "en"):
        ctx = purchase_denied_ctx(lang, service_name="svc", plan_name="p50",
                                  credit_refunded=50000, discounts_restored=True,
                                  coupon_restored=True)
        _, body = render(NotificationType.PURCHASE_DENIED, lang, ctx, strict=True)
        assert "svc" in body and "50,000" in body and not LEFTOVER_PLACEHOLDER_RE.search(body)
        ctx = purchase_denied_ctx(lang, service_name=None, plan_name=None)
        _, body = render(NotificationType.PURCHASE_DENIED, lang, ctx, strict=True)
        assert not LEFTOVER_PLACEHOLDER_RE.search(body)

        ctx = charge_denied_ctx(lang, service_name="svc", credit_refunded=80000)
        _, body = render(NotificationType.CHARGE_DENIED, lang, ctx, strict=True)
        assert "svc" in body and "80,000" in body and not LEFTOVER_PLACEHOLDER_RE.search(body)
        ctx = charge_denied_ctx(lang, service_name=None)
        _, body = render(NotificationType.CHARGE_DENIED, lang, ctx, strict=True)
        assert not LEFTOVER_PLACEHOLDER_RE.search(body)
    print("PASS purchase_denied_ctx / charge_denied_ctx render their templates in fa+en")


async def test_notify_paths(Session):
    def forbid_bot():
        raise AssertionError("bot resolver must not be called for a dm=False type")

    # (b) dm=False type: row only, resolver untouched
    async with Session() as db:
        notify_svc._resolve_bot = forbid_bot
        n = await notify(db, 1, NotificationType.GENERAL, {"title": "اطلاعیه", "body": "متن اطلاعیه"})
        assert n.id and n.type == "general"
        assert n.title == "اطلاعیه" and n.message == "متن اطلاعیه"
        assert n.sent_to_webapp is True and n.sent_to_bot is False
        assert n.bot_message_sent is False and n.bot_message_id is None
    print("PASS dm=False type writes the row and never resolves the bot")

    # (c) dm=True type with a working stub bot
    async with Session() as db:
        stub = StubBot()
        notify_svc._resolve_bot = lambda: stub
        ctx = {"service_name": "astro_user_42", "details": " حجم افزوده‌شده: 30 GB"}
        n = await notify(db, 1, "charge_approved", ctx)
        assert n.sent_to_bot is True and n.bot_message_sent is True and n.bot_message_id == 4242
        assert len(stub.sent) == 1
        chat_id, text = stub.sent[0]
        assert chat_id == 111
        assert text == f"{n.title}\n\n{n.message}"
        assert n.title == "شارژ تایید شد" and "astro_user_42" in n.message
    print("PASS dm=True type sends the DM and stamps bot_message_sent + bot_message_id")

    # language resolution: en user gets English copy
    async with Session() as db:
        stub = StubBot()
        notify_svc._resolve_bot = lambda: stub
        n = await notify(db, 2, NotificationType.VIP_DENIED, {})
        assert n.title == "VIP request denied", n.title
        assert stub.sent[0][0] == 222
    print("PASS user language (en) picked from the User row")

    # (d) DM failure: row survives, replay-proof flags
    async with Session() as db:
        broken = StubBot(fail=True)
        notify_svc._resolve_bot = lambda: broken
        n = await notify(db, 1, NotificationType.CASHOUT_PAID, {"request_id": 9, "amount": "80,000"})
        assert n.id, "row must survive a DM failure"
        assert n.bot_message_sent is False and n.bot_message_id is None
        assert n.sent_to_bot is False, "sent_to_bot must flip False on DM failure (replay-proof)"

    async with Session() as db:
        replayable = (await db.execute(
            select(Notification).where(
                Notification.sent_to_bot.is_(True),
                Notification.bot_message_sent.is_(False),
            )
        )).scalars().all()
        assert not replayable, f"rows still eligible for a bot replay sweep: {[r.id for r in replayable]}"
    print("PASS DM failure keeps the row but flips sent_to_bot=False (no replay possible)")

    # unknown type
    async with Session() as db:
        try:
            await notify(db, 1, "made_up_type", {})
            raise AssertionError("expected ValueError for unknown type")
        except ValueError:
            pass
    print("PASS notify() rejects unknown types with ValueError")

    # dm_override=False on a dm=True type: row only, resolver untouched,
    # sent_to_bot=False (call site delivers its own rich DM instead)
    async with Session() as db:
        notify_svc._resolve_bot = forbid_bot
        assert CATALOG[NotificationType.PURCHASE_APPROVED].dm is True
        n = await notify(db, 1, NotificationType.PURCHASE_APPROVED,
                         {"service_name": "svc", "plan_name": "پلن"}, dm_override=False)
        assert n.id and n.sent_to_webapp is True
        assert n.sent_to_bot is False and n.bot_message_sent is False and n.bot_message_id is None
    print("PASS dm_override=False suppresses the DM on a dm=True type (row only)")

    # dm_override=True on a dm=False type: DM sent + stamped (broadcast to bot)
    async with Session() as db:
        stub = StubBot()
        notify_svc._resolve_bot = lambda: stub
        assert CATALOG[NotificationType.GENERAL].dm is False
        n = await notify(db, 1, NotificationType.GENERAL,
                         {"title": "اطلاعیه", "body": "متن"}, dm_override=True)
        assert n.sent_to_bot is True and n.bot_message_sent is True and n.bot_message_id == 4242
        assert len(stub.sent) == 1 and stub.markups == [None]
    print("PASS dm_override=True forces the DM on a dm=False type")

    # dm_reply_markup is passed through to send_message (ticket deep-link button)
    async with Session() as db:
        stub = StubBot()
        notify_svc._resolve_bot = lambda: stub
        markup = object()
        n = await notify(db, 1, NotificationType.TICKET_NEW_MESSAGE,
                         {"ticket_no": 7}, ticket_id=7, dm_reply_markup=markup)
        assert n.bot_message_sent is True
        assert stub.markups == [markup]
    print("PASS dm_reply_markup reaches send_message")


async def test_unread_count(Session):
    async with Session() as db:
        a = await create_notification(db, user_id=3, type="general", title="t1", message="m1")
        await create_notification(db, user_id=3, type="general", title="t2", message="m2")
        await create_notification(db, user_id=3, type="general", title="t3", message="m3")
        # hidden-from-webapp row must not count
        db.add(Notification(user_id=3, type="general", title="t4", message="m4",
                            sent_to_webapp=False, sent_to_bot=False))
        await db.commit()

        assert await get_unread_count(db, 3) == 3
        await mark_notification_as_read(db, a.id, 3)
        count = await get_unread_count(db, 3)
        assert count == 2, count
        assert isinstance(count, int)
        unread_rows = await get_user_notifications(db, 3, unread_only=True)
        assert len(unread_rows) == count
        assert await get_unread_count(db, 999) == 0
    print("PASS unread count is a correct COUNT(*): excludes read and webapp-hidden rows")


async def test_to_payload(Session):
    async with Session() as db:
        stub = StubBot()
        notify_svc._resolve_bot = lambda: stub
        n = await notify(db, 1, NotificationType.CHARGE_APPROVED,
                         {"service_name": "svc", "details": ""})
        p = to_payload(n)
        assert p["category"] == "money" and p["icon"] == "check-circle" and p["deeplink"] == "services"
        assert p["id"] == n.id and p["type"] == "charge_approved" and p["read"] is False
        assert p["created_at"] and p["title"] == n.title and p["message"] == n.message

        t = await notify(db, 1, NotificationType.TICKET_NEW_MESSAGE, {"ticket_no": 12}, ticket_id=12)
        pt = to_payload(t)
        assert pt["category"] == "support" and pt["deeplink"] == "support?ticket_id=12"
        assert pt["ticket_id"] == 12

        # ticket-type row without a ticket_id: deeplink degrades to None
        orphan = Notification(user_id=1, type="ticket_closed", title="x", message="y")
        db.add(orphan)
        await db.commit()
        await db.refresh(orphan)
        assert to_payload(orphan)["deeplink"] is None

        legacy = Notification(user_id=1, type="ticket_status_changed", title="old", message="row")
        db.add(legacy)
        await db.commit()
        await db.refresh(legacy)
        pl = to_payload(legacy)
        assert pl["category"] == "system" and pl["icon"] == "bell" and pl["deeplink"] is None
    print("PASS to_payload computes category/icon/deeplink; legacy unknown types fall back to system")


async def main():
    eng = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with eng.begin() as c:
        await c.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(eng, expire_on_commit=False)
    async with Session() as db:
        db.add(User(id=1, chat_id=111, referral_code="r1"))                  # language defaults to fa
        db.add(User(id=2, chat_id=222, referral_code="r2", language="en"))
        db.add(User(id=3, chat_id=333, referral_code="r3"))
        await db.commit()

    test_catalog_rendering()
    await test_notify_paths(Session)
    await test_unread_count(Session)
    await test_to_payload(Session)

    print("test_notify_service: OK")


asyncio.run(main())

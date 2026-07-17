"""Shared purchase-order flow: create / cancel / receipt / deny.

Used by both the webapp routes (``api/routes/dashboard_purchase``) and the bot
purchase FSM (``handlers/user/purchase``). Money rules live here once:

- order rows start as ``draft`` and become ``pending`` only when a receipt arrives;
- credit / user-discounts / the reward coupon are consumed atomically at order
  creation and restored on every exit path (cancel, deny, auto-approve failure);
- fully-covered orders (final price <= 0) are provisioned immediately through
  ``process_approved_subscription`` with a full rollback when PasarGuard fails.
"""
from __future__ import annotations

import logging
import random
import re
import string
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.database import crud
from app.database.models import Subscription, UserDiscount
from app.services.flows.errors import FlowError
from app.services.flows.pricing import PurchaseQuote

logger = logging.getLogger(__name__)

SERVICE_NAME_RE = re.compile(r"^[A-Za-z0-9]{3,20}$")

# States in which an order has no verified payment yet and may be cancelled/denied
# with a full refund of everything consumed at creation time.
_REFUNDABLE_STATUSES = ("draft", "pending")


@dataclass
class OrderResult:
    subscription: Subscription
    quote: PurchaseQuote
    auto_approved: bool = False


@dataclass
class DenyResult:
    user_id: int
    credit_refunded: int
    discounts_restored: bool
    coupon_restored: bool
    service_name: str | None
    plan_name: str | None


# ── username helpers (canonical; both surfaces' duplicates defer here) ──────────

_PANEL_SEED_BAD_RE = re.compile(r"[^A-Za-z0-9_]+")
_PANEL_SEED_RUNS_RE = re.compile(r"_{2,}")


def sanitize_panel_username_seed(seed: str) -> str:
    """Make a seed safe for PasarGuard usernames before any suffix is appended.

    PasarGuard 422s "Username cannot have consecutive special characters" when
    a seam creates them (bakbot incident: customer name "YMS_" + "_ab12" ->
    "YMS__ab12"). Collapse repeated underscores, fold other specials to one
    underscore, and trim leading/trailing underscores; empty seeds (e.g. an
    all-Persian Telegram name) fall back to "user"."""
    s = _PANEL_SEED_BAD_RE.sub("_", str(seed or ""))
    s = _PANEL_SEED_RUNS_RE.sub("_", s).strip("_")
    return s or "user"


async def is_service_name_taken(session: AsyncSession, username: str) -> bool:
    """True if the name exists locally or on PasarGuard."""
    if await crud.get_subscription_by_username(session, username):
        return True
    from app.services.pasarguard import pasarguard_api

    return await pasarguard_api.get_user_info(username) is not None


async def generate_unique_service_name(session: AsyncSession, base_username: str) -> str:
    """Append a counter until the name is free both in our DB and on PasarGuard.

    The seed is sanitized first (gift flow feeds raw Telegram usernames /
    full names here — "YMS_"-style seeds used to reach the panel unchanged)."""
    base = sanitize_panel_username_seed(base_username)
    username = base
    i = 1
    while await is_service_name_taken(session, username):
        username = f"{base}{i}"
        i += 1
    return username


async def resolve_service_name(session: AsyncSession, service_name: str | None) -> str:
    """Validate a user-chosen service name, or generate a random unique one."""
    if service_name:
        if not SERVICE_NAME_RE.fullmatch(service_name):
            raise FlowError("invalid_service_name", "Service name must be 3-20 English letters/digits")
        if await is_service_name_taken(session, service_name):
            raise FlowError("service_name_taken", "This service name is already taken")
        return service_name
    base = "".join(random.choices(string.ascii_lowercase + string.digits, k=8))
    return await generate_unique_service_name(session, base)


# ── order lifecycle ──────────────────────────────────────────────────────────────

async def start_purchase_order(
    session: AsyncSession,
    user,
    *,
    quote: PurchaseQuote,
    service_name: str | None = None,
    referrer_id: int | None = None,
    auto_renewal: bool = False,
    bot=None,
) -> OrderResult:
    """Create the order row and consume credit/discounts/coupon.

    ``bot`` is the **user** Telegram bot, required only for the auto-approve path
    (it DMs the subscription link). Raises FlowError(auto_approve_failed) after a
    full rollback when provisioning fails.
    """
    from datetime import datetime

    marzban_username = await resolve_service_name(session, service_name)

    renewal_plan = quote.renewal_plan if auto_renewal else None
    sub = await crud.create_subscription(
        db=session,
        user_id=user.id,
        referrer_id=referrer_id,
        marzban_username=marzban_username,
        plan=quote.plan_name,
        receipt_message_id=None,
        renewal_paid=auto_renewal,
        renewal_template=renewal_plan,
        renewal_price=quote.renewal_price if renewal_plan else None,
        renewal_requested_at=datetime.utcnow() if auto_renewal else None,
        renewal_applied=False,
        price=quote.plan_price,
        status="draft",
    )

    sub.credit_used = quote.credit_used
    sub.applied_discount_ids = (
        ",".join(str(i) for i in quote.applied_discount_ids) if quote.applied_discount_ids else None
    )
    sub.applied_coupon_id = quote.coupon.id if quote.coupon else None
    # Net toman the buyer actually transfers (after credit/discount/coupon) —
    # the figure a bank-deposit SMS carries, for SMS auto-approval matching.
    sub.paid_amount = int(quote.final_price)
    await session.commit()
    await session.refresh(sub)

    if quote.credit_used > 0:
        if await crud.deduct_credit(session, user.id, quote.credit_used) is None:
            await crud.delete_subscription(session, sub.id)
            raise FlowError("insufficient_credit", "Not enough credit")
    if quote.applied_discount_ids:
        await crud.mark_user_discounts_used(session, quote.applied_discount_ids)
    if quote.coupon:
        await crud.mark_coupon_used(session, quote.coupon.id)

    if quote.final_price <= 0:
        await _auto_approve(session, sub, bot)
        return OrderResult(subscription=sub, quote=quote, auto_approved=True)

    return OrderResult(subscription=sub, quote=quote)


async def _auto_approve(session: AsyncSession, sub: Subscription, bot) -> None:
    """Provision a fully-covered order now; roll everything back on failure."""
    from app.services.subscription_processing import process_approved_subscription

    ok = False
    if bot is not None:
        # process_approved_subscription only activates orders in "pending".
        sub.status = "pending"
        await session.commit()
        try:
            ok = await process_approved_subscription(sub.id, session, bot, approved_by="سیستم (پرداخت با اعتبار)")
        except Exception as e:
            logger.error(f"Auto-approve failed for order {sub.id}: {e}")
            ok = False
    else:
        # No user bot in this process: provision directly (no link DM). The coupon's
        # free_gb bonus must still apply, same as process_approved_subscription does.
        try:
            # Read PLANS through the pricing module so tests (and runtime catalog
            # reloads) see one consistent source.
            from app.services.flows import pricing as _pricing

            plan_info = _pricing.get_plan_info(sub.plan_name)
            if not plan_info:
                raise FlowError("invalid_plan", f"Unknown plan {sub.plan_name}")
            bonus_gb = await crud.free_gb_bonus_for_coupon(session, getattr(sub, "applied_coupon_id", None))
            if bonus_gb > 0:
                plan_info = {**plan_info, "gb": int(plan_info.get("gb") or 0) + int(bonus_gb)}
            pasarguard_info = await crud.create_subscription_on_pasarguard(sub, plan_info)
            if pasarguard_info and pasarguard_info.get("subscription_url"):
                await crud.activate_subscription(session, sub.id)
                try:
                    sub.user_link_sent = True
                    await session.commit()
                except Exception:
                    pass
                ok = True
        except Exception as e:
            logger.error(f"Auto-approve (botless) failed for order {sub.id}: {e}")
            ok = False

    if not ok:
        try:
            await _rollback_order(session, sub)
        except Exception as e:
            logger.error(f"Rollback after failed auto-approve of order {sub.id} failed: {e}")
        raise FlowError("auto_approve_failed", "Purchase could not be completed automatically. Please try again.")


async def cancel_purchase_order(session: AsyncSession, user, order_id: int) -> None:
    """User-initiated cancel of an order that has no receipt yet. Refunds everything."""
    sub = await session.get(Subscription, order_id)
    if not sub:
        raise FlowError("order_not_found")
    if sub.user_id != user.id:
        raise FlowError("unauthorized")
    if sub.receipt_message_id is not None or (sub.status or "") not in _REFUNDABLE_STATUSES:
        raise FlowError("cannot_cancel")
    await _rollback_order(session, sub)


async def submit_purchase_receipt(
    session: AsyncSession,
    user,
    order_id: int,
    *,
    receipt_message_id: int | None = None,
    receipt_image_url: str | None = None,
) -> Subscription:
    """Attach a payment receipt to a draft/pending order and mark it pending.

    The transport supplies either the Telegram photo message id (bot) or a stored
    image URL (webapp, which passes ``receipt_message_id=-1`` semantics here).
    Double submission is rejected.
    """
    sub = await session.get(Subscription, order_id)
    if not sub:
        raise FlowError("order_not_found")
    if sub.user_id != user.id:
        raise FlowError("unauthorized")
    if (sub.status or "") not in _REFUNDABLE_STATUSES or sub.receipt_message_id is not None:
        raise FlowError("order_already_processed")

    sub.receipt_message_id = receipt_message_id if receipt_message_id is not None else -1
    if receipt_image_url:
        sub.receipt_image_url = receipt_image_url
    sub.status = "pending"
    await session.commit()
    await session.refresh(sub)
    return sub


async def deny_purchase_order(session: AsyncSession, sub_id: int) -> DenyResult:
    """Admin denial of a pending order: refund credit, restore discounts AND the
    consumed coupon, then delete the order row. Idempotent via the status guard.

    The atomic pending → processing claim closes the double-deny race (two taps
    both passing the status check, refunding the credit twice)."""
    from sqlalchemy import update as _sql_update

    res = await session.execute(
        _sql_update(Subscription)
        .where(Subscription.id == sub_id, Subscription.status == "pending")
        .values(status="processing")
    )
    await session.commit()
    if (res.rowcount or 0) == 0:
        sub = await session.get(Subscription, sub_id)
        raise FlowError("not_found" if not sub else "already_processed")

    sub = await session.get(Subscription, sub_id)
    if not sub:
        raise FlowError("not_found")

    result = DenyResult(
        user_id=sub.user_id,
        credit_refunded=int(sub.credit_used or 0),
        discounts_restored=bool(sub.applied_discount_ids),
        coupon_restored=bool(sub.applied_coupon_id),
        service_name=sub.marzban_username,
        plan_name=sub.plan_name,
    )
    try:
        await _rollback_order(session, sub)
    except Exception:
        # Release the claim so a transient failure mid-rollback doesn't wedge the
        # order in 'processing' (invisible to every pending queue, un-actionable,
        # user's money held). Back to 'pending' → admin can retry.
        try:
            await session.rollback()
            await session.execute(
                _sql_update(Subscription)
                .where(Subscription.id == sub_id, Subscription.status == "processing")
                .values(status="pending")
            )
            await session.commit()
        except Exception:
            logger.exception("purchase %s: could not release deny claim", sub_id)
        raise
    return result


async def _rollback_order(session: AsyncSession, sub: Subscription) -> None:
    """Return everything consumed at order creation and delete the order row.

    Shared by cancel, deny and the auto-approve failure path. Refunds always go to
    the internal ``User.id`` (NOT the Telegram chat id — that mixup silently lost
    users' credit in the old bot cancel path)."""
    if sub.credit_used and sub.credit_used > 0:
        await crud.add_credit(session, sub.user_id, int(sub.credit_used))

    if sub.applied_coupon_id:
        try:
            await crud.restore_coupon(session, sub.applied_coupon_id)
        except Exception as e:
            logger.error(f"Failed to restore coupon for order {sub.id}: {e}")

    if sub.applied_discount_ids:
        try:
            id_list = [int(x) for x in sub.applied_discount_ids.split(",") if x.strip().isdigit()]
            if id_list:
                res = await session.execute(select(UserDiscount).filter(UserDiscount.id.in_(id_list)))
                for d in res.scalars().all():
                    d.used = False
                await session.commit()
        except Exception as e:
            logger.error(f"Failed to restore discounts for order {sub.id}: {e}")

    await crud.delete_subscription(session, sub.id)

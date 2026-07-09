"""Shared cash-out (wallet withdrawal) flow.

The eligibility gate lives here — not in the webapp route — so any future surface
(bot, admin) goes through the same checks. Funds are reserved atomically by
``CashoutRepository.create_cashout_request``.
"""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.rewards_config import CASHOUT_MIN_AMOUNT_TOMAN, PROMOTER_REFERRAL_CUT
from app.database import crud
from app.database.models import CashoutRequest, Referral
from app.services.flows.errors import FlowError

# Cash payout is a VIP-Promoter-only perk (final reward map §6): normal users stay
# inside the VPN reward economy. "Active referral" = a referred user with a live
# subscription. Payout is intentionally 1:1 (no 5% haircut): credit is referral-only
# here, so it's already earned reach — discounting it punishes the best promoters.
CASHOUT_MIN_ACTIVE_REFERRALS = 20


def promoter_credit_percent(active_referrals: int) -> float:
    """Store-credit % a referrer earns per referral, by active-referral tier
    (PROMOTER_REFERRAL_CUT). 0→10%, 20→12%, 50→15%. Returns a percent (e.g. 12.0)."""
    pct = PROMOTER_REFERRAL_CUT[min(PROMOTER_REFERRAL_CUT)]
    for thr in sorted(PROMOTER_REFERRAL_CUT):
        if active_referrals >= thr:
            pct = PROMOTER_REFERRAL_CUT[thr]
    return pct * 100


# A referral counts as ACTIVE only while the referee keeps buying (Pasha
# 2026-07-09: "a good referee is one that has bought at least one sub in one
# month"): at least one provisioned subscription purchase OR one approved
# top-up inside the trailing window. Purchase recency is what counts — a
# recently-bought sub that already ran out still qualifies; an old sub that
# merely stays active does not.
ACTIVE_REFEREE_WINDOW_DAYS = 30
# Rows that were never approved/provisioned are not purchases.
_UNPAID_SUB_STATUSES = ("draft", "pending", "cancelled")


async def count_active_referrals(session: AsyncSession, user_id: int) -> int:
    import datetime as _dt

    from app.database.models import ChargeRequest, Subscription

    cutoff = _dt.datetime.utcnow() - _dt.timedelta(days=ACTIVE_REFEREE_WINDOW_DAYS)
    referee_ids = select(Referral.referee_id).where(Referral.referrer_id == user_id)

    recent_sub_buyers = (
        await session.execute(
            select(Subscription.user_id).where(
                Subscription.user_id.in_(referee_ids),
                Subscription.status.notin_(_UNPAID_SUB_STATUSES),
                Subscription.created_at >= cutoff,
            )
        )
    ).scalars().all()
    recent_chargers = (
        await session.execute(
            select(ChargeRequest.user_id).where(
                ChargeRequest.user_id.in_(referee_ids),
                ChargeRequest.status == "approved",
                ChargeRequest.created_at >= cutoff,
            )
        )
    ).scalars().all()
    return len(set(recent_sub_buyers) | set(recent_chargers))


async def create_cashout(
    session: AsyncSession,
    user,
    *,
    amount: int,
    destination: str | None = None,
) -> CashoutRequest:
    """Create a withdrawal request, reserving the amount from the user's
    CASHBACK balance (two-stage model: store credit is never withdrawable).

    Raises FlowError with codes: invalid_amount, invalid_destination,
    requires_vip_promoter (with ``.active_referrals``),
    requires_active_paid_subscription, insufficient_credit, cannot_create.
    """
    if amount <= 0:
        raise FlowError("invalid_amount")
    if amount < CASHOUT_MIN_AMOUNT_TOMAN:
        # Small balances stay in-app as spendable credit — card transfers under this
        # threshold aren't worth the manual admin round-trip.
        err = FlowError("amount_below_minimum")
        err.min_amount = CASHOUT_MIN_AMOUNT_TOMAN
        raise err
    if destination and len(destination) < 8:
        raise FlowError("invalid_destination")

    # LIVE gate (2026-07-09, replaces the permanent unlock): withdrawals
    # require >=20 active referrals RIGHT NOW. Dropping under the gate keeps
    # the earned cashback balance but pauses withdrawals until the account
    # is back above it.
    from app.services.flows.earnings import is_promoter_active

    if not await is_promoter_active(session, user):
        active_referrals = await count_active_referrals(session, user.id)
        err = FlowError("requires_vip_promoter")
        err.active_referrals = active_referrals
        err.min_active_referrals = CASHOUT_MIN_ACTIVE_REFERRALS
        raise err

    req = await crud.create_cashout_request(session, user.id, int(amount), destination)
    if req:
        return req

    # The repo refuses for one of a few reasons — surface which one.
    try:
        has_paid = await crud.has_active_paid_subscription(session, user.id)
    except Exception:
        has_paid = False
    if not has_paid:
        raise FlowError("requires_active_paid_subscription")
    if int(getattr(user, "cashback_balance", 0) or 0) < int(amount):
        raise FlowError("insufficient_credit")
    raise FlowError("cannot_create")

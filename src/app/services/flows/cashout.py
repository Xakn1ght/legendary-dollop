"""Shared cash-out (wallet withdrawal) flow.

The eligibility gate lives here — not in the webapp route — so any future surface
(bot, admin) goes through the same checks. Funds are reserved atomically by
``CashoutRepository.create_cashout_request``.
"""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.rewards_config import PROMOTER_REFERRAL_CUT
from app.database import crud
from app.database.models import CashoutRequest, Referral, User
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


async def count_active_referrals(session: AsyncSession, user_id: int) -> int:
    referees = (
        await session.execute(
            select(User).join(Referral, Referral.referee_id == User.id).filter(Referral.referrer_id == user_id)
        )
    ).scalars().all()
    active = 0
    for referee in referees:
        # Owned active subscriptions only — a shared/linked subscription shouldn't
        # qualify someone as an "active referral" for cash-out purposes.
        subs = await crud.get_user_active_subscriptions(session, referee.id)
        if subs:
            active += 1
    return active


async def create_cashout(
    session: AsyncSession,
    user,
    *,
    amount: int,
    destination: str | None = None,
) -> CashoutRequest:
    """Create a withdrawal request, reserving the amount from the user's credit.

    Raises FlowError with codes: invalid_amount, invalid_destination,
    requires_vip_promoter (with ``.active_referrals``),
    requires_active_paid_subscription, insufficient_credit, cannot_create.
    """
    if amount <= 0:
        raise FlowError("invalid_amount")
    if destination and len(destination) < 8:
        raise FlowError("invalid_destination")

    active_referrals = await count_active_referrals(session, user.id)
    if active_referrals < CASHOUT_MIN_ACTIVE_REFERRALS:
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
    if int(getattr(user, "credit", 0) or 0) < int(amount):
        raise FlowError("insufficient_credit")
    raise FlowError("cannot_create")

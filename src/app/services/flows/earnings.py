"""Two-stage referral earnings routing (Pasha's cash-back model, 2026-07-08;
LIVE gate since 2026-07-09).

The 10–15% promoter cut lands differently depending on the account stage:

- BELOW THE GATE (fewer than 20 active referrals): the cut pays STORE
  CREDIT (`User.credit`), capped at REFERRAL_STORE_CREDIT_CAP_TOMAN
  lifetime. A voucher that would bust the cap is rejected so the user can
  pick a non-credit option instead of silently losing the excess.
- AT/ABOVE THE GATE: the cut pays the withdrawable CASH balance
  (`User.cashback_balance`). Store credit earned below the gate stays
  in-app spendable and never converts.
- THE GATE IS LIVE (2026-07-09 — replaces the permanent unlock): dropping
  under 20 active referrals re-closes cash mode (new earnings go back to
  store credit, withdrawals pause) until the account is back above it.
  Already-earned cashback_balance is kept, just not extendable/withdrawable
  while under. An "active referral" is a referee who BOUGHT something
  (provisioned sub or approved top-up) within the last 30 days — see
  cashout.count_active_referrals. `promoter_unlocked_at` remains as a
  first-crossing historical marker only.

Every credit-landing surface (dashboard redeem, bot redeem) must call
`credit_referral_payout` instead of `crud.add_credit` so the routing and the
cap ledger (RewardHistory source='referral_voucher') stay consistent.
"""
from __future__ import annotations

import datetime

from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.rewards_config import REFERRAL_STORE_CREDIT_CAP_TOMAN
from app.database import crud
from app.database.models import RewardHistory, User
from app.services.flows.cashout import CASHOUT_MIN_ACTIVE_REFERRALS, count_active_referrals
from app.services.flows.errors import FlowError


async def is_promoter_active(session: AsyncSession, user: User) -> bool:
    """LIVE stage-2 check: cash mode holds only while active referrals meet
    the gate right now. First crossing still stamps `promoter_unlocked_at`
    as a historical marker (it no longer grants anything by itself)."""
    active = await count_active_referrals(session, user.id)
    if active >= CASHOUT_MIN_ACTIVE_REFERRALS:
        if not user.promoter_unlocked_at:
            user.promoter_unlocked_at = datetime.datetime.utcnow()
            await session.commit()
        return True
    return False


# Old name kept for existing callers; semantics are the LIVE gate now.
ensure_promoter_unlock = is_promoter_active


async def referral_store_credit_earned(session: AsyncSession, user_id: int) -> int:
    """Lifetime store credit granted from referral vouchers (the cap ledger)."""
    total = await session.scalar(
        select(func.sum(RewardHistory.reward_value)).where(
            RewardHistory.user_id == user_id,
            RewardHistory.source == "referral_voucher",
            RewardHistory.reward_type == "credit",
        )
    )
    return int(total or 0)


async def credit_referral_payout(session: AsyncSession, user: User, amount: int, *, source_id: int | None = None) -> str:
    """Land a referral credit payout in the right bucket.

    Returns the bucket used: "cash" or "credit".
    Raises FlowError("credit_cap_reached") when the store-credit cap leaves no
    room for this amount (nothing is granted; the voucher stays unspent).
    """
    amount = int(amount)
    if amount <= 0:
        raise FlowError("invalid_amount")

    # LIVE gate: >=20 active referrals RIGHT NOW pays cash; below it the
    # payout falls back to store credit even for previously-unlocked users.
    if await is_promoter_active(session, user):
        user.cashback_balance = int(user.cashback_balance or 0) + amount
        await session.commit()
        await crud.add_reward_history(session, user.id, "cashback", amount, "referral_voucher", source_id)
        return "cash"

    earned = await referral_store_credit_earned(session, user.id)
    if earned + amount > REFERRAL_STORE_CREDIT_CAP_TOMAN:
        err = FlowError("credit_cap_reached")
        err.cap = REFERRAL_STORE_CREDIT_CAP_TOMAN
        err.earned = earned
        raise err

    await crud.add_credit(session, user.id, amount)
    await crud.add_reward_history(session, user.id, "credit", amount, "referral_voucher", source_id)
    return "credit"

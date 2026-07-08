"""Two-stage referral earnings routing (Pasha's cash-back model, 2026-07-08).

The 10–15% promoter cut lands differently depending on the account stage:

- PRE-GATE (fewer than 20 active referrals, never unlocked): the cut pays
  STORE CREDIT (`User.credit`), capped at REFERRAL_STORE_CREDIT_CAP_TOMAN
  lifetime. A voucher that would bust the cap is rejected so the user can
  pick a non-credit option instead of silently losing the excess.
- UNLOCK: the first time the account is seen with >=20 active referrals,
  `promoter_unlocked_at` is stamped — permanently.
- POST-GATE: the cut pays the withdrawable CASH balance
  (`User.cashback_balance`). Store credit earned before the gate stays
  in-app spendable and never converts.

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


async def ensure_promoter_unlock(session: AsyncSession, user: User) -> bool:
    """Stamp the permanent unlock the first time the gate is met. Returns
    True when the account is (now) unlocked."""
    if user.promoter_unlocked_at:
        return True
    active = await count_active_referrals(session, user.id)
    if active >= CASHOUT_MIN_ACTIVE_REFERRALS:
        user.promoter_unlocked_at = datetime.datetime.utcnow()
        await session.commit()
        return True
    return False


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

    if await ensure_promoter_unlock(session, user):
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

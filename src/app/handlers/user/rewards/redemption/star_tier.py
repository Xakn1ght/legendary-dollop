"""Legacy star-tier claim flow — RETIRED (2026-07-19).

The old credit/plan/VIP tier ladder was replaced by the Star Season coupon
system on 2026-06-02 (tiers deactivated, nothing re-seeds them, no new claims
can be created since add_stars only crosses ACTIVE tiers). This module used
to hold ~470 lines of live minting code (store credit, plans-as-credit,
lifetime VIP) reachable from any stale claim button in old chat messages —
a sealed economy hole now: every legacy claim callback gets a graceful
retired notice and mints nothing.

Claims already in 'pending_subscription' state keep being honored by
services/subscription_processing.py (extra days on the next purchase) until
they expire; that path grants time, not money, and is owned by the money
workstream.
"""

from aiogram import F
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from .common import router

RETIRED_NOTICE = (
    "این بخش جوایز قدیمی جمع شده است.\n\n"
    "جای آن، سیستم «ستاره‌های فصل» فعال است: با معرفی دوستان ستاره جمع کنید "
    "تا کوپن‌های تخفیف و ترافیک رایگان به کیف کوپن شما اضافه شود."
)


async def _retired(callback: CallbackQuery):
    await callback.answer(RETIRED_NOTICE, show_alert=True)


@router.callback_query(F.data.startswith("starchoice_"))
async def handle_star_choice(callback: CallbackQuery, session: AsyncSession):
    await _retired(callback)


@router.callback_query(F.data.startswith("claim_star_reward_"))
async def claim_star_reward(callback: CallbackQuery, session: AsyncSession):
    await _retired(callback)


@router.callback_query(F.data.startswith("apply_days_"))
async def apply_days_to_subscription(callback: CallbackQuery, session: AsyncSession):
    await _retired(callback)

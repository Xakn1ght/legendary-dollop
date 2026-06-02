"""Star Season maintenance job (Phase B4).

Rotates the season when its window ends and sweeps expired coupons out of wallets.
Season rotation is also lazy (get_or_create_active_season runs on any star activity),
but this job makes it proactive and timely regardless of traffic, and expires coupons
even for users who don't open their wallet.
"""
from datetime import datetime

from sqlalchemy import select

from app.database import crud
from app.database.models import AsyncSessionLocal, RewardCoupon
from app.utils.logger import bot_logger


async def season_reset_job(bot=None):
    async with AsyncSessionLocal() as session:
        now = datetime.utcnow()

        # 1. Expire coupons past their expiry date.
        try:
            stale = (await session.execute(
                select(RewardCoupon).filter(
                    RewardCoupon.status == "active",
                    RewardCoupon.expires_at <= now,
                )
            )).scalars().all()
            for c in stale:
                c.status = "expired"
            if stale:
                await session.commit()
                bot_logger.debug(f"Season job: expired {len(stale)} coupons")
        except Exception as e:
            bot_logger.warning(f"Season job: coupon expiry error: {e}")

        # 2. Rotate the season if the active window has ended (handled inside the
        #    helper: it deactivates an expired season and opens a fresh one at 0 stars).
        try:
            season = await crud.get_or_create_active_season(session)
            bot_logger.debug(f"Season job: active season {season.id} ends {season.ends_at}")
        except Exception as e:
            bot_logger.warning(f"Season job: rotation error: {e}")

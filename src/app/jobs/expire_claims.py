from datetime import datetime, timedelta

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import AsyncSessionLocal, UserDiscount, UserStarRewardClaim
from app.utils.logger import bot_logger


async def expire_star_reward_claims_job(bot=None):
    """
    Job to find and mark unclaimed star reward claims as 'expired'
    if they are past their claim window.
    Also removes expired claimed discounts from user profiles.
    """
    async with AsyncSessionLocal() as session:
        now = datetime.utcnow()
        
        # 1. Expire unclaimed star reward claims
        try:
            expired_claims_query = select(UserStarRewardClaim).filter(
                UserStarRewardClaim.status == 'offered',
                UserStarRewardClaim.expires_at <= now
            )
            result = await session.execute(expired_claims_query)
            claims_to_expire = result.scalars().all()
            if claims_to_expire:
                for claim in claims_to_expire:
                    claim.status = 'expired'
                await session.commit()
                bot_logger.debug(f"Expired {len(claims_to_expire)} star reward claims")
        except Exception as e:
            bot_logger.warning(f"Error expiring star reward claims: {e}")
        
        # 2. Remove expired user discounts from UserDiscount table
        try:
            expired_discounts_query = select(UserDiscount).filter(
                UserDiscount.used == False,
                UserDiscount.expiration <= now
            )
            result = await session.execute(expired_discounts_query)
            discounts_to_expire = result.scalars().all()
            if discounts_to_expire:
                for discount in discounts_to_expire:
                    discount.used = True
                await session.commit()
                bot_logger.debug(f"Expired {len(discounts_to_expire)} user discounts")
        except Exception as e:
            bot_logger.warning(f"Error expiring user discounts: {e}")
        
        # 3. Remove expired discounts from users table (if columns exist)
        # Using raw SQL to avoid model attribute errors if columns don't exist
        try:
            await session.execute(text("""
                UPDATE users 
                SET discount_percent = 0, discount_expiration = NULL 
                WHERE discount_percent > 0 
                AND discount_expiration IS NOT NULL 
                AND discount_expiration <= :now
            """), {"now": now})
            await session.commit()
        except Exception as e:
            # Columns might not exist, that's fine
            pass
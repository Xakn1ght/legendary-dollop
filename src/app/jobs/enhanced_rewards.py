"""
Enhanced Rewards Background Jobs
Hourly analytics + legacy-achievement sweep (XP-only).

Trimmed 2026-07-19 (launch hardening):
- check_challenge_progress_job / create_daily_challenges_job /
  create_weekly_challenges_job DELETED — they were never scheduled; challenge
  creation and progress are event-driven in repos/reward/_challenges.py
  (ensure-on-access + record_challenge_event from the arcade submit and the
  referral-approval hooks), which also pays the XP and notifies.
- reminder_unclaimed_star_rewards_job DELETED — the legacy star-tier ladder
  is retired (tiers deactivated 2026-06-02, claim flow now shows a retired
  notice); DMing people every 12h about unclaimable rewards was pure noise.
"""

import logging

from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.crud import (
    check_and_award_achievements,
    get_referees_by_referrer,
    get_user_analytics,
    get_user_subscriptions,
    update_leaderboard,
)
from app.database.models import AsyncSessionLocal
from app.services.pasarguard import pasarguard_api

logger = logging.getLogger(__name__)

async def update_user_analytics_job(bot: Bot):
    """Hourly job to update user analytics and check for achievements.

    Achievements granted here are XP-only (see repos/reward/_achievements.py
    — the credit/loyalty/stars branches were removed so this sweep can never
    mint money, whatever the Achievement rows say)."""
    async with AsyncSessionLocal() as session:
        try:
            # Get all users
            users = await get_all_users(session)
            
            for user in users:
                try:
                    # Update analytics
                    analytics = await get_user_analytics(session, user.id)  # noqa: F841
                    
                    # Check for referral achievements
                    referees = await get_referees_by_referrer(session, user.id)
                    await check_and_award_achievements(session, user.id, "referrals", len(referees))
                    
                    # Check for purchase achievements
                    subscriptions = await get_user_subscriptions(session, user.id)
                    await check_and_award_achievements(session, user.id, "purchases", len(subscriptions))
                    
                    # Check for streak achievements
                    await check_and_award_achievements(session, user.id, "streak", user.login_streak)
                    
                    # Update leaderboards
                    await update_leaderboard(session, user.id, "referrals", len(referees))
                    await update_leaderboard(session, user.id, "activity", user.login_streak)

                    # --- Update usage leaderboard ---
                    # Cached fast path: this sweep touches every user's subs —
                    # leaderboard math happily tolerates the 90s cache TTL.
                    total_usage = 0
                    for sub in subscriptions:
                        if sub.marzban_username:
                            try:
                                user_info = await pasarguard_api.get_fast_user_info(
                                    sub.marzban_username, getattr(sub, "sub_token", None)
                                )
                                if user_info and user_info.get("used_traffic") is not None:
                                    total_usage += user_info["used_traffic"]
                            except Exception:
                                continue
                    usage_gb = total_usage // (1024 * 1024 * 1024)  # Convert to GB
                    await update_leaderboard(session, user.id, "usage", usage_gb)

                    # --- Update spending leaderboard ---
                    # You can use number of purchases or total price. Here, we use number of purchases.
                    spending = len(subscriptions)
                    await update_leaderboard(session, user.id, "spending", spending)

                    logger.debug(f"Updated analytics for user {user.id}")
                    
                except Exception as e:
                    logger.error(f"Error updating analytics for user {user.id}: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"Error in update_user_analytics_job: {e}")

# Helper functions (these should be imported from crud.py)
async def get_all_users(session: AsyncSession):
    """Get all users from database."""
    from sqlalchemy import select

    from app.database.models import User
    
    result = await session.execute(select(User))
    return result.scalars().all()

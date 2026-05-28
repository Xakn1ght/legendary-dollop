"""
Enhanced Rewards Background Jobs
Handles automatic updates for analytics, achievements, and challenges.
"""

import logging
from datetime import datetime, timedelta

from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.crud import (
    check_and_award_achievements,
    get_active_challenges,
    get_leaderboard,
    get_referees_by_referrer,
    get_user,
    get_user_analytics,
    get_user_subscriptions,
    update_challenge_progress,
    update_leaderboard,
    update_user_analytics,
)
from app.database.models import AsyncSessionLocal
from app.services.marzban import marzban_api
from app.utils.text_format import to_persian_digits

logger = logging.getLogger(__name__)

async def update_user_analytics_job(bot: Bot):
    """Daily job to update user analytics and check for achievements."""
    async with AsyncSessionLocal() as session:
        try:
            # Get all users
            from app.database.crud import get_all_users
            users = await get_all_users(session)
            
            for user in users:
                try:
                    # Update analytics
                    analytics = await get_user_analytics(session, user.id)
                    
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

                    # --- NEW: Update usage leaderboard ---
                    total_usage = 0
                    for sub in subscriptions:
                        if sub.marzban_username:
                            try:
                                user_info = await marzban_api.get_user_info(sub.marzban_username)
                                if user_info and "used_traffic" in user_info:
                                    total_usage += user_info["used_traffic"]
                            except Exception:
                                continue
                    usage_gb = total_usage // (1024 * 1024 * 1024)  # Convert to GB
                    await update_leaderboard(session, user.id, "usage", usage_gb)

                    # --- NEW: Update spending leaderboard ---
                    # You can use number of purchases or total price. Here, we use number of purchases.
                    spending = len(subscriptions)
                    await update_leaderboard(session, user.id, "spending", spending)

                    logger.debug(f"Updated analytics for user {user.id}")
                    
                except Exception as e:
                    logger.error(f"Error updating analytics for user {user.id}: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"Error in update_user_analytics_job: {e}")

async def check_challenge_progress_job(bot: Bot):
    """Job to check and update challenge progress for all users."""
    async with AsyncSessionLocal() as session:
        try:
            # Get all active challenges
            active_challenges = await get_active_challenges(session)
            
            if not active_challenges:
                return
            
            # Get all users
            from app.database.crud import get_all_users
            users = await get_all_users(session)
            
            for user in users:
                try:
                    for challenge in active_challenges:
                        # Calculate progress based on challenge type
                        progress = 0
                        
                        if challenge.requirement_type == "referrals":
                            referees = await get_referees_by_referrer(session, user.id)
                            progress = len(referees)
                        elif challenge.requirement_type == "logins":
                            progress = user.login_streak
                        elif challenge.requirement_type == "usage":
                            # Calculate total usage from subscriptions
                            subscriptions = await get_user_subscriptions(session, user.id)
                            total_usage = 0
                            for sub in subscriptions:
                                if sub.marzban_username:
                                    try:
                                        user_info = await marzban_api.get_user_info(sub.marzban_username)
                                        if user_info and "used_traffic" in user_info:
                                            total_usage += user_info["used_traffic"]
                                    except Exception:
                                        continue
                            progress = total_usage // (1024 * 1024 * 1024)  # Convert to GB
                        
                        # Update challenge progress and notify instantly if completed
                        user_challenge, just_completed = await update_challenge_progress(
                            session, user.id, challenge.id, progress
                        )

                        if just_completed:
                            # Fire-and-forget: we don't want the whole job to block if send_message fails
                            try:
                                await bot.send_message(
                                    user.chat_id,
                                    (
                                        "🎉 تبریک! شما چالش "
                                        f"«{challenge.title}» را با موفقیت به پایان رساندید و جایزه خود را دریافت کردید."
                                    ),
                                )
                            except Exception as send_err:
                                logger.warning(
                                    "Failed to send challenge completion notification to %s: %s",
                                    user.chat_id,
                                    send_err,
                                )
                        
                except Exception as e:
                    logger.error(f"Error updating challenge progress for user {user.id}: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"Error in check_challenge_progress_job: {e}")

async def create_daily_challenges_job(bot: Bot):
    """Job to create new daily challenges."""
    async with AsyncSessionLocal() as session:
        try:
            from sqlalchemy import select

            from app.database.models import Challenge
            
            # Check if daily challenge already exists for today
            today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            today_end = today_start + timedelta(days=1) - timedelta(microseconds=1)
            
            existing_challenge = await session.execute(
                select(Challenge).filter(
                    Challenge.challenge_type == "daily",
                    Challenge.start_date >= today_start,
                    Challenge.start_date <= today_end
                )
            )
            
            if existing_challenge.scalar_one_or_none():
                return  # Daily challenge already exists
            
            # Create new daily challenge
            daily_challenge = Challenge(
                title="بازی روزانه",
                description="امروز یک‌بار بازی کن",
                challenge_type="daily",
                requirement_type="play_daily_game",
                requirement_value=1,
                reward_type="xp",
                reward_value=10,
                start_date=today_start,
                end_date=today_end,
                active=True
            )
            
            session.add(daily_challenge)
            await session.commit()
            
            logger.info("Created new daily challenge")
            
        except Exception as e:
            logger.error(f"Error in create_daily_challenges_job: {e}")

async def create_weekly_challenges_job(bot: Bot):
    """Job to create new weekly challenges."""
    async with AsyncSessionLocal() as session:
        try:
            from sqlalchemy import select

            from app.database.models import Challenge
            
            # Calculate week start and end
            now = datetime.utcnow()
            week_start = now - timedelta(days=now.weekday())
            week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
            week_end = week_start + timedelta(days=7) - timedelta(microseconds=1)
            
            # Check if weekly challenge already exists for this week
            existing_challenge = await session.execute(
                select(Challenge).filter(
                    Challenge.challenge_type == "weekly",
                    Challenge.start_date >= week_start,
                    Challenge.start_date <= week_end
                )
            )
            
            if existing_challenge.scalar_one_or_none():
                return  # Weekly challenge already exists
            
            # Create new weekly challenge
            weekly_challenge = Challenge(
                title="معرفی هفتگی",
                description="۳ نفر را این هفته معرفی کنید",
                challenge_type="weekly",
                requirement_type="referrals",
                requirement_value=3,
                reward_type="loyalty_points",
                reward_value=100,
                start_date=week_start,
                end_date=week_end,
                active=True
            )
            
            session.add(weekly_challenge)
            await session.commit()
            
            logger.info("Created new weekly challenge")
            
        except Exception as e:
            logger.error(f"Error in create_weekly_challenges_job: {e}")

async def reminder_unclaimed_star_rewards_job(bot: Bot):
    """Daily job to send reminders about unclaimed star rewards."""
    async with AsyncSessionLocal() as session:
        try:
            logger.debug("Starting unclaimed star rewards reminder job")

            # Get all users
            users = await get_all_users(session)

            reminders_sent = 0
            for user in users:
                try:
                    # Check for unclaimed star rewards
                    from app.database.crud import get_user_unclaimed_rewards
                    unclaimed = await get_user_unclaimed_rewards(session, user.id)

                    if unclaimed:
                        # Send reminder message
                        message = (
                            f"⭐ سلام {user.full_name or user.username or 'کاربر عزیز'}!\n\n"
                            f"شما {len(unclaimed)} جایزه ستاره‌ای قابل دریافت دارید که هنوز برداشت نکردید.\n\n"
                            f"برای دریافت جوایز خود به بخش 🎁 سیستم پاداش پیشرفته بروید."
                        )

                        try:
                            await bot.send_message(
                                chat_id=user.chat_id,
                                text=message
                            )
                            reminders_sent += 1
                            logger.debug(f"Sent reminder to user {user.id} for {len(unclaimed)} unclaimed rewards")
                        except Exception as e:
                            logger.warning(f"Failed to send reminder to user {user.id}: {e}")

                except Exception as e:
                    logger.error(f"Error processing user {user.id} for reminders: {e}")

            logger.debug(f"Unclaimed rewards reminder done. Sent {reminders_sent}")

        except Exception as e:
            logger.error(f"Error in reminder_unclaimed_star_rewards_job: {e}")

# Helper functions (these should be imported from crud.py)
async def get_all_users(session: AsyncSession):
    """Get all users from database."""
    from sqlalchemy import select

    from app.database.crud import get_user
    from app.database.models import User
    
    result = await session.execute(select(User))
    return result.scalars().all()

async def get_referees_by_referrer(session: AsyncSession, referrer_id: int):
    """Get all users referred by a specific user."""
    from app.database.crud import get_referees_by_referrer as get_referees
    return await get_referees(session, referrer_id)

async def get_user_subscriptions(session: AsyncSession, user_id: int):
    """Get all subscriptions for a user."""
    from app.database.crud import get_user_subscriptions as get_subs
    return await get_subs(session, user_id) 

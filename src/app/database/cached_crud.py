"""
Cached CRUD operations for ASSTRO bot
Integrates Redis caching with database operations
"""

import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy.exc import IntegrityError, OperationalError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.core.redis_config import CACHE_CONFIG, cache, cache_invalidate, cached
from app.utils.logger import DatabaseError, log_database_operation, log_error

from .models import (
    Achievement,
    Challenge,
    ChargeRequest,
    Leaderboard,
    Referral,
    ReferralReward,
    RenewalHistory,
    RewardEffectiveness,
    RewardHistory,
    SeasonalEvent,
    Subscription,
    User,
    UserAchievement,
    UserAnalytics,
    UserChallenge,
    UserGift,
)

# ========================================
# CACHED USER OPERATIONS
# ========================================

@cached(ttl=CACHE_CONFIG["user_data_ttl"], key_prefix="user")
async def get_user_cached(session: AsyncSession, chat_id: int) -> Optional[User]:
    """Get user with caching"""
    start_time = time.time()
    try:
        result = await session.execute(select(User).filter(User.chat_id == chat_id))
        user = result.scalars().first()
        duration = time.time() - start_time
        log_database_operation("select_cached", "users", True, duration, user_id=user.id if user else None)
        return user
    except SQLAlchemyError as e:
        duration = time.time() - start_time
        log_database_operation("select_cached", "users", False, duration, error=str(e))
        log_error(e, {"operation": "get_user_cached", "chat_id": chat_id})
        raise DatabaseError(f"Failed to get user: {str(e)}")

@cached(ttl=CACHE_CONFIG["user_data_ttl"], key_prefix="user")
async def get_user_by_referral_code_cached(session: AsyncSession, code: str) -> Optional[User]:
    """Get user by referral code with caching"""
    start_time = time.time()
    try:
        result = await session.execute(select(User).filter(User.referral_code == code))
        user = result.scalars().first()
        duration = time.time() - start_time
        log_database_operation("select_cached", "users", True, duration, user_id=user.id if user else None)
        return user
    except SQLAlchemyError as e:
        duration = time.time() - start_time
        log_database_operation("select_cached", "users", False, duration, error=str(e))
        log_error(e, {"operation": "get_user_by_referral_code_cached", "code": code})
        raise DatabaseError(f"Failed to get user by referral code: {str(e)}")

@cache_invalidate("user:*")
async def create_user_cached(session: AsyncSession, chat_id: int, username: str, full_name: str, language: str | None = None) -> User:
    """Create user with cache invalidation"""
    start_time = time.time()
    try:
        # Check if user already exists
        existing_user = await get_user_cached(session, chat_id)
        if existing_user:
            duration = time.time() - start_time
            log_database_operation("select_cached", "users", True, duration, user_id=existing_user.id)
            return existing_user
        
        # Import the original create_user function
        from .crud import create_user
        user = await create_user(session, chat_id, username, full_name, language=language)
        
        duration = time.time() - start_time
        log_database_operation("insert_cached", "users", True, duration, user_id=user.id)
        return user
        
    except Exception as e:
        duration = time.time() - start_time
        log_database_operation("insert_cached", "users", False, duration, error=str(e))
        log_error(e, {"operation": "create_user_cached", "chat_id": chat_id})
        raise DatabaseError(f"Failed to create user: {str(e)}")

# ========================================
# CACHED SUBSCRIPTION OPERATIONS
# ========================================

@cached(ttl=CACHE_CONFIG["subscription_data_ttl"], key_prefix="subscription")
async def get_user_subscriptions_cached(session: AsyncSession, user_id: int) -> List[Subscription]:
    """Get user subscriptions with caching"""
    start_time = time.time()
    try:
        # Import the original function
        from .crud import get_user_subscriptions
        subscriptions = await get_user_subscriptions(session, user_id)
        duration = time.time() - start_time
        log_database_operation("select_cached", "subscriptions", True, duration, user_id=user_id)
        return subscriptions
    except SQLAlchemyError as e:
        duration = time.time() - start_time
        log_database_operation("select_cached", "subscriptions", False, duration, error=str(e))
        log_error(e, {"operation": "get_user_subscriptions_cached", "user_id": user_id})
        raise DatabaseError(f"Failed to get user subscriptions: {str(e)}")

@cached(ttl=CACHE_CONFIG["subscription_data_ttl"], key_prefix="subscription")
async def get_user_active_subscriptions_cached(session: AsyncSession, user_id: int) -> List[Subscription]:
    """Get user active subscriptions with caching"""
    start_time = time.time()
    try:
        result = await session.execute(
            select(Subscription)
            .filter(Subscription.user_id == user_id, Subscription.status == 'active')
        )
        subscriptions = result.scalars().all()
        duration = time.time() - start_time
        log_database_operation("select_cached", "subscriptions", True, duration, user_id=user_id)
        return subscriptions
    except SQLAlchemyError as e:
        duration = time.time() - start_time
        log_database_operation("select_cached", "subscriptions", False, duration, error=str(e))
        log_error(e, {"operation": "get_user_active_subscriptions_cached", "user_id": user_id})
        raise DatabaseError(f"Failed to get active subscriptions: {str(e)}")

@cached(ttl=CACHE_CONFIG["subscription_data_ttl"], key_prefix="subscription")
async def get_pending_subscriptions_cached(session: AsyncSession) -> List[Subscription]:
    """Get pending subscriptions with caching"""
    start_time = time.time()
    try:
        result = await session.execute(
            select(Subscription)
            .options(selectinload(Subscription.user))
            .filter(Subscription.status == 'pending', Subscription.receipt_message_id != None)
        )
        subscriptions = result.scalars().all()
        duration = time.time() - start_time
        log_database_operation("select_cached", "subscriptions", True, duration)
        return subscriptions
    except SQLAlchemyError as e:
        duration = time.time() - start_time
        log_database_operation("select_cached", "subscriptions", False, duration, error=str(e))
        log_error(e, {"operation": "get_pending_subscriptions_cached"})
        raise DatabaseError(f"Failed to get pending subscriptions: {str(e)}")

@cache_invalidate("subscription:*")
async def create_subscription_cached(session: AsyncSession, user_id: int, marzban_username: str, plan: str, receipt_message_id: int, referrer_id: int = None, **kwargs) -> Subscription:
    """Create subscription with cache invalidation"""
    start_time = time.time()
    try:
        from .crud import create_subscription
        subscription = await create_subscription(session, user_id, marzban_username, plan, receipt_message_id, referrer_id, **kwargs)
        duration = time.time() - start_time
        log_database_operation("insert_cached", "subscriptions", True, duration, user_id=user_id)
        return subscription
    except Exception as e:
        duration = time.time() - start_time
        log_database_operation("insert_cached", "subscriptions", False, duration, error=str(e))
        log_error(e, {"operation": "create_subscription_cached", "user_id": user_id})
        raise DatabaseError(f"Failed to create subscription: {str(e)}")

# ========================================
# CACHED REFERRAL OPERATIONS
# ========================================

@cached(ttl=CACHE_CONFIG["user_data_ttl"], key_prefix="referral")
async def get_referees_by_referrer_cached(session: AsyncSession, referrer_id: int) -> List[User]:
    """Get referrer's referees with caching"""
    start_time = time.time()
    try:
        result = await session.execute(
            select(User)
            .join(Referral, User.id == Referral.referee_id)
            .filter(Referral.referrer_id == referrer_id)
        )
        users = result.scalars().all()
        duration = time.time() - start_time
        log_database_operation("select_cached", "referrals", True, duration, user_id=referrer_id)
        return users
    except SQLAlchemyError as e:
        duration = time.time() - start_time
        log_database_operation("select_cached", "referrals", False, duration, error=str(e))
        log_error(e, {"operation": "get_referees_by_referrer_cached", "referrer_id": referrer_id})
        raise DatabaseError(f"Failed to get referees: {str(e)}")

@cache_invalidate("referral:*")
async def create_referral_cached(session: AsyncSession, referrer_id: int, referee_id: int) -> Referral:
    """Create referral with cache invalidation"""
    start_time = time.time()
    try:
        from .crud import create_referral
        referral = await create_referral(session, referrer_id, referee_id)
        duration = time.time() - start_time
        log_database_operation("insert_cached", "referrals", True, duration, user_id=referrer_id)
        return referral
    except Exception as e:
        duration = time.time() - start_time
        log_database_operation("insert_cached", "referrals", False, duration, error=str(e))
        log_error(e, {"operation": "create_referral_cached", "referrer_id": referrer_id, "referee_id": referee_id})
        raise DatabaseError(f"Failed to create referral: {str(e)}")

# ========================================
# CACHED REWARD OPERATIONS
# ========================================

@cached(ttl=CACHE_CONFIG["reward_data_ttl"], key_prefix="reward")
async def get_unspent_rewards_by_referrer_cached(session: AsyncSession, referrer_id: int) -> List[ReferralReward]:
    """Get unspent rewards with caching"""
    start_time = time.time()
    try:
        result = await session.execute(
            select(ReferralReward)
            .filter(ReferralReward.referrer_id == referrer_id, ReferralReward.spent == False)
        )
        rewards = result.scalars().all()
        duration = time.time() - start_time
        log_database_operation("select_cached", "referral_rewards", True, duration, user_id=referrer_id)
        return rewards
    except SQLAlchemyError as e:
        duration = time.time() - start_time
        log_database_operation("select_cached", "referral_rewards", False, duration, error=str(e))
        log_error(e, {"operation": "get_unspent_rewards_by_referrer_cached", "referrer_id": referrer_id})
        raise DatabaseError(f"Failed to get unspent rewards: {str(e)}")

@cache_invalidate("reward:*")
async def create_referral_reward_cached(session: AsyncSession, subscription_id: int, referrer_id: int, **kwargs) -> ReferralReward:
    """Create referral reward with cache invalidation"""
    start_time = time.time()
    try:
        from .crud import create_referral_reward
        reward = await create_referral_reward(session, subscription_id, referrer_id, **kwargs)
        duration = time.time() - start_time
        log_database_operation("insert_cached", "referral_rewards", True, duration, user_id=referrer_id)
        return reward
    except Exception as e:
        duration = time.time() - start_time
        log_database_operation("insert_cached", "referral_rewards", False, duration, error=str(e))
        log_error(e, {"operation": "create_referral_reward_cached", "subscription_id": subscription_id, "referrer_id": referrer_id})
        raise DatabaseError(f"Failed to create referral reward: {str(e)}")

# ========================================
# CACHED ACHIEVEMENT OPERATIONS
# ========================================

@cached(ttl=CACHE_CONFIG["achievement_ttl"], key_prefix="achievement")
async def get_user_achievements_cached(session: AsyncSession, user_id: int) -> List[UserAchievement]:
    """Get user achievements with caching"""
    start_time = time.time()
    try:
        result = await session.execute(
            select(UserAchievement)
            .options(selectinload(UserAchievement.achievement))
            .filter(UserAchievement.user_id == user_id)
        )
        achievements = result.scalars().all()
        duration = time.time() - start_time
        log_database_operation("select_cached", "user_achievements", True, duration, user_id=user_id)
        return achievements
    except SQLAlchemyError as e:
        duration = time.time() - start_time
        log_database_operation("select_cached", "user_achievements", False, duration, error=str(e))
        log_error(e, {"operation": "get_user_achievements_cached", "user_id": user_id})
        raise DatabaseError(f"Failed to get user achievements: {str(e)}")

@cached(ttl=CACHE_CONFIG["achievement_ttl"], key_prefix="achievement")
async def get_active_achievements_cached(session: AsyncSession) -> List[Achievement]:
    """Get active achievements with caching"""
    start_time = time.time()
    try:
        result = await session.execute(select(Achievement))
        achievements = result.scalars().all()
        duration = time.time() - start_time
        log_database_operation("select_cached", "achievements", True, duration)
        return achievements
    except SQLAlchemyError as e:
        duration = time.time() - start_time
        log_database_operation("select_cached", "achievements", False, duration, error=str(e))
        log_error(e, {"operation": "get_active_achievements_cached"})
        raise DatabaseError(f"Failed to get active achievements: {str(e)}")

# ========================================
# CACHED CHALLENGE OPERATIONS
# ========================================

@cached(ttl=CACHE_CONFIG["challenge_ttl"], key_prefix="challenge")
async def get_active_challenges_cached(session: AsyncSession, challenge_type: str = None) -> List[Challenge]:
    """Get **currently running** challenges with caching.

    We filter not only by ``active`` flag but also by the current time window
    so that old challenges (whose ``active`` flag was never toggled off) do
    not appear in the UI / background jobs.
    """
    start_time = time.time()
    try:
        now = datetime.utcnow()

        query = (
            select(Challenge)
            .filter(
                Challenge.active == True,
                Challenge.start_date <= now,
                Challenge.end_date >= now,
            )
        )

        if challenge_type:
            query = query.filter(Challenge.challenge_type == challenge_type)
        
        result = await session.execute(query)
        challenges = result.scalars().all()
        duration = time.time() - start_time
        log_database_operation("select_cached", "challenges", True, duration)
        return challenges
    except SQLAlchemyError as e:
        duration = time.time() - start_time
        log_database_operation("select_cached", "challenges", False, duration, error=str(e))
        log_error(e, {"operation": "get_active_challenges_cached", "challenge_type": challenge_type})
        raise DatabaseError(f"Failed to get active challenges: {str(e)}")

@cached(ttl=CACHE_CONFIG["challenge_ttl"], key_prefix="challenge")
async def get_user_challenge_progress_cached(session: AsyncSession, user_id: int, challenge_id: int = None) -> List[UserChallenge]:
    """Get user challenge progress with caching"""
    start_time = time.time()
    try:
        query = select(UserChallenge).filter(UserChallenge.user_id == user_id)
        if challenge_id:
            query = query.filter(UserChallenge.challenge_id == challenge_id)
        
        result = await session.execute(query)
        progress = result.scalars().all()
        duration = time.time() - start_time
        log_database_operation("select_cached", "user_challenges", True, duration, user_id=user_id)
        return progress
    except SQLAlchemyError as e:
        duration = time.time() - start_time
        log_database_operation("select_cached", "user_challenges", False, duration, error=str(e))
        log_error(e, {"operation": "get_user_challenge_progress_cached", "user_id": user_id})
        raise DatabaseError(f"Failed to get challenge progress: {str(e)}")

# ========================================
# CACHED LEADERBOARD OPERATIONS
# ========================================

@cached(ttl=CACHE_CONFIG["leaderboard_ttl"], key_prefix="leaderboard")
async def get_leaderboard_cached(session: AsyncSession, category: str, period: str = "all_time", limit: int = 10) -> List[Leaderboard]:
    """Get leaderboard with caching"""
    start_time = time.time()
    try:
        result = await session.execute(
            select(Leaderboard)
            .options(selectinload(Leaderboard.user))
            .filter(Leaderboard.category == category, Leaderboard.period == period)
            .order_by(Leaderboard.score.desc())
            .limit(limit)
        )
        leaderboard = result.scalars().all()
        duration = time.time() - start_time
        log_database_operation("select_cached", "leaderboards", True, duration)
        return leaderboard
    except SQLAlchemyError as e:
        duration = time.time() - start_time
        log_database_operation("select_cached", "leaderboards", False, duration, error=str(e))
        log_error(e, {"operation": "get_leaderboard_cached", "category": category, "period": period})
        raise DatabaseError(f"Failed to get leaderboard: {str(e)}")

# ========================================
# CACHED ANALYTICS OPERATIONS
# ========================================

@cached(ttl=CACHE_CONFIG["analytics_ttl"], key_prefix="analytics")
async def get_user_analytics_cached(session: AsyncSession, user_id: int, date: datetime = None) -> Optional[UserAnalytics]:
    """Get user analytics with caching"""
    start_time = time.time()
    try:
        if date is None:
            date = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        
        result = await session.execute(
            select(UserAnalytics)
            .filter(UserAnalytics.user_id == user_id, UserAnalytics.date == date)
        )
        analytics = result.scalars().first()
        duration = time.time() - start_time
        log_database_operation("select_cached", "user_analytics", True, duration, user_id=user_id)
        return analytics
    except SQLAlchemyError as e:
        duration = time.time() - start_time
        log_database_operation("select_cached", "user_analytics", False, duration, error=str(e))
        log_error(e, {"operation": "get_user_analytics_cached", "user_id": user_id})
        raise DatabaseError(f"Failed to get user analytics: {str(e)}")

# ========================================
# CACHE MANAGEMENT FUNCTIONS
# ========================================

async def invalidate_user_cache(user_id: int) -> bool:
    """Invalidate all cache related to a user"""
    try:
        await cache.invalidate_user_data(user_id)
        return True
    except Exception as e:
        log_error(e, {"operation": "invalidate_user_cache", "user_id": user_id})
        return False

async def invalidate_subscription_cache(subscription_id: int) -> bool:
    """Invalidate subscription-related cache"""
    try:
        patterns = ["subscription:*", f"subscription:{subscription_id}"]
        for pattern in patterns:
            await cache.invalidate_pattern(pattern)
        return True
    except Exception as e:
        log_error(e, {"operation": "invalidate_subscription_cache", "subscription_id": subscription_id})
        return False

async def invalidate_leaderboard_cache() -> bool:
    """Invalidate leaderboard cache"""
    try:
        await cache.invalidate_pattern("leaderboard:*")
        return True
    except Exception as e:
        log_error(e, {"operation": "invalidate_leaderboard_cache"})
        return False

async def invalidate_analytics_cache() -> bool:
    """Invalidate analytics cache"""
    try:
        await cache.invalidate_pattern("analytics:*")
        return True
    except Exception as e:
        log_error(e, {"operation": "invalidate_analytics_cache"})
        return False

async def get_cache_stats() -> Dict[str, Any]:
    """Get cache statistics"""
    try:
        return await cache.get_stats()
    except Exception as e:
        log_error(e, {"operation": "get_cache_stats"})
        return {}

# ========================================
# CACHE-ENHANCED UTILITY FUNCTIONS
# ========================================

async def get_user_with_cache(session: AsyncSession, chat_id: int) -> Optional[User]:
    """Get user with intelligent caching"""
    # Try cache first
    cached_user = await get_user_cached(session, chat_id)
    if cached_user:
        return cached_user
    
    # Fallback to database
    from .crud import get_user
    return await get_user(session, chat_id)

async def get_user_subscriptions_with_cache(session: AsyncSession, user_id: int) -> List[Subscription]:
    """Get user subscriptions with intelligent caching"""
    # Try cache first
    cached_subs = await get_user_subscriptions_cached(session, user_id)
    if cached_subs:
        return cached_subs
    
    # Fallback to database
    from .crud import get_user_subscriptions
    return await get_user_subscriptions(session, user_id)

async def get_leaderboard_with_cache(session: AsyncSession, category: str, period: str = "all_time", limit: int = 10) -> List[Leaderboard]:
    """Get leaderboard with intelligent caching"""
    # Try cache first
    cached_lb = await get_leaderboard_cached(session, category, period, limit)
    if cached_lb:
        return cached_lb
    
    # Fallback to database
    from .crud import get_leaderboard
    return await get_leaderboard(session, category, period, limit) 
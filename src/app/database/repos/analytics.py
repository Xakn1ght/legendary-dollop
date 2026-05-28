from datetime import datetime, timedelta

from sqlalchemy import and_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.database.models import Leaderboard, StarHistory, StarRewardTier, User, UserAnalytics, UserStarRewardClaim


class AnalyticsRepository:
    @staticmethod
    async def get_user_analytics(db: AsyncSession, user_id: int, date: datetime = None):
        if not date:
            date = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        
        result = await db.execute(
            select(UserAnalytics).filter(UserAnalytics.user_id == user_id, UserAnalytics.date == date)
        )
        analytics = result.scalars().first()
        
        if not analytics:
            analytics = UserAnalytics(user_id=user_id, date=date)
            db.add(analytics)
            await db.commit()
            await db.refresh(analytics)
        
        return analytics

    @staticmethod
    async def update_user_analytics(db: AsyncSession, user_id: int, **kwargs):
        analytics = await AnalyticsRepository.get_user_analytics(db, user_id)
        
        for key, value in kwargs.items():
            if hasattr(analytics, key):
                current_value = getattr(analytics, key)
                if isinstance(current_value, (int, float)):
                    setattr(analytics, key, current_value + value)
                else:
                    setattr(analytics, key, value)
        
        await db.commit()
        await db.refresh(analytics)
        return analytics

    # --- Leaderboards ---
    @staticmethod
    async def update_leaderboard(db: AsyncSession, user_id: int, category: str, score: int, period: str = "all_time"):
        date = datetime.utcnow()
        
        result = await db.execute(
            select(Leaderboard).filter(
                Leaderboard.user_id == user_id,
                Leaderboard.category == category,
                Leaderboard.period == period
            )
        )
        entry = result.scalars().first()
        
        if not entry:
            entry = Leaderboard(user_id=user_id, category=category, score=0, period=period, date=date)
            db.add(entry)
        
        entry.score = score
        entry.date = date
        
        await db.commit()
        await db.refresh(entry)
        return entry

    @staticmethod
    async def get_leaderboard(db: AsyncSession, category: str, period: str = "all_time", limit: int = 10):
        result = await db.execute(
            select(Leaderboard)
            .options(selectinload(Leaderboard.user))
            .filter(Leaderboard.category == category, Leaderboard.period == period)
            .order_by(Leaderboard.score.desc())
            .limit(limit)
        )
        return result.scalars().all()

    # --- Star Analytics ---
    @staticmethod
    async def get_star_analytics_overview(db: AsyncSession) -> dict:
        # Total stars earned
        total_stars_result = await db.execute(select(func.coalesce(func.sum(StarHistory.delta), 0)).filter(StarHistory.delta > 0))
        total_stars_earned = total_stars_result.scalar() or 0

        # Total rewards claimed
        total_rewards_result = await db.execute(select(func.count(UserStarRewardClaim.id)).filter(UserStarRewardClaim.claimed_at.isnot(None)))
        total_rewards_claimed = total_rewards_result.scalar() or 0

        # Active users with stars
        active_users_result = await db.execute(select(func.count(func.distinct(User.id))).filter(User.stars > 0))
        active_users_with_stars = active_users_result.scalar() or 0

        # Total users
        total_users_result = await db.execute(select(func.count(User.id)))
        total_users = total_users_result.scalar() or 0

        # Average stars per user
        avg_stars_per_user = total_stars_earned / total_users if total_users > 0 else 0

        # Today's activity
        today = datetime.now().date()
        today_start = datetime.combine(today, datetime.min.time())

        today_stars_result = await db.execute(
            select(func.coalesce(func.sum(StarHistory.delta), 0))
            .filter(and_(StarHistory.delta > 0, StarHistory.created_at >= today_start))
        )
        stars_today = today_stars_result.scalar() or 0

        today_rewards_result = await db.execute(
            select(func.count(UserStarRewardClaim.id))
            .filter(and_(UserStarRewardClaim.claimed_at.isnot(None), UserStarRewardClaim.claimed_at >= today_start))
        )
        rewards_today = today_rewards_result.scalar() or 0

        return {
            'total_stars_earned': int(total_stars_earned),
            'total_rewards_claimed': int(total_rewards_claimed),
            'active_users_with_stars': int(active_users_with_stars),
            'total_users': int(total_users),
            'avg_stars_per_user': float(avg_stars_per_user),
            'stars_today': int(stars_today),
            'rewards_today': int(rewards_today)
        }

    @staticmethod
    async def get_star_distribution_by_reason(db: AsyncSession) -> list:
        result = await db.execute(
            select(
                StarHistory.reason,
                func.count(StarHistory.id).label('count'),
                func.sum(StarHistory.delta).label('total_stars')
            )
            .filter(StarHistory.delta > 0)
            .group_by(StarHistory.reason)
            .order_by(func.sum(StarHistory.delta).desc())
        )

        return [
            {'reason': row.reason, 'count': int(row.count), 'total_stars': int(row.total_stars)}
            for row in result.fetchall()
        ]

    @staticmethod
    async def get_popular_star_rewards(db: AsyncSession) -> list:
        result = await db.execute(
            select(
                StarRewardTier.title.label('tier_title'),
                StarRewardTier.star_threshold,
                StarRewardTier.reward_type,
                StarRewardTier.reward_value,
                func.count(UserStarRewardClaim.id).label('claim_count')
            )
            .join(UserStarRewardClaim, UserStarRewardClaim.tier_id == StarRewardTier.id)
            .filter(UserStarRewardClaim.claimed_at.isnot(None))
            .group_by(StarRewardTier.id, StarRewardTier.title, StarRewardTier.star_threshold, StarRewardTier.reward_type, StarRewardTier.reward_value)
            .order_by(func.count(UserStarRewardClaim.id).desc())
            .limit(10)
        )

        return [
            {
                'tier_title': row.tier_title,
                'tier_threshold': int(row.star_threshold),
                'reward_type': row.reward_type,
                'reward_value': row.reward_value,
                'claim_count': int(row.claim_count)
            }
            for row in result.fetchall()
        ]

    @staticmethod
    async def get_star_analytics_by_period(db: AsyncSession, period: str) -> dict:
        now = datetime.now()

        if period == 'today':
            start_date = datetime.combine(now.date(), datetime.min.time())
        elif period == 'week':
            start_date = now - timedelta(days=7)
        elif period == 'month':
            start_date = now - timedelta(days=30)
        else:
            return {'stars': 0, 'rewards': 0}

        # Stars earned in period
        stars_result = await db.execute(
            select(func.coalesce(func.sum(StarHistory.delta), 0))
            .filter(and_(StarHistory.delta > 0, StarHistory.created_at >= start_date))
        )
        stars = stars_result.scalar() or 0

        # Rewards claimed in period
        rewards_result = await db.execute(
            select(func.count(UserStarRewardClaim.id))
            .filter(and_(UserStarRewardClaim.claimed_at.isnot(None), UserStarRewardClaim.claimed_at >= start_date))
        )
        rewards = rewards_result.scalar() or 0

        return {'stars': int(stars), 'rewards': int(rewards)}

    @staticmethod
    async def get_user_star_statistics(db: AsyncSession) -> dict:
        # Basic counts
        total_users_result = await db.execute(select(func.count(User.id)))
        total_users = total_users_result.scalar() or 0

        users_with_stars_result = await db.execute(select(func.count(User.id)).filter(User.stars > 0))
        users_with_stars = users_with_stars_result.scalar() or 0

        users_without_stars = total_users - users_with_stars

        # Star distribution stats
        avg_stars_result = await db.execute(select(func.avg(User.stars)))
        avg_stars = avg_stars_result.scalar() or 0

        max_stars_result = await db.execute(select(func.max(User.stars)))
        max_stars = max_stars_result.scalar() or 0

        min_stars_result = await db.execute(select(func.min(User.stars)))
        min_stars = min_stars_result.scalar() or 0

        # Top users
        top_users_result = await db.execute(
            select(User.username, User.full_name, User.stars)
            .filter(User.stars > 0)
            .order_by(User.stars.desc())
            .limit(10)
        )
        top_users = [
            {'username': row.username, 'full_name': row.full_name, 'stars': int(row.stars)}
            for row in top_users_result.fetchall()
        ]

        return {
            'total_users': int(total_users),
            'users_with_stars': int(users_with_stars),
            'users_without_stars': int(users_without_stars),
            'avg_stars': float(avg_stars),
            'max_stars': int(max_stars),
            'min_stars': int(min_stars),
            'top_users': top_users
        }


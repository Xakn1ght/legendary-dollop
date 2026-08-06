from sqlalchemy import and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.database.models import Achievement, UserAchievement


class _AchievementsMixin:
    @staticmethod
    async def get_user_achievements(db: AsyncSession, user_id: int):
        result = await db.execute(
            select(UserAchievement)
            .options(selectinload(UserAchievement.achievement))
            .filter(UserAchievement.user_id == user_id)
        )
        return result.scalars().all()

    @staticmethod
    async def check_and_award_achievements(
        db: AsyncSession, user_id: int, achievement_type: str, current_value: int
    ):
        """Grant newly-reached legacy achievements — XP ONLY (2026-07-19 seal).

        The old credit/loyalty/stars branches are gone for good: this runs
        from the hourly analytics job, so a single edited Achievement row
        could otherwise mint money for every user, every hour. Any non-XP
        reward_type still in the table grants nothing but the badge row.
        (The NEW mission achievements in services/achievements.py — 1GB
        coupons for paying customers — are a separate, gated path.)
        """
        from app.database.repos.reward import RewardRepository as _RR

        result = await db.execute(
            select(Achievement)
            .outerjoin(
                UserAchievement,
                and_(
                    Achievement.id == UserAchievement.achievement_id,
                    UserAchievement.user_id == user_id,
                ),
            )
            .filter(
                Achievement.requirement_type == achievement_type,
                UserAchievement.id == None,  # noqa: E711
            )
        )
        available = result.scalars().all()
        earned = []

        for achievement in available:
            if current_value >= achievement.requirement_value:
                ua = UserAchievement(user_id=user_id, achievement_id=achievement.id)
                db.add(ua)

                if achievement.reward_type == "xp":
                    try:
                        xp = int(achievement.reward_value)
                    except (TypeError, ValueError):
                        xp = 0
                    if xp > 0:
                        await _RR.add_experience_points(db, user_id, xp, "achievement")

                earned.append(achievement)

        if earned:
            await db.commit()
        return earned

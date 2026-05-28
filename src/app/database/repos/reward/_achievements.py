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
                    await _RR.add_experience_points(db, user_id, achievement.reward_value, "achievement")
                elif achievement.reward_type == "loyalty_points":
                    await _RR.add_loyalty_points(db, user_id, achievement.reward_value, "achievement")
                elif achievement.reward_type == "credit":
                    from app.database.repos.user import UserRepository

                    await UserRepository.add_credit(db, user_id, achievement.reward_value)
                    await _RR.add_reward_history(db, user_id, "credit", achievement.reward_value, "achievement", achievement.id)
                elif achievement.reward_type == "stars":
                    await _RR.add_stars(db, user_id, achievement.reward_value, "achievement", achievement.id)

                earned.append(achievement)

        if earned:
            await db.commit()
        return earned

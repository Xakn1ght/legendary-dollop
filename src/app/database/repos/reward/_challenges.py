from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.database.models import Challenge, User, UserChallenge


class _ChallengesMixin:
    @staticmethod
    async def get_active_challenges(db: AsyncSession, challenge_type: str = None):
        now = datetime.utcnow()
        query = select(Challenge).filter(
            Challenge.active == True,  # noqa: E712
            Challenge.start_date <= now,
            Challenge.end_date >= now,
        )
        if challenge_type:
            query = query.filter(Challenge.challenge_type == challenge_type)
        result = await db.execute(query)
        return result.scalars().all()

    @staticmethod
    async def get_user_challenge_progress(
        db: AsyncSession, user_id: int, challenge_id: int = None
    ):
        query = select(UserChallenge).options(selectinload(UserChallenge.challenge))
        if challenge_id:
            query = query.filter(
                UserChallenge.user_id == user_id,
                UserChallenge.challenge_id == challenge_id,
            )
        else:
            query = query.filter(UserChallenge.user_id == user_id)
        result = await db.execute(query)
        return result.scalars().all()

    @staticmethod
    async def update_challenge_progress(
        db: AsyncSession, user_id: int, challenge_id: int, progress: int
    ):
        result = await db.execute(
            select(UserChallenge).filter(
                UserChallenge.user_id == user_id,
                UserChallenge.challenge_id == challenge_id,
            )
        )
        user_challenge = result.scalars().first()

        if not user_challenge:
            user_challenge = UserChallenge(
                user_id=user_id,
                challenge_id=challenge_id,
                progress=progress,
                completed=False,
            )
            db.add(user_challenge)
        else:
            user_challenge.progress = progress

        challenge_result = await db.execute(
            select(Challenge).filter(Challenge.id == challenge_id)
        )
        challenge = challenge_result.scalars().first()
        just_completed = False

        if challenge and progress >= challenge.requirement_value:
            if not user_challenge.completed:
                user_challenge.completed = True
                user_challenge.completed_at = datetime.utcnow()
                just_completed = True
        else:
            user_challenge.completed = False

        await db.commit()
        await db.refresh(user_challenge)
        return user_challenge, just_completed

    @staticmethod
    async def ensure_today_daily_challenge(db: AsyncSession):
        today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_today = today.replace(hour=23, minute=59, second=59, microsecond=999999)
        result = await db.execute(
            select(Challenge).filter(
                Challenge.challenge_type == "daily",
                Challenge.active == True,  # noqa: E712
                Challenge.start_date <= today,
                Challenge.end_date >= today,
            )
        )
        daily_challenge = result.scalars().first()
        if not daily_challenge:
            daily_challenge = Challenge(
                title="بازی روزانه",
                description="امروز یک‌بار بازی کن",
                challenge_type="daily",
                requirement_type="play_daily_game",
                requirement_value=1,
                reward_type="xp",
                reward_value=10,
                start_date=today,
                end_date=end_of_today,
                active=True,
            )
            db.add(daily_challenge)
            await db.commit()
            await db.refresh(daily_challenge)
        return daily_challenge

    @staticmethod
    async def ensure_current_weekly_challenge(db: AsyncSession):
        now = datetime.utcnow()
        week_start = now - timedelta(days=now.weekday())
        week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
        week_end = week_start + timedelta(days=7, hours=23, minutes=59, seconds=59, microseconds=999999)
        result = await db.execute(
            select(Challenge).filter(
                Challenge.challenge_type == "weekly",
                Challenge.active == True,  # noqa: E712
                Challenge.start_date <= now,
                Challenge.end_date >= now,
            )
        )
        weekly_challenge = result.scalars().first()
        if not weekly_challenge:
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
                active=True,
            )
            db.add(weekly_challenge)
            await db.commit()
            await db.refresh(weekly_challenge)
        return weekly_challenge

    @staticmethod
    async def record_daily_login(db: AsyncSession, user_id: int):
        result = await db.execute(select(User).filter(User.id == user_id))
        user = result.scalars().first()
        if not user:
            return None, False
        # Deprecated: streak is now based on the daily game, not logins.
        return user, False

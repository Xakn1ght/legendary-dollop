from datetime import date, datetime

from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.settings import GAME_REWARDS
from app.database.models import ArcadeFlag, DailyGamePlay, User


class _GameMixin:
    @staticmethod
    async def get_monthly_arcade_ranking(
        db: AsyncSession, month_start: date, month_end: date, limit: int | None = None
    ):
        """The canonical monthly race ranking (also used for prize payouts):
        per-user best VALIDATED daily-run score in the window, visible users
        only, ties broken by whoever reached the score on an earlier day.
        Returns rows of (user_id, top_score, first_play, display_name)."""
        name = func.coalesce(
            func.nullif(User.custom_username, ""),
            func.nullif(User.username, ""),
            func.nullif(User.full_name, ""),
        )
        q = (
            select(
                DailyGamePlay.user_id,
                func.max(DailyGamePlay.best_score).label("top_score"),
                func.min(DailyGamePlay.play_date).label("first_play"),
                func.max(name).label("display_name"),
            )
            .join(User, User.id == DailyGamePlay.user_id)
            .filter(
                DailyGamePlay.play_date >= month_start,
                DailyGamePlay.play_date <= month_end,
                DailyGamePlay.rewarded == True,  # noqa: E712
                DailyGamePlay.best_score > 0,
                User.show_on_leaderboard == True,  # noqa: E712
            )
            .group_by(DailyGamePlay.user_id)
            .order_by(
                func.max(DailyGamePlay.best_score).desc(),
                func.min(DailyGamePlay.play_date).asc(),
                DailyGamePlay.user_id.asc(),
            )
        )
        if limit:
            q = q.limit(limit)
        return (await db.execute(q)).all()

    @staticmethod
    async def add_arcade_flag(
        db: AsyncSession, user_id: int, score: int, claimed_duration: int,
        server_elapsed: int | None, reason: str,
    ):
        """Persist a rejected arcade submit for the admin cheat log."""
        db.add(ArcadeFlag(
            user_id=user_id, score=score, claimed_duration=claimed_duration,
            server_elapsed=server_elapsed, reason=reason,
        ))
        await db.commit()
    @staticmethod
    async def get_or_create_daily_game_play(
        db: AsyncSession, user_id: int, date: datetime | None = None
    ) -> DailyGamePlay:
        if date is None:
            date = datetime.utcnow()
        play_date = date.date()
        result = await db.execute(
            select(DailyGamePlay).filter(
                DailyGamePlay.user_id == user_id,
                DailyGamePlay.play_date == play_date,
            )
        )
        row = result.scalars().first()
        if row:
            return row
        row = DailyGamePlay(user_id=user_id, play_date=play_date)
        db.add(row)
        await db.commit()
        await db.refresh(row)
        return row

    @staticmethod
    async def can_play_daily_game(db: AsyncSession, user_id: int) -> dict:
        from app.database.repos.reward import RewardRepository as _RR

        play = await _RR.get_or_create_daily_game_play(db, user_id)
        return {"allowed": not play.rewarded, "best_score": play.best_score}

    @staticmethod
    async def submit_daily_game_score(
        db: AsyncSession,
        user_id: int,
        score: int,
        duration_seconds: int,
        is_practice: bool = False,
    ) -> dict:
        from app.database.repos.reward import RewardRepository as _RR

        result = await db.execute(select(User).filter(User.id == user_id))
        user = result.scalars().first()
        if not user:
            raise ValueError("User not found")

        play = await _RR.get_or_create_daily_game_play(db, user_id)
        if score > play.best_score:
            play.best_score = score

        awarded = False
        rewards = {"credit": 0, "stars": 0, "xp": 0, "star_pieces": 0}

        if not is_practice and not play.rewarded:
            prev_streak = max(int(getattr(user, "login_streak", 0) or 0), 0)
            now = datetime.utcnow()
            last = getattr(user, "last_daily_login", None)

            if not last:
                next_streak = 1
            elif last.date() == now.date():
                next_streak = max(prev_streak, 1) if prev_streak else 1
            else:
                days_since = (now.date() - last.date()).days
                next_streak = (prev_streak + 1) if days_since == 1 else 1

            min_duration = GAME_REWARDS.get("min_session_seconds", 20)
            if duration_seconds >= min_duration:
                thresholds = GAME_REWARDS.get("thresholds", [])
                credit = 0
                xp = 0
                star_pieces = 0

                for threshold in thresholds:
                    if score >= threshold.get("min_score", 0):
                        credit = threshold.get("credits", 0)
                        xp = threshold.get("xp", 0)
                        star_pieces = threshold.get("star_pieces", 0)
                        break

                streak_bonus_per_day = GAME_REWARDS.get("streak_bonus_percent_per_day", 5)
                streak_bonus_max = GAME_REWARDS.get("streak_bonus_max_percent", 25)
                streak_bonus_percent = min(prev_streak * streak_bonus_per_day, streak_bonus_max)
                multiplier = 1.0 + (streak_bonus_percent / 100.0)

                credit = int(credit * multiplier)
                xp = int(xp * multiplier)

                stars_awarded = 0
                pieces_per_star = GAME_REWARDS.get("pieces_per_star", 10)
                monthly_cap = GAME_REWARDS.get("monthly_star_cap", 6)

                current_month = datetime.utcnow().replace(day=1).date()
                if user.arcade_stars_month_reset is None or user.arcade_stars_month_reset < current_month:
                    user.arcade_stars_this_month = 0
                    user.arcade_stars_month_reset = current_month

                if star_pieces > 0:
                    user.star_pieces += star_pieces
                    if user.star_pieces >= pieces_per_star:
                        potential_stars = user.star_pieces // pieces_per_star
                        remaining_pieces = user.star_pieces % pieces_per_star
                        stars_can_award = min(potential_stars, monthly_cap - user.arcade_stars_this_month)
                        if stars_can_award > 0:
                            user.star_pieces = remaining_pieces + ((potential_stars - stars_can_award) * pieces_per_star)
                            user.arcade_stars_this_month += stars_can_award
                            stars_awarded = stars_can_award
                            await _RR.add_stars(db, user_id, stars_can_award, "arcade_game")

                if credit > 0:
                    user.credit += credit
                if xp > 0:
                    await _RR.add_experience_points(db, user_id, xp, "arcade_play")

                loyalty_rate = GAME_REWARDS.get("loyalty_points_per_1000_credits", 1)
                loyalty_points = (credit // 1000) * loyalty_rate
                if loyalty_points > 0:
                    user.loyalty_points += loyalty_points

                play.rewarded = True
                play.duration_seconds = duration_seconds
                play.reward_credit = credit
                play.reward_stars = stars_awarded
                play.reward_xp = xp
                play.streak_on_play = next_streak
                awarded = True
                rewards = {"credit": credit, "stars": stars_awarded, "xp": xp, "star_pieces": star_pieces}

                user.login_streak = next_streak
                user.last_daily_login = now

                if credit:
                    await _RR.add_reward_history(db, user_id, "credit", credit, "arcade", notes=f"Score: {score}")
                if stars_awarded:
                    await _RR.add_reward_history(
                        db, user_id, "stars", stars_awarded, "arcade",
                        notes=f"Converted from {star_pieces} pieces",
                    )
                if xp:
                    await _RR.add_reward_history(db, user_id, "xp", xp, "arcade", notes=f"Score: {score}")

                active_challenges = await _RR.get_active_challenges(db)
                user_progress = {
                    p.challenge_id: p
                    for p in await _RR.get_user_challenge_progress(db, user_id)
                }
                for c in active_challenges:
                    if c.requirement_type in ("daily_game", "play_daily_game"):
                        prev = user_progress.get(c.id).progress if user_progress.get(c.id) else 0
                        await _RR.update_challenge_progress(db, user_id, c.id, prev + 1)
                    if c.requirement_type in ("weekly_game_score", "game_score"):
                        prev = user_progress.get(c.id).progress if user_progress.get(c.id) else 0
                        await _RR.update_challenge_progress(db, user_id, c.id, prev + score)
                    if c.requirement_type == "high_score" and score >= c.requirement_value:
                        await _RR.update_challenge_progress(db, user_id, c.id, score)

        await db.commit()
        await db.refresh(play)

        pieces_per_star = int(GAME_REWARDS.get("pieces_per_star", 10) or 10)
        monthly_cap = int(GAME_REWARDS.get("monthly_star_cap", 6) or 6)
        current_pieces = int(getattr(user, "star_pieces", 0) or 0) if user else 0
        monthly_stars = int(getattr(user, "arcade_stars_this_month", 0) or 0) if user else 0
        cap_reached = bool(monthly_stars >= monthly_cap) if user else False

        if pieces_per_star > 0:
            pieces_progress = current_pieces % pieces_per_star
            has_ready_star = (current_pieces >= pieces_per_star) and (pieces_progress == 0)
            if has_ready_star:
                pieces_progress = pieces_per_star
                to_next_star = 0
            else:
                to_next_star = pieces_per_star - pieces_progress
        else:
            pieces_progress = 0
            to_next_star = 0

        return {
            "awarded": awarded,
            "play": play,
            "rewards": rewards,
            "best_score": play.best_score,
            "already_rewarded": play.rewarded and not awarded,
            "star_pieces_total": user.star_pieces if user else 0,
            "star_pieces_progress": pieces_progress,
            "monthly_stars": monthly_stars,
            "monthly_star_cap": monthly_cap,
            "monthly_star_cap_reached": cap_reached,
            "pieces_per_star": pieces_per_star,
            "pieces_to_next_star": to_next_star,
        }

    @staticmethod
    async def check_daily_game_play(db: AsyncSession, user_id: int, play_date: date):
        result = await db.execute(
            select(DailyGamePlay)
            .filter(DailyGamePlay.user_id == user_id)
            .filter(DailyGamePlay.play_date == play_date)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def save_game_play(
        db: AsyncSession,
        user_id: int,
        score: int,
        duration: int,
        display_name: str,
        rewarded: bool = False,
        reward_credit: int = 0,
        reward_stars: int = 0,
        reward_xp: int = 0,
        count_for_leaderboard: bool = False,
    ):
        """Record a play. best_score is ONLY updated when count_for_leaderboard
        is True — i.e. by the single validated rewarded run per day. Practice,
        already-played and rejected runs are stored for analytics but can never
        reach a leaderboard or the monthly prize ranking (anti-cheat 2026-07-03)."""
        from app.database.repos.reward import RewardRepository as _RR

        today = date.today()
        existing = await _RR.check_daily_game_play(db, user_id, today)

        if existing:
            if count_for_leaderboard and score > existing.best_score:
                existing.best_score = score
            existing.duration_seconds = duration
            existing.display_name = display_name or existing.display_name
            if rewarded and not existing.rewarded:
                existing.rewarded = True
                existing.reward_credit = reward_credit
                existing.reward_stars = reward_stars
                existing.reward_xp = reward_xp
            await db.commit()
            return existing

        play = DailyGamePlay(
            user_id=user_id,
            play_date=today,
            best_score=score if count_for_leaderboard else 0,
            duration_seconds=duration,
            display_name=display_name,
            rewarded=rewarded,
            reward_credit=reward_credit if rewarded else 0,
            reward_stars=reward_stars if rewarded else 0,
            reward_xp=reward_xp if rewarded else 0,
        )
        db.add(play)
        await db.commit()
        await db.refresh(play)
        return play

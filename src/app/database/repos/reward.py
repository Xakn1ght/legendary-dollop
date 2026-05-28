from datetime import date, datetime, timedelta

import sqlalchemy
from sqlalchemy import and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.core.level_config import get_level_from_xp, get_level_rewards
from app.core.settings import GAME_REWARDS
from app.database.models import (
    Achievement,
    Challenge,
    DailyGamePlay,
    DailyStarCap,
    RewardHistory,
    StarHistory,
    StarRewardTier,
    User,
    UserAchievement,
    UserChallenge,
    UserDiscount,
    UserGift,
    UserStarRewardClaim,
)
from app.database.models import RewardConfig as _RewardConfig
from app.utils.logger import bot_logger, log_error


class RewardRepository:
    # --- Star Manager Logic ---
    @staticmethod
    async def add_stars(db: AsyncSession, user_id: int, count: int, reason: str = "general",
                       source_id: int = None, notes: str = None) -> tuple[User, bool, list]:
        if count == 0:
            raise ValueError("count must be non-zero")

        result = await db.execute(select(User).filter(User.id == user_id))
        user = result.scalars().first()
        if not user:
            return user, False, []

        original_stars = user.stars
        if count < 0 and (user.stars + count) < 0:
            # Prevent negative star balances.
            return user, False, []
        user.stars += count

        # Log star change
        await RewardRepository.log_star_change(db, user_id, count, reason, source_id, notes)

        bot_logger.info(f"[STAR_MANAGER] Added {count} stars to user {user_id} for '{reason}'. "
                       f"Original: {original_stars}, New: {user.stars}")

        newly_unlocked_tiers = []
        # Only unlock milestone tiers when stars increased.
        if count > 0:
            all_tiers = await RewardRepository.get_all_star_reward_tiers(db)
            for tier in all_tiers:
                if original_stars < tier.star_threshold <= user.stars:
                    claim = await RewardRepository.create_user_star_reward_claim(db, user_id, tier.id)
                    if claim:
                        newly_unlocked_tiers.append(tier)

        threshold_reached = user.stars >= 5
        await db.commit()
        await db.refresh(user)
        return user, threshold_reached, newly_unlocked_tiers

    @staticmethod
    async def reset_stars(db: AsyncSession, user_id: int, reason: str = "reset",
                         source_id: int = None, notes: str = None) -> User:
        result = await db.execute(select(User).filter(User.id == user_id))
        user = result.scalars().first()
        if user and user.stars > 0:
            await RewardRepository.log_star_change(db, user_id, -user.stars, reason, source_id, notes)
            user.stars = 0
            await db.commit()
            await db.refresh(user)
        return user

    @staticmethod
    async def get_star_balance(db: AsyncSession, user_id: int) -> int:
        result = await db.execute(select(User.stars).filter(User.id == user_id))
        stars = result.scalar()
        return stars or 0

    @staticmethod
    async def transfer_stars(db: AsyncSession, from_user_id: int, to_user_id: int, count: int,
                           reason: str = "transfer", notes: str = None) -> tuple[bool, str]:
        if count <= 0:
            return False, "Transfer amount must be positive"

        sender_stars = await RewardRepository.get_star_balance(db, from_user_id)
        if sender_stars < count:
            return False, f"Insufficient stars. Have {sender_stars}, need {count}"

        await RewardRepository.add_stars(db, from_user_id, -count, f"{reason}_out", None, notes)
        await RewardRepository.add_stars(db, to_user_id, count, f"{reason}_in", None, notes)
        return True, f"Successfully transferred {count} stars"

    @staticmethod
    async def log_star_change(db: AsyncSession, user_id: int, delta: int, reason: str, source_id: int = None, notes: str = None):
        star_entry = StarHistory(
            user_id=user_id,
            delta=delta,
            reason=reason,
            source_id=source_id,
            notes=notes
        )
        db.add(star_entry)
        await db.commit()
        await db.refresh(star_entry)
        return star_entry

    @staticmethod
    async def get_star_history(db: AsyncSession, user_id: int, limit: int = 50):
        result = await db.execute(
            select(StarHistory)
            .filter(StarHistory.user_id == user_id)
            .order_by(StarHistory.created_at.desc())
            .limit(limit)
        )
        return result.scalars().all()

    # --- Star Reward Tiers ---
    @staticmethod
    async def create_star_reward_tier(db: AsyncSession, tier_data: dict):
        new_tier = StarRewardTier(**tier_data)
        db.add(new_tier)
        await db.commit()
        await db.refresh(new_tier)
        return new_tier

    @staticmethod
    async def get_star_reward_tier(db: AsyncSession, tier_id: int):
        result = await db.execute(select(StarRewardTier).filter(StarRewardTier.id == tier_id))
        return result.scalars().first()

    @staticmethod
    async def get_all_star_reward_tiers(db: AsyncSession, active_only: bool = True):
        query = select(StarRewardTier)
        if active_only:
            query = query.filter(StarRewardTier.is_active == True)
        result = await db.execute(query.order_by(StarRewardTier.star_threshold))
        return result.scalars().all()

    @staticmethod
    async def update_star_reward_tier(db: AsyncSession, tier_id: int, tier_data: dict):
        tier = await RewardRepository.get_star_reward_tier(db, tier_id)
        if tier:
            for key, value in tier_data.items():
                setattr(tier, key, value)
            await db.commit()
            await db.refresh(tier)
        return tier

    @staticmethod
    async def delete_star_reward_tier(db: AsyncSession, tier_id: int):
        tier = await RewardRepository.get_star_reward_tier(db, tier_id)
        if tier:
            await db.delete(tier)
            await db.commit()
        return tier

    # --- User Star Reward Claims ---
    @staticmethod
    async def create_user_star_reward_claim(db: AsyncSession, user_id: int, tier_id: int):
        now = datetime.utcnow()
        expires = now + timedelta(days=3)
        start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        result = await db.execute(
            select(UserStarRewardClaim).filter(
                UserStarRewardClaim.user_id == user_id,
                UserStarRewardClaim.tier_id == tier_id,
                UserStarRewardClaim.status == 'offered',
                UserStarRewardClaim.offered_at >= start_of_month
            )
        )
        if result.scalars().first():
            return None

        new_claim = UserStarRewardClaim(
            user_id=user_id,
            tier_id=tier_id,
            expires_at=expires
        )
        db.add(new_claim)
        await db.commit()
        await db.refresh(new_claim)
        return new_claim

    @staticmethod
    async def get_user_unclaimed_rewards(db: AsyncSession, user_id: int):
        now = datetime.utcnow()
        result = await db.execute(
            select(UserStarRewardClaim)
            .options(selectinload(UserStarRewardClaim.tier))
            .filter(
                UserStarRewardClaim.user_id == user_id,
                UserStarRewardClaim.status.in_(['offered', 'pending_subscription']),
                UserStarRewardClaim.expires_at > now
            )
            .order_by(UserStarRewardClaim.offered_at.asc())
        )
        return result.scalars().all()

    @staticmethod
    async def claim_user_star_reward(db: AsyncSession, claim_id: int, reward_type: str):
        result = await db.execute(
            select(UserStarRewardClaim)
            .options(selectinload(UserStarRewardClaim.tier))
            .filter(UserStarRewardClaim.id == claim_id)
        )
        claim = result.scalars().first()
        
        if not claim or claim.status != 'offered' or claim.expires_at <= datetime.utcnow():
            return None, "Claim not found, already claimed, or expired."
            
        if reward_type != claim.tier.reward_type:
            return None, "Invalid reward choice."

        claim.status = 'claimed'
        claim.claimed_at = datetime.utcnow()
        claim.chosen_reward_type = reward_type
        
        await db.commit()
        await db.refresh(claim)
        return claim, "Success"

    @staticmethod
    async def get_user_star_reward_claim_by_id(db: AsyncSession, claim_id: int):
        result = await db.execute(select(UserStarRewardClaim).options(selectinload(UserStarRewardClaim.tier)).filter(UserStarRewardClaim.id == claim_id))
        return result.scalars().first()

    @staticmethod
    async def get_pending_extradays_claim(db: AsyncSession, user_id: int):
        now = datetime.utcnow()
        result = await db.execute(
            select(UserStarRewardClaim)
            .options(selectinload(UserStarRewardClaim.tier))
            .join(UserStarRewardClaim.tier)
            .filter(
                UserStarRewardClaim.user_id == user_id,
                UserStarRewardClaim.status == 'pending_subscription',
                StarRewardTier.reward_type == 'extra_days',
                UserStarRewardClaim.expires_at > now
            )
            .order_by(UserStarRewardClaim.offered_at.desc())
            .limit(1)
        )
        return result.scalars().first()

    # --- Arcade Game ---
    @staticmethod
    async def get_or_create_daily_game_play(db: AsyncSession, user_id: int, date: datetime | None = None) -> DailyGamePlay:
        if date is None:
            date = datetime.utcnow()
        play_date = date.date()
        result = await db.execute(select(DailyGamePlay).filter(DailyGamePlay.user_id == user_id, DailyGamePlay.play_date == play_date))
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
        play = await RewardRepository.get_or_create_daily_game_play(db, user_id)
        return {"allowed": not play.rewarded, "best_score": play.best_score}

    @staticmethod
    async def submit_daily_game_score(db: AsyncSession, user_id: int, score: int, duration_seconds: int, is_practice: bool = False) -> dict:
        """Submit daily game score with balanced reward system"""
        result = await db.execute(select(User).filter(User.id == user_id))
        user = result.scalars().first()
        if not user:
            raise ValueError("User not found")

        play = await RewardRepository.get_or_create_daily_game_play(db, user_id)
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
                            await RewardRepository.add_stars(db, user_id, stars_can_award, "arcade_game")

                if credit > 0:
                    user.credit += credit
                if xp > 0:
                    await RewardRepository.add_experience_points(db, user_id, xp, "arcade_play")

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
                    await RewardRepository.add_reward_history(db, user_id, "credit", credit, "arcade", notes=f"Score: {score}")
                if stars_awarded:
                    await RewardRepository.add_reward_history(
                        db,
                        user_id,
                        "stars",
                        stars_awarded,
                        "arcade",
                        notes=f"Converted from {star_pieces} pieces",
                    )
                if xp:
                    await RewardRepository.add_reward_history(db, user_id, "xp", xp, "arcade", notes=f"Score: {score}")

                active_challenges = await RewardRepository.get_active_challenges(db)
                user_progress = {p.challenge_id: p for p in await RewardRepository.get_user_challenge_progress(db, user_id)}
                for c in active_challenges:
                    if c.requirement_type in ("daily_game", "play_daily_game"):
                        prev = user_progress.get(c.id).progress if user_progress.get(c.id) else 0
                        await RewardRepository.update_challenge_progress(db, user_id, c.id, prev + 1)
                    if c.requirement_type in ("weekly_game_score", "game_score"):
                        prev = user_progress.get(c.id).progress if user_progress.get(c.id) else 0
                        await RewardRepository.update_challenge_progress(db, user_id, c.id, prev + score)
                    if c.requirement_type == "high_score" and score >= c.requirement_value:
                        await RewardRepository.update_challenge_progress(db, user_id, c.id, score)

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

    # --- Challenges ---
    @staticmethod
    async def get_active_challenges(db: AsyncSession, challenge_type: str = None):
        now = datetime.utcnow()
        query = select(Challenge).filter(Challenge.active == True, Challenge.start_date <= now, Challenge.end_date >= now)
        if challenge_type:
            query = query.filter(Challenge.challenge_type == challenge_type)
        result = await db.execute(query)
        return result.scalars().all()

    @staticmethod
    async def get_user_challenge_progress(db: AsyncSession, user_id: int, challenge_id: int = None):
        query = select(UserChallenge).options(selectinload(UserChallenge.challenge))
        if challenge_id:
            query = query.filter(UserChallenge.user_id == user_id, UserChallenge.challenge_id == challenge_id)
        else:
            query = query.filter(UserChallenge.user_id == user_id)
        result = await db.execute(query)
        return result.scalars().all()

    @staticmethod
    async def update_challenge_progress(db: AsyncSession, user_id: int, challenge_id: int, progress: int):
        result = await db.execute(select(UserChallenge).filter(UserChallenge.user_id == user_id, UserChallenge.challenge_id == challenge_id))
        user_challenge = result.scalars().first()
        
        if not user_challenge:
            user_challenge = UserChallenge(user_id=user_id, challenge_id=challenge_id, progress=progress, completed=False)
            db.add(user_challenge)
        else:
            user_challenge.progress = progress
            
        challenge_result = await db.execute(select(Challenge).filter(Challenge.id == challenge_id))
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

    # --- Achievements ---
    @staticmethod
    async def get_user_achievements(db: AsyncSession, user_id: int):
        result = await db.execute(select(UserAchievement).options(selectinload(UserAchievement.achievement)).filter(UserAchievement.user_id == user_id))
        return result.scalars().all()

    @staticmethod
    async def check_and_award_achievements(db: AsyncSession, user_id: int, achievement_type: str, current_value: int):
        result = await db.execute(
            select(Achievement)
            .outerjoin(UserAchievement, and_(Achievement.id == UserAchievement.achievement_id, UserAchievement.user_id == user_id))
            .filter(Achievement.requirement_type == achievement_type, UserAchievement.id == None)
        )
        available = result.scalars().all()
        earned = []
        
        for achievement in available:
            if current_value >= achievement.requirement_value:
                ua = UserAchievement(user_id=user_id, achievement_id=achievement.id)
                db.add(ua)
                
                if achievement.reward_type == "xp":
                    await RewardRepository.add_experience_points(db, user_id, achievement.reward_value, "achievement")
                elif achievement.reward_type == "loyalty_points":
                    await RewardRepository.add_loyalty_points(db, user_id, achievement.reward_value, "achievement")
                elif achievement.reward_type == "credit":
                     from app.database.repos.user import UserRepository
                     await UserRepository.add_credit(db, user_id, achievement.reward_value)
                     await RewardRepository.add_reward_history(db, user_id, "credit", achievement.reward_value, "achievement", achievement.id)
                elif achievement.reward_type == "stars":
                    await RewardRepository.add_stars(db, user_id, achievement.reward_value, "achievement", achievement.id)
                
                earned.append(achievement)
        
        if earned:
            await db.commit()
        return earned

    # --- History & Points ---
    @staticmethod
    async def add_reward_history(db: AsyncSession, user_id: int, reward_type: str, reward_value: int, source: str, source_id: int = None, notes: str = None):
        entry = RewardHistory(user_id=user_id, reward_type=reward_type, reward_value=reward_value, source=source, source_id=source_id, notes=notes)
        db.add(entry)
        await db.commit()
        await db.refresh(entry)
        return entry

    @staticmethod
    async def get_user_reward_history(db: AsyncSession, user_id: int, limit: int = 50):
        result = await db.execute(select(RewardHistory).filter(RewardHistory.user_id == user_id).order_by(RewardHistory.earned_at.desc()).limit(limit))
        return result.scalars().all()

    @staticmethod
    async def add_experience_points(db: AsyncSession, user_id: int, points: int, source: str = "general"):
        if points <= 0: return None, False
        result = await db.execute(select(User).filter(User.id == user_id))
        user = result.scalars().first()
        if not user: return None, False
        
        old_level = user.level
        user.experience_points += points
        new_level = get_level_from_xp(user.experience_points)
        user.level = new_level
        
        await RewardRepository.add_reward_history(db, user_id, "xp", points, source)
        await db.commit()
        await db.refresh(user)
        
        leveled_up = new_level > old_level
        if leveled_up:
            rewards = get_level_rewards(new_level)
            if rewards.get("loyalty_points"):
                user.loyalty_points += rewards["loyalty_points"]
                await RewardRepository.add_reward_history(db, user_id, "loyalty_points", rewards["loyalty_points"], "level_up", new_level)
            if rewards.get("credit"):
                user.credit += rewards["credit"]
                await RewardRepository.add_reward_history(db, user_id, "credit", rewards["credit"], "level_up", new_level)
            await db.commit()
            await db.refresh(user)
            
        return user, leveled_up

    @staticmethod
    async def add_loyalty_points(db: AsyncSession, user_id: int, points: int, source: str = "general", description: str | None = None):
        if points <= 0: return None
        result = await db.execute(select(User).filter(User.id == user_id))
        user = result.scalars().first()
        if user:
            user.loyalty_points += points
            await RewardRepository.add_reward_history(db, user_id, "loyalty_points", points, source, notes=description)
            await db.commit()
            await db.refresh(user)
        return user

    @staticmethod
    async def get_reward_config(db: AsyncSession):
        result = await db.execute(select(_RewardConfig).limit(1))
        cfg = result.scalars().first()
        if cfg is None:
            cfg = _RewardConfig(traffic_percent=10.0, days_percent=10.0, credit_percent=10.0)
            db.add(cfg)
            await db.commit()
            await db.refresh(cfg)
        return cfg

    @staticmethod
    async def update_reward_config(db: AsyncSession, **kwargs):
        cfg = await RewardRepository.get_reward_config(db)
        allowed = {'traffic_percent', 'days_percent', 'credit_percent'}
        for k, v in kwargs.items():
            if k in allowed and v is not None:
                setattr(cfg, k, v)
        await db.commit()
        await db.refresh(cfg)
        return cfg

    # --- Gifts ---
    @staticmethod
    async def create_user_gift(db: AsyncSession, sender_id: int, receiver_id: int, gift_type: str, gift_value: int, message: str = None, plan_name: str | None = None):
        gift = UserGift(
            sender_id=sender_id, receiver_id=receiver_id, gift_type=gift_type, 
            gift_value=gift_value, plan_name=plan_name, message=message
        )
        db.add(gift)
        await db.commit()
        await db.refresh(gift)
        return gift

    @staticmethod
    async def get_user_gifts(db: AsyncSession, user_id: int, gift_type: str = "received"):
        if gift_type == "received":
            result = await db.execute(select(UserGift).options(selectinload(UserGift.sender)).filter(UserGift.receiver_id == user_id))
        else:
            result = await db.execute(select(UserGift).options(selectinload(UserGift.receiver)).filter(UserGift.sender_id == user_id))
        return result.scalars().all()

    @staticmethod
    async def accept_user_gift(db: AsyncSession, gift_id: int):
        result = await db.execute(select(UserGift).filter(UserGift.id == gift_id, UserGift.accepted == False))
        gift = result.scalars().first()
        if not gift: return None
        
        if gift.gift_type == "credit":
             from app.database.repos.user import UserRepository
             await UserRepository.add_credit(db, gift.receiver_id, gift.gift_value)
        elif gift.gift_type == "loyalty_points":
            await RewardRepository.add_loyalty_points(db, gift.receiver_id, gift.gift_value, "gift")
            
        gift.accepted = True
        gift.accepted_at = datetime.utcnow()
        await db.commit()
        await db.refresh(gift)
        return gift

    # --- Daily Cap ---
    @staticmethod
    async def get_or_create_daily_cap(db: AsyncSession, user_id: int, date: date = None, max_allowed: int = 10):
        if date is None: date = datetime.utcnow().date()
        result = await db.execute(select(DailyStarCap).filter(DailyStarCap.user_id == user_id, DailyStarCap.date == date))
        cap = result.scalar_one_or_none()
        if not cap:
            cap = DailyStarCap(user_id=user_id, date=date, stars_earned=0, max_allowed=max_allowed)
            db.add(cap)
            await db.commit()
            await db.refresh(cap)
        return cap

    @staticmethod
    async def get_daily_cap_status(db: AsyncSession, user_id: int, max_allowed: int = 10) -> dict:
        cap = await RewardRepository.get_or_create_daily_cap(db, user_id, max_allowed=max_allowed)
        return {
            "stars_earned": cap.stars_earned,
            "max_allowed": cap.max_allowed,
            "remaining": max(cap.max_allowed - cap.stars_earned, 0),
            "can_earn_more": cap.stars_earned < cap.max_allowed
        }

    # --- Discounts ---
    @staticmethod
    async def add_user_discount(db: AsyncSession, user_id: int, percent: int, expiration: datetime, source: str = None):
        discount = UserDiscount(user_id=user_id, percent=percent, expiration=expiration, used=False, source=source)
        db.add(discount)
        await db.commit()
        await db.refresh(discount)
        return discount

    @staticmethod
    async def get_active_user_discounts(db: AsyncSession, user_id: int):
        now = datetime.utcnow()
        result = await db.execute(
            select(UserDiscount).filter(UserDiscount.user_id == user_id, UserDiscount.used == False, UserDiscount.expiration > now)
        )
        return result.scalars().all()

    @staticmethod
    async def mark_user_discounts_used(db: AsyncSession, discount_ids: list):
        if not discount_ids: return
        result = await db.execute(select(UserDiscount).filter(UserDiscount.id.in_(discount_ids)))
        discounts = result.scalars().all()
        for d in discounts:
            d.used = True
        await db.commit()
        return discounts

    @staticmethod
    async def check_daily_game_play(db: AsyncSession, user_id: int, play_date: date):
        """Check if user already played and was rewarded today"""
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
        reward_xp: int = 0
    ):
        """Save or update game play record"""
        today = date.today()
        
        # Check if record exists for today
        existing = await RewardRepository.check_daily_game_play(db, user_id, today)
        
        if existing:
            # Update if new score is better
            if score > existing.best_score:
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
        else:
            # Create new record
            play = DailyGamePlay(
                user_id=user_id,
                play_date=today,
                best_score=score,
                duration_seconds=duration,
                display_name=display_name,
                rewarded=rewarded,
                reward_credit=reward_credit if rewarded else 0,
                reward_stars=reward_stars if rewarded else 0,
                reward_xp=reward_xp if rewarded else 0
            )
            db.add(play)
            await db.commit()
            await db.refresh(play)
            return play

    @staticmethod
    async def ensure_today_daily_challenge(db: AsyncSession):
        today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_today = today.replace(hour=23, minute=59, second=59, microsecond=999999)
        result = await db.execute(
            select(Challenge).filter(
                Challenge.challenge_type == "daily",
                Challenge.active == True,
                Challenge.start_date <= today,
                Challenge.end_date >= today
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
                active=True
            )
            db.add(daily_challenge)
            await db.commit()
            await db.refresh(daily_challenge)
        return daily_challenge

    @staticmethod
    async def record_daily_login(db: AsyncSession, user_id: int):
        result = await db.execute(select(User).filter(User.id == user_id))
        user = result.scalars().first()
        if not user:
            return None, False
        # Deprecated: streak is now based on the daily game, not logins.
        # Keep this for backward compatibility with older bot flows.
        return user, False

    @staticmethod
    async def ensure_current_weekly_challenge(db: AsyncSession):
        now = datetime.utcnow()
        week_start = now - timedelta(days=now.weekday())
        week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
        week_end = week_start + timedelta(days=7, hours=23, minutes=59, seconds=59, microseconds=999999)
        result = await db.execute(
            select(Challenge).filter(
                Challenge.challenge_type == "weekly",
                Challenge.active == True,
                Challenge.start_date <= now,
                Challenge.end_date >= now
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
                active=True
            )
            db.add(weekly_challenge)
            await db.commit()
            await db.refresh(weekly_challenge)
        return weekly_challenge

    @staticmethod
    async def calculate_and_award_cashback(db: AsyncSession, user_id: int, milestone: int) -> int:
        from app.database.repos.subscription import SubscriptionRepository
        subs = await SubscriptionRepository.get_user_subscriptions(db, user_id)
        if len(subs) < milestone:
            return 0
        
        last_subs = subs[-milestone:]
        total_cashback = 0
        for sub in last_subs:
            if not sub.price:
                continue
            
            plan_name = sub.plan_name or ""
            # Reduced cashback rates to prevent financial issues
            if "20" in plan_name or sub.price <= 70000:
                rate = 0.03  # 3% (was 8%)
            elif "40" in plan_name or sub.price <= 140000:
                rate = 0.04  # 4% (was 10%)
            elif "60" in plan_name or sub.price <= 200000:
                rate = 0.05  # 5% (was 12%)
            else:
                rate = 0.06  # 6% (was 13%)
            
            cashback = int(sub.price * rate)
            total_cashback += cashback
        
        if total_cashback > 0:
            from app.database.repos.user import UserRepository
            await UserRepository.add_credit(db, user_id, total_cashback)
            await RewardRepository.add_reward_history(
                db, user_id, "credit", total_cashback, "purchase_cashback",
                notes=f"Cashback for {milestone} purchases"
            )
        
        return total_cashback

    @staticmethod
    async def check_level_up(db: AsyncSession, user_id: int):
        result = await db.execute(select(User).filter(User.id == user_id))
        user = result.scalars().first()
        if not user:
            return None, False
        
        old_level = user.level
        new_level = get_level_from_xp(user.experience_points)
        
        if new_level > old_level:
            user.level = new_level
            await db.commit()
            await db.refresh(user)
            return user, True
        
        return user, False

    @staticmethod
    async def deduct_loyalty_points(
        db: AsyncSession,
        user_id: int,
        points: int,
        reason: str | None = None,
    ):
        if points <= 0:
            return None

        result = await db.execute(select(User).filter(User.id == user_id))
        user = result.scalars().first()
        if not user or user.loyalty_points < points:
            return None

        user.loyalty_points -= points

        await RewardRepository.add_reward_history(
            db,
            user_id,
            "loyalty_points",
            -points,
            "deduction",
            notes=reason,
        )

        await db.commit()
        await db.refresh(user)
        return user

    @staticmethod
    async def set_gift_payment_status(db: AsyncSession, gift_id: int, status: str, receipt_message_id: int | None = None):
        result = await db.execute(select(UserGift).filter(UserGift.id == gift_id))
        gift = result.scalars().first()
        if not gift:
            return None
        gift.payment_status = status
        if receipt_message_id is not None:
            gift.payment_receipt_message_id = receipt_message_id
        await db.commit()
        await db.refresh(gift)
        return gift

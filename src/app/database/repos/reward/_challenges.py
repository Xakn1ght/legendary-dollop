"""Challenge progress + XP-only payouts (rebuilt 2026-07-19 for launch).

The challenge system is fully event-driven — no scheduler jobs:
- Creation: ensure_* helpers run on access (bot challenges screen) and on
  every progress event, so an active daily/weekly challenge always exists
  exactly when someone can see or advance one.
- Progress: callers fire ``record_challenge_event`` from real product events
  (validated arcade run via api/routes/game/reward_core.py, referral approval
  in services/subscription_processing.py + services/flows/charge.py).
- Payout: ECONOMY IRON RULE — challenges pay XP ONLY, never credit / stars /
  loyalty / GB. Legacy monetary reward definitions are mapped to XP at grant
  time (see ``challenge_xp_value``); the grant is idempotent via a
  RewardHistory guard row (source='challenge', source_id=challenge_id).
"""

from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.database.models import Challenge, RewardHistory, User, UserChallenge

# XP mapping for legacy monetary challenge definitions (documented rule):
#   xp            -> value unchanged
#   credit        -> value / 10, clamped to 10..200   (500 credit -> 50 XP)
#   loyalty_points-> value / 2,  clamped to 10..200   (100 pts    -> 50 XP)
#   stars / other -> flat 50 XP
# The clamp keeps challenge payouts inside the arcade daily XP scale (10-200).
CHALLENGE_XP_MIN = 10
CHALLENGE_XP_MAX = 200
CHALLENGE_XP_FALLBACK = 50


def challenge_xp_value(reward_type: str, reward_value) -> int:
    try:
        value = int(reward_value or 0)
    except (TypeError, ValueError):
        value = 0
    rt = (reward_type or "").strip().lower()
    if rt == "xp":
        return max(0, value)
    if rt == "credit":
        xp = value // 10
    elif rt == "loyalty_points":
        xp = value // 2
    else:
        xp = CHALLENGE_XP_FALLBACK
    return max(CHALLENGE_XP_MIN, min(CHALLENGE_XP_MAX, xp))


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

    # ------------------------------------------------------------------
    # Payout (XP only, exactly once per user+challenge)
    # ------------------------------------------------------------------
    @staticmethod
    async def _grant_challenge_reward(db: AsyncSession, user_id: int, challenge: Challenge) -> int:
        """Grant the challenge XP exactly once. Returns the XP paid (0 when
        the guard row already exists). Caller commits."""
        from app.database.repos.reward import RewardRepository as _RR

        existing = (await db.execute(
            select(RewardHistory.id).filter(
                RewardHistory.user_id == user_id,
                RewardHistory.source == "challenge",
                RewardHistory.source_id == challenge.id,
            ).limit(1)
        )).scalars().first()
        if existing:
            return 0

        xp = challenge_xp_value(challenge.reward_type, challenge.reward_value)
        # Guard row FIRST (also the audit trail), then the XP itself.
        await _RR.add_reward_history(
            db, user_id, "xp", xp, "challenge", challenge.id,
            notes=f"Challenge completed: {challenge.title}",
        )
        if xp > 0:
            await _RR.add_experience_points(db, user_id, xp, "challenge_completion")
        return xp

    @staticmethod
    async def _notify_challenge_completed(db: AsyncSession, user_id: int, challenge: Challenge, xp: int):
        """Emoji-free Persian completion notice via the notification system
        (dashboard polls it; failures never block the grant)."""
        try:
            from app.database.notifications_crud import create_notification
            from app.utils.text_format import to_persian_digits

            await create_notification(
                db,
                user_id=user_id,
                type="general",
                title="چالش تکمیل شد",
                message=(
                    f"چالش «{challenge.title}» را کامل کردید و {to_persian_digits(xp)} امتیاز تجربه گرفتید."
                ),
            )
        except Exception:
            pass

    @staticmethod
    async def update_challenge_progress(
        db: AsyncSession, user_id: int, challenge_id: int, progress: int
    ):
        """Set absolute progress; on first completion grant the XP payout
        (idempotent) and queue the user notification."""
        from app.database.repos.reward import RewardRepository as _RR

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

        if just_completed and challenge:
            xp = await _RR._grant_challenge_reward(db, user_id, challenge)
            if xp > 0:
                await _RR._notify_challenge_completed(db, user_id, challenge, xp)
            await db.commit()

        await db.refresh(user_challenge)
        return user_challenge, just_completed

    # ------------------------------------------------------------------
    # Event-driven progress (the only live write path)
    # ------------------------------------------------------------------
    @staticmethod
    async def record_challenge_event(
        db: AsyncSession, user_id: int, kind: str, amount: int = 1, score: int | None = None
    ) -> list:
        """Advance every active challenge that the event touches.

        kind='daily_game'  — one validated (rewarded, non-practice) arcade run;
                             ``score`` additionally feeds score challenges.
        kind='referral'    — one approved referral purchase for this referrer.
        Ensures the standing daily/weekly challenges exist first (creation is
        on-demand — there are no scheduler jobs). Returns the challenges
        completed by this event.
        """
        from app.database.repos.reward import RewardRepository as _RR

        if kind == "daily_game":
            await _RR.ensure_today_daily_challenge(db)
            await _RR.ensure_current_weekly_challenges(db)
        elif kind == "referral":
            await _RR.ensure_current_weekly_challenges(db)

        active = await _RR.get_active_challenges(db)
        progress_map = {
            p.challenge_id: p for p in await _RR.get_user_challenge_progress(db, user_id)
        }

        def _prev(challenge_id: int) -> int:
            row = progress_map.get(challenge_id)
            return int(row.progress or 0) if row else 0

        completed = []
        for c in active:
            req = (c.requirement_type or "").strip().lower()
            uc = None
            just = False
            if kind == "daily_game" and req in ("daily_game", "play_daily_game"):
                uc, just = await _RR.update_challenge_progress(db, user_id, c.id, _prev(c.id) + max(1, amount))
            elif kind == "daily_game" and req in ("weekly_game_score", "game_score") and score:
                uc, just = await _RR.update_challenge_progress(db, user_id, c.id, _prev(c.id) + int(score))
            elif kind == "daily_game" and req == "high_score" and score and score >= c.requirement_value:
                uc, just = await _RR.update_challenge_progress(db, user_id, c.id, int(score))
            elif kind == "referral" and req == "referrals":
                uc, just = await _RR.update_challenge_progress(db, user_id, c.id, _prev(c.id) + max(1, amount))
            if just:
                completed.append(c)
        return completed

    # ------------------------------------------------------------------
    # On-demand creation (XP-only definitions)
    # ------------------------------------------------------------------
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
                description="امروز یک دور امتیازی بازی کن",
                challenge_type="daily",
                requirement_type="daily_game",
                requirement_value=1,
                reward_type="xp",
                reward_value=20,
                start_date=today,
                end_date=end_of_today,
                active=True,
            )
            db.add(daily_challenge)
            await db.commit()
            await db.refresh(daily_challenge)
        return daily_challenge

    @staticmethod
    async def ensure_current_weekly_challenges(db: AsyncSession):
        """Ensure this week's standing challenges exist (referrals + game
        score). XP-only by definition."""
        now = datetime.utcnow()
        week_start = now - timedelta(days=now.weekday())
        week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
        week_end = week_start + timedelta(days=6, hours=23, minutes=59, seconds=59, microseconds=999999)

        result = await db.execute(
            select(Challenge).filter(
                Challenge.challenge_type == "weekly",
                Challenge.active == True,  # noqa: E712
                Challenge.start_date <= now,
                Challenge.end_date >= now,
            )
        )
        existing = result.scalars().all()
        have_types = {(c.requirement_type or "").strip().lower() for c in existing}
        created = list(existing)

        if "referrals" not in have_types:
            ch = Challenge(
                title="معرفی هفتگی",
                description="۳ نفر را این هفته معرفی کنید",
                challenge_type="weekly",
                requirement_type="referrals",
                requirement_value=3,
                reward_type="xp",
                reward_value=50,
                start_date=week_start,
                end_date=week_end,
                active=True,
            )
            db.add(ch)
            created.append(ch)
        if not have_types.intersection({"weekly_game_score", "game_score"}):
            ch = Challenge(
                title="امتیاز هفتگی آرکید",
                description="این هفته در مجموع ۱۰ هزار امتیاز در بازی جمع کن",
                challenge_type="weekly",
                requirement_type="weekly_game_score",
                requirement_value=10000,
                reward_type="xp",
                reward_value=75,
                start_date=week_start,
                end_date=week_end,
                active=True,
            )
            db.add(ch)
            created.append(ch)
        if db.new:
            await db.commit()
        return created

    @staticmethod
    async def ensure_current_weekly_challenge(db: AsyncSession):
        """Back-compat shim for old callers — returns the referral weekly."""
        from app.database.repos.reward import RewardRepository as _RR

        challenges = await _RR.ensure_current_weekly_challenges(db)
        for c in challenges:
            if (c.requirement_type or "").strip().lower() == "referrals":
                return c
        return challenges[0] if challenges else None

    @staticmethod
    async def record_daily_login(db: AsyncSession, user_id: int):
        result = await db.execute(select(User).filter(User.id == user_id))
        user = result.scalars().first()
        if not user:
            return None, False
        # Deprecated: streak is now based on the daily game, not logins.
        return user, False

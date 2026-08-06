import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from ._base import Base


class RewardConfig(Base):
    """Singleton table (id=1) storing adjustable reward percentages."""
    __tablename__ = "reward_config"

    id = Column(Integer, primary_key=True, default=1)
    traffic_percent = Column(Float, default=5.0, nullable=False)
    days_percent = Column(Float, default=1.0, nullable=False)
    credit_percent = Column(Float, default=10.0, nullable=False)


class Achievement(Base):
    """Predefined achievements that users can earn."""
    __tablename__ = "achievements"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=False)
    icon = Column(String(50), nullable=True)
    requirement_type = Column(String(50), nullable=False)
    requirement_value = Column(Integer, nullable=False)
    reward_type = Column(String(50), nullable=False)
    reward_value = Column(String(100), nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class UserAchievement(Base):
    """Achievements earned by users."""
    __tablename__ = "user_achievements"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    achievement_id = Column(Integer, ForeignKey("achievements.id"), nullable=False)
    earned_at = Column(DateTime, default=datetime.datetime.utcnow)

    user = relationship("User", back_populates="achievements")
    achievement = relationship("Achievement")


class AchievementClaim(Base):
    """One-time reward claims for the code-defined mission achievements
    (services/achievements.py) — separate from the legacy seeded
    Achievement/UserAchievement pair, which the old bot UI still reads."""
    __tablename__ = "achievement_claims"
    __table_args__ = (
        UniqueConstraint("user_id", "achievement_key", name="uq_achievement_claim_user_key"),
    )

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    achievement_key = Column(String(32), nullable=False)
    coupon_id = Column(Integer, ForeignKey("reward_coupons.id"), nullable=True)
    claimed_at = Column(DateTime, default=datetime.datetime.utcnow)

    user = relationship("User")


class Challenge(Base):
    """Daily, weekly, and seasonal challenges."""
    __tablename__ = "challenges"

    id = Column(Integer, primary_key=True)
    title = Column(String(100), nullable=False)
    description = Column(Text, nullable=False)
    challenge_type = Column(String(50), nullable=False)
    requirement_type = Column(String(50), nullable=False)
    requirement_value = Column(Integer, nullable=False)
    reward_type = Column(String(50), nullable=False)
    reward_value = Column(Integer, nullable=False)
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=False)
    active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class UserChallenge(Base):
    """User progress on challenges."""
    __tablename__ = "user_challenges"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    challenge_id = Column(Integer, ForeignKey("challenges.id"), nullable=False)
    progress = Column(Integer, default=0, nullable=False)
    completed = Column(Boolean, default=False, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    user = relationship("User", back_populates="challenge_progress")
    challenge = relationship("Challenge")


class RewardHistory(Base):
    """Detailed tracking of all rewards earned and spent."""
    __tablename__ = "reward_history"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    reward_type = Column(String(50), nullable=False)
    reward_value = Column(Integer, nullable=False)
    source = Column(String(50), nullable=False)
    source_id = Column(Integer, nullable=True)
    notes = Column(String, nullable=True)
    earned_at = Column(DateTime, default=datetime.datetime.utcnow)
    spent_at = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="reward_history")


class DailyGamePlay(Base):
    """One play session per user per day for the daily arcade game."""
    __tablename__ = "daily_game_plays"
    __table_args__ = (
        UniqueConstraint("user_id", "play_date", name="uq_daily_play_user_date"),
    )

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    play_date = Column(Date, nullable=False)
    best_score = Column(Integer, default=0, nullable=False)
    duration_seconds = Column(Integer, default=0, nullable=False)
    display_name = Column(String(40), default="", nullable=False)
    rewarded = Column(Boolean, default=False, nullable=False)
    streak_on_play = Column(Integer, default=0, nullable=False)
    reward_credit = Column(Integer, default=0, nullable=False)
    reward_stars = Column(Integer, default=0, nullable=False)
    reward_xp = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    user = relationship("User")


class ArcadeFlag(Base):
    """Anti-cheat audit trail: arcade submits rejected by the round-token /
    plausibility gate (2026-07-03). Reviewed via /api/admin/arcade/flags."""
    __tablename__ = "arcade_flags"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    score = Column(Integer, default=0, nullable=False)
    claimed_duration = Column(Integer, default=0, nullable=False)   # client-claimed seconds
    server_elapsed = Column(Integer, nullable=True)                 # token age; None = no/invalid token
    reason = Column(String(40), nullable=False)                     # no_token | implausible_score
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    user = relationship("User")


class ArcadeWallet(Base):
    """Arcade-only coin wallet + shop inventory (2026-07-07).

    Coins are minted ONLY by the validated daily run (server-capped per run)
    and spent on skins / permanent powers / an extra starting life / a
    daily-run retry. They can never convert to credit, stars or traffic —
    the arcade economy stays sealed off from money.
    """
    __tablename__ = "arcade_wallets"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True)
    coins = Column(Integer, default=0, nullable=False)
    equipped_skin = Column(String(24), default="default", nullable=False)
    owned_skins = Column(Text, default="[]", nullable=False)    # JSON list of skin keys
    owned_powers = Column(Text, default="[]", nullable=False)   # JSON list of power keys
    extra_lives = Column(Integer, default=0, nullable=False)    # permanent +N starting lives
    coins_earned_total = Column(Integer, default=0, nullable=False)  # lifetime, for analytics
    # admin-set per-user difficulty (2026-07-08): easy | normal | hard |
    # boss_rush (QA mode — bosses from level 2). Rides the loadout to the game.
    difficulty = Column(String(16), default="normal", server_default="normal", nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    user = relationship("User")


class UserAnalytics(Base):
    """Daily user behavior analytics."""
    __tablename__ = "user_analytics"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    date = Column(DateTime, nullable=False)
    login_count = Column(Integer, default=0, nullable=False)
    referral_clicks = Column(Integer, default=0, nullable=False)
    reward_redemptions = Column(Integer, default=0, nullable=False)
    subscription_usage_bytes = Column(BigInteger, default=0, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    user = relationship("User", back_populates="analytics")


class RewardEffectiveness(Base):
    """Track effectiveness of different reward types."""
    __tablename__ = "reward_effectiveness"

    id = Column(Integer, primary_key=True)
    reward_type = Column(String(50), nullable=False)
    total_given = Column(Integer, default=0, nullable=False)
    total_redeemed = Column(Integer, default=0, nullable=False)
    conversion_rate = Column(Float, default=0.0, nullable=False)
    date = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class Leaderboard(Base):
    """Leaderboard entries for different categories."""
    __tablename__ = "leaderboards"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    category = Column(String(50), nullable=False)
    score = Column(Integer, default=0, nullable=False)
    rank = Column(Integer, nullable=True)
    period = Column(String(20), nullable=False)
    date = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    user = relationship("User")


class SeasonalEvent(Base):
    """Seasonal events and special promotions."""
    __tablename__ = "seasonal_events"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=False)
    event_type = Column(String(50), nullable=False)
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=False)
    reward_multiplier = Column(Float, default=1.0, nullable=False)
    active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class UserGift(Base):
    """DORMANT — the peer-to-peer gift feature was deleted (2026-07-21).

    All handlers/crud around this model are gone; the model and its empty
    user_gifts table are kept so no migration/data loss happens. Drop both
    in a future DB cleanup.
    """
    __tablename__ = "user_gifts"

    id = Column(Integer, primary_key=True)
    sender_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    receiver_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    gift_type = Column(String(50), nullable=False)
    gift_value = Column(Integer, nullable=False)
    plan_name = Column(String(100), nullable=True)
    message = Column(Text, nullable=True)
    payment_status = Column(String(20), nullable=False, default="none")
    payment_receipt_message_id = Column(BigInteger, nullable=True)
    accepted = Column(Boolean, default=False, nullable=False)
    accepted_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    sender = relationship("User", foreign_keys=[sender_id])
    receiver = relationship("User", foreign_keys=[receiver_id])


class StarRewardTier(Base):
    __tablename__ = "star_reward_tiers"

    id = Column(Integer, primary_key=True)
    star_threshold = Column(Integer, unique=True, nullable=False)
    title = Column(String(100), nullable=False)
    description = Column(Text, nullable=False)
    reward_type = Column(String(50), nullable=False)
    reward_value = Column(String(100), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class UserStarRewardClaim(Base):
    """Tracks when a user unlocks and claims a star reward tier."""
    __tablename__ = "user_star_reward_claims"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    tier_id = Column(Integer, ForeignKey("star_reward_tiers.id"), nullable=False)
    offered_at = Column(DateTime, default=datetime.datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    claimed_at = Column(DateTime, nullable=True)
    chosen_reward_type = Column(String(50), nullable=True)
    status = Column(String(50), default="offered", nullable=False)

    user = relationship("User")
    tier = relationship("StarRewardTier")


class UserDiscount(Base):
    __tablename__ = "user_discounts"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    percent = Column(Integer, nullable=False)
    expiration = Column(DateTime, nullable=False)
    used = Column(Boolean, default=False, nullable=False)
    source = Column(String(50), nullable=True)

    user = relationship("User", backref="discounts")


class StarHistory(Base):
    """Ledger tracking all star changes for audit and analytics."""
    __tablename__ = "star_history"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    delta = Column(Integer, nullable=False)
    reason = Column(String(50), nullable=False)
    source_id = Column(Integer, nullable=True)
    notes = Column(String(200), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    user = relationship("User")


class DailyStarCap(Base):
    """Tracks daily star earnings to prevent farming."""
    __tablename__ = "daily_star_caps"
    __table_args__ = (
        UniqueConstraint("user_id", "date", name="unique_user_date_cap"),
    )

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    date = Column(Date, nullable=False)
    stars_earned = Column(Integer, default=0, nullable=False)
    max_allowed = Column(Integer, default=3, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    user = relationship("User")

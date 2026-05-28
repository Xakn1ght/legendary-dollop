import datetime

import sqlalchemy
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
    create_engine,
    func,
)
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import backref, declarative_base, relationship, sessionmaker

from app.core.settings import DATABASE_URL

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    chat_id = Column(BigInteger, unique=True, nullable=False)
    username = Column(String)
    full_name = Column(String)
    # UI language preference for bot/webapp messaging (e.g., 'fa', 'en')
    language = Column(String(8), nullable=False, default='fa')
    # Per-user dashboard preferences (JSON string). Used to sync settings across devices.
    dashboard_prefs = Column(Text, nullable=False, default='{}')
    referral_code = Column(String, unique=True)
    phone_number = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    stars = Column(Integer, default=0, nullable=False)
    credit = Column(Integer, default=0, nullable=False)
    banned = Column(Boolean, default=False, nullable=False)
    is_admin = Column(Boolean, default=False, nullable=False)
    
    # Account category (e.g., normal, super, hyper)
    category = Column(String(32), nullable=False, default='normal')
    
    # Enhanced Reward System Fields
    level = Column(Integer, default=1, nullable=False)
    experience_points = Column(Integer, default=0, nullable=False)
    last_daily_login = Column(DateTime, nullable=True)
    login_streak = Column(Integer, default=0, nullable=False)
    loyalty_points = Column(Integer, default=0, nullable=False)
    custom_username = Column(String, nullable=True)  # For premium features
    
    # Star pieces system (10 pieces = 1 star)
    star_pieces = Column(Integer, default=0, nullable=False)
    arcade_stars_this_month = Column(Integer, default=0, nullable=False)
    arcade_stars_month_reset = Column(Date, nullable=True)  # Track when to reset monthly cap
    
    # Leaderboard visibility preference (opt-out)
    show_on_leaderboard = Column(Boolean, default=True, nullable=False)
    
    # VIP status
    is_vip = Column(Boolean, default=False, nullable=False)
    vip_until = Column(DateTime, nullable=True)  # None = lifetime VIP if is_vip is True
    
    subscriptions = relationship("Subscription", back_populates="user", foreign_keys="[Subscription.user_id]")
    referred_subscriptions = relationship("Subscription", back_populates="referrer", foreign_keys="[Subscription.referrer_id]")
    
    # Referrals this user has made
    referred = relationship("Referral", back_populates="referrer", foreign_keys="[Referral.referrer_id]")
    # The referral that brought this user here
    referral_entry = relationship("Referral", back_populates="referee", foreign_keys="[Referral.referee_id]", uselist=False)
    
    # New relationships for enhanced system
    achievements = relationship("UserAchievement", back_populates="user")
    challenge_progress = relationship("UserChallenge", back_populates="user")
    reward_history = relationship("RewardHistory", back_populates="user")
    analytics = relationship("UserAnalytics", back_populates="user")

    # Support tickets relationships
    tickets = relationship("Ticket", back_populates="user", foreign_keys="[Ticket.user_id]")
    assigned_tickets = relationship("Ticket", back_populates="assigned_admin", foreign_keys="[Ticket.assigned_admin_id]")

class Subscription(Base):
    __tablename__ = 'subscriptions'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    referrer_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    marzban_username = Column(String, unique=True)
    # Optional: share-link token for fast, read-only status via /sub/{token}/info
    sub_token = Column(String, nullable=True)
    plan_name = Column(String)  # Add plan_name
    price = Column(Integer)  # Add price
    status = Column(String, default="pending") # pending, active, expired, cancelled
    receipt_message_id = Column(Integer)
    # Telegram admin-side message IDs (for cleanup/edits after web approval)
    admin_receipt_forward_message_id = Column(BigInteger, nullable=True)
    admin_request_message_id = Column(BigInteger, nullable=True)
    # Web receipt image URL (saved under /app/webapp/admin/uploads so admin panel can preview)
    receipt_image_url = Column(String, nullable=True)
    # Idempotency flag: ensures we don't send the subscription link multiple times
    user_link_sent = Column(Boolean, default=False, nullable=False)
    low_data_notified = Column(Boolean, default=False, nullable=False)
    imminent_expiry_notified = Column(Boolean, default=False, nullable=False)
    expired_notified = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    # Renewal fields
    renewal_paid = Column(Boolean, default=False, nullable=False)
    renewal_template = Column(String, nullable=True)
    renewal_price = Column(Integer, nullable=True)
    renewal_requested_at = Column(DateTime, nullable=True)
    renewal_applied = Column(Boolean, default=False, nullable=False)
    # Persist credit and discounts used during purchase flow for rollback on denial
    credit_used = Column(Integer, default=0)
    applied_discount_ids = Column(String, nullable=True)  # comma-separated IDs
    # Carry-over traffic from early recharge (>7-day rule)
    carry_over_bytes = Column(BigInteger, nullable=True)
    carry_over_reset_at = Column(DateTime, nullable=True)
    
    user = relationship("User", back_populates="subscriptions", foreign_keys=[user_id])
    referrer = relationship("User", back_populates="referred_subscriptions", foreign_keys=[referrer_id])

class Receipt(Base):
    __tablename__ = 'receipts'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    subscription_id = Column(Integer, ForeignKey('subscriptions.id'), nullable=True)
    plan_name = Column(String)
    price = Column(Integer)
    paid_amount = Column(Integer)
    status = Column(String, default='pending')  # pending, completed, failed
    created_at = Column(DateTime, default=func.now())
    
    user = relationship("User")
    subscription = relationship("Subscription")


class VipOrder(Base):
    """VIP membership purchase orders."""
    __tablename__ = 'vip_orders'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    plan_id = Column(String, nullable=False)  # e.g., "1_month", "3_months", "lifetime"
    days = Column(Integer, nullable=True)  # None for lifetime
    price = Column(Integer, nullable=False)
    receipt_image_url = Column(String, nullable=True)
    status = Column(String, default='draft')  # draft, pending, approved, denied
    created_at = Column(DateTime, default=func.now())
    approved_at = Column(DateTime, nullable=True)
    approved_by = Column(Integer, nullable=True)  # Admin user ID who approved
    
    user = relationship("User")


class Referral(Base):
    __tablename__ = 'referrals'
    id = Column(Integer, primary_key=True)
    referrer_id = Column(Integer, ForeignKey('users.id')) # The one who refers
    referee_id = Column(Integer, ForeignKey('users.id'), unique=True) # The one who is referred
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    referrer = relationship("User", back_populates="referred", foreign_keys=[referrer_id])
    referee = relationship("User", back_populates="referral_entry", foreign_keys=[referee_id])

class RenewalHistory(Base):
    __tablename__ = 'renewal_history'
    __table_args__ = (
        UniqueConstraint('subscription_id', 'renewed_at', name='uq_subscription_renewed_at'),
    )
    id = Column(Integer, primary_key=True)
    subscription_id = Column(Integer, ForeignKey('subscriptions.id'), nullable=False)
    renewed_at = Column(DateTime, default=datetime.datetime.utcnow)
    result = Column(String, nullable=False)  # e.g., 'success', 'failure'
    details = Column(String, nullable=True)  # Optional: error message or info
    
    subscription = relationship("Subscription")

class ReferralReward(Base):
    __tablename__ = 'referral_rewards'
    id = Column(Integer, primary_key=True)
    subscription_id = Column(Integer, ForeignKey('subscriptions.id'), nullable=False)
    referrer_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    reward_value = Column(Integer)  # Add reward_value
    traffic_bytes = Column(BigInteger)
    extra_days = Column(Integer)
    credit_amount = Column(Integer)
    spent = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Relationships
    subscription = relationship("Subscription")
    referrer = relationship("User")

# ---------------------------
#  Reward configuration
# ---------------------------


class RewardConfig(Base):
    """Singleton table (id=1) storing adjustable reward percentages.

    Percentages are stored as *whole number* percentages (e.g. 5 means 5 %).
    """
    __tablename__ = 'reward_config'

    id = Column(Integer, primary_key=True, default=1)
    traffic_percent = Column(Float, default=5.0, nullable=False)  # % of total GB
    days_percent = Column(Float, default=1.0, nullable=False)     # % of total days
    credit_percent = Column(Float, default=10.0, nullable=False)  # % of total price (wallet)

# ----------------------------------
#  ChargeRequest – manual top-up flow
# ----------------------------------

class ChargeRequest(Base):
    """A pending top-up submitted by user and awaiting admin approval."""
    __tablename__ = 'charge_requests'

    id = Column(Integer, primary_key=True)
    subscription_id = Column(Integer, ForeignKey('subscriptions.id'), nullable=False)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)

    traffic_bytes = Column(BigInteger, nullable=False)  # amount of traffic to add (bytes)
    extra_days = Column(Integer, nullable=True)        # optional extra days to extend
    price = Column(Integer, nullable=False)            # price the user pays (Toman)
    
    charge_type = Column(String(32), nullable=True, default='normal')  # 'normal', 'normal_5gb_limit', 'booking'

    receipt_message_id = Column(Integer, nullable=True)
    receipt_image_url = Column(String, nullable=True)  # Web receipt image URL
    status = Column(String, default='pending')         # pending | approved | denied
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    subscription = relationship("Subscription")
    user = relationship("User")


class PendingDeletionRequest(Base):
    """A pending deletion request submitted by user and awaiting admin approval."""
    __tablename__ = 'pending_deletion_requests'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    subscription_id = Column(Integer, ForeignKey('subscriptions.id'), nullable=False)
    subscription_username = Column(String, nullable=False)
    reason = Column(String, nullable=True)
    status = Column(String, default='pending')  # pending | approved | denied
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    processed_at = Column(DateTime, nullable=True)
    processed_by = Column(Integer, ForeignKey('users.id'), nullable=True)  # admin who processed it

    user = relationship("User", foreign_keys=[user_id])
    subscription = relationship("Subscription")
    admin = relationship("User", foreign_keys=[processed_by])

# ----------------------------------
#  Enhanced Reward System Tables
# ----------------------------------

class Achievement(Base):
    """Predefined achievements that users can earn."""
    __tablename__ = 'achievements'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=False)
    icon = Column(String(50), nullable=True)  # Emoji or icon identifier
    requirement_type = Column(String(50), nullable=False)  # 'referrals', 'usage', 'purchases', 'streak'
    requirement_value = Column(Integer, nullable=False)
    reward_type = Column(String(50), nullable=False)  # 'xp', 'loyalty_points', 'credit', 'traffic', 'bundle'
    reward_value = Column(String(100), nullable=False)  # Integer for simple rewards, String for bundles (e.g., "credit:500|xp:100")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class UserAchievement(Base):
    """Achievements earned by users."""
    __tablename__ = 'user_achievements'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    achievement_id = Column(Integer, ForeignKey('achievements.id'), nullable=False)
    earned_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    user = relationship("User", back_populates="achievements")
    achievement = relationship("Achievement")

class Challenge(Base):
    """Daily, weekly, and seasonal challenges."""
    __tablename__ = 'challenges'
    
    id = Column(Integer, primary_key=True)
    title = Column(String(100), nullable=False)
    description = Column(Text, nullable=False)
    challenge_type = Column(String(50), nullable=False)  # 'daily', 'weekly', 'seasonal'
    requirement_type = Column(String(50), nullable=False)  # 'referrals', 'usage', 'logins', 'purchases'
    requirement_value = Column(Integer, nullable=False)
    reward_type = Column(String(50), nullable=False)  # 'xp', 'loyalty_points', 'credit', 'traffic'
    reward_value = Column(Integer, nullable=False)
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=False)
    active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class UserChallenge(Base):
    """User progress on challenges."""
    __tablename__ = 'user_challenges'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    challenge_id = Column(Integer, ForeignKey('challenges.id'), nullable=False)
    progress = Column(Integer, default=0, nullable=False)
    completed = Column(Boolean, default=False, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    user = relationship("User", back_populates="challenge_progress")
    challenge = relationship("Challenge")

class RewardHistory(Base):
    """Detailed tracking of all rewards earned and spent."""
    __tablename__ = 'reward_history'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    reward_type = Column(String(50), nullable=False)  # 'xp', 'loyalty_points', 'credit', 'traffic', 'days'
    reward_value = Column(Integer, nullable=False)
    source = Column(String(50), nullable=False)  # 'referral', 'achievement', 'challenge', 'streak', 'level_up'
    source_id = Column(Integer, nullable=True)  # ID of the source (referral_id, achievement_id, etc.)
    notes = Column(String, nullable=True)
    earned_at = Column(DateTime, default=datetime.datetime.utcnow)
    spent_at = Column(DateTime, nullable=True)
    
    user = relationship("User", back_populates="reward_history")

class DailyGamePlay(Base):
    """Tracks one play session per user per day for the daily arcade game.

    We store best score for the day and the rewards granted to make leaderboards
    and anti‑abuse audits straightforward.
    """
    __tablename__ = 'daily_game_plays'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    play_date = Column(Date, nullable=False)  # UTC date boundary
    best_score = Column(Integer, default=0, nullable=False)
    duration_seconds = Column(Integer, default=0, nullable=False)
    display_name = Column(String(40), default="", nullable=False)  # For leaderboard
    rewarded = Column(Boolean, default=False, nullable=False)
    streak_on_play = Column(Integer, default=0, nullable=False)
    reward_credit = Column(Integer, default=0, nullable=False)
    reward_stars = Column(Integer, default=0, nullable=False)
    reward_xp = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    user = relationship("User")

    __table_args__ = (
        UniqueConstraint('user_id', 'play_date', name='uq_daily_play_user_date'),
    )

class UserAnalytics(Base):
    """Daily user behavior analytics."""
    __tablename__ = 'user_analytics'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    date = Column(DateTime, nullable=False)
    login_count = Column(Integer, default=0, nullable=False)
    referral_clicks = Column(Integer, default=0, nullable=False)
    reward_redemptions = Column(Integer, default=0, nullable=False)
    subscription_usage_bytes = Column(BigInteger, default=0, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    user = relationship("User", back_populates="analytics")

class RewardEffectiveness(Base):
    """Track effectiveness of different reward types."""
    __tablename__ = 'reward_effectiveness'
    
    id = Column(Integer, primary_key=True)
    reward_type = Column(String(50), nullable=False)
    total_given = Column(Integer, default=0, nullable=False)
    total_redeemed = Column(Integer, default=0, nullable=False)
    conversion_rate = Column(Float, default=0.0, nullable=False)
    date = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class Leaderboard(Base):
    """Leaderboard entries for different categories."""
    __tablename__ = 'leaderboards'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    category = Column(String(50), nullable=False)  # 'referrals', 'usage', 'activity', 'spending'
    score = Column(Integer, default=0, nullable=False)
    rank = Column(Integer, nullable=True)
    period = Column(String(20), nullable=False)  # 'daily', 'weekly', 'monthly', 'all_time'
    date = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    user = relationship("User")

class SeasonalEvent(Base):
    """Seasonal events and special promotions."""
    __tablename__ = 'seasonal_events'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=False)
    event_type = Column(String(50), nullable=False)  # 'holiday', 'promotion', 'special'
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=False)
    reward_multiplier = Column(Float, default=1.0, nullable=False)
    active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class UserGift(Base):
    """Peer-to-peer gift system."""
    __tablename__ = 'user_gifts'
    
    id = Column(Integer, primary_key=True)
    sender_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    receiver_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    gift_type = Column(String(50), nullable=False)  # 'credit', 'loyalty_points', 'traffic'
    gift_value = Column(Integer, nullable=False)
    # Optional: plan name for subscription gifts
    plan_name = Column(String(100), nullable=True)
    message = Column(Text, nullable=True)
    payment_status = Column(String(20), nullable=False, default='none')  # none | pending | approved | denied
    payment_receipt_message_id = Column(BigInteger, nullable=True)
    accepted = Column(Boolean, default=False, nullable=False)
    accepted_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    sender = relationship("User", foreign_keys=[sender_id])
    receiver = relationship("User", foreign_keys=[receiver_id])

class StarRewardTier(Base):
    __tablename__ = 'star_reward_tiers'
    
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
    __tablename__ = 'user_star_reward_claims'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    tier_id = Column(Integer, ForeignKey('star_reward_tiers.id'), nullable=False)
    
    offered_at = Column(DateTime, default=datetime.datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    claimed_at = Column(DateTime, nullable=True)
    
    # Which reward did they choose if multiple options were available?
    chosen_reward_type = Column(String(50), nullable=True)
    
    status = Column(String(50), default='offered', nullable=False)  # offered, claimed, expired

    user = relationship("User")
    tier = relationship("StarRewardTier")

class UserDiscount(Base):
    __tablename__ = 'user_discounts'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    percent = Column(Integer, nullable=False)
    expiration = Column(DateTime, nullable=False)
    used = Column(Boolean, default=False, nullable=False)
    source = Column(String(50), nullable=True)  # e.g., '3 stars', '5 stars'
    
    user = relationship("User", backref="discounts")


# ----------------------------------
#  Star History Ledger
# ----------------------------------

class StarHistory(Base):
    """Ledger tracking all star changes for audit and analytics."""
    __tablename__ = 'star_history'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    delta = Column(Integer, nullable=False)  # +1 for earned, -1 for spent, etc.
    reason = Column(String(50), nullable=False)  # 'referral', 'achievement', 'tier_claim', 'admin_grant', etc.
    source_id = Column(Integer, nullable=True)  # Optional reference to source (reward_id, achievement_id, etc.)
    notes = Column(String(200), nullable=True)  # Additional context
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    user = relationship("User")


# ----------------------------------
#  Daily Star Caps (Anti-Farming)
# ----------------------------------

class DailyStarCap(Base):
    """Tracks daily star earnings to prevent farming."""
    __tablename__ = 'daily_star_caps'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    date = Column(Date, nullable=False)  # Date for the limit (YYYY-MM-DD)
    stars_earned = Column(Integer, default=0, nullable=False)
    max_allowed = Column(Integer, default=3, nullable=False)  # Daily limit
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    user = relationship("User")

    # Ensure one record per user per date
    __table_args__ = (
        UniqueConstraint('user_id', 'date', name='unique_user_date_cap'),
    )


# ----------------------------------
#  Support / Ticketing System Tables
# ----------------------------------

class Ticket(Base):
    __tablename__ = 'tickets'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    # Optional link to an affected subscription (selected by user during support intake)
    subscription_id = Column(Integer, ForeignKey('subscriptions.id'), nullable=True)
    
    # User-specific ticket number (for privacy - shows #1, #2, #3 for each user)
    user_ticket_number = Column(Integer, nullable=False, default=1)

    # Categories: connection | money | other
    category = Column(String(32), nullable=False)
    # Short user-provided subject/title
    subject = Column(String(80), nullable=False, default="")

    # Status: pending (in queue, unassigned) | open (assigned/in progress) | closed | private_chat
    status = Column(String(16), nullable=False, default='pending')

    # Priority: low | normal | high
    priority = Column(String(16), nullable=False, default='normal')

    # Optional metadata for connection issues
    os = Column(String(32), nullable=True)
    isp = Column(String(64), nullable=True)

    # Admin assignment
    assigned_admin_id = Column(Integer, ForeignKey('users.id'), nullable=True)

    # Control whether user can add more messages post-submission (upon admin request)
    allow_more_from_user = Column(Boolean, nullable=False, default=False)
    notify_on_reply = Column(Boolean, nullable=False, default=True)
    
    # User deletion (soft delete - hides from user but admin can still see)
    hidden_from_user = Column(Boolean, nullable=False, default=False)
    hidden_at = Column(DateTime, nullable=True)
    
    # Private chat fields
    is_private_chat = Column(Boolean, default=False, nullable=False)
    chat_invitation_sent = Column(Boolean, default=False, nullable=False)
    chat_invitation_accepted = Column(Boolean, default=False, nullable=False)
    chat_invitation_expired = Column(Boolean, default=False, nullable=False)
    chat_invitation_sent_at = Column(DateTime, nullable=True)
    chat_started_at = Column(DateTime, nullable=True)
    chat_ended_at = Column(DateTime, nullable=True)

    last_message_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=True)
    last_reminder_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow)
    closed_at = Column(DateTime, nullable=True)
    resolved = Column(Boolean, default=False, nullable=False)
    feedback_score = Column(Integer, nullable=True)  # +1 / -1
    feedback_text = Column(Text, nullable=True)

    user = relationship("User", back_populates="tickets", foreign_keys=[user_id])
    assigned_admin = relationship("User", back_populates="assigned_tickets", foreign_keys=[assigned_admin_id])
    messages = relationship("TicketMessage", back_populates="ticket", cascade="all, delete-orphan")
    affected_subscription = relationship("Subscription")


class TicketMessage(Base):
    __tablename__ = 'ticket_messages'

    id = Column(Integer, primary_key=True)
    ticket_id = Column(Integer, ForeignKey('tickets.id'), nullable=False)

    # Sender: user | admin | system
    sender = Column(String(16), nullable=False)

    # Content type: text | photo | voice | document
    content_type = Column(String(16), nullable=False, default='text')

    text = Column(Text, nullable=True)

    # Telegram fields
    telegram_message_id = Column(BigInteger, nullable=True)
    file_id = Column(String, nullable=True)
    
    # For reply functionality
    reply_to_message_id = Column(BigInteger, nullable=True)  # Telegram message ID being replied to
    replied_to = Column(Integer, ForeignKey('ticket_messages.id'), nullable=True)  # Our DB message ID being replied to
    
    # Support for different file types
    file_unique_id = Column(String, nullable=True)
    file_name = Column(String, nullable=True)  # For documents
    file_size = Column(Integer, nullable=True)
    file_mime_type = Column(String, nullable=True)
    voice_duration = Column(Integer, nullable=True)  # For voice messages
    
    # Read tracking
    read_by_admin = Column(Boolean, default=False)
    # Whether the ticket owner (user) has read this message (used for unread badges in dashboard support UI)
    read_by_user = Column(Boolean, default=True)

    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    ticket = relationship("Ticket", back_populates="messages")
    replies = relationship("TicketMessage", backref=backref("replied_message", remote_side=[id]))


class Notification(Base):
    """
    Notification system for webapp and bot notifications.
    Supports ticket-related and general admin announcements.
    """
    __tablename__ = 'notifications'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    
    # Notification types: ticket_closed, ticket_status_changed, ticket_new_message, general
    type = Column(String(32), nullable=False)
    
    # Title and body of notification
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    
    # Optional link to related entity
    ticket_id = Column(Integer, ForeignKey('tickets.id'), nullable=True)
    
    # Read status
    read = Column(Boolean, nullable=False, default=False)
    read_at = Column(DateTime, nullable=True)
    
    # Delivery channels (admin can choose where to send)
    sent_to_webapp = Column(Boolean, nullable=False, default=True)
    sent_to_bot = Column(Boolean, nullable=False, default=False)
    
    # For bot notifications, track if sent successfully
    bot_message_sent = Column(Boolean, nullable=False, default=False)
    bot_message_id = Column(BigInteger, nullable=True)
    
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    user = relationship("User")
    ticket = relationship("Ticket")


# Configure engine with connection pooling
# SQLite benefits from these settings too (connection reuse, timeout handling)
engine = create_async_engine(
    DATABASE_URL,
    pool_size=20,             # Number of connections to keep open (scaled for 100+ users)
    max_overflow=30,          # Extra connections when needed
    pool_timeout=30,          # Wait time for connection (seconds)
    pool_recycle=1800,        # Recycle connections after 30 min (better for busy systems)
    pool_pre_ping=True,       # Verify connection before using
    echo=False,               # Set True to see SQL queries in logs (debugging)
    future=True,              # Use SQLAlchemy 2.0 style
)

# Setting expire_on_commit=False prevents attributes of instances from being expired after
# each commit. This avoids implicit lazy-loading (and therefore database I/O) when simple
# attribute access happens after a commit inside the same async event, which otherwise can
# raise `MissingGreenlet` in async SQLAlchemy.

AsyncSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
    bind=engine,
    class_=AsyncSession,
)

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

        # Perform lightweight migration for existing databases (SQLite) to add missing columns
        def _migrate(connection):
            # Detect database type for proper SQL syntax
            db_type = connection.dialect.name
            datetime_type = "DATETIME" if db_type == "sqlite" else "TIMESTAMP"
            
            inspector = sqlalchemy.inspect(connection)
            if 'users' in inspector.get_table_names():
                existing_cols = {col['name'] for col in inspector.get_columns('users')}
                if 'language' not in existing_cols:
                    connection.exec_driver_sql("ALTER TABLE users ADD COLUMN language VARCHAR(8) NOT NULL DEFAULT 'fa';")
                if 'dashboard_prefs' not in existing_cols:
                    connection.exec_driver_sql("ALTER TABLE users ADD COLUMN dashboard_prefs TEXT NOT NULL DEFAULT '{}';")
                if 'credit' not in existing_cols:
                    connection.exec_driver_sql("ALTER TABLE users ADD COLUMN credit INTEGER NOT NULL DEFAULT 0;")
                if 'stars' not in existing_cols:
                    connection.exec_driver_sql("ALTER TABLE users ADD COLUMN stars INTEGER NOT NULL DEFAULT 0;")
                # Enhanced Reward System migrations
                if 'level' not in existing_cols:
                    connection.exec_driver_sql("ALTER TABLE users ADD COLUMN level INTEGER NOT NULL DEFAULT 1;")
                if 'experience_points' not in existing_cols:
                    connection.exec_driver_sql("ALTER TABLE users ADD COLUMN experience_points INTEGER NOT NULL DEFAULT 0;")
                if 'last_daily_login' not in existing_cols:
                    connection.exec_driver_sql(f"ALTER TABLE users ADD COLUMN last_daily_login {datetime_type};")
                if 'login_streak' not in existing_cols:
                    connection.exec_driver_sql("ALTER TABLE users ADD COLUMN login_streak INTEGER NOT NULL DEFAULT 0;")
                if 'loyalty_points' not in existing_cols:
                    connection.exec_driver_sql("ALTER TABLE users ADD COLUMN loyalty_points INTEGER NOT NULL DEFAULT 0;")
                if 'custom_username' not in existing_cols:
                    connection.exec_driver_sql("ALTER TABLE users ADD COLUMN custom_username VARCHAR;")
                if 'star_pieces' not in existing_cols:
                    connection.exec_driver_sql("ALTER TABLE users ADD COLUMN star_pieces INTEGER NOT NULL DEFAULT 0;")
                if 'arcade_stars_this_month' not in existing_cols:
                    connection.exec_driver_sql("ALTER TABLE users ADD COLUMN arcade_stars_this_month INTEGER NOT NULL DEFAULT 0;")
                if 'arcade_stars_month_reset' not in existing_cols:
                    connection.exec_driver_sql("ALTER TABLE users ADD COLUMN arcade_stars_month_reset DATE;")
                if 'banned' not in existing_cols:
                    connection.exec_driver_sql("ALTER TABLE users ADD COLUMN banned BOOLEAN NOT NULL DEFAULT FALSE;")
                if 'username' not in existing_cols:
                    connection.exec_driver_sql("ALTER TABLE users ADD COLUMN username VARCHAR;")
                if 'phone_number' not in existing_cols:
                    connection.exec_driver_sql("ALTER TABLE users ADD COLUMN phone_number VARCHAR;")
                if 'discount_percent' not in existing_cols:
                    connection.exec_driver_sql("ALTER TABLE users ADD COLUMN discount_percent INTEGER NOT NULL DEFAULT 0;")
                if 'discount_expiration' not in existing_cols:
                    connection.exec_driver_sql(f"ALTER TABLE users ADD COLUMN discount_expiration {datetime_type};")
                if 'category' not in existing_cols:
                    connection.exec_driver_sql("ALTER TABLE users ADD COLUMN category VARCHAR(32) NOT NULL DEFAULT 'normal';")
                if 'is_vip' not in existing_cols:
                    connection.exec_driver_sql("ALTER TABLE users ADD COLUMN is_vip BOOLEAN NOT NULL DEFAULT FALSE;")
                if 'vip_until' not in existing_cols:
                    connection.exec_driver_sql(f"ALTER TABLE users ADD COLUMN vip_until {datetime_type};")
            # Ensure user_gifts has plan_name for subscription gifting
            if 'user_gifts' in inspector.get_table_names():
                gift_cols = {col['name'] for col in inspector.get_columns('user_gifts')}
                if 'plan_name' not in gift_cols:
                    connection.exec_driver_sql("ALTER TABLE user_gifts ADD COLUMN plan_name VARCHAR(100);")
                if 'payment_status' not in gift_cols:
                    connection.exec_driver_sql("ALTER TABLE user_gifts ADD COLUMN payment_status VARCHAR(20) NOT NULL DEFAULT 'none';")
                if 'payment_receipt_message_id' not in gift_cols:
                    connection.exec_driver_sql("ALTER TABLE user_gifts ADD COLUMN payment_receipt_message_id BIGINT;")
            # Ensure support tables exist (create_all handles new tables). Add lightweight column migrations here if needed in future.
            if 'subscriptions' in inspector.get_table_names():
                sub_cols = {col['name'] for col in inspector.get_columns('subscriptions')}
                if 'sub_token' not in sub_cols:
                    connection.exec_driver_sql("ALTER TABLE subscriptions ADD COLUMN sub_token VARCHAR;")
                if 'carry_over_bytes' not in sub_cols:
                    connection.exec_driver_sql("ALTER TABLE subscriptions ADD COLUMN carry_over_bytes BIGINT;")
                if 'carry_over_reset_at' not in sub_cols:
                    connection.exec_driver_sql(f"ALTER TABLE subscriptions ADD COLUMN carry_over_reset_at {datetime_type};")
                if 'price' not in sub_cols:
                    connection.exec_driver_sql("ALTER TABLE subscriptions ADD COLUMN price INTEGER;")
                if 'plan_name' not in sub_cols:
                    connection.exec_driver_sql("ALTER TABLE subscriptions ADD COLUMN plan_name VARCHAR;")
                if 'credit_used' not in sub_cols:
                    connection.exec_driver_sql("ALTER TABLE subscriptions ADD COLUMN credit_used INTEGER NOT NULL DEFAULT 0;")
                if 'applied_discount_ids' not in sub_cols:
                    connection.exec_driver_sql("ALTER TABLE subscriptions ADD COLUMN applied_discount_ids VARCHAR;")
                if 'admin_receipt_forward_message_id' not in sub_cols:
                    connection.exec_driver_sql("ALTER TABLE subscriptions ADD COLUMN admin_receipt_forward_message_id BIGINT;")
                if 'admin_request_message_id' not in sub_cols:
                    connection.exec_driver_sql("ALTER TABLE subscriptions ADD COLUMN admin_request_message_id BIGINT;")
                if 'receipt_image_url' not in sub_cols:
                    connection.exec_driver_sql("ALTER TABLE subscriptions ADD COLUMN receipt_image_url VARCHAR;")
                if 'user_link_sent' not in sub_cols:
                    connection.exec_driver_sql("ALTER TABLE subscriptions ADD COLUMN user_link_sent BOOLEAN NOT NULL DEFAULT FALSE;")
                if 'referral_rewards' in inspector.get_table_names():
                    reward_cols = {col['name'] for col in inspector.get_columns('referral_rewards')}
                    if 'reward_value' not in reward_cols:
                        connection.exec_driver_sql("ALTER TABLE referral_rewards ADD COLUMN reward_value INTEGER;")
            if 'tickets' in inspector.get_table_names():
                ticket_cols = {col['name'] for col in inspector.get_columns('tickets')}
                if 'subscription_id' not in ticket_cols:
                    connection.exec_driver_sql("ALTER TABLE tickets ADD COLUMN subscription_id INTEGER;")
                if 'last_reminder_at' not in ticket_cols:
                    connection.exec_driver_sql(f"ALTER TABLE tickets ADD COLUMN last_reminder_at {datetime_type};")
                if 'notify_on_reply' not in ticket_cols:
                    connection.exec_driver_sql("ALTER TABLE tickets ADD COLUMN notify_on_reply BOOLEAN NOT NULL DEFAULT TRUE;")
                if 'closed_at' not in ticket_cols:
                    connection.exec_driver_sql(f"ALTER TABLE tickets ADD COLUMN closed_at {datetime_type};")
                if 'resolved' not in ticket_cols:
                    connection.exec_driver_sql("ALTER TABLE tickets ADD COLUMN resolved BOOLEAN NOT NULL DEFAULT FALSE;")
                if 'feedback_score' not in ticket_cols:
                    connection.exec_driver_sql("ALTER TABLE tickets ADD COLUMN feedback_score INTEGER;")
                if 'feedback_text' not in ticket_cols:
                    connection.exec_driver_sql("ALTER TABLE tickets ADD COLUMN feedback_text TEXT;")
                if 'hidden_from_user' not in ticket_cols:
                    connection.exec_driver_sql("ALTER TABLE tickets ADD COLUMN hidden_from_user BOOLEAN NOT NULL DEFAULT FALSE;")
                if 'hidden_at' not in ticket_cols:
                    connection.exec_driver_sql(f"ALTER TABLE tickets ADD COLUMN hidden_at {datetime_type};")
            if 'ticket_messages' in inspector.get_table_names():
                msg_cols = {col['name'] for col in inspector.get_columns('ticket_messages')}
                if 'read_by_user' not in msg_cols:
                    # Default TRUE so existing rows don't suddenly appear unread.
                    connection.exec_driver_sql("ALTER TABLE ticket_messages ADD COLUMN read_by_user BOOLEAN NOT NULL DEFAULT TRUE;")
            # star_history table is new, handled by create_all
            # Ensure star_reward_tiers has latest columns
            if 'star_reward_tiers' in inspector.get_table_names():
                tier_cols = {col['name'] for col in inspector.get_columns('star_reward_tiers')}
                if 'reward_type' not in tier_cols:
                    connection.exec_driver_sql("ALTER TABLE star_reward_tiers ADD COLUMN reward_type VARCHAR(50) NOT NULL DEFAULT 'credit';")
                if 'reward_value' not in tier_cols:
                    connection.exec_driver_sql("ALTER TABLE star_reward_tiers ADD COLUMN reward_value VARCHAR(100) NOT NULL DEFAULT '0';")
            
            # Ensure charge_requests has receipt_image_url and charge_type
            if 'charge_requests' in inspector.get_table_names():
                charge_cols = {col['name'] for col in inspector.get_columns('charge_requests')}
                if 'receipt_image_url' not in charge_cols:
                    connection.exec_driver_sql("ALTER TABLE charge_requests ADD COLUMN receipt_image_url VARCHAR;")
                if 'charge_type' not in charge_cols:
                    connection.exec_driver_sql("ALTER TABLE charge_requests ADD COLUMN charge_type VARCHAR(32) DEFAULT 'normal';")

        await conn.run_sync(_migrate)

        # ------------------
        # Shared subscriptions
        # ------------------
        def _ensure_link_table(connection):
            # Detect database type for proper SQL syntax
            db_type = connection.dialect.name
            datetime_type = "DATETIME" if db_type == "sqlite" else "TIMESTAMP"
            
            inspector = sqlalchemy.inspect(connection)
            if 'subscription_links' not in inspector.get_table_names():
                connection.exec_driver_sql(
                    f"""
                    CREATE TABLE subscription_links (
                        user_id INTEGER NOT NULL,
                        subscription_id INTEGER NOT NULL,
                        added_at {datetime_type},
                        PRIMARY KEY (user_id, subscription_id),
                        FOREIGN KEY(user_id) REFERENCES users (id),
                        FOREIGN KEY(subscription_id) REFERENCES subscriptions (id)
                    );
                    """
                )

        await conn.run_sync(_ensure_link_table)

        # Ensure we have exactly one RewardConfig row (id=1)
        from sqlalchemy import select
        result = await conn.execute(select(RewardConfig).limit(1))
        cfg = result.scalar_one_or_none()
        if cfg is None:
            await conn.execute(
                sqlalchemy.insert(RewardConfig).values(id=1, traffic_percent=10.0, days_percent=10.0, credit_percent=10.0)
            )
        
        # Initialize default achievements
        await _initialize_default_achievements(conn)
        
        # Initialize default challenges
        await _initialize_default_challenges(conn)
        
        # Create critical database indexes for optimal performance
        await _create_database_indexes(conn)

async def _initialize_default_achievements(conn):
    """Initialize default achievements if they don't exist."""
    from sqlalchemy import select
    
    # Check if achievements already exist
    result = await conn.execute(select(Achievement).limit(1))
    if result.scalar_one_or_none():
        return  # Achievements already exist
    
    # Default achievements - NEW BALANCED SYSTEM
    default_achievements = [
        {
            "name": "بلند پرواز",
            "description": "اولین بازی خود را انجام دهید",
            "icon": "🚀",
            "requirement_type": "game_plays",
            "requirement_value": 1,
            "reward_type": "bundle",
            "reward_value": "credit:500|xp:100"
        },
        {
            "name": "اولین تماس",
            "description": "اولین دوست خود را معرفی کنید",
            "icon": "🎯",
            "requirement_type": "referrals",
            "requirement_value": 1,
            "reward_type": "bundle",
            "reward_value": "credit:2000|xp:200"
        },
        {
            "name": "رهبر گروه",
            "description": "۵ نفر را معرفی کنید",
            "icon": "👥",
            "requirement_type": "referrals",
            "requirement_value": 5,
            "reward_type": "bundle",
            "reward_value": "credit:10000|xp:500|stars:1"
        },
        {
            "name": "امپراتوری کهکشانی",
            "description": "۲۰ معرفی فعال (خرید پلن ۲۰GB+)",
            "icon": "🌌",
            "requirement_type": "active_referrals",
            "requirement_value": 20,
            "reward_type": "bundle",
            "reward_value": "credit:50000|xp:1200|stars:3"
        },
        {
            "name": "مسافر داده",
            "description": "۵۰ گیگابایت داده مصرف کنید",
            "icon": "📡",
            "requirement_type": "usage",
            "requirement_value": 50,
            "reward_type": "bundle",
            "reward_value": "credit:5000|xp:300"
        },
        {
            "name": "فرمانده داده",
            "description": "۲۰۰ گیگابایت داده مصرف کنید",
            "icon": "📊",
            "requirement_type": "usage",
            "requirement_value": 200,
            "reward_type": "bundle",
            "reward_value": "credit:20000|xp:800"
        },
        {
            "name": "جنگجوی نوار",
            "description": "۷ روز متوالی بازی کنید",
            "icon": "🔥",
            "requirement_type": "play_streak",
            "requirement_value": 7,
            "reward_type": "bundle",
            "reward_value": "credit:5000|xp:400"
        },
        {
            "name": "مسافر زمان",
            "description": "۳۰ روز متوالی بازی کنید",
            "icon": "⏰",
            "requirement_type": "play_streak",
            "requirement_value": 30,
            "reward_type": "bundle",
            "reward_value": "credit:25000|xp:1200|stars:2"
        },
        {
            "name": "خریدار بزرگ",
            "description": "۵ اشتراک خریداری کنید",
            "icon": "💎",
            "requirement_type": "purchases",
            "requirement_value": 5,
            "reward_type": "bundle",
            "reward_value": "xp:800|stars:1|cashback:5"
        },
        {
            "name": "حامی",
            "description": "۱۰ اشتراک خریداری کنید",
            "icon": "👑",
            "requirement_type": "purchases",
            "requirement_value": 10,
            "reward_type": "bundle",
            "reward_value": "xp:2000|stars:2|cashback:10"
        },
        {
            "name": "امتیاز کامل",
            "description": "در بازی به ۱۵۰۰۰+ امتیاز برسید",
            "icon": "🏆",
            "requirement_type": "high_score",
            "requirement_value": 15000,
            "reward_type": "bundle",
            "reward_value": "credit:5000|xp:500|stars:1"
        }
    ]
    
    for achievement_data in default_achievements:
        await conn.execute(
            sqlalchemy.insert(Achievement).values(**achievement_data)
        )

async def _initialize_default_challenges(conn):
    """Initialize default challenges if they don't exist."""
    from datetime import datetime, timedelta

    from sqlalchemy import select
    
    # Check if challenges already exist
    result = await conn.execute(select(Challenge).limit(1))
    if result.scalar_one_or_none():
        return  # Challenges already exist
    
    now = datetime.utcnow()
    week_start = now - timedelta(days=now.weekday())
    week_end = week_start + timedelta(days=7)
    
    # Default challenges
    default_challenges = [
        {
            "title": "ورود روزانه",
            "description": "امروز وارد شوید",
            "challenge_type": "daily",
            "requirement_type": "logins",
            "requirement_value": 1,
            "reward_type": "xp",
            "reward_value": 10,
            "start_date": now.replace(hour=0, minute=0, second=0, microsecond=0),
            "end_date": now.replace(hour=23, minute=59, second=59, microsecond=999999)
        },
        {
            "title": "معرفی هفتگی",
            "description": "۳ نفر را این هفته معرفی کنید",
            "challenge_type": "weekly",
            "requirement_type": "referrals",
            "requirement_value": 3,
            "reward_type": "loyalty_points",
            "reward_value": 100,
            "start_date": week_start,
            "end_date": week_end
        },
        {
            "title": "بازی روزانه",
            "description": "یک بار بازی روزانه انجام دهید",
            "challenge_type": "daily",
            "requirement_type": "daily_game",
            "requirement_value": 1,
            "reward_type": "xp",
            "reward_value": 20,
            "start_date": now.replace(hour=0, minute=0, second=0, microsecond=0),
            "end_date": now.replace(hour=23, minute=59, second=59, microsecond=999999)
        },
        {
            "title": "امتیاز بازی هفتگی",
            "description": "این هفته به امتیاز مشخصی در بازی برسید",
            "challenge_type": "weekly",
            "requirement_type": "weekly_game_score",
            "requirement_value": 3000,
            "reward_type": "loyalty_points",
            "reward_value": 150,
            "start_date": week_start,
            "end_date": week_end
        }
    ]
    
    for challenge_data in default_challenges:
        await conn.execute(
            sqlalchemy.insert(Challenge).values(**challenge_data)
        )

async def _create_database_indexes(conn):
    """Create critical database indexes for optimal performance"""
    from app.database.indexes import (
        create_analytics_indexes,
        create_notification_indexes,
        create_reward_indexes,
        create_subscription_indexes,
        create_ticket_indexes,
        create_user_indexes,
    )
    
    try:
        # Create indexes for each table category
        await create_user_indexes(conn)
        await create_subscription_indexes(conn)
        await create_reward_indexes(conn)
        await create_analytics_indexes(conn)
        await create_ticket_indexes(conn)
        await create_notification_indexes(conn)
        
        # Additional critical indexes
        await conn.execute(sqlalchemy.text("CREATE INDEX IF NOT EXISTS idx_referrals_referrer ON referrals (referrer_id)"))
        await conn.execute(sqlalchemy.text("CREATE INDEX IF NOT EXISTS idx_referrals_created_at ON referrals (created_at)"))
        await conn.execute(sqlalchemy.text("CREATE INDEX IF NOT EXISTS idx_charge_requests_status ON charge_requests (status)"))
        await conn.execute(sqlalchemy.text("CREATE INDEX IF NOT EXISTS idx_charge_requests_user ON charge_requests (user_id)"))
        await conn.execute(sqlalchemy.text("CREATE INDEX IF NOT EXISTS idx_renewal_history_subscription ON renewal_history (subscription_id)"))
        await conn.execute(sqlalchemy.text("CREATE INDEX IF NOT EXISTS idx_achievements_requirement_type ON achievements (requirement_type)"))
        await conn.execute(sqlalchemy.text("CREATE INDEX IF NOT EXISTS idx_challenges_type_active ON challenges (challenge_type, active)"))
        await conn.execute(sqlalchemy.text("CREATE INDEX IF NOT EXISTS idx_user_gifts_sender ON user_gifts (sender_id)"))
        await conn.execute(sqlalchemy.text("CREATE INDEX IF NOT EXISTS idx_user_gifts_receiver ON user_gifts (receiver_id)"))
        
        print("✅ Database indexes created successfully")
        
    except Exception as e:
        print(f"⚠️ Warning: Some indexes may already exist or failed to create: {e}")
        # Continue execution even if some indexes fail 

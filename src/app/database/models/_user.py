import datetime

from sqlalchemy import BigInteger, Boolean, Column, Date, DateTime, Integer, String, Text
from sqlalchemy.orm import relationship

from ._base import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    chat_id = Column(BigInteger, unique=True, nullable=False)
    username = Column(String)
    full_name = Column(String)
    language = Column(String(8), nullable=False, default="fa")
    dashboard_prefs = Column(Text, nullable=False, default="{}")
    referral_code = Column(String, unique=True)
    phone_number = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    stars = Column(Integer, default=0, nullable=False)
    credit = Column(Integer, default=0, nullable=False)
    # Saved cash-out destination (digits only, 16 chars) — masked everywhere in
    # the user UI; admins see it in full on the payout request they approve.
    payout_card = Column(String(20), nullable=True)
    banned = Column(Boolean, default=False, nullable=False)
    is_admin = Column(Boolean, default=False, nullable=False)
    category = Column(String(32), nullable=False, default="normal")

    # Reward system
    level = Column(Integer, default=1, nullable=False)
    experience_points = Column(Integer, default=0, nullable=False)
    last_daily_login = Column(DateTime, nullable=True)
    login_streak = Column(Integer, default=0, nullable=False)
    loyalty_points = Column(Integer, default=0, nullable=False)
    custom_username = Column(String, nullable=True)
    star_pieces = Column(Integer, default=0, nullable=False)
    arcade_stars_this_month = Column(Integer, default=0, nullable=False)
    arcade_stars_month_reset = Column(Date, nullable=True)
    show_on_leaderboard = Column(Boolean, default=True, nullable=False)

    # VIP
    is_vip = Column(Boolean, default=False, nullable=False)
    vip_until = Column(DateTime, nullable=True)

    subscriptions = relationship("Subscription", back_populates="user", foreign_keys="[Subscription.user_id]")
    referred_subscriptions = relationship("Subscription", back_populates="referrer", foreign_keys="[Subscription.referrer_id]")
    referred = relationship("Referral", back_populates="referrer", foreign_keys="[Referral.referrer_id]")
    referral_entry = relationship("Referral", back_populates="referee", foreign_keys="[Referral.referee_id]", uselist=False)
    achievements = relationship("UserAchievement", back_populates="user")
    challenge_progress = relationship("UserChallenge", back_populates="user")
    reward_history = relationship("RewardHistory", back_populates="user")
    analytics = relationship("UserAnalytics", back_populates="user")
    tickets = relationship("Ticket", back_populates="user", foreign_keys="[Ticket.user_id]")
    assigned_tickets = relationship("Ticket", back_populates="assigned_admin", foreign_keys="[Ticket.assigned_admin_id]")

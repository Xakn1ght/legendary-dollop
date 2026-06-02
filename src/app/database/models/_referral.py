import datetime

from sqlalchemy import BigInteger, Boolean, Column, DateTime, ForeignKey, Integer
from sqlalchemy.orm import relationship

from ._base import Base


class Referral(Base):
    __tablename__ = "referrals"

    id = Column(Integer, primary_key=True)
    referrer_id = Column(Integer, ForeignKey("users.id"))
    referee_id = Column(Integer, ForeignKey("users.id"), unique=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    referrer = relationship("User", back_populates="referred", foreign_keys=[referrer_id])
    referee = relationship("User", back_populates="referral_entry", foreign_keys=[referee_id])


class ReferralReward(Base):
    __tablename__ = "referral_rewards"

    id = Column(Integer, primary_key=True)
    subscription_id = Column(Integer, ForeignKey("subscriptions.id"), nullable=False)
    referrer_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    reward_value = Column(Integer)
    traffic_bytes = Column(BigInteger)
    extra_days = Column(Integer)
    credit_amount = Column(Integer)
    stars = Column(Integer)  # season-star option (1, or 2 with reserved auto-renew)
    spent = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    subscription = relationship("Subscription")
    referrer = relationship("User")

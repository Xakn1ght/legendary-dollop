"""Star Season + coupon models (Phase B of the reward system rework).

See docs/design-specs/specs/2026-05-31-final-reward-system-map.md §3 and
docs/design-specs/specs/asstroo_star_season_coupon_spec_v2.md.

- StarSeason       : a 90-day season window; season stars reset between seasons.
- UserStarProgress : a user's season-star count within one season (referral-only).
- StarMilestoneClaim: dedup record so each milestone unlocks once per season.
- RewardCoupon     : the unlocked, VPN-only, expiring reward saved in the wallet.
"""

import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from ._base import Base


class StarSeason(Base):
    __tablename__ = "star_seasons"

    id = Column(Integer, primary_key=True)
    name = Column(String(100))
    starts_at = Column(DateTime, nullable=False)
    ends_at = Column(DateTime, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class UserStarProgress(Base):
    __tablename__ = "user_star_progress"
    __table_args__ = (UniqueConstraint("user_id", "season_id", name="uq_user_season_progress"),)

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    season_id = Column(Integer, ForeignKey("star_seasons.id"), nullable=False)
    season_stars = Column(Integer, default=0, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    user = relationship("User")
    season = relationship("StarSeason")


class StarMilestoneClaim(Base):
    __tablename__ = "star_milestone_claims"
    __table_args__ = (
        UniqueConstraint("user_id", "season_id", "milestone_stars", name="uq_milestone_claim"),
    )

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    season_id = Column(Integer, ForeignKey("star_seasons.id"), nullable=False)
    milestone_stars = Column(Integer, nullable=False)
    claim_key = Column(String(160), unique=True, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    user = relationship("User")


class RewardCoupon(Base):
    __tablename__ = "reward_coupons"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    source = Column(String(40), default="star_season")  # star_season | marketing | ...
    season_id = Column(Integer, nullable=True)
    milestone_stars = Column(Integer, nullable=True)
    # discount_percent | free_gb | free_plan | free_autorenew | vip_pack | legend_pack
    coupon_type = Column(String(40), nullable=False)
    # JSON string with the specifics (discount_percent, gb, plan_gb, duration_days, items…)
    payload = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    used_at = Column(DateTime, nullable=True)
    status = Column(String(16), default="active", nullable=False)  # active | used | expired

    user = relationship("User")

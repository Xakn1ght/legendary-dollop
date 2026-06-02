import datetime

from sqlalchemy import BigInteger, Boolean, Column, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy import func
from sqlalchemy.orm import relationship

from ._base import Base


class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    referrer_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    marzban_username = Column(String, unique=True)
    sub_token = Column(String, nullable=True)
    plan_name = Column(String)
    price = Column(Integer)
    status = Column(String, default="pending")
    receipt_message_id = Column(Integer)
    admin_receipt_forward_message_id = Column(BigInteger, nullable=True)
    admin_request_message_id = Column(BigInteger, nullable=True)
    receipt_image_url = Column(String, nullable=True)
    user_link_sent = Column(Boolean, default=False, nullable=False)
    low_data_notified = Column(Boolean, default=False, nullable=False)
    imminent_expiry_notified = Column(Boolean, default=False, nullable=False)
    expired_notified = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    renewal_paid = Column(Boolean, default=False, nullable=False)
    renewal_template = Column(String, nullable=True)
    renewal_price = Column(Integer, nullable=True)
    renewal_requested_at = Column(DateTime, nullable=True)
    renewal_applied = Column(Boolean, default=False, nullable=False)
    credit_used = Column(Integer, default=0)
    applied_discount_ids = Column(String, nullable=True)
    applied_coupon_id = Column(Integer, nullable=True)
    carry_over_bytes = Column(BigInteger, nullable=True)
    carry_over_reset_at = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="subscriptions", foreign_keys=[user_id])
    referrer = relationship("User", back_populates="referred_subscriptions", foreign_keys=[referrer_id])


class Receipt(Base):
    __tablename__ = "receipts"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    subscription_id = Column(Integer, ForeignKey("subscriptions.id"), nullable=True)
    plan_name = Column(String)
    price = Column(Integer)
    paid_amount = Column(Integer)
    status = Column(String, default="pending")
    created_at = Column(DateTime, default=func.now())

    user = relationship("User")
    subscription = relationship("Subscription")


class VipOrder(Base):
    """VIP membership purchase orders."""
    __tablename__ = "vip_orders"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    plan_id = Column(String, nullable=False)
    days = Column(Integer, nullable=True)
    price = Column(Integer, nullable=False)
    receipt_image_url = Column(String, nullable=True)
    status = Column(String, default="draft")
    created_at = Column(DateTime, default=func.now())
    approved_at = Column(DateTime, nullable=True)
    approved_by = Column(Integer, nullable=True)

    user = relationship("User")


class RenewalHistory(Base):
    __tablename__ = "renewal_history"
    __table_args__ = (
        UniqueConstraint("subscription_id", "renewed_at", name="uq_subscription_renewed_at"),
    )

    id = Column(Integer, primary_key=True)
    subscription_id = Column(Integer, ForeignKey("subscriptions.id"), nullable=False)
    renewed_at = Column(DateTime, default=datetime.datetime.utcnow)
    result = Column(String, nullable=False)
    details = Column(String, nullable=True)

    subscription = relationship("Subscription")


class ChargeRequest(Base):
    """A pending top-up submitted by user and awaiting admin approval."""
    __tablename__ = "charge_requests"

    id = Column(Integer, primary_key=True)
    subscription_id = Column(Integer, ForeignKey("subscriptions.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    traffic_bytes = Column(BigInteger, nullable=False)
    extra_days = Column(Integer, nullable=True)
    price = Column(Integer, nullable=False)
    charge_type = Column(String(32), nullable=True, default="normal")
    receipt_message_id = Column(Integer, nullable=True)
    receipt_image_url = Column(String, nullable=True)
    status = Column(String, default="pending")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    subscription = relationship("Subscription")
    user = relationship("User")


class PendingDeletionRequest(Base):
    """A pending deletion request submitted by user and awaiting admin approval."""
    __tablename__ = "pending_deletion_requests"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    subscription_id = Column(Integer, ForeignKey("subscriptions.id"), nullable=False)
    subscription_username = Column(String, nullable=False)
    reason = Column(String, nullable=True)
    status = Column(String, default="pending")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    processed_at = Column(DateTime, nullable=True)
    processed_by = Column(Integer, ForeignKey("users.id"), nullable=True)

    user = relationship("User", foreign_keys=[user_id])
    subscription = relationship("Subscription")
    admin = relationship("User", foreign_keys=[processed_by])

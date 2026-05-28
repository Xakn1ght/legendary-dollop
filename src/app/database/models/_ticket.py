import datetime

from sqlalchemy import BigInteger, Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import backref, relationship

from ._base import Base


class Ticket(Base):
    __tablename__ = "tickets"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    subscription_id = Column(Integer, ForeignKey("subscriptions.id"), nullable=True)
    user_ticket_number = Column(Integer, nullable=False, default=1)
    category = Column(String(32), nullable=False)
    subject = Column(String(80), nullable=False, default="")
    status = Column(String(16), nullable=False, default="pending")
    priority = Column(String(16), nullable=False, default="normal")
    os = Column(String(32), nullable=True)
    isp = Column(String(64), nullable=True)
    assigned_admin_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    allow_more_from_user = Column(Boolean, nullable=False, default=False)
    notify_on_reply = Column(Boolean, nullable=False, default=True)
    hidden_from_user = Column(Boolean, nullable=False, default=False)
    hidden_at = Column(DateTime, nullable=True)
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
    feedback_score = Column(Integer, nullable=True)
    feedback_text = Column(Text, nullable=True)

    user = relationship("User", back_populates="tickets", foreign_keys=[user_id])
    assigned_admin = relationship("User", back_populates="assigned_tickets", foreign_keys=[assigned_admin_id])
    messages = relationship("TicketMessage", back_populates="ticket", cascade="all, delete-orphan")
    affected_subscription = relationship("Subscription")


class TicketMessage(Base):
    __tablename__ = "ticket_messages"

    id = Column(Integer, primary_key=True)
    ticket_id = Column(Integer, ForeignKey("tickets.id"), nullable=False)
    sender = Column(String(16), nullable=False)
    content_type = Column(String(16), nullable=False, default="text")
    text = Column(Text, nullable=True)
    telegram_message_id = Column(BigInteger, nullable=True)
    file_id = Column(String, nullable=True)
    reply_to_message_id = Column(BigInteger, nullable=True)
    replied_to = Column(Integer, ForeignKey("ticket_messages.id"), nullable=True)
    file_unique_id = Column(String, nullable=True)
    file_name = Column(String, nullable=True)
    file_size = Column(Integer, nullable=True)
    file_mime_type = Column(String, nullable=True)
    voice_duration = Column(Integer, nullable=True)
    read_by_admin = Column(Boolean, default=False)
    read_by_user = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    ticket = relationship("Ticket", back_populates="messages")
    replies = relationship("TicketMessage", backref=backref("replied_message", remote_side=[id]))


class Notification(Base):
    """Notification system for webapp and bot notifications."""
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    type = Column(String(32), nullable=False)
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    ticket_id = Column(Integer, ForeignKey("tickets.id"), nullable=True)
    read = Column(Boolean, nullable=False, default=False)
    read_at = Column(DateTime, nullable=True)
    sent_to_webapp = Column(Boolean, nullable=False, default=True)
    sent_to_bot = Column(Boolean, nullable=False, default=False)
    bot_message_sent = Column(Boolean, nullable=False, default=False)
    bot_message_id = Column(BigInteger, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    user = relationship("User")
    ticket = relationship("Ticket")

import datetime

from sqlalchemy import Column, DateTime, Integer, String, Text

from ._base import Base


class AdminAuditLog(Base):
    """Immutable trail of every admin action that moves money or changes state.

    Written fire-and-forget by ``app.services.audit.record_audit`` — a failed
    audit write must never break the action itself.
    """

    __tablename__ = "admin_audit_logs"

    id = Column(Integer, primary_key=True)
    # who: admin chat_id + friendly name from the session (denormalised on
    # purpose — the trail must survive admin account changes)
    admin_chat_id = Column(String(32), nullable=True)
    admin_name = Column(String(120), nullable=True)
    ip = Column(String(64), nullable=True)
    # what: dotted action key, e.g. receipt.approve / charge.deny / user.ban
    action = Column(String(64), nullable=False, index=True)
    target_type = Column(String(32), nullable=True)  # subscription|charge|vip|user|ticket|...
    target_id = Column(String(64), nullable=True)
    # human-readable summary + JSON detail blob
    summary = Column(String(300), nullable=True)
    detail = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, index=True)

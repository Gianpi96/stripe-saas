import enum
import json
from datetime import datetime, timezone

from sqlalchemy import (
    Column, DateTime, Enum, ForeignKey, Integer, String, Text, Index
)
from sqlalchemy.orm import relationship

from database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SubscriptionStatus(str, enum.Enum):
    active = "active"
    trialing = "trialing"
    past_due = "past_due"
    canceled = "canceled"
    unpaid = "unpaid"
    incomplete = "incomplete"


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True)
    email = Column(String, unique=True, nullable=False, index=True)
    stripe_customer_id = Column(String, unique=True, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)

    subscription = relationship("Subscription", back_populates="user", uselist=False)


class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    stripe_subscription_id = Column(String, unique=True, nullable=False)
    stripe_customer_id = Column(String, nullable=False)
    plan = Column(String, nullable=False)  # "basic" or "pro"
    status = Column(Enum(SubscriptionStatus), nullable=False)
    trial_end = Column(DateTime(timezone=True), nullable=True)
    current_period_end = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    user = relationship("User", back_populates="subscription")
    status_logs = relationship("SubscriptionStatusLog", back_populates="subscription")

    __table_args__ = (
        Index("ix_subscriptions_stripe_subscription_id", "stripe_subscription_id"),
        Index("ix_subscriptions_user_id", "user_id"),
    )


class SubscriptionStatusLog(Base):
    """Immutable log of every subscription state transition."""
    __tablename__ = "subscription_status_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    subscription_id = Column(Integer, ForeignKey("subscriptions.id"), nullable=False)
    old_status = Column(String, nullable=True)
    new_status = Column(String, nullable=False)
    reason = Column(String, nullable=True)
    changed_at = Column(DateTime(timezone=True), default=utcnow)

    subscription = relationship("Subscription", back_populates="status_logs")


class WebhookEvent(Base):
    """Idempotency table — one row per Stripe event ID."""
    __tablename__ = "webhook_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_id = Column(String, unique=True, nullable=False)
    event_type = Column(String, nullable=False)
    status = Column(String, nullable=False, default="processed")  # processed | failed | skipped
    payload = Column(Text, nullable=True)  # raw JSON for audit trail
    processed_at = Column(DateTime(timezone=True), default=utcnow)

    __table_args__ = (
        Index("ix_webhook_events_event_id", "event_id"),
    )

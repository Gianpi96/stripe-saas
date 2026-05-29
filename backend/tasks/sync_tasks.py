"""
Celery tasks:
- process_webhook_event: handles individual Stripe events (called from webhook endpoint)
- sync_all_subscriptions: daily cron that reconciles DB with Stripe API
- send_trial_expiry_reminders: daily cron, fires 3-day-before-trial-end emails
"""
import json
import logging
from datetime import datetime, timedelta, timezone

import stripe

from config import settings
from database import SessionLocal
from models import Subscription, SubscriptionStatus, SubscriptionStatusLog, User, WebhookEvent
from tasks.celery_app import celery_app

stripe.api_key = settings.STRIPE_SECRET_KEY
logger = logging.getLogger(__name__)

PRICE_TO_PLAN = {
    settings.STRIPE_BASIC_PRICE_ID: "basic",
    settings.STRIPE_PRO_PRICE_ID: "pro",
}


def _to_dt(ts: int | None) -> datetime | None:
    return datetime.fromtimestamp(ts, tz=timezone.utc) if ts else None


def _stripe_status(raw: str) -> SubscriptionStatus:
    try:
        return SubscriptionStatus(raw)
    except ValueError:
        return SubscriptionStatus.incomplete


def _log_change(db, sub: Subscription, old: str | None, new: str, reason: str):
    db.add(SubscriptionStatusLog(
        subscription_id=sub.id,
        old_status=old,
        new_status=new,
        reason=reason,
    ))
    logger.info(
        "status_changed",
        extra={"sub_id": sub.stripe_subscription_id, "old": old, "new": new, "reason": reason},
    )


def _upsert_subscription(db, stripe_sub: dict, user_id: str | None = None):
    """Create or update a Subscription row from a Stripe subscription object."""
    sub_id = stripe_sub["id"]
    customer_id = stripe_sub["customer"]
    raw_status = stripe_sub["status"]
    new_status = _stripe_status(raw_status)
    trial_end = _to_dt(stripe_sub.get("trial_end"))
    period_end = _to_dt(stripe_sub.get("current_period_end"))

    # Determine plan from first item's price
    items = stripe_sub.get("items", {}).get("data", [])
    price_id = items[0]["price"]["id"] if items else None
    plan = PRICE_TO_PLAN.get(price_id, "unknown")

    # Resolve user if not passed
    if not user_id:
        user = db.query(User).filter(User.stripe_customer_id == customer_id).first()
        user_id = user.id if user else None

    sub = db.query(Subscription).filter(Subscription.stripe_subscription_id == sub_id).first()
    if sub:
        old_status = sub.status.value if sub.status else None
        if old_status != new_status.value:
            _log_change(db, sub, old_status, new_status.value, "stripe_event")
        sub.status = new_status
        sub.plan = plan
        sub.trial_end = trial_end
        sub.current_period_end = period_end
        sub.updated_at = datetime.now(timezone.utc)
    else:
        if not user_id:
            logger.warning("upsert_subscription_no_user", extra={"customer_id": customer_id})
            return None
        sub = Subscription(
            user_id=user_id,
            stripe_subscription_id=sub_id,
            stripe_customer_id=customer_id,
            plan=plan,
            status=new_status,
            trial_end=trial_end,
            current_period_end=period_end,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(sub)
        logger.info("subscription_created", extra={"sub_id": sub_id, "user_id": user_id})

    db.commit()
    return sub


# ---------------------------------------------------------------------------
# process_webhook_event — dispatched by the webhook endpoint
# ---------------------------------------------------------------------------
@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def process_webhook_event(self, event_id: str, event_type: str, data_json: str):
    db = SessionLocal()
    try:
        data = json.loads(data_json)
        # Guard: in some Stripe SDK versions the StripeObject is serialised via
        # __str__ (its repr) instead of as a dict, producing a double-encoded
        # JSON string.  Parse once more to recover the actual dict.
        if isinstance(data, str):
            logger.warning(
                "data_json_double_encoded",
                extra={"event_id": event_id, "preview": data[:120]},
            )
            data = json.loads(data)

        record = db.query(WebhookEvent).filter(WebhookEvent.event_id == event_id).first()

        if event_type == "checkout.session.completed":
            _handle_checkout_completed(db, data)

        elif event_type in ("customer.subscription.updated", "customer.subscription.created"):
            _handle_subscription_updated(db, data)

        elif event_type == "customer.subscription.deleted":
            _handle_subscription_deleted(db, data)

        elif event_type == "invoice.payment_failed":
            _handle_payment_failed(db, data)

        elif event_type == "invoice.payment_succeeded":
            _handle_payment_succeeded(db, data)

        if record:
            record.status = "processed"
            db.commit()

        logger.info("webhook_processed", extra={"event_id": event_id, "event_type": event_type})

    except Exception as exc:
        db.rollback()
        logger.exception("webhook_processing_error", extra={"event_id": event_id})
        if record := db.query(WebhookEvent).filter(WebhookEvent.event_id == event_id).first():
            record.status = "failed"
            db.commit()
        raise self.retry(exc=exc)
    finally:
        db.close()


def _handle_checkout_completed(db, data: dict):
    sub_id = data.get("subscription")
    user_id = data.get("metadata", {}).get("user_id")
    if not sub_id:
        return
    stripe_sub = stripe.Subscription.retrieve(sub_id)
    _upsert_subscription(db, dict(stripe_sub), user_id=user_id)


def _handle_subscription_updated(db, data: dict):
    _upsert_subscription(db, data)


def _handle_subscription_deleted(db, data: dict):
    sub_id = data.get("id")
    sub = db.query(Subscription).filter(Subscription.stripe_subscription_id == sub_id).first()
    if sub:
        old = sub.status.value
        sub.status = SubscriptionStatus.canceled
        sub.updated_at = datetime.now(timezone.utc)
        _log_change(db, sub, old, "canceled", "subscription_deleted")
        db.commit()


def _handle_payment_failed(db, data: dict):
    customer_id = data.get("customer")
    user = db.query(User).filter(User.stripe_customer_id == customer_id).first()
    if user and user.subscription:
        old = user.subscription.status.value
        user.subscription.status = SubscriptionStatus.past_due
        user.subscription.updated_at = datetime.now(timezone.utc)
        _log_change(db, user.subscription, old, "past_due", "payment_failed")
        db.commit()
        # Alert
        from tasks.email_tasks import alert_payment_failed
        alert_payment_failed.delay(user.email, data.get("amount_due", 0))


def _handle_payment_succeeded(db, data: dict):
    customer_id = data.get("customer")
    user = db.query(User).filter(User.stripe_customer_id == customer_id).first()
    if user:
        from tasks.email_tasks import send_payment_confirmed_email
        amount = data.get("amount_paid", 0)
        send_payment_confirmed_email.delay(
            user.email, amount, data.get("id", ""), data.get("hosted_invoice_url", "")
        )


# ---------------------------------------------------------------------------
# sync_all_subscriptions — daily cron
# ---------------------------------------------------------------------------
@celery_app.task
def sync_all_subscriptions():
    """Pull every active subscription from Stripe and reconcile the DB."""
    db = SessionLocal()
    synced = 0
    try:
        for stripe_sub in stripe.Subscription.list(limit=100, status="all").auto_paging_iter():
            _upsert_subscription(db, dict(stripe_sub))
            synced += 1
        logger.info("sync_complete", extra={"synced": synced})
    finally:
        db.close()


# ---------------------------------------------------------------------------
# send_trial_expiry_reminders — daily cron
# ---------------------------------------------------------------------------
@celery_app.task
def send_trial_expiry_reminders():
    """Email users whose trial ends in exactly 3 days."""
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        window_start = now + timedelta(days=2, hours=23)
        window_end = now + timedelta(days=3, hours=1)

        subs = (
            db.query(Subscription)
            .filter(
                Subscription.status == SubscriptionStatus.trialing,
                Subscription.trial_end >= window_start,
                Subscription.trial_end <= window_end,
            )
            .all()
        )

        from tasks.email_tasks import send_trial_expiring_email
        for sub in subs:
            if sub.user:
                send_trial_expiring_email.delay(
                    sub.user.email,
                    sub.trial_end.isoformat() if sub.trial_end else "",
                    sub.plan,
                )
        logger.info("trial_reminders_sent", extra={"count": len(subs)})
    finally:
        db.close()

import json
import logging
from datetime import datetime, timezone

import stripe
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from config import settings
from database import get_db
from models import Subscription, SubscriptionStatus, SubscriptionStatusLog, User, WebhookEvent

stripe.api_key = settings.STRIPE_SECRET_KEY

router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])
logger = logging.getLogger(__name__)

ACTIVE_STATUSES = {SubscriptionStatus.active, SubscriptionStatus.trialing}


def _to_datetime(ts: int | None) -> datetime | None:
    if ts is None:
        return None
    return datetime.fromtimestamp(ts, tz=timezone.utc)


def _stripe_status(raw: str) -> SubscriptionStatus:
    try:
        return SubscriptionStatus(raw)
    except ValueError:
        return SubscriptionStatus.incomplete


def _log_status_change(db: Session, sub: Subscription, old: str | None, new: str, reason: str):
    entry = SubscriptionStatusLog(
        subscription_id=sub.id,
        old_status=old,
        new_status=new,
        reason=reason,
    )
    db.add(entry)
    logger.info(
        "subscription_status_changed",
        extra={"subscription_id": sub.stripe_subscription_id, "old": old, "new": new, "reason": reason},
    )


# ---------------------------------------------------------------------------
# POST /api/webhooks/stripe
# ---------------------------------------------------------------------------
@router.post("/stripe")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")

    try:
        event = stripe.Webhook.construct_event(payload, sig, settings.STRIPE_WEBHOOK_SECRET)
    except stripe.SignatureVerificationError:
        logger.warning("webhook_invalid_signature")
        raise HTTPException(status_code=400, detail="Invalid signature")

    event_id: str = event["id"]
    event_type: str = event["type"]

    # Idempotency — skip already-processed events
    existing = db.query(WebhookEvent).filter(WebhookEvent.event_id == event_id).first()
    if existing:
        logger.info("webhook_already_processed", extra={"event_id": event_id})
        return {"status": "skipped"}

    # Record the raw event before processing
    record = WebhookEvent(
        event_id=event_id,
        event_type=event_type,
        payload=json.dumps(event.data.object, default=str),
        status="processing",
    )
    db.add(record)
    db.commit()

    logger.info("webhook_received", extra={"event_id": event_id, "event_type": event_type})

    # Dispatch to Celery — respond in < 5 s regardless of processing time
    from tasks.email_tasks import (
        send_payment_confirmed_email,
        send_trial_expiring_email,
        alert_payment_failed,
    )
    from tasks.sync_tasks import process_webhook_event

    process_webhook_event.delay(event_id, event_type, json.dumps(event.data.object, default=str))

    record.status = "queued"
    db.commit()

    return {"status": "queued", "event_id": event_id}

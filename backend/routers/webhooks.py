import json
import logging
from datetime import datetime, timezone

import stripe
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from config import settings
from database import get_db
from models import Subscription, SubscriptionStatus, SubscriptionStatusLog, User, WebhookEvent

stripe.api_key = settings.STRIPE_SECRET_KEY

router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])
logger = logging.getLogger(__name__)

ACTIVE_STATUSES = {SubscriptionStatus.active, SubscriptionStatus.trialing}


def _stripe_obj_to_dict(val) -> dict:
    """Convert a Stripe SDK StripeObject to a plain Python dict.

    In Stripe Python SDK v15 the StripeObject stores data in an internal
    _data dict and dict(stripe_obj) fails with KeyError on integer keys.
    str(stripe_obj) always returns a valid JSON representation, so we
    parse that.  For plain dicts (e.g. test mocks) we fall back to
    iterating .items() directly.
    """
    try:
        result = json.loads(str(val))
        if isinstance(result, dict):
            return result
    except Exception:
        pass
    # Fallback for plain dicts / StripeEventMock used in tests
    if isinstance(val, dict):
        return {k: _stripe_obj_to_dict(v) if isinstance(v, dict) else v
                for k, v in val.items()}
    return {}


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

    # Idempotency — skip events that were already queued or processed.
    # An event whose previous delivery failed to reach the queue is "failed":
    # Stripe's retry must be processed, not skipped, or the event would be lost.
    existing = db.query(WebhookEvent).filter(WebhookEvent.event_id == event_id).first()
    if existing and existing.status != "failed":
        logger.info("webhook_already_processed", extra={"event_id": event_id})
        return {"status": "skipped"}

    # Safely serialise the Stripe event data to a plain JSON string.
    # StripeObject (Stripe SDK v15) must be recursively converted to native
    # Python types before json.dumps — otherwise default=str turns the whole
    # object into its repr string and the Celery task receives a str, not a dict.
    obj_dict = _stripe_obj_to_dict(event["data"]["object"])
    data_json = json.dumps(obj_dict, default=str)

    # Record the raw event before processing (or reuse the failed record)
    if existing:
        record = existing
        record.payload = data_json
        record.status = "processing"
    else:
        record = WebhookEvent(
            event_id=event_id,
            event_type=event_type,
            payload=data_json,
            status="processing",
        )
        db.add(record)
    try:
        db.commit()
    except IntegrityError:
        # Two deliveries of the same event raced: the other one won (unique event_id).
        db.rollback()
        logger.info("webhook_already_processed", extra={"event_id": event_id})
        return {"status": "skipped"}

    logger.info("webhook_received", extra={"event_id": event_id, "event_type": event_type})

    # Dispatch to Celery — respond in < 5 s regardless of processing time
    from tasks.sync_tasks import process_webhook_event

    try:
        process_webhook_event.delay(event_id, event_type, data_json)
    except Exception:
        # Queue unavailable (e.g. Redis down). Mark the event as failed and ask
        # Stripe to retry later; the retry will be processed, not skipped.
        logger.exception("webhook_enqueue_failed", extra={"event_id": event_id})
        record.status = "failed"
        db.commit()
        raise HTTPException(status_code=503, detail="Queue unavailable, retry later")

    record.status = "queued"
    db.commit()

    return {"status": "queued", "event_id": event_id}

import logging
import time
from datetime import datetime, timezone

import stripe
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from config import settings
from database import get_db
from models import Subscription, SubscriptionStatus, User

stripe.api_key = settings.STRIPE_SECRET_KEY

router = APIRouter(prefix="/api/payments", tags=["payments"])
logger = logging.getLogger(__name__)

PRICE_TO_PLAN = {
    settings.STRIPE_BASIC_PRICE_ID: "basic",
    settings.STRIPE_PRO_PRICE_ID: "pro",
}


# ---------------------------------------------------------------------------
# Dependency: resolve current user from X-User-Id header (replace with JWT)
# ---------------------------------------------------------------------------
def get_current_user(x_user_id: str = Header(...), db: Session = Depends(get_db)) -> User:
    user = db.query(User).filter(User.id == x_user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


# ---------------------------------------------------------------------------
# POST /api/payments/create-checkout-session
# ---------------------------------------------------------------------------
class CheckoutRequest(BaseModel):
    price_id: str
    user_id: str
    user_email: str


@router.post("/create-checkout-session")
async def create_checkout_session(body: CheckoutRequest, db: Session = Depends(get_db)):
    if body.price_id not in PRICE_TO_PLAN:
        raise HTTPException(status_code=400, detail="Invalid price_id")

    # Upsert user
    user = db.query(User).filter(User.id == body.user_id).first()
    if not user:
        user = User(
            id=body.user_id,
            email=body.user_email,
            created_at=datetime.now(timezone.utc),
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        # Fire welcome email (imported here to avoid circular import)
        from tasks.email_tasks import send_welcome_email
        send_welcome_email.delay(body.user_email, body.user_id)

    # Create or reuse Stripe customer
    if not user.stripe_customer_id:
        customer = stripe.Customer.create(
            email=user.email,
            metadata={"user_id": user.id},
        )
        user.stripe_customer_id = customer.id
        db.commit()

    # Checkout expires in 30 minutes
    expires_at = int(time.time()) + 1800

    session = stripe.checkout.Session.create(
        customer=user.stripe_customer_id,
        payment_method_types=["card"],
        line_items=[{"price": body.price_id, "quantity": 1}],
        mode="subscription",
        subscription_data={
            "trial_period_days": 14,
            "metadata": {"user_id": user.id, "plan": PRICE_TO_PLAN[body.price_id]},
        },
        metadata={"user_id": user.id},
        success_url=f"{settings.APP_URL}/success?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{settings.APP_URL}/cancel",
        expires_at=expires_at,
    )

    logger.info("checkout_session_created", extra={"session_id": session.id, "user_id": user.id})
    return {"url": session.url, "session_id": session.id}


# ---------------------------------------------------------------------------
# POST /api/payments/portal-session
# ---------------------------------------------------------------------------
@router.post("/portal-session")
async def create_portal_session(user: User = Depends(get_current_user)):
    if not user.stripe_customer_id:
        raise HTTPException(status_code=400, detail="No Stripe customer associated with this user")

    portal = stripe.billing_portal.Session.create(
        customer=user.stripe_customer_id,
        return_url=f"{settings.APP_URL}/billing/return",
    )

    logger.info(
        "customer_portal_accessed",
        extra={"user_id": user.id, "customer_id": user.stripe_customer_id},
    )
    return {"url": portal.url}


# ---------------------------------------------------------------------------
# GET /api/payments/subscription-status
# ---------------------------------------------------------------------------
@router.get("/subscription-status")
async def subscription_status(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    sub = db.query(Subscription).filter(Subscription.user_id == user.id).first()
    if not sub:
        return {"has_subscription": False, "status": None, "plan": None}
    return {
        "has_subscription": True,
        "status": sub.status.value,
        "plan": sub.plan,
        "trial_end": sub.trial_end.isoformat() if sub.trial_end else None,
        "current_period_end": sub.current_period_end.isoformat() if sub.current_period_end else None,
    }

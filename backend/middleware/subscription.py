"""
FastAPI dependency that gates access to Pro features.
Raises 403 if the user has no active/trialing subscription.
"""
import logging

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models import Subscription, SubscriptionStatus, User

logger = logging.getLogger(__name__)

PRO_STATUSES = {SubscriptionStatus.active, SubscriptionStatus.trialing}
PRO_PLANS = {"pro"}


def get_current_user_id(x_user_id: str = Header(...)) -> str:
    return x_user_id


def require_active_subscription(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> Subscription:
    """Dependency: user must have active or trialing subscription (any plan)."""
    sub = _get_subscription(db, user_id)
    if not sub or sub.status not in PRO_STATUSES:
        logger.warning(
            "subscription_access_denied",
            extra={"user_id": user_id, "status": sub.status.value if sub else "none"},
        )
        raise HTTPException(
            status_code=403,
            detail={
                "code": "subscription_required",
                "message": "Abbonamento attivo richiesto per accedere a questa funzionalità.",
                "upgrade_url": "/pricing",
            },
        )
    return sub


def require_pro_subscription(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> Subscription:
    """Dependency: user must have active/trialing Pro plan specifically."""
    sub = _get_subscription(db, user_id)
    if not sub or sub.status not in PRO_STATUSES or sub.plan not in PRO_PLANS:
        logger.warning(
            "pro_access_denied",
            extra={
                "user_id": user_id,
                "status": sub.status.value if sub else "none",
                "plan": sub.plan if sub else "none",
            },
        )
        raise HTTPException(
            status_code=403,
            detail={
                "code": "pro_required",
                "message": "Piano Pro richiesto per accedere a questa funzionalità.",
                "upgrade_url": "/pricing",
            },
        )
    return sub


def _get_subscription(db: Session, user_id: str) -> Subscription | None:
    return db.query(Subscription).filter(Subscription.user_id == user_id).first()

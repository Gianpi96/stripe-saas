from celery import Celery
from celery.schedules import crontab

from config import settings

celery_app = Celery(
    "stripe_saas",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["tasks.email_tasks", "tasks.sync_tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    # Retry failed tasks up to 3 times with exponential backoff
    task_max_retries=3,
    # Beat schedule for daily sync
    beat_schedule={
        "sync-subscriptions-daily": {
            "task": "tasks.sync_tasks.sync_all_subscriptions",
            "schedule": crontab(hour=3, minute=0),  # 03:00 UTC every day
        },
        "trial-expiry-reminders-daily": {
            "task": "tasks.sync_tasks.send_trial_expiry_reminders",
            "schedule": crontab(hour=9, minute=0),  # 09:00 UTC every day
        },
    },
)

"""
Fire-and-forget Celery email tasks.
All tasks are async — they never block the HTTP response.
"""
import logging

import httpx

from config import settings
from email_service import (
    render_payment_confirmed,
    render_trial_expiring,
    render_welcome,
    send_email,
)
from tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60, ignore_result=True)
def send_welcome_email(self, user_email: str, user_id: str):
    try:
        html = render_welcome(user_email, settings.APP_URL)
        send_email(to=user_email, subject="Benvenuto in StripeSaaS!", html=html)
    except Exception as exc:
        raise self.retry(exc=exc)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60, ignore_result=True)
def send_payment_confirmed_email(
    self, user_email: str, amount_cents: int, invoice_id: str, invoice_url: str
):
    try:
        html = render_payment_confirmed(
            user_email, amount_cents, invoice_id, invoice_url, settings.APP_URL
        )
        send_email(to=user_email, subject="Pagamento confermato - StripeSaaS", html=html)
    except Exception as exc:
        raise self.retry(exc=exc)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60, ignore_result=True)
def send_trial_expiring_email(self, user_email: str, trial_end: str, plan: str):
    try:
        html = render_trial_expiring(user_email, trial_end, plan, settings.APP_URL)
        send_email(
            to=user_email,
            subject="Il tuo trial scade tra 3 giorni - Passa a Pro",
            html=html,
        )
    except Exception as exc:
        raise self.retry(exc=exc)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60, ignore_result=True)
def alert_payment_failed(self, user_email: str, amount_cents: int):
    """Alert admin via Slack and send failure email to user."""
    amount = f"{amount_cents / 100:.2f}"

    # Slack alert
    if settings.SLACK_WEBHOOK_URL:
        try:
            with httpx.Client(timeout=5) as client:
                client.post(
                    settings.SLACK_WEBHOOK_URL,
                    json={
                        "text": f":warning: *Payment failed* for `{user_email}` — amount: ${amount}"
                    },
                )
        except Exception:
            logger.exception("slack_alert_failed")

    # Email alert to admin
    if settings.ALERT_EMAIL:
        try:
            html = f"""
            <h2>Pagamento fallito</h2>
            <p>L'utente <strong>{user_email}</strong> ha avuto un pagamento fallito di <strong>${amount}</strong>.</p>
            <p>Controlla il <a href="https://dashboard.stripe.com">Stripe Dashboard</a> per i dettagli.</p>
            """
            send_email(
                to=settings.ALERT_EMAIL,
                subject=f"[ALERT] Pagamento fallito: {user_email}",
                html=html,
            )
        except Exception:
            logger.exception("admin_alert_email_failed")

    # Email to user
    try:
        html = f"""
        <h2>Problema con il tuo pagamento</h2>
        <p>Non siamo riusciti ad addebitare <strong>${amount}</strong> sul tuo metodo di pagamento.</p>
        <p>Aggiorna i tuoi dati di pagamento per mantenere l'accesso al piano Pro:</p>
        <p><a href="{settings.APP_URL}/dashboard/billing" style="background:#7c3aed;color:#fff;padding:12px 24px;text-decoration:none;border-radius:6px;">Aggiorna carta</a></p>
        """
        send_email(
            to=user_email,
            subject="Azione richiesta: problema con il pagamento",
            html=html,
        )
    except Exception as exc:
        raise self.retry(exc=exc)

"""
Resend email service with exponential backoff retry.
Never log card data or PII beyond email address.
"""
import logging
import time
from pathlib import Path
from string import Template

import resend

from config import settings

resend.api_key = settings.RESEND_API_KEY

logger = logging.getLogger(__name__)

EMAILS_ENABLED = bool(settings.RESEND_API_KEY)

TEMPLATES_DIR = Path(__file__).parent / "templates"

UNSUBSCRIBE_FOOTER = """
<p style="font-size:12px;color:#6b7280;text-align:center;margin-top:32px;">
  Non vuoi più ricevere queste email?
  <a href="{unsubscribe_url}" style="color:#6b7280;">Annulla l'iscrizione</a>
</p>
"""


def _load_template(name: str) -> Template:
    path = TEMPLATES_DIR / name
    return Template(path.read_text(encoding="utf-8"))


def send_email(
    to: str,
    subject: str,
    html: str,
    max_retries: int = 3,
) -> dict:
    """Send an email via Resend with exponential backoff on failure."""
    if not EMAILS_ENABLED:
        logger.info("email_skipped_no_api_key", extra={"to": to, "subject": subject})
        return {"id": "skipped"}

    last_exc: Exception | None = None

    for attempt in range(max_retries):
        try:
            result = resend.Emails.send({
                "from": f"{settings.EMAIL_FROM_NAME} <{settings.EMAIL_FROM}>",
                "to": [to],
                "subject": subject,
                "html": html,
            })
            # resend v2 returns an Email object; v0 returned a dict
            email_id = getattr(result, "id", None) or (result.get("id", "unknown") if isinstance(result, dict) else "unknown")
            logger.info("email_sent", extra={"email_id": email_id, "to": to, "subject": subject})
            return result
        except Exception as exc:
            last_exc = exc
            if attempt < max_retries - 1:
                wait = 2 ** attempt  # 1s, 2s, 4s
                logger.warning(
                    "email_retry",
                    extra={"attempt": attempt + 1, "wait_s": wait, "error": str(exc)},
                )
                time.sleep(wait)

    logger.error("email_failed", extra={"to": to, "subject": subject, "error": str(last_exc)})
    raise last_exc


# ---------------------------------------------------------------------------
# Rendered helpers
# ---------------------------------------------------------------------------
def render_welcome(user_email: str, app_url: str) -> str:
    tpl = _load_template("welcome.html")
    footer = UNSUBSCRIBE_FOOTER.format(unsubscribe_url=f"{app_url}/unsubscribe")
    return tpl.substitute(user_email=user_email, app_url=app_url, unsubscribe_footer=footer)


def render_payment_confirmed(
    user_email: str, amount_cents: int, invoice_id: str, invoice_url: str, app_url: str
) -> str:
    tpl = _load_template("payment_confirmed.html")
    footer = UNSUBSCRIBE_FOOTER.format(unsubscribe_url=f"{app_url}/unsubscribe")
    return tpl.substitute(
        user_email=user_email,
        amount=f"{amount_cents / 100:.2f}",
        invoice_id=invoice_id,
        invoice_url=invoice_url,
        app_url=app_url,
        unsubscribe_footer=footer,
    )


def render_trial_expiring(user_email: str, trial_end: str, plan: str, app_url: str) -> str:
    tpl = _load_template("trial_expiring.html")
    footer = UNSUBSCRIBE_FOOTER.format(unsubscribe_url=f"{app_url}/unsubscribe")
    return tpl.substitute(
        user_email=user_email,
        trial_end=trial_end,
        plan=plan.capitalize(),
        app_url=app_url,
        unsubscribe_footer=footer,
    )

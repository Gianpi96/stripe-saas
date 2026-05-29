"""
Test di sicurezza — verificano che i controlli critici siano attivi.

Copertura:
- Verifica firma webhook (HMAC)
- Accesso endpoint Pro senza subscription
- Header obbligatori
- Price ID invalido
- Idempotency webhook
- SQL injection nei parametri
- XSS nei campi email
"""
import json
import pytest
from unittest.mock import patch


class TestWebhookSecurity:
    """Sicurezza endpoint /api/webhooks/stripe"""

    def test_invalid_signature_returns_400(self, client):
        """Firma HMAC sbagliata → 400, mai processato."""
        resp = client.post(
            "/api/webhooks/stripe",
            content=b'{"id":"evt_fake"}',
            headers={
                "stripe-signature": "t=123,v1=badhash",
                "Content-Type": "application/json",
            },
        )
        assert resp.status_code == 400
        assert "Invalid signature" in resp.json()["detail"]

    def test_missing_signature_returns_400(self, client):
        """Nessun header stripe-signature → 400."""
        resp = client.post(
            "/api/webhooks/stripe",
            content=b'{"id":"evt_fake"}',
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 400

    def test_empty_payload_with_bad_sig_returns_400(self, client):
        """Payload vuoto con firma invalida → 400."""
        resp = client.post(
            "/api/webhooks/stripe",
            content=b"",
            headers={"stripe-signature": "invalid", "Content-Type": "application/json"},
        )
        assert resp.status_code == 400

    def test_valid_webhook_accepted(self, client, db):
        """Evento con firma valida (mock) → 200."""
        from tests.conftest import StripeEventMock
        fake_event = StripeEventMock({
            "id": "evt_security_test_001",
            "type": "customer.subscription.updated",
            "data": {
                "object": {
                    "id": "sub_mock",
                    "customer": "cus_mock",
                    "status": "active",
                    "items": {"data": [{"price": {"id": "price_basic_test"}}]},
                    "trial_end": None,
                    "current_period_end": 9999999999,
                }
            },
        })
        with patch("stripe.Webhook.construct_event", return_value=fake_event):
            resp = client.post(
                "/api/webhooks/stripe",
                content=b"fake_body",
                headers={
                    "stripe-signature": "t=1,v1=mock",
                    "Content-Type": "application/json",
                },
            )
        assert resp.status_code == 200
        assert resp.json()["status"] in ("queued", "skipped")

    def test_idempotency_duplicate_event_skipped(self, client, db):
        """Lo stesso event_id processato due volte → secondo restituisce 'skipped'."""
        from models import WebhookEvent
        from datetime import datetime, timezone

        event_id = "evt_idempotency_test_unique"

        # Inserisci evento già processato nel DB
        existing = WebhookEvent(
            event_id=event_id,
            event_type="checkout.session.completed",
            status="processed",
            processed_at=datetime.now(timezone.utc),
        )
        db.add(existing)
        db.commit()

        fake_event = {
            "id": event_id,
            "type": "checkout.session.completed",
            "data": {"object": {}},
        }
        with patch("stripe.Webhook.construct_event", return_value=fake_event):
            resp = client.post(
                "/api/webhooks/stripe",
                content=b"body",
                headers={"stripe-signature": "t=1,v1=mock", "Content-Type": "application/json"},
            )

        assert resp.status_code == 200
        assert resp.json()["status"] == "skipped"

        # Cleanup
        db.delete(existing)
        db.commit()


class TestSubscriptionGate:
    """Middleware require_pro_subscription / require_active_subscription"""

    def test_pro_feature_without_subscription_returns_403(self, client):
        """Utente senza subscription → 403."""
        resp = client.get("/api/pro-feature", headers={"x-user-id": "ghost-no-sub"})
        assert resp.status_code == 403
        body = resp.json()
        assert body["detail"]["code"] == "pro_required"
        assert "upgrade_url" in body["detail"]

    def test_pro_feature_missing_header_returns_422(self, client):
        """Header x-user-id mancante → 422 (validation error)."""
        resp = client.get("/api/pro-feature")
        assert resp.status_code == 422

    def test_pro_feature_with_active_subscription_allowed(self, client, db):
        """Utente con sub Pro attiva → 200."""
        from models import User, Subscription, SubscriptionStatus
        from datetime import datetime, timezone

        uid = "pro-user-security-test"
        user = User(id=uid, email=f"{uid}@test.com", created_at=datetime.now(timezone.utc))
        sub = Subscription(
            user_id=uid,
            stripe_subscription_id="sub_active_security",
            stripe_customer_id="cus_active_security",
            plan="pro",
            status=SubscriptionStatus.active,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(user)
        db.add(sub)
        db.commit()

        resp = client.get("/api/pro-feature", headers={"x-user-id": uid})
        assert resp.status_code == 200
        assert resp.json()["plan"] == "pro"

        # Cleanup
        db.delete(sub)
        db.delete(user)
        db.commit()

    def test_pro_feature_with_trialing_subscription_allowed(self, client, db):
        """Utente in trial → 200 (trial conta come accesso Pro)."""
        from models import User, Subscription, SubscriptionStatus
        from datetime import datetime, timezone

        uid = "trial-user-security-test"
        user = User(id=uid, email=f"{uid}@test.com", created_at=datetime.now(timezone.utc))
        sub = Subscription(
            user_id=uid,
            stripe_subscription_id="sub_trialing_security",
            stripe_customer_id="cus_trialing_security",
            plan="pro",
            status=SubscriptionStatus.trialing,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(user)
        db.add(sub)
        db.commit()

        resp = client.get("/api/pro-feature", headers={"x-user-id": uid})
        assert resp.status_code == 200

        db.delete(sub)
        db.delete(user)
        db.commit()

    def test_pro_feature_with_canceled_subscription_returns_403(self, client, db):
        """Subscription cancellata → 403."""
        from models import User, Subscription, SubscriptionStatus
        from datetime import datetime, timezone

        uid = "canceled-user-security-test"
        user = User(id=uid, email=f"{uid}@test.com", created_at=datetime.now(timezone.utc))
        sub = Subscription(
            user_id=uid,
            stripe_subscription_id="sub_canceled_security",
            stripe_customer_id="cus_canceled_security",
            plan="pro",
            status=SubscriptionStatus.canceled,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(user)
        db.add(sub)
        db.commit()

        resp = client.get("/api/pro-feature", headers={"x-user-id": uid})
        assert resp.status_code == 403

        db.delete(sub)
        db.delete(user)
        db.commit()


class TestInputValidation:
    """Validazione input — SQL injection, XSS, price_id invalido."""

    def test_invalid_price_id_returns_400(self, client):
        """Price ID non nei piani configurati → 400."""
        resp = client.post(
            "/api/payments/create-checkout-session",
            json={"price_id": "price_FAKE_HACKER", "user_id": "u1", "user_email": "x@x.com"},
        )
        assert resp.status_code == 400

    def test_sql_injection_in_user_id_does_not_crash(self, client):
        """SQL injection nel user_id → non crasha (SQLAlchemy ORM protegge)."""
        malicious_id = "'; DROP TABLE users; --"
        resp = client.get(
            "/api/payments/subscription-status",
            headers={"x-user-id": malicious_id},
        )
        # Non deve restituire 500 — l'ORM para l'injection
        assert resp.status_code != 500

    def test_xss_in_email_stored_safely(self, client, mock_stripe_checkout, mock_stripe_customer):
        """XSS nell'email → salvato come stringa, non eseguito."""
        xss_email = "<script>alert('xss')</script>@evil.com"
        resp = client.post(
            "/api/payments/create-checkout-session",
            json={
                "price_id": "price_pro_test",
                "user_id": "xss-test-user",
                "user_email": xss_email,
            },
        )
        # Non crasha — il dato viene trattato come stringa normale
        assert resp.status_code in (200, 400, 422)

    def test_missing_required_fields_returns_422(self, client):
        """Campi obbligatori mancanti → 422 validation error."""
        resp = client.post(
            "/api/payments/create-checkout-session",
            json={"price_id": "price_pro_test"},  # mancano user_id e user_email
        )
        assert resp.status_code == 422

    def test_portal_unknown_user_returns_404(self, client):
        """Portal per utente non esistente → 404."""
        resp = client.post(
            "/api/payments/portal-session",
            headers={"x-user-id": "non-existent-user-xyz"},
        )
        assert resp.status_code == 404

    def test_portal_user_without_customer_returns_400(self, client, db):
        """Portal per utente senza stripe_customer_id → 400."""
        from models import User
        from datetime import datetime, timezone

        uid = "user-no-customer-portal"
        user = User(id=uid, email=f"{uid}@test.com",
                    stripe_customer_id=None,
                    created_at=datetime.now(timezone.utc))
        db.add(user)
        db.commit()

        resp = client.post("/api/payments/portal-session", headers={"x-user-id": uid})
        assert resp.status_code == 400

        db.delete(user)
        db.commit()

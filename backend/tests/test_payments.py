"""
Test endpoint pagamenti:
- POST /api/payments/create-checkout-session
- POST /api/payments/portal-session
- GET  /api/payments/subscription-status
"""
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone


class TestCheckoutSession:

    def test_valid_pro_checkout_returns_url(self, client, mock_stripe_checkout, mock_stripe_customer):
        """Checkout valido con piano Pro → 200 con url Stripe."""
        resp = client.post(
            "/api/payments/create-checkout-session",
            json={
                "price_id": "price_pro_test",
                "user_id": "checkout-test-user-pro",
                "user_email": "pro@test.com",
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "url" in body
        assert "session_id" in body
        assert body["url"].startswith("https://checkout.stripe.com")

    def test_valid_basic_checkout_returns_url(self, client, mock_stripe_checkout, mock_stripe_customer):
        """Checkout valido con piano Basic → 200 con url Stripe."""
        resp = client.post(
            "/api/payments/create-checkout-session",
            json={
                "price_id": "price_basic_test",
                "user_id": "checkout-test-user-basic",
                "user_email": "basic@test.com",
            },
        )
        assert resp.status_code == 200
        assert "url" in resp.json()

    def test_invalid_price_id_rejected(self, client):
        """Price ID non configurato → 400."""
        resp = client.post(
            "/api/payments/create-checkout-session",
            json={"price_id": "price_unknown", "user_id": "u", "user_email": "x@x.com"},
        )
        assert resp.status_code == 400

    def test_checkout_creates_stripe_customer_for_new_user(
        self, client, db, mock_stripe_checkout, mock_stripe_customer
    ):
        """Nuovo utente → viene creato customer Stripe e salvato nel DB."""
        from models import User

        uid = "brand-new-user-checkout"
        resp = client.post(
            "/api/payments/create-checkout-session",
            json={"price_id": "price_pro_test", "user_id": uid, "user_email": "new@test.com"},
        )
        assert resp.status_code == 200
        mock_stripe_customer.assert_called_once()

        user = db.query(User).filter(User.id == uid).first()
        assert user is not None
        assert user.stripe_customer_id is not None
        assert user.stripe_customer_id.startswith("cus_")

        db.delete(user)
        db.commit()

    def test_checkout_reuses_existing_customer(
        self, client, db, mock_stripe_checkout, mock_stripe_customer, test_user
    ):
        """Utente con customer_id già nel DB → NON crea nuovo customer Stripe."""
        resp = client.post(
            "/api/payments/create-checkout-session",
            json={
                "price_id": "price_pro_test",
                "user_id": test_user.id,
                "user_email": test_user.email,
            },
        )
        assert resp.status_code == 200
        mock_stripe_customer.assert_not_called()  # customer già esistente, non ricreato


class TestSubscriptionStatus:

    def test_status_for_user_without_subscription(self, client, db):
        """Utente senza subscription → has_subscription: false."""
        from models import User

        uid = "status-test-no-sub"
        user = User(id=uid, email=f"{uid}@test.com", created_at=datetime.now(timezone.utc))
        db.add(user)
        db.commit()

        resp = client.get("/api/payments/subscription-status", headers={"x-user-id": uid})
        assert resp.status_code == 200
        body = resp.json()
        assert body["has_subscription"] is False
        assert body["status"] is None

        db.delete(user)
        db.commit()

    def test_status_for_user_with_active_subscription(self, client, db):
        """Utente con sub attiva → status: active, plan corretto."""
        from models import User, Subscription, SubscriptionStatus

        uid = "status-test-active"
        user = User(id=uid, email=f"{uid}@test.com", created_at=datetime.now(timezone.utc))
        sub = Subscription(
            user_id=uid,
            stripe_subscription_id="sub_status_active",
            stripe_customer_id="cus_status",
            plan="pro",
            status=SubscriptionStatus.active,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(user)
        db.add(sub)
        db.commit()

        resp = client.get("/api/payments/subscription-status", headers={"x-user-id": uid})
        assert resp.status_code == 200
        body = resp.json()
        assert body["has_subscription"] is True
        assert body["status"] == "active"
        assert body["plan"] == "pro"

        db.delete(sub)
        db.delete(user)
        db.commit()

    def test_status_missing_header_returns_422(self, client):
        """Header x-user-id mancante → 422."""
        resp = client.get("/api/payments/subscription-status")
        assert resp.status_code == 422


class TestCustomerPortal:

    def test_portal_returns_url(self, client, db, mock_stripe_portal, test_user):
        """Utente con customer_id → 200 con url portale."""
        resp = client.post(
            "/api/payments/portal-session",
            headers={"x-user-id": test_user.id},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "url" in body
        assert "billing.stripe.com" in body["url"]
        mock_stripe_portal.assert_called_once()

    def test_portal_unknown_user_returns_404(self, client):
        """Utente non nel DB → 404."""
        resp = client.post(
            "/api/payments/portal-session",
            headers={"x-user-id": "ghost-xyz"},
        )
        assert resp.status_code == 404

    def test_portal_user_without_customer_id_returns_400(self, client, db):
        """Utente nel DB ma senza stripe_customer_id → 400."""
        from models import User

        uid = "portal-no-customer"
        user = User(id=uid, email=f"{uid}@test.com",
                    stripe_customer_id=None,
                    created_at=datetime.now(timezone.utc))
        db.add(user)
        db.commit()

        resp = client.post("/api/payments/portal-session", headers={"x-user-id": uid})
        assert resp.status_code == 400

        db.delete(user)
        db.commit()

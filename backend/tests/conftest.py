"""
Pytest fixtures condivisi da tutti i test.
- DB SQLite isolato per ogni test session
- FastAPI TestClient pronto all'uso
- Mock Celery (tutti i .delay() sono no-op nei test)
- Mock chiamate Stripe
"""
import os
import pytest
from unittest.mock import MagicMock, patch

# Imposta env vars di test PRIMA di importare l'app
os.environ["STRIPE_SECRET_KEY"] = "sk_test_fixture"
os.environ["STRIPE_PUBLISHABLE_KEY"] = "pk_test_fixture"
os.environ["STRIPE_WEBHOOK_SECRET"] = "whsec_test_fixture"
os.environ["STRIPE_BASIC_PRICE_ID"] = "price_basic_test"
os.environ["STRIPE_PRO_PRICE_ID"] = "price_pro_test"
os.environ["DATABASE_URL"] = "sqlite:///./test_stripe_saas.db"
os.environ["REDIS_URL"] = "redis://localhost:6379/0"
os.environ["APP_URL"] = "http://localhost:3000"
os.environ["RESEND_API_KEY"] = ""

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


class StripeEventMock(dict):
    """Dict che supporta accesso ad attributo — simula StripeObject del SDK."""
    def __getattr__(self, key):
        try:
            val = self[key]
            return StripeEventMock(val) if isinstance(val, dict) else val
        except KeyError:
            raise AttributeError(key)

    def __setattr__(self, key, value):
        self[key] = value

from database import Base, get_db
from main import app

TEST_DB_URL = "sqlite:///./test_stripe_saas.db"
engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSession()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(scope="session", autouse=True)
def setup_db():
    """Crea le tabelle una volta per la session di test."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    try:
        os.remove("test_stripe_saas.db")
    except Exception:
        pass


@pytest.fixture(autouse=True)
def mock_celery_delays():
    """
    Mock GLOBALE di tutti i Celery .delay() — nessun test
    necessita di Redis o del worker per girare.
    """
    with patch("tasks.sync_tasks.process_webhook_event.delay") as p1, \
         patch("tasks.email_tasks.send_welcome_email.delay") as p2, \
         patch("tasks.email_tasks.send_payment_confirmed_email.delay") as p3, \
         patch("tasks.email_tasks.send_trial_expiring_email.delay") as p4, \
         patch("tasks.email_tasks.alert_payment_failed.delay") as p5:
        yield {
            "process_webhook_event": p1,
            "send_welcome_email": p2,
            "send_payment_confirmed_email": p3,
            "send_trial_expiring_email": p4,
            "alert_payment_failed": p5,
        }


@pytest.fixture
def client():
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


@pytest.fixture
def db():
    session = TestingSession()
    yield session
    session.close()


@pytest.fixture
def mock_stripe_checkout():
    import uuid
    with patch("stripe.checkout.Session.create") as mock:
        def _create(**kwargs):
            sid = f"cs_test_{uuid.uuid4().hex[:12]}"
            return MagicMock(id=sid, url=f"https://checkout.stripe.com/c/pay/{sid}")
        mock.side_effect = _create
        yield mock


@pytest.fixture
def mock_stripe_portal():
    with patch("stripe.billing_portal.Session.create") as mock:
        mock.return_value = MagicMock(url="https://billing.stripe.com/p/session/test")
        yield mock


@pytest.fixture
def mock_stripe_customer():
    """Ogni chiamata restituisce un customer ID univoco — evita violazioni UNIQUE."""
    import uuid
    with patch("stripe.Customer.create") as mock:
        mock.side_effect = lambda **kwargs: MagicMock(id=f"cus_{uuid.uuid4().hex[:12]}")
        yield mock


@pytest.fixture
def test_user(db):
    """Utente con stripe_customer_id già impostato."""
    from models import User
    from datetime import datetime, timezone

    user = User(
        id="test-user-with-customer",
        email="testuser@example.com",
        stripe_customer_id="cus_test_existing",
        created_at=datetime.now(timezone.utc),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    yield user
    db.delete(user)
    db.commit()

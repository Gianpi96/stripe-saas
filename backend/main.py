import logging
import logging.config

import stripe
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from database import Base, engine
from routers import payments, webhooks

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.config.dictConfig({
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "format": '{"time":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","msg":"%(message)s"}',
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json",
        }
    },
    "root": {"handlers": ["console"], "level": "INFO"},
})

stripe.api_key = settings.STRIPE_SECRET_KEY

# ---------------------------------------------------------------------------
# DB init (for SQLite / dev; use Alembic for production)
# ---------------------------------------------------------------------------
Base.metadata.create_all(bind=engine)

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(
    title="StripeSaaS API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        settings.APP_URL,
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(payments.router)
app.include_router(webhooks.router)


@app.get("/health")
def health():
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Example Pro-gated endpoint (demonstrates middleware usage)
# ---------------------------------------------------------------------------
from fastapi import Depends
from middleware.subscription import require_pro_subscription
from models import Subscription


@app.get("/api/pro-feature")
def pro_feature(sub: Subscription = Depends(require_pro_subscription)):
    return {"message": "Accesso Pro confermato", "plan": sub.plan, "status": sub.status}

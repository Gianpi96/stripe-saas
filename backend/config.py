from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    STRIPE_SECRET_KEY: str
    STRIPE_PUBLISHABLE_KEY: str
    STRIPE_WEBHOOK_SECRET: str
    STRIPE_BASIC_PRICE_ID: str
    STRIPE_PRO_PRICE_ID: str

    APP_URL: str = "http://localhost:3000"
    BACKEND_URL: str = "http://localhost:8000"
    DATABASE_URL: str = "sqlite:///./stripe_saas.db"
    REDIS_URL: str = "redis://localhost:6379/0"

    RESEND_API_KEY: str = ""          # opzionale — le email vengono saltate se vuoto
    EMAIL_FROM: str = "noreply@yourdomain.com"
    EMAIL_FROM_NAME: str = "StripeSaaS"

    SLACK_WEBHOOK_URL: str = ""
    ALERT_EMAIL: str = ""

    class Config:
        env_file = ".env"


settings = Settings()

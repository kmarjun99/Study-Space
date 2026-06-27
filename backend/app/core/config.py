from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 14
    REFRESH_SESSION_ABSOLUTE_DAYS: int = 30

    # Deployment environment (development | production)
    ENVIRONMENT: str = "development"

    # Comma-separated list of extra allowed CORS origins (e.g. Cloud Run URLs)
    CORS_ORIGINS: Optional[str] = ""

    # Email Configuration for OTP
    mail_username: Optional[str] = ""
    mail_password: Optional[str] = ""
    mail_from: Optional[str] = "noreply@studyspace.com"
    mail_port: Optional[int] = 587
    mail_server: Optional[str] = "smtp.gmail.com"
    FRONTEND_URL: Optional[str] = ""

    # SendGrid Configuration
    sendgrid_api_key: Optional[str] = ""

    # Razorpay Payment Configuration
    razorpay_key_id: Optional[str] = ""
    razorpay_key_secret: Optional[str] = ""
    payment_demo_mode: Optional[str] = "false"

    # Dev-only debug endpoints (e.g. /payments/venue/dev-bypass,
    # /bookings/extend-test) are 404 in production by default. Setting
    # ENABLE_DEV_BYPASS=true on a non-dev environment is an EXPLICIT,
    # auditable override — useful for short-lived staging diagnostics.
    # Do NOT enable in production without understanding the risk: these
    # endpoints can bypass payment or modify booking state with no signing
    # check.
    ENABLE_DEV_BYPASS: Optional[str] = "false"

    class Config:
        env_file = ".env"
        # Tolerate stray env vars in the project's .env (e.g., DEBUG, API_VERSION
        # used by other tooling). Pydantic v2 defaults to forbidding extras,
        # which made the app refuse to import on any machine that had those set.
        extra = "ignore"

settings = Settings()

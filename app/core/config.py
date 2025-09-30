from __future__ import annotations

import os
from functools import lru_cache

from dotenv import load_dotenv


load_dotenv()


class Settings:
    """Application configuration loaded from environment variables."""

    database_url: str
    session_secret: str
    session_cookie_secure: bool
    entry_event_queue_size: int
    google_client_id: str
    google_client_secret: str
    google_redirect_uri: str
    google_superuser_email: str
    google_allowed_domain: str

    def __init__(self) -> None:
        self.database_url = os.getenv(
            "DATABASE_URL",
            "postgresql+psycopg://postgres:postgres@localhost:5432/hermas_stock",
        )
        self.session_secret = os.getenv("SESSION_SECRET", "change_me")
        queue_size_raw = os.getenv("ENTRY_EVENT_QUEUE_SIZE", "512")
        try:
            queue_size = int(queue_size_raw)
        except ValueError:
            queue_size = 512
        self.entry_event_queue_size = max(0, min(queue_size, 100000))
        self.session_cookie_secure = self._parse_bool(os.getenv("SESSION_COOKIE_SECURE"), default=True)
        self.google_client_id = os.getenv("GOOGLE_CLIENT_ID", "").strip()
        self.google_client_secret = os.getenv("GOOGLE_CLIENT_SECRET", "").strip()
        self.google_redirect_uri = os.getenv("GOOGLE_REDIRECT_URI", "").strip()
        allowed_domain = os.getenv("GOOGLE_ALLOWED_DOMAIN", "gmail.com").strip().lower()
        self.google_allowed_domain = allowed_domain or "gmail.com"
        self.google_superuser_email = (
            os.getenv("GOOGLE_SUPERUSER_EMAIL", "").strip().lower()
        )

        self._validate()

    @staticmethod
    def _parse_bool(raw: str | None, *, default: bool) -> bool:
        if raw is None:
            return default
        normalized = raw.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
        return default

    def _validate(self) -> None:
        if self.session_secret == "change_me" or len(self.session_secret) < 32:
            raise ValueError(
                "SESSION_SECRET must be set to a random value of at least 32 characters."
            )
        if not self.google_superuser_email:
            raise ValueError("GOOGLE_SUPERUSER_EMAIL must be configured.")
        if not self.google_superuser_email.endswith(f"@{self.google_allowed_domain}"):
            raise ValueError(
                "GOOGLE_SUPERUSER_EMAIL must belong to the allowed Google domain."
            )


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

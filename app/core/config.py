from __future__ import annotations

import os
from functools import lru_cache

from dotenv import load_dotenv


load_dotenv()


class Settings:
    """Application configuration loaded from environment variables."""

    database_url: str
    session_secret: str
    entry_event_queue_size: int

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


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

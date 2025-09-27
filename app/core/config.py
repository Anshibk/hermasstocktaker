from __future__ import annotations

import os
from functools import lru_cache

from dotenv import load_dotenv


load_dotenv()


class Settings:
    """Application configuration loaded from environment variables."""

    database_url: str
    session_secret: str

    def __init__(self) -> None:
        self.database_url = os.getenv("DATABASE_URL", "postgresql+psycopg://postgres:postgres@localhost:5432/hermas_stock")
        self.session_secret = os.getenv("SESSION_SECRET", "change_me")


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

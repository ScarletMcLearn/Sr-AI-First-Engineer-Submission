"""Application configuration, read from environment variables."""

from datetime import UTC, datetime
from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_APP_NOW = datetime(2026, 11, 11, 15, 0, tzinfo=UTC)


class Settings(BaseSettings):
    """Runtime settings. Every value can be overridden by an environment variable."""

    model_config = SettingsConfigDict(env_file=None, extra="ignore")

    database_url: str = "postgresql+psycopg://l10:l10@localhost:5432/l10"
    app_now: datetime = DEFAULT_APP_NOW
    # Development-only signing key for the seeded-user session cookie (not a real secret).
    session_secret: str = "dev-only-session-key-change-me"  # noqa: S105
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    enable_test_endpoints: bool = False
    seed_path: str = "seed.json"

    @field_validator("app_now")
    @classmethod
    def _require_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            msg = "APP_NOW must include a UTC offset, e.g. 2026-11-11T15:00:00Z"
            raise ValueError(msg)
        return value.astimezone(UTC)

    @property
    def cors_origin_list(self) -> list[str]:
        """Allowed CORS origins as a list."""
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    """Return cached settings."""
    return Settings()

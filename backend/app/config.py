"""Application settings loaded from environment variables (or a .env file).

Keeping configuration here means no secrets or environment-specific values
are hard-coded in the rest of the code.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "SentinelDesk"
    environment: str = "development"
    database_url: str = "sqlite:///./data/sentineldesk.db"

    # Stored as a comma-separated string so it is easy to set in .env
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    max_upload_mb: int = 2
    max_events_per_file: int = 10000

    # Not used yet. Lives in the environment so it never ends up in Git.
    api_secret_key: str = "change-me"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    """Return one shared Settings object (read from the environment once)."""
    return Settings()

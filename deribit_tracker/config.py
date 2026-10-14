from functools import cached_property

from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL


class Settings(BaseSettings):
    """Application settings read from environment variables (and `.env` if present)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    postgres_user: str = "tracker"
    postgres_password: str = "tracker"
    postgres_db: str = "prices"
    postgres_host: str = "localhost"
    postgres_port: int = 5432

    redis_url: str = "redis://localhost:6379/0"

    deribit_base_url: str = "https://www.deribit.com/api/v2"
    deribit_request_timeout_seconds: float = 10.0

    fetch_interval_seconds: float = 60.0

    @cached_property
    def database_url(self) -> URL:
        # URL.create escapes special characters in the password (e.g. "@", "/", ":").
        return URL.create(
            drivername="postgresql+asyncpg",
            username=self.postgres_user,
            password=self.postgres_password,
            host=self.postgres_host,
            port=self.postgres_port,
            database=self.postgres_db,
        )

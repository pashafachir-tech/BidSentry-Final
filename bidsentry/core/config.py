"""Environment-backed settings for the asynchronous job engine."""

from __future__ import annotations

from urllib.parse import urlsplit

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AsyncEngineSettings(BaseSettings):
    """Settings shared by the API process and ARQ worker process."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    database_url: str = Field(default="sqlite+aiosqlite:///./bidsentry_jobs.db", min_length=1)
    redis_url: str = Field(default="redis://localhost:6379/0", min_length=1)
    audit_queue_name: str = Field(default="bidsentry:audit", min_length=1, max_length=128)
    audit_job_timeout_seconds: int = Field(default=900, ge=30, le=86_400)
    audit_job_result_ttl_seconds: int = Field(default=86_400, ge=60, le=31_536_000)
    database_echo: bool = False

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: str) -> str:
        normalized = value.strip()
        if normalized.startswith("postgresql://"):
            normalized = "postgresql+asyncpg://" + normalized[len("postgresql://"):]
        parsed = urlsplit(normalized)
        if parsed.scheme not in {"sqlite+aiosqlite", "postgresql+asyncpg"}:
            raise ValueError("DATABASE_URL must use sqlite+aiosqlite or postgresql+asyncpg.")
        if parsed.scheme == "postgresql+asyncpg" and not parsed.hostname:
            raise ValueError("DATABASE_URL must include a PostgreSQL host.")
        if not normalized:
            raise ValueError("DATABASE_URL cannot be empty.")
        return normalized

    @field_validator("redis_url")
    @classmethod
    def validate_redis_url(cls, value: str) -> str:
        normalized = value.strip()
        parsed = urlsplit(normalized)
        if parsed.scheme not in {"redis", "rediss"} or not parsed.hostname:
            raise ValueError("REDIS_URL must be an absolute redis:// or rediss:// URL.")
        if parsed.query or parsed.fragment:
            raise ValueError("REDIS_URL query strings and fragments are not supported.")
        try:
            port = parsed.port
            database = int(parsed.path.lstrip("/") or "0")
        except (ValueError, TypeError) as exc:
            raise ValueError("REDIS_URL must contain a valid port and database number.") from exc
        if port is not None and not 1 <= port <= 65535:
            raise ValueError("REDIS_URL port must be between 1 and 65535.")
        if database < 0:
            raise ValueError("REDIS_URL database number cannot be negative.")
        return normalized


# Conventional alias for code that imports ``Settings`` from this module.
Settings = AsyncEngineSettings

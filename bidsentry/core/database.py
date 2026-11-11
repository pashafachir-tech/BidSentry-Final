"""Async SQLAlchemy persistence for audit job lifecycle and results."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from sqlalchemy import DateTime, Integer, JSON, String, Text, event, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


JobState = Literal["queued", "running", "complete", "failed"]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    """Base metadata for the job engine's tables."""


class AuditJobRecord(Base):
    """Persisted status and result for one asynchronous audit."""

    __tablename__ = "audit_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tender_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    vendor_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    progress: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    stage: Mapped[str] = mapped_column(String(80), nullable=False, default="queued")
    payload_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)


class AsyncDatabase:
    """Owns the async engine and provides transaction-scoped job operations."""

    def __init__(self, database_url: str, *, echo: bool = False) -> None:
        self.engine: AsyncEngine = create_async_engine(database_url, echo=echo, pool_pre_ping=True)
        if "sqlite" in str(database_url).lower():
            @event.listens_for(self.engine.sync_engine, "connect")
            def set_sqlite_pragma(dbapi_connection, connection_record):
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA journal_mode=WAL;")
                cursor.execute("PRAGMA synchronous=NORMAL;")
                cursor.execute("PRAGMA busy_timeout=5000;")
                cursor.close()

        self.sessions: async_sessionmaker[AsyncSession] = async_sessionmaker(
            self.engine,
            expire_on_commit=False,
            autoflush=False,
        )

    async def initialize(self) -> None:
        async with self.engine.begin() as connection:
            if "sqlite" in str(self.engine.url).lower():
                await connection.execute(text("PRAGMA journal_mode=WAL;"))
                await connection.execute(text("PRAGMA synchronous=NORMAL;"))
                await connection.execute(text("PRAGMA busy_timeout=5000;"))
            await connection.run_sync(Base.metadata.create_all)

    async def dispose(self) -> None:
        await self.engine.dispose()

    async def create_job(
        self,
        *,
        job_id: str,
        tender_id: str,
        vendor_id: str,
        payload_sha256: str,
    ) -> AuditJobRecord:
        record = AuditJobRecord(
            id=job_id,
            tender_id=tender_id,
            vendor_id=vendor_id,
            status="queued",
            progress=0,
            stage="queued",
            payload_sha256=payload_sha256,
        )
        async with self.sessions.begin() as session:
            session.add(record)
        return record

    async def get_job(self, job_id: str) -> AuditJobRecord | None:
        async with self.sessions() as session:
            return await session.get(AuditJobRecord, job_id)

    async def update_job(
        self,
        job_id: str,
        *,
        status: JobState,
        progress: int,
        stage: str,
        result: dict[str, Any] | None = None,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> AuditJobRecord | None:
        if not 0 <= progress <= 100:
            raise ValueError("Job progress must be between 0 and 100.")
        async with self.sessions.begin() as session:
            record = await session.get(AuditJobRecord, job_id)
            if record is None:
                return None
            record.status = status
            record.progress = progress
            record.stage = stage
            record.updated_at = utc_now()
            if result is not None:
                record.result = result
            record.error_code = error_code
            record.error_message = error_message
            await session.flush()
            return record


def serialize_job(record: AuditJobRecord) -> dict[str, Any]:
    """Convert a detached job row into a JSON-ready status response."""

    return {
        "job_id": record.id,
        "tender_id": record.tender_id,
        "vendor_id": record.vendor_id,
        "status": record.status,
        "progress": record.progress,
        "stage": record.stage,
        "result": record.result,
        "error": (
            {"code": record.error_code, "message": record.error_message}
            if record.error_code is not None
            else None
        ),
        "created_at": record.created_at.isoformat(),
        "updated_at": record.updated_at.isoformat(),
    }

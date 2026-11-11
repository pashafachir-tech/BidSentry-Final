"""ARQ worker lifecycle and asynchronous procurement audit task."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from collections.abc import MutableMapping
from typing import Any
from urllib.parse import unquote, urlsplit

from arq.connections import RedisSettings
from pydantic import ValidationError

from bidsentry.config import Settings as ApplicationSettings
from bidsentry.core.config import AsyncEngineSettings
from bidsentry.core.database import AsyncDatabase, JobState
from bidsentry.core.job_events import publish_job_event
from bidsentry.schemas.comprehensive import ComprehensiveAuditRequest
from bidsentry.services.comprehensive_audit_service import (
    ComprehensiveAuditInputError,
    ComprehensiveAuditService,
)
from bidsentry.services.langflow_service import LangflowService


LOGGER = logging.getLogger("bidsentry.worker")


def build_redis_settings(url: str) -> RedisSettings:
    """Translate a redis:// or rediss:// URL into ARQ connection settings."""

    parsed = urlsplit(url)
    if parsed.scheme not in {"redis", "rediss"} or not parsed.hostname:
        raise ValueError("REDIS_URL must be an absolute redis:// or rediss:// URL.")
    try:
        database = int(parsed.path.lstrip("/") or "0")
        port = parsed.port or 6379
    except ValueError as exc:
        raise ValueError("REDIS_URL contains an invalid port or database number.") from exc
    if database < 0 or not 1 <= port <= 65535:
        raise ValueError("REDIS_URL contains an out-of-range port or database number.")
    return RedisSettings(
        host=parsed.hostname,
        port=port,
        database=database,
        username=unquote(parsed.username) if parsed.username else None,
        password=unquote(parsed.password) if parsed.password else None,
        ssl=parsed.scheme == "rediss",
        conn_retries=1,
        conn_timeout=1,
    )


def serialize_job_definition(value: dict[str, Any]) -> bytes:
    """Serialize ARQ job definitions as JSON rather than executable pickle data."""

    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def deserialize_job_definition(value: bytes) -> dict[str, Any]:
    decoded = json.loads(value.decode("utf-8"))
    if not isinstance(decoded, dict):
        raise ValueError("ARQ job payload must be a JSON object.")
    return decoded


async def on_worker_startup(ctx: MutableMapping[str, Any]) -> None:
    """Create worker-scoped DB and audit service dependencies."""

    settings = AsyncEngineSettings()
    database = AsyncDatabase(settings.database_url, echo=settings.database_echo)
    await database.initialize()
    application_settings = ApplicationSettings.from_environment()
    langflow = LangflowService(application_settings)
    ctx["engine_settings"] = settings
    ctx["database"] = database
    ctx["audit_service"] = ComprehensiveAuditService(application_settings, langflow)


async def on_worker_shutdown(ctx: MutableMapping[str, Any]) -> None:
    database = ctx.get("database")
    if isinstance(database, AsyncDatabase):
        await database.dispose()


_CONCURRENCY_SEMAPHORE: asyncio.Semaphore | None = None


def get_concurrency_semaphore() -> asyncio.Semaphore:
    """Return bounded queue concurrency semaphore to prevent event-loop lock contention."""
    global _CONCURRENCY_SEMAPHORE
    if _CONCURRENCY_SEMAPHORE is None:
        _CONCURRENCY_SEMAPHORE = asyncio.Semaphore(4)
    return _CONCURRENCY_SEMAPHORE


async def execute_procurement_audit_job(
    ctx: MutableMapping[str, Any],
    job_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Run one comprehensive audit and publish durable progress transitions."""

    database: AsyncDatabase = ctx["database"]
    redis = ctx["redis"]
    existing = await database.get_job(job_id)
    if existing is None:
        raise LookupError("Audit job record does not exist.")
    if existing.status == "complete" and existing.result is not None:
        return {"job_id": job_id, "status": "complete"}

    try:
        canonical_payload = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        payload_hash = hashlib.sha256(canonical_payload.encode("utf-8")).hexdigest()
        if payload_hash != existing.payload_sha256:
            raise PayloadIntegrityError("Queued audit payload does not match its stored integrity hash.")
        request = ComprehensiveAuditRequest.model_validate(payload)
        await _advance(ctx, job_id, status="running", progress=5, stage="validating_request")
        await _advance(ctx, job_id, status="running", progress=15, stage="preparing_evidence")
        await _advance(ctx, job_id, status="running", progress=35, stage="forensic_analysis")

        service: ComprehensiveAuditService = ctx["audit_service"]
        async with get_concurrency_semaphore():
            result = await asyncio.to_thread(service.audit, request, audit_run_id=job_id)

        await _advance(ctx, job_id, status="running", progress=95, stage="persisting_result")
        updated = await database.update_job(
            job_id,
            status="complete",
            progress=100,
            stage="complete",
            result=result,
        )
        if updated is None:
            raise LookupError("Audit job record disappeared before completion.")
        await publish_job_event(redis, job_id, {
            "status": "complete",
            "progress": 100,
            "stage": "complete",
            "result_available": True,
        })
        return {"job_id": job_id, "status": "complete"}
    except (ValidationError, ComprehensiveAuditInputError) as exc:
        await _mark_failed(ctx, job_id, "INVALID_AUDIT_INPUT", "The audit input could not be validated.")
        LOGGER.info("Audit job rejected as invalid", extra={"job_id": job_id, "error_type": type(exc).__name__})
        raise
    except PayloadIntegrityError:
        await _mark_failed(ctx, job_id, "PAYLOAD_INTEGRITY_ERROR", "The queued audit data failed its integrity check.")
        LOGGER.error("Audit job payload integrity check failed", extra={"job_id": job_id})
        raise
    except Exception as exc:
        await _mark_failed(ctx, job_id, "AUDIT_FAILED", "The audit could not be completed.")
        LOGGER.exception("Audit job failed", extra={"job_id": job_id, "error_type": type(exc).__name__})
        raise


async def _advance(
    ctx: MutableMapping[str, Any],
    job_id: str,
    *,
    status: JobState,
    progress: int,
    stage: str,
) -> None:
    database: AsyncDatabase = ctx["database"]
    updated = await database.update_job(
        job_id,
        status=status,
        progress=progress,
        stage=stage,
    )
    if updated is None:
        raise LookupError("Audit job record disappeared during processing.")
    await publish_job_event(ctx["redis"], job_id, {
        "status": status,
        "progress": progress,
        "stage": stage,
    })


async def _mark_failed(ctx: MutableMapping[str, Any], job_id: str, code: str, message: str) -> None:
    database: AsyncDatabase = ctx["database"]
    await database.update_job(
        job_id,
        status="failed",
        progress=100,
        stage="failed",
        error_code=code,
        error_message=message,
    )
    await publish_job_event(ctx["redis"], job_id, {
        "status": "failed",
        "progress": 100,
        "stage": "failed",
        "error": {"code": code, "message": message},
    })


class PayloadIntegrityError(ValueError):
    """Raised when a queued payload differs from the database digest."""


class WorkerSettings:
    """ARQ CLI configuration: ``arq bidsentry.core.worker.WorkerSettings``."""

    _settings = AsyncEngineSettings()
    functions = [execute_procurement_audit_job]
    on_startup = on_worker_startup
    on_shutdown = on_worker_shutdown
    redis_settings = build_redis_settings(_settings.redis_url)
    queue_name = _settings.audit_queue_name
    job_timeout = _settings.audit_job_timeout_seconds
    keep_result = _settings.audit_job_result_ttl_seconds
    job_serializer = serialize_job_definition
    job_deserializer = deserialize_job_definition
    max_tries = 3
    max_jobs = 2
    log_results = False


__all__ = [
    "WorkerSettings",
    "build_redis_settings",
    "deserialize_job_definition",
    "execute_procurement_audit_job",
    "on_worker_shutdown",
    "on_worker_startup",
    "serialize_job_definition",
]

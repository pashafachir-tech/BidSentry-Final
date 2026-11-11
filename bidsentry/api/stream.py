"""Server-Sent Events endpoint for live audit job progress."""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse

from bidsentry.core.database import AsyncDatabase, serialize_job
from bidsentry.core.job_events import event_channel
from bidsentry.types.responses import failure


LOGGER = logging.getLogger("bidsentry.api.stream")
router = APIRouter(tags=["audit-jobs"])
TERMINAL_STATES = {"complete", "failed"}


@router.get("/api/v1/audit/stream/{job_id}", response_model=None)
async def stream_audit_job(job_id: str, request: Request) -> Response:
    database: AsyncDatabase | None = getattr(request.app.state, "database", None)
    redis = getattr(request.app.state, "redis_pool", None)
    if database is None or redis is None:
        return JSONResponse(
            failure("JOB_ENGINE_UNAVAILABLE", "The asynchronous audit engine is not available.", job_id),
            status_code=503,
        )

    pubsub = redis.pubsub()
    try:
        await pubsub.subscribe(event_channel(job_id))
        record = await database.get_job(job_id)
        if record is None:
            await pubsub.unsubscribe(event_channel(job_id))
            await pubsub.aclose()
            return JSONResponse(failure("JOB_NOT_FOUND", "Audit job was not found.", job_id), status_code=404)
    except Exception:
        LOGGER.exception("Could not subscribe to audit job stream", extra={"job_id": job_id})
        try:
            await pubsub.aclose()
        except Exception:
            LOGGER.debug("PubSub cleanup failed", exc_info=True)
        return JSONResponse(
            failure("JOB_STREAM_UNAVAILABLE", "Audit progress is temporarily unavailable.", job_id),
            status_code=503,
            headers={"Retry-After": "5"},
        )

    initial = serialize_job(record)
    initial_event = {
        "job_id": job_id,
        "status": initial["status"],
        "progress": initial["progress"],
        "stage": initial["stage"],
        "result_available": initial["result"] is not None,
        "error": initial["error"],
    }

    async def events() -> AsyncIterator[str]:
        try:
            yield _sse_frame("progress", initial_event)
            if initial_event["status"] in TERMINAL_STATES:
                return
            while not await request.is_disconnected():
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=15.0)
                if message is None:
                    yield ": keep-alive\n\n"
                    continue
                data = message.get("data")
                if isinstance(data, bytes):
                    data = data.decode("utf-8", errors="replace")
                if not isinstance(data, str):
                    continue
                try:
                    event: Any = json.loads(data)
                except json.JSONDecodeError:
                    LOGGER.warning("Ignoring malformed Redis job event", extra={"job_id": job_id})
                    continue
                if not isinstance(event, dict):
                    continue
                yield _sse_frame("progress", event)
                if event.get("status") in TERMINAL_STATES:
                    break
        except Exception:
            LOGGER.exception("Audit job stream terminated unexpectedly", extra={"job_id": job_id})
            yield _sse_frame("error", {"job_id": job_id, "message": "Progress stream interrupted."})
        finally:
            try:
                await pubsub.unsubscribe(event_channel(job_id))
                await pubsub.aclose()
            except Exception:
                LOGGER.debug("PubSub cleanup failed", exc_info=True)

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


def _sse_frame(event_name: str, data: dict[str, Any]) -> str:
    encoded = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return f"event: {event_name}\ndata: {encoded}\n\n"

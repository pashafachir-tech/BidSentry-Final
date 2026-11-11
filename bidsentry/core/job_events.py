"""Redis PubSub event helpers shared by the API and ARQ worker."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any


LOGGER = logging.getLogger("bidsentry.jobs.events")


def event_channel(job_id: str) -> str:
    return f"job_events:{job_id}"


async def publish_job_event(redis: Any, job_id: str, event: dict[str, Any]) -> bool:
    """Publish a small status update, without allowing telemetry to fail a job."""

    message = {**event, "job_id": job_id, "occurred_at": datetime.now(timezone.utc).isoformat()}
    try:
        await redis.publish(event_channel(job_id), json.dumps(message, ensure_ascii=False, separators=(",", ":")))
        return True
    except Exception:
        LOGGER.exception("Could not publish audit job progress", extra={"job_id": job_id})
        return False

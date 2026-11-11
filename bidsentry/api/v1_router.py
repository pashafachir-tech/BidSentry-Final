"""FastAPI router for versioned forensic audits and generated review drafts."""

from __future__ import annotations

import json
import logging
import uuid

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from bidsentry.api.auth_router import session_role
from bidsentry.api.routes import ApiRouter
from bidsentry.app import Application
from bidsentry.types.responses import failure


LOGGER = logging.getLogger("bidsentry.api.v1")


def create_v1_router(application: Application) -> APIRouter:
    """Expose v1 operations through the same validated service contract."""
    router = APIRouter(prefix="/api/v1", tags=["forensic-audit-v1"])
    dispatch = ApiRouter(application)

    @router.post("/audit/comprehensive")
    async def comprehensive_audit(request: Request) -> JSONResponse:
        payload, error = await _json_payload(request, application.settings.max_request_bytes)
        if error is not None:
            return error
        result = await run_in_threadpool(dispatch.dispatch, "POST", "/api/v1/audit/comprehensive", "", payload, session_role(request, application))
        return JSONResponse(result.body, status_code=result.status, headers=result.headers or {})

    @router.post("/audit/evaluate")
    async def evaluate_tender(request: Request) -> JSONResponse:
        payload, error = await _json_payload(request, application.settings.max_request_bytes)
        if error is not None:
            return error
        result = await run_in_threadpool(dispatch.dispatch, "POST", "/api/v1/audit/evaluate", "", payload, session_role(request, application))
        return JSONResponse(result.body, status_code=result.status, headers=result.headers or {})

    @router.post("/audit/sanggahan-doc")
    async def sanggahan_document(request: Request) -> JSONResponse:
        payload, error = await _json_payload(request, application.settings.max_request_bytes)
        if error is not None:
            return error
        result = await run_in_threadpool(dispatch.dispatch, "POST", "/api/v1/audit/sanggahan-doc", "", payload, session_role(request, application))
        return JSONResponse(result.body, status_code=result.status, headers=result.headers or {})

    @router.post("/audit/clarification-doc")
    async def clarification_document(request: Request) -> JSONResponse:
        payload, error = await _json_payload(request, application.settings.max_request_bytes)
        if error is not None:
            return error
        result = await run_in_threadpool(dispatch.dispatch, "POST", "/api/v1/audit/clarification-doc", "", payload, session_role(request, application))
        return JSONResponse(result.body, status_code=result.status, headers=result.headers or {})

    @router.post("/audit/minutes-eval-doc")
    async def minutes_document(request: Request) -> JSONResponse:
        payload, error = await _json_payload(request, application.settings.max_request_bytes)
        if error is not None:
            return error
        result = await run_in_threadpool(dispatch.dispatch, "POST", "/api/v1/audit/minutes-eval-doc", "", payload, session_role(request, application))
        return JSONResponse(result.body, status_code=result.status, headers=result.headers or {})

    return router


async def _json_payload(request: Request, maximum: int) -> tuple[object, JSONResponse | None]:
    content_type = request.headers.get("content-type", "").split(";", 1)[0].strip().casefold()
    if content_type != "application/json":
        request_id = str(uuid.uuid4())
        return None, JSONResponse(failure("UNSUPPORTED_MEDIA_TYPE", "Content-Type must be application/json.", request_id), status_code=415)
    body = bytearray()
    try:
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > maximum:
                request_id = str(uuid.uuid4())
                return None, JSONResponse(failure("PAYLOAD_TOO_LARGE", "Ukuran data melebihi batas server (maksimal 12 MB per permintaan). Pecah dokumen menjadi beberapa bagian.", request_id), status_code=413)
        payload = json.loads(body.decode("utf-8")) if body else {}
        return payload, None
    except (UnicodeDecodeError, json.JSONDecodeError):
        request_id = str(uuid.uuid4())
        return None, JSONResponse(failure("INVALID_JSON", "Request body must be valid UTF-8 JSON.", request_id), status_code=400)

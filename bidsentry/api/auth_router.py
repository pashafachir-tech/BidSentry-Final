"""FastAPI routes for the Pokja / Vendor role login."""

from __future__ import annotations

import json
import uuid

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from bidsentry.app import Application
from bidsentry.schemas.api import SessionInfo
from bidsentry.core.auth import SESSION_COOKIE, SESSION_TTL_SECONDS, AuthError, Role, describe, login, role_from_token
from bidsentry.types.responses import failure, success


def session_role(request: Request, application: Application) -> str | None:
    role = role_from_token(request.cookies.get(SESSION_COOKIE), application.settings)
    return role.value if role else None


def create_auth_router(application: Application) -> APIRouter:
    router = APIRouter(prefix="/api/auth", tags=["auth"])

    def _session(role: Role | None) -> dict:
        return SessionInfo.model_validate(describe(role, application.settings)).model_dump(mode="json")

    @router.get("/me")
    async def me(request: Request) -> JSONResponse:
        role = role_from_token(request.cookies.get(SESSION_COOKIE), application.settings)
        return JSONResponse(success(_session(role), str(uuid.uuid4())))

    @router.post("/login")
    async def do_login(request: Request) -> JSONResponse:
        request_id = str(uuid.uuid4())
        if request.headers.get("content-type", "").split(";", 1)[0].strip().casefold() != "application/json":
            return JSONResponse(failure("UNSUPPORTED_MEDIA_TYPE", "Content-Type must be application/json.", request_id), status_code=415)
        body = await request.body()
        if len(body) > 4096:
            return JSONResponse(failure("PAYLOAD_TOO_LARGE", "Data login terlalu besar.", request_id), status_code=413)
        try:
            payload = json.loads(body.decode("utf-8") or "{}")
        except (UnicodeDecodeError, json.JSONDecodeError):
            return JSONResponse(failure("INVALID_JSON", "Request body must be valid UTF-8 JSON.", request_id), status_code=400)
        if not isinstance(payload, dict):
            return JSONResponse(failure("INVALID_REQUEST", "Request body must be a JSON object.", request_id), status_code=400)
        client = request.client.host if request.client else ""
        try:
            token = login(payload.get("role"), payload.get("pin"), application.settings, client=client)
        except AuthError as exc:
            if exc.code in {"INVALID_PIN", "TOO_MANY_ATTEMPTS"}:
                application.audit_log.append({"event_type": "auth.login_failed", "role": str(payload.get("role") or "")[:16], "reason": exc.code})
            headers = {"Retry-After": str(exc.retry_after)} if exc.retry_after else None
            return JSONResponse(failure(exc.code, exc.message, request_id), status_code=exc.status, headers=headers)
        role = Role(str(payload.get("role")).strip().casefold())
        application.audit_log.append({"event_type": "auth.login", "role": role.value})
        response = JSONResponse(success(_session(role), request_id))
        response.set_cookie(
            SESSION_COOKIE, token, max_age=SESSION_TTL_SECONDS, httponly=True, samesite="strict",
            # Mark Secure whenever the browser actually talks HTTPS (directly or via a TLS proxy).
            # Tying it to the access token broke login on plain-HTTP LAN deployments.
            secure=request.url.scheme == "https" or request.headers.get("x-forwarded-proto", "").casefold() == "https",
            path="/",
        )
        return response

    @router.post("/logout")
    async def do_logout() -> JSONResponse:
        response = JSONResponse(success(_session(None), str(uuid.uuid4())))
        response.delete_cookie(SESSION_COOKIE, path="/")
        return response

    return router


__all__ = ["create_auth_router", "session_role"]

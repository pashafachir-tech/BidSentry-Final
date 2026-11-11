"""Consistent JSON envelope helpers for the HTTP API."""

from __future__ import annotations

from typing import Any


def success(data: Any, request_id: str) -> dict[str, Any]:
    return {"data": data, "meta": {"request_id": request_id, "schema_version": "1.0"}}


def failure(code: str, message: str, request_id: str, details: list[dict[str, str]] | None = None) -> dict[str, Any]:
    return {
        "error": {"code": code, "message": message, "details": details or []},
        "meta": {"request_id": request_id, "schema_version": "1.0"},
    }

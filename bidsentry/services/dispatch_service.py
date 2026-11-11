"""Composio dispatch facade; unavailable integrations return no fabricated artifacts."""

from __future__ import annotations

from typing import Any

from bidsentry.lib.pii import mask_value


class DispatchService:
    def __init__(self, settings: Any = None) -> None:
        self.settings = settings

    def dispatch(self, payload: dict[str, Any]) -> dict[str, Any]:
        safe_payload = mask_value(payload)
        try:
            from bidsentry.services.composio_dispatcher import dispatch_tender_workspace
            result = dispatch_tender_workspace(safe_payload, settings=self.settings)
        except Exception as exc:  # Keep the local app available when an optional connector fails.
            result = {
                "status": "unavailable",
                "message": "Connector tidak tersedia; tidak ada tindakan yang dijalankan.",
                "actions": {},
                "errors": [type(exc).__name__],
            }
        if not isinstance(result, dict):
            return {"status": "unavailable", "message": "Connector mengembalikan respons yang tidak valid; tidak ada tindakan yang dijalankan.", "actions": {}, "errors": ["invalid_connector_response"]}
        return result

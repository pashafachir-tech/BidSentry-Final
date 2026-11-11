"""Workspace dispatch controller."""

from __future__ import annotations

from typing import Any

from bidsentry.lib.audit_log import AuditLog
from bidsentry.services.dispatch_service import DispatchService
from bidsentry.types.schemas import DispatchRequest, ValidationError


class DispatchController:
    def __init__(self, service: DispatchService, audit_log: AuditLog):
        self.service = service
        self.audit_log = audit_log

    def create(self, payload: Any, *, require_external_consent: bool = False) -> dict[str, Any]:
        request = DispatchRequest.from_payload(payload)
        if require_external_consent and not request.payload["allow_external_processing"]:
            raise ValidationError("Setujui pengiriman ringkasan ke Composio sebelum menjalankan tindak lanjut.", [{"field": "allow_external_processing", "issue": "consent_required"}])
        dispatch_payload = {key: value for key, value in request.payload.items() if key != "allow_external_processing"}
        result = self.service.dispatch(dispatch_payload)
        self.audit_log.append({
            "event_type": "workspace.dispatch",
            "verdict": str(request.payload.get("verdict", "UNKNOWN"))[:80],
            "mode": "live" if result.get("status") in {"success", "partial"} else "unavailable",
            "actions": sorted((result.get("actions") or {}).keys()),
            "status": result.get("status", "unknown"),
        })
        return result

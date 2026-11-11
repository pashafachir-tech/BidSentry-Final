"""Validated request schemas shared by API controllers."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any


class ValidationError(ValueError):
    def __init__(self, message: str, details: list[dict[str, str]] | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or []


@dataclass(frozen=True)
class DispatchRequest:
    payload: dict[str, Any]

    @classmethod
    def from_payload(cls, payload: Any) -> "DispatchRequest":
        if not isinstance(payload, dict):
            raise ValidationError("Request body must be a JSON object.", [{"field": "$", "issue": "expected_object"}])
        allowed = {"nama_paket", "verdict", "risk_level", "alasan_utama", "catatan", "tender_id", "email_penerima", "allow_external_processing"}
        unknown = sorted(set(payload) - allowed)
        if unknown:
            raise ValidationError("Ada kolom tindak lanjut yang tidak dikenal.", [{"field": key, "issue": "unknown_field"} for key in unknown])

        package_name = payload.get("nama_paket", "")
        if not isinstance(package_name, str) or not package_name.strip() or len(package_name) > 240:
            raise ValidationError("Nama paket wajib diisi dan maksimal 240 karakter.", [{"field": "nama_paket", "issue": "invalid_value"}])
        verdict = payload.get("verdict", "REVIEW_REQUIRED")
        if not isinstance(verdict, str) or len(verdict) > 80:
            raise ValidationError("Status review tidak valid.", [{"field": "verdict", "issue": "invalid_value"}])
        risk_level = payload.get("risk_level", "NOT_ASSESSABLE")
        if risk_level not in {"NOT_ASSESSABLE", "LOW", "MEDIUM", "HIGH", "CRITICAL"}:
            raise ValidationError("Tingkat risiko tidak valid.", [{"field": "risk_level", "issue": "invalid_value"}])
        reasons = payload.get("alasan_utama", payload.get("catatan", []))
        if isinstance(reasons, str):
            reasons = [reasons]
        if not isinstance(reasons, list) or len(reasons) > 5 or any(not isinstance(item, str) or len(item) > 500 for item in reasons):
            raise ValidationError("Ringkasan tindak lanjut maksimal berisi 5 teks, masing-masing 500 karakter.", [{"field": "alasan_utama", "issue": "invalid_value"}])
        tender_id = payload.get("tender_id", "")
        if not isinstance(tender_id, str) or len(tender_id) > 80:
            raise ValidationError("ID paket tidak valid.", [{"field": "tender_id", "issue": "invalid_value"}])
        consent = payload.get("allow_external_processing", False)
        if not isinstance(consent, bool):
            raise ValidationError("Persetujuan pengiriman harus berupa pilihan ya/tidak.", [{"field": "allow_external_processing", "issue": "expected_boolean"}])
        recipient = payload.get("email_penerima", "")
        if not isinstance(recipient, str) or len(recipient) > 254 or (recipient and not re.fullmatch(r"[^\s@]+@[^\s@]+", recipient.strip())):
            raise ValidationError("Alamat email penerima tidak valid.", [{"field": "email_penerima", "issue": "invalid_value"}])
        normalized = {
            "nama_paket": package_name.strip(),
            "verdict": verdict.strip() or "REVIEW_REQUIRED",
            "risk_level": risk_level,
            "alasan_utama": [item.strip() for item in reasons if item.strip()],
            "tender_id": tender_id.strip(),
            "email_penerima": recipient.strip(),
            "allow_external_processing": consent,
        }
        return cls(normalized)

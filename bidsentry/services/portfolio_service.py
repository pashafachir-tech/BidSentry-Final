"""Portfolio views built only from completed, locally recorded audits."""

from __future__ import annotations

import math
import statistics
from datetime import datetime, timezone
from typing import Any

from bidsentry.lib.audit_log import AuditLog


class PortfolioService:
    def __init__(self, audit_log: AuditLog):
        self.audit_log = audit_log

    def list_audits(self, query: str = "", risk: str = "ALL", role: str | None = None) -> list[dict[str, Any]]:
        rows = [self._history_row(event) for event in self.audit_log.recent()]
        if role:
            # Pokja and Vendor workspaces are separate; legacy rows without an owner stay visible.
            rows = [row for row in rows if row.get("owner_role") in (None, role)]
        normalized_query = query.strip().casefold()
        normalized_risk = risk.strip().upper()
        if normalized_query:
            rows = [row for row in rows if normalized_query in " ".join(str(row.get(key, "")) for key in ("package_name", "tender_id", "agency", "company_name", "risk_level")).casefold()]
        if normalized_risk not in {"", "ALL"}:
            rows = [row for row in rows if row.get("risk_level") == normalized_risk]
        return rows

    def overview(self, role: str | None = None) -> dict[str, Any]:
        rows = self.list_audits(role=role)
        levels = ("NOT_ASSESSABLE", "LOW", "MEDIUM", "HIGH", "CRITICAL")
        distribution = {level: sum(row.get("risk_level") == level for row in rows) for level in levels}
        runtimes = [
            float(value) for row in rows
            if isinstance((value := row.get("engine_duration_ms")), (int, float))
            and not isinstance(value, bool) and math.isfinite(value) and value >= 0
        ]
        return {
            "dataset_label": "Audit lokal tersimpan",
            "total_audits": len(rows), "local_audits_shown": len(rows),
            "review_required": distribution["HIGH"] + distribution["CRITICAL"],
            "risk_distribution": distribution,
            "local_engine_runtime": {"sample_count": len(runtimes), "median_ms": round(statistics.median(runtimes), 2) if runtimes else None, "window": "Maksimal 100 audit lokal terbaru.", "scope": "Durasi evaluasi yang direkam per audit."},
            "audits": rows, "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    def _history_row(event: dict[str, Any]) -> dict[str, Any]:
        risk = event.get("risk") if isinstance(event.get("risk"), dict) else {}
        summary = event.get("summary") if isinstance(event.get("summary"), dict) else {}
        findings = event.get("findings") if isinstance(event.get("findings"), list) else []
        normalized_findings = [
            {
                "id": item.get("id", "FINDING"),
                "category": item.get("category", "Review"),
                "clause": item.get("clause") or item.get("id", "Temuan evaluasi"),
                "status": item.get("status", "REVIEW"),
                "severity": item.get("severity", "MEDIUM"),
                "source": item.get("source") or "Audit tersimpan",
                "evidence": item.get("evidence") or "Bukti tidak disimpan dalam log.",
                "requirement_evidence": item.get("requirement_evidence"),
                "evidence_source": item.get("evidence_source"),
                "review_note": item.get("review_note", ""),
                **{key: item[key] for key in ("rule_family", "party", "objectionable", "legal_reference", "legal_verification", "origin", "calculation_ref", "threshold_unverified") if key in item},
            }
            for item in findings if isinstance(item, dict)
        ]
        return {
            "audit_id": event.get("audit_id", "local-audit"), "created_at": event.get("created_at", ""),
            "package_name": event.get("package_name") or "Audit pengadaan", "review_role": event.get("review_role", "procurement"),
            "tender_id": event.get("tender_id", ""), "agency": event.get("pokja_name", ""),
            "company_name": event.get("company_name", ""), "vendor_name": event.get("company_name") or "Tidak disimpan",
            "contract_value_idr": event.get("contract_value_idr"),
            "verdict": event.get("verdict", "REVIEW"), "risk_level": risk.get("level", "NOT_ASSESSABLE"),
            "risk_label": risk.get("label") or {"LOW": "Rendah", "MEDIUM": "Sedang", "HIGH": "Tinggi", "CRITICAL": "Kritis"}.get(str(risk.get("level")), "Tidak Dapat Dinilai"),
            "risk": risk, "owner_role": event.get("owner_role"), "proof_summary": event.get("proof_summary") or {},
            "summary": {**summary, "findings": len(normalized_findings)}, "findings": normalized_findings,
            "executive_summary": event.get("executive_summary") or event.get("evaluation", {}).get("executive_summary") or {},
            "penalty_simulation": event.get("penalty_simulation") or event.get("evaluation", {}).get("penalty_simulation") or {},
            "adendum_reconciliation": event.get("adendum_reconciliation") or event.get("evaluation", {}).get("adendum_reconciliation") or {},
            "contextual_extraction": event.get("contextual_extraction") or event.get("evaluation", {}).get("contextual_extraction") or {},
            "ai_governance_metadata": event.get("ai_governance_metadata") or event.get("evaluation", {}).get("ai_governance_metadata") or {},
            "source": "local_audit_log", "risk_method": risk.get("method", "legacy-score"),
            "engine_duration_ms": event.get("engine_duration_ms"),
            "has_source_text": bool(event.get("source_text") or event.get("has_source_text")),
            "coverage": event.get("coverage") or {},
            # Without this a stored audit loses its "AI + Aturan Python" / local badge after a reload.
            "engine_mode": event.get("engine_mode") if isinstance(event.get("engine_mode"), dict) else None,
        }

"""Audit and portfolio controllers."""

from __future__ import annotations

from typing import Any

from bidsentry.lib.audit_log import AuditLog
from bidsentry.services.audit_service import AuditService
from bidsentry.services.langflow_service import LangflowService
from bidsentry.services.portfolio_service import PortfolioService
from bidsentry.evaluators.engine import EvaluationRequest
from bidsentry.types.schemas import ValidationError


class AuditController:
    def __init__(self, audit_service: AuditService, langflow: LangflowService, audit_log: AuditLog, watsonx: Any = None):
        self.audit_service = audit_service
        self.langflow = langflow
        self.audit_log = audit_log
        self.watsonx = watsonx

    def create(self, payload: Any, role: str | None = None) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise ValidationError("Request body harus berupa objek JSON.", [{"field": "$", "issue": "expected_object"}])
        try:
            request = EvaluationRequest.model_validate(payload)
        except Exception as exc:
            from pydantic import ValidationError as PydanticValidationError
            if not isinstance(exc, PydanticValidationError):
                raise
            details = [{"field": ".".join(str(part) for part in item["loc"]), "issue": str(item["type"]), "message": str(item["msg"])} for item in exc.errors(include_url=False)]
            too_long = [item for item in exc.errors(include_url=False) if item.get("type") == "string_too_long"]
            if too_long:
                field = str(too_long[0]["loc"][-1])
                limit = (too_long[0].get("ctx") or {}).get("max_length")
                raise ValidationError(
                    f"Isi '{field}' terlalu panjang (maksimal {limit:,} karakter). Pecah dokumen menjadi beberapa bagian lalu audit per bagian.".replace(",", "."),
                    details,
                ) from exc
            raise ValidationError("Data evaluasi tidak lengkap atau formatnya tidak sesuai. Periksa kembali isian formulir.", details) from exc
        if not request.all_document_text:
            raise ValidationError("Masukkan setidaknya satu teks dokumen.", [{"field": "dok_pemilihan", "issue": "at_least_one_document_required"}])
        result = self.audit_service.audit(request)
        contextual = result.get("contextual_extraction", {})
        integration = {
            "status": contextual.get("status", "not_requested"),
            "advisory": None,
            "review_role": request.review_role,
            "message": contextual.get("message"),
            "provider": contextual.get("provider"),
        }
        result["integrations"] = {"langflow": integration}
        result["owner_role"] = role
        result["has_source_text"] = bool(request.all_document_text)

        from bidsentry.lib.pii import count_redacted_pii

        pii_tokens = count_redacted_pii(request.all_document_text)
        watsonx_status = self.watsonx.status() if self.watsonx else {"configured": False, "model_id": None}
        langflow_status = self.langflow.status() if self.langflow else {"configured": False}
        telemetry = contextual.get("telemetry") or {}
        ai_ran = contextual.get("status") == "success"

        ai_governance = {
            # What actually ran for THIS audit, taken from call telemetry, not from configuration.
            "ai_used_for_this_audit": ai_ran,
            "provider_used": telemetry.get("provider") if ai_ran else None,
            "model_used": telemetry.get("model_id") if ai_ran else None,
            "ai_call_status": contextual.get("status", "not_requested"),
            "role_of_ai": "Ekstraksi kutipan saja; verdict dan tingkat risiko dihitung aturan Python.",
            "configured_providers": {
                "watsonx": {"configured": watsonx_status.get("configured", False), "model_id": watsonx_status.get("model_id")},
                "langflow": {"configured": langflow_status.get("configured", False), "flow_id": langflow_status.get("flow_id")},
                "active_provider": langflow_status.get("active_provider"),
            },
            "mode": "ai_extraction_plus_local_rules" if ai_ran else "local_rules_only",
            "pii_governance": {
                "policy": "UU_27_2022_PDP",
                "status": "RULE_BASED_REDACTION",
                "redacted_token_count": pii_tokens,
                "scope": "pola NIK, NPWP, nomor rekening, telepon, dan email (tidak menyensor nama/alamat)",
                "deterministic_sanitization": True,
            },
            "guardrails": {
                "hallucination_prevention": "EXACT_SUBSTRING_LEXICAL_MATCHING",
                "ai_candidates_revalidated_by_python": True,
                "drift_monitoring": "NOT_IMPLEMENTED",
            },
            "orchestration": {
                "langflow_ready": langflow_status.get("configured", False),
                "flow_definition": "langflow/tender_extraction_flow.json",
            },
        }
        result["ai_governance_metadata"] = ai_governance

        if request.all_document_text:
            self.audit_log.save_source_text(
                result["audit_id"],
                request.all_document_text,
            )
        self.audit_log.append({
            "event_type": "audit.completed",
            "audit_id": result["audit_id"],
            "review_role": request.review_role,
            "owner_role": role,
            "package_name": request.package_name,
            "tender_id": request.tender_id,
            "notice_number": request.notice_number,
            "pokja_name": request.pokja_name,
            "company_name": request.company_name,
            "contract_value_idr": request.contract_value_idr,
            "verdict": result["verdict"],
            "risk": result["risk"],
            "summary": result["summary"],
            "engine_duration_ms": result.get("performance", {}).get("engine_duration_ms"),
            "findings": result["findings"],
            "executive_summary": result.get("executive_summary", {}),
            "penalty_simulation": result.get("penalty_simulation", {}),
            "adendum_reconciliation": result.get("adendum_reconciliation", {}),
            "contextual_extraction": result.get("contextual_extraction", {}),
            "ai_governance_metadata": ai_governance,
            "engine_mode": result.get("engine_mode"),
            "coverage": result.get("coverage", {}),
            "proof_log": result.get("proof_log", []),
            "proof_summary": result.get("proof_summary", {}),
            "has_source_text": bool(request.all_document_text),
            "integrations": {"langflow": integration.get("status", "not_requested")},
        })
        return result


class PortfolioController:
    def __init__(self, portfolio: PortfolioService):
        self.portfolio = portfolio

    def overview(self, role: str | None = None) -> dict[str, Any]:
        return self.portfolio.overview(role=role)

    def list_audits(self, query: str = "", risk: str = "ALL", role: str | None = None) -> dict[str, Any]:
        return {"audits": self.portfolio.list_audits(query, risk, role=role)}

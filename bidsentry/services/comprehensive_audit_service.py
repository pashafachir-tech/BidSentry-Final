"""Orchestrate the six evidence-based enterprise audit modules."""

from __future__ import annotations

import base64
import binascii
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from bidsentry.audits.default_predictor import predict_default_risk
from bidsentry.audits.financial import parse_boq_tables, parse_boq_text, run_financial_audit
from bidsentry.config import Settings
from bidsentry.core.audit_trail import HashChainedAuditTrail
from bidsentry.core.sandbox_defense import inspect_pdf, inspect_text_chunks
from bidsentry.evaluators.legal_mapper import map_findings
from bidsentry.evaluators.grounded_checker import GroundedChecker
from bidsentry.forensics.collusion import compare_proposals, scan_contract_dilution
from bidsentry.forensics.contract_diff import diff_contracts
from bidsentry.forensics.metadata import MAX_PDF_BYTES, compare_vendor_metadata, extract_pdf_metadata
from bidsentry.forensics.network_graph import build_entity_graph
from bidsentry.lib.pii import mask_text
from bidsentry.schemas.comprehensive import ComprehensiveAuditRequest, ComprehensiveAuditResponse, PageChunk
from bidsentry.schemas.audit_contracts import GroundedProviderResponse
from bidsentry.services.langflow_service import LangflowService
from bidsentry.vision.verifier import verify_artifacts


LOGGER = logging.getLogger("bidsentry.comprehensive_audit")


class ComprehensiveAuditInputError(ValueError):
    """A user-supplied PDF payload failed safe input validation."""


class ComprehensiveAuditService:
    def __init__(self, settings: Settings, langflow: LangflowService):
        trail_path = settings.audit_log_path.with_name(f"{settings.audit_log_path.stem}_comprehensive_chain.jsonl")
        self.trail = HashChainedAuditTrail(trail_path)
        self.langflow = langflow
        self.checker = GroundedChecker()

    def _model_label(self) -> str | None:
        if not self.langflow:
            return None
        settings = self.langflow.settings
        provider = self.langflow.active_provider()
        if provider == "watsonx":
            from bidsentry.services.watsonx_service import WatsonxService
            return WatsonxService(settings).default_model_id
        if provider == "langflow":
            return f"flow:{settings.langflow_flow_id}"
        return settings.llm_model_name or settings.gemini_model or None

    def audit(self, request: ComprehensiveAuditRequest, *, audit_run_id: str | None = None) -> dict[str, Any]:
        audit_run_id = audit_run_id or str(uuid.uuid4())
        target_pdf = _decode_pdf(request.pdf_base64) if request.pdf_base64 else None
        target_metadata = dict(request.document_metadata or {})
        extracted_pdf = extract_pdf_metadata(target_pdf) if target_pdf else {"status": "not_provided"}
        if extracted_pdf.get("status") in {"invalid_pdf", "rejected"}:
            raise ComprehensiveAuditInputError("PDF tidak dapat diproses atau melewati batas 500 halaman.")
        if target_pdf and extracted_pdf.get("status") == "extracted":
            target_metadata = {**extracted_pdf, **target_metadata}

        pages = list(request.document_chunks)
        extracted_pages = extracted_pdf.get("page_text", [])
        if not pages and extracted_pages:
            pages = [PageChunk.model_validate(item) for item in extracted_pages]

        vendor_records = self._vendor_records(request, target_metadata)
        metadata_comparison = compare_vendor_metadata(vendor_records)
        safe_metadata = {key: value for key, value in target_metadata.items() if key not in {"page_text", "page_visual_inventory", "page_tables"}}
        module_metadata = {
            "status": "metadata_provided" if extracted_pdf.get("status") == "not_provided" and target_metadata else extracted_pdf.get("status", "not_available"),
            "target_document": safe_metadata,
            "cross_vendor_comparison": metadata_comparison,
            "interpretation": "Metadata hanya sinyal investigasi dan tidak membuktikan kepemilikan bersama atau kolusi.",
        }

        boq_items = list(request.boq_items)
        if not boq_items:
            boq_items.extend(parse_boq_tables(extracted_pdf.get("page_tables", [])))
        if not boq_items:
            for page in pages:
                boq_items.extend(item.model_copy(update={"page_ref": page.page_ref}) for item in parse_boq_text(page.text))
        source_pages = {page.page_ref: page.text for page in pages}
        financial = run_financial_audit(boq_items, request.offered_total_price, request.hps_total_price, source_pages)

        sandbox = inspect_pdf(target_pdf) if target_pdf else inspect_text_chunks([page.model_dump(mode="python") for page in pages])
        sanitized_pages = {
            str(page.get("page_ref")): str(page.get("sanitized_text") or "")
            for page in sandbox.get("pages", [])
        }

        provider_result: dict[str, Any] = {}
        provider = None
        provider_status = self.langflow.status()
        if request.allow_external_processing and (provider_status.get("configured") or provider_status.get("structured_provider", {}).get("configured")):
            def call_structured_provider(prompt: str) -> str:
                result = self.langflow.run_structured_prompt(prompt, consent=True, response_model=GroundedProviderResponse)
                provider_result.update(result)
                if result.get("status") != "success" or not result.get("text"):
                    raise RuntimeError(str(result.get("status", "provider_unavailable")))
                return str(result["text"])
            provider = call_structured_provider
        grounded = self.checker.run(
            provider,
            mask_text(request.tender_regulations_and_hps),
            pages,
            supplied_candidates=request.candidate_evaluations,
            prompt_pages=[PageChunk(page_ref=page.page_ref, text=mask_text(sanitized_pages.get(page.page_ref, page.text))) for page in pages],
        )
        if provider_result and provider_result.get("status") != "success":
            grounded["llm_status"] = provider_result.get("status", "fallback")
            grounded["llm_error_type"] = provider_result.get("error_type")
        elif not request.allow_external_processing and not request.candidate_evaluations:
            grounded["llm_status"] = "not_requested"

        target_vendor = next((item for item in vendor_records if item["vendor_id"] == request.vendor_id), vendor_records[0])
        competitor_result = compare_proposals(vendor_records)
        contract_result = scan_contract_dilution(
            str(target_vendor.get("contract_text", "")),
            request.baseline_contract_text,
        )
        text_diff = diff_contracts(request.baseline_contract_text, str(target_vendor.get("contract_text", "")))
        entity_graph = build_entity_graph(vendor_records)
        collusion = {
            "status": "screened",
            "proposal_similarity": competitor_result,
            "contract_dilution": contract_result,
            "contract_text_diff": text_diff,
            "entity_network_alerts": entity_graph.get("alerts", []),
            "metadata_signal_count": len(metadata_comparison.get("alerts", [])),
            "interpretation": "Sinyal kemiripan dan perubahan klausul bukan kesimpulan bid-rigging atau pelanggaran hukum.",
        }

        artifact = verify_artifacts(request.artifact_signals, extracted_pdf.get("page_visual_inventory", []))
        run_time = datetime.now(timezone.utc).isoformat()
        benford = financial.get("benford_first_digit_screen", {})
        benford_alerts = ([{
            "anomaly_type": "BENFORD_DISTRIBUTION_SCREENING_FLAG",
            **benford,
        }] if benford.get("flag") else [])
        all_alerts = (
            sandbox.get("findings", [])
            + metadata_comparison.get("alerts", [])
            + financial.get("line_item_anomalies", [])
            + benford_alerts
            + contract_result.get("findings", [])
            + text_diff.get("findings", [])
            + entity_graph.get("alerts", [])
            + [item for item in competitor_result.get("comparisons", []) if item.get("screening_result") == "HIGH_SIMILARITY_REVIEW"]
            + [item for item in artifact.get("findings", []) if item.get("status") in {"SUSPICIOUS_RASTER_OVERLAY_SIGNAL", "DETECTED_UNVERIFIED"}]
        )
        legal_mapping = map_findings(all_alerts)
        execution_risk = predict_default_risk(request.default_risk_metrics)
        verdict = {
            "status": "REVIEW_REQUIRED",
            "composite_compliance_score": None,
            "risk_level": "ELEVATED" if all_alerts else "UNASSESSED",
            "primary_disqualification_reason": None,
            "automatic_disqualification": False,
            "reviewer_note": "Keluaran adalah sinyal triase. Tidak ada kesimpulan lulus/gagal, fraud, kolusi, diskualifikasi, atau keaslian yang ditetapkan otomatis.",
        }
        modules = {
            "module_1_document_metadata_forensics": module_metadata,
            "module_2_financial_and_boq_audit": financial,
            "module_3_grounded_evaluation": grounded,
            "module_4_bid_rigging_and_contract_dilution": collusion,
            "module_5_artifact_and_signature_verification": artifact,
            "module_7_pdf_sandbox_defense": sandbox,
            "module_8_entity_network_graph": entity_graph,
            "module_9_execution_risk_forecast": execution_risk,
            "module_10_statutory_mapping": legal_mapping,
            "ai_governance_metadata": {
                # Report the provider/model that actually answered, never a hard-coded claim.
                "foundation_model": self._model_label() if grounded.get("llm_status") == "success" else None,
                "provider": self.langflow.active_provider() if (self.langflow and grounded.get("llm_status") == "success") else None,
                "status": "CONFIGURED_ACTIVE" if (grounded.get("llm_status") == "success") else "LOCAL_GUARDRAIL_ACTIVE",
                "pii_governance": {
                    "policy": "UU_27_2022_PDP",
                    "status": "RULE_BASED_REDACTION",
                    "redacted_token_count": 0,
                    "scope": "pola NIK, NPWP, nomor rekening, telepon, dan email (tidak menyensor nama/alamat)",
                    "deterministic_sanitization": True,
                },
                "guardrails": {
                    "hallucination_prevention": "EXACT_SUBSTRING_LEXICAL_MATCHING",
                    "drift_monitoring": "NOT_IMPLEMENTED",
                    "statutory_alignment": "PERPRES_12_2021",
                },
                "orchestration": {
                    "langflow_ready": bool(self.langflow.status().get("configured")),
                    "flow_definition": "tender_extraction_flow.json",
                },
            },
        }
        quotes = self._collect_quotes(modules)
        trail = self.trail.append(
            audit_run_id=audit_run_id,
            input_payload=request.model_dump(mode="json"),
            extracted_quotes=quotes,
            scoring_weights={key: str(value) for key, value in request.scoring_weights.items()},
            verdict=verdict,
        )
        chain_state = self.trail.verify()
        trail["chain_valid_after_append"] = chain_state.get("valid", False)
        trail["records_checked"] = chain_state.get("records_checked", 0)
        modules["module_6_immutable_audit_trail"] = trail

        LOGGER.info(
            "comprehensive audit completed",
            extra={"audit_run_id": audit_run_id, "tender_id": request.tender_id, "vendor_id": request.vendor_id, "alert_count": len(all_alerts)},
        )
        response = ComprehensiveAuditResponse(
            audit_run_id=audit_run_id,
            tender_metadata={
                "tender_id": request.tender_id,
                "vendor_id": request.vendor_id,
                "vendor_name": request.vendor_name,
                "audit_timestamp": run_time,
            },
            executive_verdict=verdict,
            modules=modules,
            tamper_evident_audit_trail=trail,
        )
        return response.model_dump(mode="json")

    @staticmethod
    def _vendor_records(
        request: ComprehensiveAuditRequest,
        target_metadata: dict[str, Any],
    ) -> list[dict[str, Any]]:
        records: dict[str, dict[str, Any]] = {
            request.vendor_id: {
                "vendor_id": request.vendor_id,
                "vendor_name": request.vendor_name,
                "submission_timestamp": request.submission_timestamp,
                "document_metadata": target_metadata,
                "entities": request.entities,
                "technical_proposal_text": request.technical_proposal_text,
                "contract_text": request.contract_text,
                "embedding": request.embedding,
            },
        }
        for vendor in request.vendor_submissions:
            record = vendor.model_dump(mode="python")
            record.pop("pdf_base64", None)
            metadata = dict(record.get("document_metadata") or {})
            if vendor.pdf_base64:
                parsed = extract_pdf_metadata(_decode_pdf(vendor.pdf_base64))
                if parsed.get("status") in {"invalid_pdf", "rejected"}:
                    raise ComprehensiveAuditInputError(f"PDF vendor {vendor.vendor_id} tidak dapat diproses atau melewati batas halaman.")
                if parsed.get("status") == "extracted":
                    metadata = {**parsed, **metadata}
            record["document_metadata"] = metadata
            current = records.get(vendor.vendor_id, {})
            merged = {**current, **record}
            merged["document_metadata"] = {**(current.get("document_metadata") or {}), **metadata}
            merged["entities"] = {**(current.get("entities") or {}), **(record.get("entities") or {})}
            for text_key in ("technical_proposal_text", "contract_text"):
                if not merged.get(text_key):
                    merged[text_key] = current.get(text_key, "")
            if merged.get("submission_timestamp") is None:
                merged["submission_timestamp"] = current.get("submission_timestamp")
            records[vendor.vendor_id] = merged
        return list(records.values())

    @staticmethod
    def _collect_quotes(modules: dict[str, Any]) -> list[dict[str, Any]]:
        quotes: list[dict[str, Any]] = []
        def visit(value: Any) -> None:
            if isinstance(value, dict):
                for key, child in value.items():
                    if key in {"verbatim_quote", "source_quote", "baseline_quote", "vendor_quote"} and isinstance(child, str) and child:
                        quotes.append({"field": key, "quote": child, "page_ref": value.get("page_ref")})
                    else:
                        visit(child)
            elif isinstance(value, list):
                for child in value:
                    visit(child)
        visit(modules)
        return quotes


def _decode_pdf(encoded: str) -> bytes:
    try:
        value = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ComprehensiveAuditInputError("pdf_base64 must contain valid base64 data.") from exc
    if not value or len(value) > MAX_PDF_BYTES:
        raise ComprehensiveAuditInputError("Each PDF must be between 1 byte and 8 MiB.")
    if not value.startswith(b"%PDF-"):
        raise ComprehensiveAuditInputError("Uploaded file does not have a PDF signature.")
    return value

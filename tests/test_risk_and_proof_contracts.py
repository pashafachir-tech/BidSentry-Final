"""Contracts for the risk decision table, proof ledger and AI-candidate validation."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from bidsentry.config import Settings
from bidsentry.core.auth import AuthError, Role, issue_token, login, require_role, role_from_token
from bidsentry.evaluators.engine import EvaluationEngine, EvaluationRequest
from bidsentry.evaluators.rule_catalog import CATALOG, family_of
from bidsentry.generators._document_support import normalize_finding
from bidsentry.services import risk_engine
from bidsentry.services.langflow_service import LangflowService, strip_code_fence


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return replace(Settings.from_environment(), audit_log_path=tmp_path / "audit.jsonl", langflow_enabled=False, langflow_flow_id="", llm_provider="", gemini_api_key="", host="127.0.0.1", pokja_pin="", vendor_pin="")


def _f(code: str, status: str, severity: str = "HIGH") -> dict:
    return {"id": code, "status": status, "severity": severity, "clause": code}


# ---------------------------------------------------------------- risk table
def test_single_critical_rule_gap_is_kritis_not_medium() -> None:
    result = risk_engine.assess([_f("CON-PENALTY", "GAP")], requirements_recognized=1)
    assert (result.level, result.verdict, result.rule_applied) == ("CRITICAL", "NO-GO", "R1")
    assert result.label == "Kritis"


def test_three_high_gaps_accumulate_to_kritis_and_one_is_tinggi() -> None:
    assert risk_engine.assess([_f("SPEC-LOCKIN-CPU", "GAP")], requirements_recognized=1).level == "HIGH"
    many = [_f(code, "GAP") for code in ("SPEC-LOCKIN-CPU", "PROC-TIMELINE-COMPRESSED", "SPEC-REGIONAL-LOCKIN")]
    assert risk_engine.assess(many, requirements_recognized=3).rule_applied == "R2"


def test_expiring_is_sedang_and_unreadable_is_not_assessable() -> None:
    expiring = risk_engine.assess([_f("ADM-SBU", "EXPIRING")], requirements_recognized=1)
    assert (expiring.level, expiring.verdict) == ("MEDIUM", "BELUM CUKUP BUKTI")
    empty = risk_engine.assess([], requirements_recognized=0)
    assert (empty.level, empty.label, empty.verdict) == ("NOT_ASSESSABLE", "Tidak Dapat Dinilai", "TIDAK ADA SYARAT TERBACA")


def test_no_go_is_never_low_risk() -> None:
    for code, rule in CATALOG.items():
        for severity in ("HIGH", "MEDIUM", "LOW"):
            result = risk_engine.assess([_f(code, "GAP", severity)], requirements_recognized=1)
            assert result.verdict == "NO-GO" and result.level in {"MEDIUM", "HIGH", "CRITICAL"}, (code, severity)


def test_reviewer_exclusion_recomputes_assessment() -> None:
    result = risk_engine.assess([_f("CON-PENALTY", "GAP"), _f("ADM-NIB", "TERPENUHI", "MEDIUM")], requirements_recognized=2, excluded_finding_ids=["CON-PENALTY"])
    assert result.verdict == "GO" and result.excluded_by_reviewer == ["CON-PENALTY"]


# ------------------------------------------------------------- engine output
def test_engine_emits_catalog_backed_findings_and_proof_log(settings: Settings) -> None:
    result = EvaluationEngine(settings).evaluate(EvaluationRequest(
        dok_pemilihan="Pagu Anggaran sebesar Rp 1.000.000.000. Total HPS Rp 1.250.000.000.",
        contract_draft="Denda keterlambatan 1/1000 per hari tanpa batas maksimal.",
        contract_value_idr=1_000_000_000,
    ))
    assert "risk_score" not in result
    for finding in result["findings"]:
        assert finding["rule_family"] == family_of(finding["id"])
        assert finding["legal_verification"] in {"DIPERIKSA_NASKAH", "DIPERIKSA_SEKUNDER", "PERLU_VERIFIKASI_HUKUM"}
        assert all(citation["status"] for citation in finding["legal_basis"])
    kinds = [step["kind"] for step in result["proof_log"]]
    assert kinds[0] == "input" and "decision" in kinds and "calculation" in kinds
    over = next(step for step in result["proof_log"] if step["inputs"].get("rule") == "FIN-OVER-BUDGET")
    assert over["outputs"]["deficit_idr"] == 250_000_000
    ai_step = next(step for step in result["proof_log"] if step["kind"] == "ai_call")
    assert ai_step["status"] == "skipped"
    assert not any("dok_pemilihan" in json.dumps(step["outputs"]) and "Pagu Anggaran sebesar" in json.dumps(step) for step in result["proof_log"] if step["kind"] == "input")


def test_ai_candidates_are_revalidated_before_affecting_verdict(settings: Settings) -> None:
    langflow = LangflowService(settings)
    response = {
        "scope": None,
        "brand_lockin_signals": [
            {"quote": "Kendaraan operasional minimal 7 penumpang", "source": "Dokumen pemilihan", "summary": "model"},
        ],
        "timeline_anomalies": [{"quote": "Masa sanggah 5 hari kerja", "source": "Dokumen pemilihan", "summary": "durasi"}],
        "addendum_changes": [], "personnel_qualifications": [], "sla_uptime": [],
    }
    langflow.run_structured_prompt = MagicMock(return_value={"status": "success", "text": json.dumps(response), "provider": "watsonx", "telemetry": {"provider": "watsonx", "model_id": "ibm/granite-3-8b-instruct", "latency_ms": 812.0, "input_tokens": 900, "output_tokens": 120}})
    result = EvaluationEngine(settings, langflow).evaluate(EvaluationRequest(
        dok_pemilihan="Kendaraan operasional minimal 7 penumpang.\nMasa sanggah 5 hari kerja.",
        allow_external_processing=True,
    ))
    # Neither candidate passes the deterministic rules, so the AI cannot create a red flag;
    # the brand candidate only asks a human to look and stays out of the decision table.
    statuses = {item["category"]: item["validation"]["status"] for item in result["contextual_extraction"]["items"]}
    assert statuses == {"brand_lockin_signals": "needs_human_review", "timeline_anomalies": "not_confirmed"}
    assert not any(finding["origin"] == "ai_extraction_python_validated" for finding in result["findings"])
    assert result["risk"]["counts"]["REVIEW"] == 0
    call = next(step for step in result["proof_log"] if step["kind"] == "ai_call")
    assert call["outputs"]["provider"] == "watsonx" and call["outputs"]["input_tokens"] == 900 and call["duration_ms"] == 812.0
    assert any(step["kind"] == "pii_redaction" for step in result["proof_log"])


def test_confirmed_ai_candidate_is_marked_with_origin(settings: Settings) -> None:
    langflow = LangflowService(settings)
    quote = "Unit wajib menggunakan prosesor Intel Xeon Gold 6430"
    response = {"scope": None, "brand_lockin_signals": [{"quote": quote, "source": "Dokumen pemilihan", "summary": "merek"}], "timeline_anomalies": [], "addendum_changes": [], "personnel_qualifications": [], "sla_uptime": []}
    langflow.run_structured_prompt = MagicMock(return_value={"status": "success", "text": json.dumps(response), "telemetry": {"provider": "langflow"}})
    engine = EvaluationEngine(settings, langflow)
    items = [{"category": "brand_lockin_signals", "quote": quote, "source": "Dokumen pemilihan"}]
    findings: list[dict] = []
    from bidsentry.core.proof_log import ProofLog
    engine._validate_ai_candidates(items, findings, ProofLog(), lockin_patterns=[r"\bIntel\s+Xeon\b"], min_bidding_days=7, min_sanggah_days=5)
    assert findings[0]["id"] == "SPEC-AI-LOCKIN" and findings[0]["origin"] == "ai_extraction_python_validated"
    assert items[0]["validation"]["status"] == "confirmed"


# ------------------------------------------------------------- integrations
def test_langflow_output_parser_ignores_request_echo_and_session_id() -> None:
    response = {"session_id": "abc", "outputs": [{"inputs": {"input_value": "PROMPT"}, "outputs": [{"results": {"message": {"text": "```json\n{\"scope\": null}\n```"}}}]}]}
    text = LangflowService.extract_langflow_output(response)
    assert text and "PROMPT" not in text and text != "abc"
    assert strip_code_fence(text) == '{"scope": null}'


def test_document_rows_never_render_empty_for_engine_findings() -> None:
    row = normalize_finding({"id": "CON-PENALTY", "clause": "Denda tanpa batas", "status": "GAP", "requirement_evidence": "Denda 1/1000 tanpa batas", "source": "Draf kontrak", "review_note": "Catatan"})
    assert row["title"] == "Denda tanpa batas" and row["quote"] == "Denda 1/1000 tanpa batas" and row["status_label"] == "Kesenjangan"


# --------------------------------------------------------------------- auth
def test_role_tokens_are_signed_and_role_gates_enforced(settings: Settings) -> None:
    token = login("vendor", None, settings)
    assert role_from_token(token, settings) is Role.VENDOR
    assert role_from_token(token[:-1] + ("0" if token[-1] != "0" else "1"), settings) is None
    assert role_from_token(issue_token(Role.POKJA, settings, now=0), settings) is None  # expired
    with pytest.raises(AuthError) as missing:
        require_role(None, Role.POKJA)
    assert missing.value.status == 401
    with pytest.raises(AuthError) as wrong:
        require_role("vendor", Role.POKJA)
    assert wrong.value.status == 403


def test_pin_required_when_configured_or_non_local(settings: Settings) -> None:
    with pytest.raises(AuthError):
        login("pokja", "salah", replace(settings, pokja_pin="2468"))
    assert role_from_token(login("pokja", "2468", replace(settings, pokja_pin="2468")), settings) is Role.POKJA
    with pytest.raises(AuthError) as disabled:
        login("vendor", None, replace(settings, host="0.0.0.0"))
    assert disabled.value.code == "ROLE_DISABLED"


# ------------------------------------------------------------- resilience
def test_slow_provider_falls_back_to_local_rules(settings: Settings) -> None:
    import time as _time
    langflow = LangflowService(replace(settings, langflow_timeout_seconds=0.1))

    def _hang(prompt: str, consent: bool) -> dict:
        _time.sleep(12)
        return {"status": "success", "text": "{}"}

    langflow.run_structured_prompt = _hang  # type: ignore[assignment]
    engine = EvaluationEngine(replace(settings, langflow_timeout_seconds=0.1), langflow)
    started = _time.perf_counter()
    result = engine.evaluate(EvaluationRequest(contract_draft="Denda 1/1000 per hari tanpa batas maksimal.", allow_external_processing=True))
    assert _time.perf_counter() - started < 10  # budget is ~5 s; the provider would take 12 s
    assert result["engine_mode"]["mode"] == "local_fallback"
    assert result["engine_mode"]["label"] == "Mode Deterministik Lokal (Fallback Aktif)"
    assert result["verdict"] == "NO-GO"  # local rules still produce the full audit


def test_provider_exception_never_breaks_the_audit(settings: Settings) -> None:
    langflow = LangflowService(settings)
    langflow.run_structured_prompt = MagicMock(side_effect=RuntimeError("boom"))
    result = EvaluationEngine(settings, langflow).evaluate(EvaluationRequest(dok_pemilihan="Masa sanggah 2 hari kerja.", allow_external_processing=True))
    assert result["engine_mode"]["mode"] == "local_fallback"
    assert result["contextual_extraction"]["status"] == "provider_error"


def test_session_secret_survives_restart(settings: Settings) -> None:
    from bidsentry.core import auth
    token = login("pokja", None, settings)
    auth._SECRET_CACHE.clear()  # simulate a fresh process
    assert role_from_token(token, settings) is Role.POKJA
    assert (settings.audit_log_path.parent / auth.SECRET_FILENAME).is_file()

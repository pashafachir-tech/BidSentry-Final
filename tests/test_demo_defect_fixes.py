"""Regressions for the defects found in the end-to-end run against live watsonx (Nov 2026)."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

from bidsentry.audits.financial import parse_boq_text
from bidsentry.config import Settings
from bidsentry.evaluators.engine import EvaluationEngine, EvaluationRequest
from bidsentry.lib.pii import mask_text, recover_unmasked_quote
from bidsentry.services import unit_economics
from bidsentry.services.langflow_service import LangflowService, classify_exception

# How a PDF text layer delivers one sentence: broken over lines.
PDF_TEXT = (
    "Server wajib menggunakan prosesor Intel Xeon Platinum generasi\n"
    "Emerald Rapids, interkoneksi bus UPI 4.0, dan modul manajemen\n"
    "remote eksklusif Dell iDRAC 10.\n"
    "Masa sanggah ditetapkan selama 2 (dua)\n"
    "hari kerja."
)
CONTRACT = "Denda keterlambatan 1/1000 per hari\ndari nilai kontrak tanpa batas maksimal."


def _settings(tmp_path: Path) -> Settings:
    return replace(
        Settings.from_environment(), audit_log_path=tmp_path / "audit.jsonl", langflow_enabled=False, langflow_flow_id="",
        llm_provider="", gemini_api_key="",
    )


# ------------------------------------------------------- quotes from PDF text
def test_quote_written_on_one_line_matches_a_sentence_wrapped_by_the_pdf() -> None:
    quote = "Server wajib menggunakan prosesor Intel Xeon Platinum generasi Emerald Rapids, interkoneksi bus UPI 4.0"
    recovered = recover_unmasked_quote(quote, PDF_TEXT)
    assert recovered is not None and recovered in PDF_TEXT  # still a verbatim slice of the source
    assert "generasi\nEmerald Rapids" in recovered
    assert recover_unmasked_quote("Masa  sanggah ditetapkan\tselama 2 (dua) hari kerja.", PDF_TEXT) == "Masa sanggah ditetapkan selama 2 (dua)\nhari kerja."


def test_whitespace_tolerance_does_not_accept_changed_words() -> None:
    assert recover_unmasked_quote("Server wajib menggunakan prosesor AMD EPYC generasi Emerald Rapids", PDF_TEXT) is None
    assert recover_unmasked_quote("Masa sanggah ditetapkan selama 5 (lima) hari kerja.", PDF_TEXT) is None
    assert recover_unmasked_quote("   \n ", PDF_TEXT) is None


def test_redacted_quote_is_recovered_across_a_line_wrap() -> None:
    source = "Penanggung jawab penyedia memiliki NIK Direktur: 3171012345670001 dan\nberkedudukan di Jakarta Selatan sesuai akta."
    masked_on_one_line = " ".join(mask_text(source).split())
    assert "[NIK-REDACTED]" in masked_on_one_line
    assert recover_unmasked_quote(masked_on_one_line, source) == source


# --------------------------------------------------------- AI quote sources
def test_ai_quote_source_is_the_document_that_holds_it_not_the_models_label(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    langflow = LangflowService(settings)
    reply = {
        "scope": None,
        "brand_lockin_signals": [
            {"quote": "Server wajib menggunakan prosesor Intel Xeon Platinum generasi Emerald Rapids", "source": "Halaman 99", "summary": "merek"},
            {"quote": "Server wajib menggunakan prosesor buatan dalam negeri", "source": "Dokumen pemilihan", "summary": "tidak ada di dokumen"},
        ],
        "timeline_anomalies": [{"quote": "Masa sanggah ditetapkan selama 2 (dua) hari kerja.", "source": "Dokumen pemilihan", "summary": "durasi"}],
        "addendum_changes": [], "personnel_qualifications": [],
        "sla_uptime": [{"quote": "Denda keterlambatan 1/1000 per hari dari nilai kontrak tanpa batas maksimal.", "source": "", "summary": "denda"}],
    }
    langflow.run_structured_prompt = lambda prompt, consent: {"status": "success", "text": json.dumps(reply), "telemetry": {"provider": "watsonx", "model_id": "test-model"}}  # type: ignore[method-assign]
    result = EvaluationEngine(settings, langflow).evaluate(EvaluationRequest(dok_pemilihan=PDF_TEXT, contract_draft=CONTRACT, allow_external_processing=True))

    extraction = result["contextual_extraction"]
    assert extraction["rejected_quotes_count"] == 1
    assert [(item["category"], item["source"]) for item in extraction["items"]] == [
        ("brand_lockin_signals", "Dokumen pemilihan"), ("timeline_anomalies", "Dokumen pemilihan"), ("sla_uptime", "Draf kontrak"),
    ]
    assert all(item["quote"] in PDF_TEXT or item["quote"] in CONTRACT for item in extraction["items"])
    statuses = {item["category"]: item["validation"]["status"] for item in extraction["items"]}
    assert statuses["brand_lockin_signals"] == "corroborated" and statuses["timeline_anomalies"] == "corroborated"


# ------------------------------------------------------------ unit economics
def test_machine_time_does_not_count_the_ai_call_twice(tmp_path: Path) -> None:
    audit = {
        "audit_id": "a", "performance": {"engine_duration_ms": 8000.0},  # measured around the whole audit, AI call included
        "proof_log": [{"kind": "ai_call", "status": "ok", "duration_ms": 7900.0, "outputs": {"input_tokens": 2000, "output_tokens": 300}}],
    }
    economics = unit_economics.compute(audit, _settings(tmp_path))
    assert economics["machine_seconds"] == 8.0
    assert economics["tokens"]["basis"] == "measured"


# ------------------------------------------------------------- BoQ from PDF
BOQ_CELLS = (
    "RINCIAN ANGGARAN BIAYA\n"
    "No\nUraian Pekerjaan\nVolume\nSatuan\nHarga Satuan (Rp)\nTotal Harga (Rp)\n"
    "3.1\nGalian Tanah Biasa Badan Jalan\n4.500,00\nM3\n42.000\n188.000.000\n"
    "3.2\nTimbunan Pilihan dari Sumber Galian\n3.200,00\nM3\n92.000\n294.400.000\n"
    "SUBTOTAL\nTotal Rincian\n482.400.000\n"
)


def test_boq_table_flattened_to_one_cell_per_line_is_read() -> None:
    items = parse_boq_text(BOQ_CELLS)
    assert [(item.item_code, item.description, int(item.volume), item.unit, int(item.unit_price_offered), int(item.total_offered)) for item in items] == [
        ("3.1", "Galian Tanah Biasa Badan Jalan", 4500, "M3", 42000, 188_000_000),
        ("3.2", "Timbunan Pilihan dari Sumber Galian", 3200, "M3", 92000, 294_400_000),
    ]
    assert all(item.source_quote in BOQ_CELLS for item in items)


def test_boq_cell_reading_stops_instead_of_shifting_columns() -> None:
    wrapped = BOQ_CELLS.replace("Timbunan Pilihan dari Sumber Galian\n", "Timbunan Pilihan dari\nSumber Galian\n")
    assert [item.item_code for item in parse_boq_text(wrapped)] == ["3.1"]  # the wrapped cell ends the table
    prose = "Volume pekerjaan dihitung per satuan.\nHarga satuan mengikuti HPS.\nTotal harga termasuk pajak.\nUraian pekerjaan ada di KAK."
    assert parse_boq_text(prose) == []


def test_audit_flags_arithmetic_error_in_a_pdf_boq_table(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    result = EvaluationEngine(settings, LangflowService(settings)).evaluate(EvaluationRequest(dok_pemilihan=BOQ_CELLS))
    finding = next(item for item in result["findings"] if item["id"] == "FIN-BOQ-ARITHMETIC")
    assert finding["status"] == "GAP" and "Rp 189.000.000 hitung vs Rp 188.000.000 tertulis" in finding["review_note"]
    assert result["verdict"] == "NO-GO"


# ------------------------------------------------------ provider error class
def test_wrong_watsonx_api_key_is_reported_as_rejected_credentials() -> None:
    invalid_credentials = type("InvalidCredentialsError", (Exception,), {})
    # The IAM message carries request ids; digits such as "429" in them must not turn this into a rate limit.
    message = 'Attempt of authenticating connection to service failed. Error: {"errorCode":"BXNIM0415E","context":{"requestId":"a429b-4010x"}}'
    assert classify_exception(invalid_credentials(message)) == "auth_failed"
    assert classify_exception(RuntimeError("HTTP 429 Too Many Requests")) == "rate_limited"
    assert classify_exception(TimeoutError("timed out")) == "timeout"

"""Regressions found by adversarial probes on realistic procurement wording.

Every clause here was written to resemble standard tender language or a real
evasion. The benchmark suites only hold short documents, so these guard the
behaviour the benchmark cannot see.
"""

from __future__ import annotations

import base64
import dataclasses
import hashlib
import json
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from starlette.testclient import TestClient

import bidsentry.evaluators.engine as engine_module
from bidsentry.asgi import create_asgi_app
from bidsentry.config import AI_CONTEXT_MAX_CHARS, Settings
from bidsentry.evaluators.engine import EvaluationEngine, EvaluationRequest, has_valid_equivalency
from bidsentry.lib.audit_log import AuditLog
from bidsentry.lib.pii import mask_text
from bidsentry.services.langflow_service import LangflowService
from bidsentry.services.risk_engine import decision_table


@pytest.fixture
def engine() -> EvaluationEngine:
    return EvaluationEngine()


def _statuses(result: dict) -> dict[str, str]:
    return {item["id"]: item["status"] for item in result["findings"]}


# ------------------------------------------------------------ standard clauses
@pytest.mark.parametrize("cap", [
    "Besarnya denda tidak melampaui besarnya Jaminan Pelaksanaan.",
    "Denda paling tinggi sebesar nilai Jaminan Pelaksanaan.",
    "Apabila denda telah mencapai nilai Jaminan Pelaksanaan, PPK dapat memutuskan kontrak.",
])
def test_performance_bond_is_recognised_as_penalty_cap(engine: EvaluationEngine, cap: str) -> None:
    result = engine.evaluate(EvaluationRequest(contract_draft=f"Denda keterlambatan 1/1000 dari nilai kontrak per hari.\n\n{cap}", contract_value_idr=1e9))
    assert "CON-PENALTY" not in _statuses(result)
    assert result["penalty_simulation"]["contract_cap_basis"] == "jaminan_pelaksanaan"


def test_regulated_rate_without_a_stated_cap_asks_for_review_not_nogo(engine: EvaluationEngine) -> None:
    result = engine.evaluate(EvaluationRequest(contract_draft="Denda keterlambatan 1/1000 dari nilai kontrak per hari.", contract_value_idr=1e9))
    assert _statuses(result)["CON-PENALTY"] == "REVIEW"
    assert result["verdict"] == "BELUM CUKUP BUKTI"


def test_explicit_uncapped_clause_stays_a_confirmed_gap(engine: EvaluationEngine) -> None:
    result = engine.evaluate(EvaluationRequest(contract_draft="Denda 1/1000 per hari dari nilai kontrak tanpa batas maksimal.", contract_value_idr=1e9))
    assert _statuses(result)["CON-PENALTY"] == "GAP"
    assert result["verdict"] == "NO-GO"


@pytest.mark.parametrize("clause", [
    "Para pihak wajib menghindari dan mencegah terjadinya benturan kepentingan.",
    "Pengendalian benturan kepentingan dilaksanakan sesuai ketentuan.",
])
def test_conflict_of_interest_duty_clause_is_not_an_incident(engine: EvaluationEngine, clause: str) -> None:
    assert "GOV-CONFLICT-INTEREST" not in _statuses(engine.evaluate(EvaluationRequest(dok_pemilihan=clause)))


def test_real_conflict_of_interest_is_still_flagged(engine: EvaluationEngine) -> None:
    result = engine.evaluate(EvaluationRequest(dok_pemilihan="Terdapat benturan kepentingan antara direktur penyedia dan anggota Pokja."))
    assert _statuses(result)["GOV-CONFLICT-INTEREST"] == "GAP"


# --------------------------------------------------------------------- brands
@pytest.mark.parametrize("sentence", [
    "Pengadaan suku cadang untuk perangkat jaringan Cisco Catalyst 9300 yang sudah terpasang.",
    "Penambahan lisensi sebagai bagian dari sistem Oracle Database yang sudah ada di instansi.",
])
def test_article_19_exceptions_ask_for_review_only(engine: EvaluationEngine, sentence: str) -> None:
    statuses = _statuses(engine.evaluate(EvaluationRequest(dok_pemilihan=sentence)))
    assert statuses == {"SPEC-BRAND-EXCEPTION": "REVIEW"}


def test_background_sentence_about_current_system_is_ignored(engine: EvaluationEngine) -> None:
    result = engine.evaluate(EvaluationRequest(dok_pemilihan="Latar belakang: saat ini data disimpan di Oracle Database dan akan dimigrasikan ke platform terbuka."))
    assert not result["findings"]


def test_excepted_mention_does_not_hide_a_later_lockin(engine: EvaluationEngine) -> None:
    doc = "Suku cadang Cisco Catalyst untuk perangkat yang sudah terpasang.\n\nSwitch baru wajib Cisco Catalyst 9300."
    assert _statuses(engine.evaluate(EvaluationRequest(dok_pemilihan=doc)))["SPEC-LOCKIN-NETWORKING"] == "GAP"


def test_construction_brands_no_longer_pass_as_go(engine: EvaluationEngine) -> None:
    doc = ("Penyedia wajib memiliki NPWP.\n\nSemen yang digunakan adalah Semen Tiga Roda tipe PCC 50 kg.\n\n"
           "Peralatan utama Excavator Komatsu PC200-8 sebanyak 2 unit.")
    result = engine.evaluate(EvaluationRequest(dok_pemilihan=doc, pustaka="NPWP: 01.234.567.8-901.000"))
    assert _statuses(result)["SPEC-BRAND-WATCH"] == "REVIEW"
    assert result["verdict"] == "BELUM CUKUP BUKTI"


def test_company_names_are_not_brand_mentions(engine: EvaluationEngine) -> None:
    assert "SPEC-BRAND-WATCH" not in _statuses(engine.evaluate(EvaluationRequest(dok_pemilihan="Pemberi tugas adalah PT Semen Gresik.")))


@pytest.mark.parametrize(("text", "expected"), [
    ("Wajib Cisco Catalyst 9300 dengan teknisi berpendidikan setara S1.", False),
    ("Wajib Cisco Catalyst 9300 atau setara dengan persetujuan tertulis dari Cisco Systems.", False),
    ("Wajib Cisco Catalyst 9300 atau setara.", True),
])
def test_equivalency_must_be_about_products(text: str, expected: bool) -> None:
    assert has_valid_equivalency(text) is expected


# ------------------------------------------------------------------- schedule
@pytest.mark.parametrize(("sentence", "expected"), [
    ("Pemasukan penawaran selama 6 hari kalender.", "REVIEW"),
    ("Pemasukan penawaran selama 10 hari kalender.", None),
    ("Pemasukan penawaran 2 Maret 2026 sampai dengan 4 Maret 2026.", "REVIEW"),
    ("Pemasukan penawaran dimulai 1 hari setelah penjelasan dan berlangsung selama 14 hari kerja.", None),
])
def test_bid_period_reads_dates_units_and_offsets(engine: EvaluationEngine, sentence: str, expected: str | None) -> None:
    assert _statuses(engine.evaluate(EvaluationRequest(dok_pemilihan=sentence))).get("PROC-TIMELINE-COMPRESSED") == expected


def test_unverified_bid_threshold_never_produces_nogo(engine: EvaluationEngine) -> None:
    result = engine.evaluate(EvaluationRequest(dok_pemilihan="Pemasukan penawaran hanya 3 hari kerja."))
    finding = next(item for item in result["findings"] if item["id"] == "PROC-TIMELINE-COMPRESSED")
    assert finding["threshold_unverified"] is True and finding["objectionable"] is False
    assert result["verdict"] == "BELUM CUKUP BUKTI"


@pytest.mark.parametrize(("sentence", "expected"), [
    ("Masa sanggah selama 5 (lima) hari kalender setelah pengumuman pemenang.", None),
    ("Masa sanggah selama 2 hari kalender.", "GAP"),
    ("Masa sanggah 3 hari kerja.", "GAP"),
])
def test_objection_period_uses_calendar_days_from_lkpp(engine: EvaluationEngine, sentence: str, expected: str | None) -> None:
    assert _statuses(engine.evaluate(EvaluationRequest(dok_pemilihan=sentence))).get("PROC-TIMELINE-COMPRESSED") == expected


# ---------------------------------------------------- determinism and coverage
def test_verdict_does_not_depend_on_the_day_of_the_audit(engine: EvaluationEngine, monkeypatch: pytest.MonkeyPatch) -> None:
    class Later(date):
        @classmethod
        def today(cls) -> date:
            return date(2040, 1, 1)

    request = EvaluationRequest(dok_pemilihan="Syarat: SBU yang masih berlaku.", pustaka="SBU berlaku hingga 5 Februari 2027.")
    before = _statuses(engine.evaluate(request))
    monkeypatch.setattr(engine_module, "date", Later)
    assert _statuses(engine.evaluate(request)) == before == {"ADM-SBU": "REVIEW"}


def test_bid_deadline_is_read_from_the_document(engine: EvaluationEngine) -> None:
    doc = "Syarat: SBU yang masih berlaku.\n\nBatas akhir penyampaian penawaran: 10 Maret 2026."
    assert _statuses(engine.evaluate(EvaluationRequest(dok_pemilihan=doc, pustaka="SBU berlaku hingga 1 Januari 2026.")))["ADM-SBU"] == "GAP"


def test_go_is_withheld_when_almost_nothing_was_recognised(engine: EvaluationEngine) -> None:
    doc = "Syarat: NPWP perusahaan.\n" + "\n".join(f"Klausul {i}. Ketentuan yang tidak dikenali aturan." for i in range(60))
    result = engine.evaluate(EvaluationRequest(dok_pemilihan=doc, pustaka="NPWP: 01.234.567.8-901.000"))
    assert result["verdict"] == "BELUM CUKUP BUKTI" and result["risk"]["rule_applied"] == "R5b"
    assert result["coverage"]["low_coverage"] is True
    assert any(row["rule"] == "R5b" for row in decision_table())


# ------------------------------------------------------------------------- AI
def _engine_with_ai(settings: Settings, payload: dict) -> tuple[EvaluationEngine, MagicMock]:
    langflow = LangflowService(settings)
    langflow.run_structured_prompt = MagicMock(return_value={"status": "success", "text": json.dumps(payload), "provider": "watsonx", "telemetry": {"provider": "watsonx", "model_id": "mock"}})
    return EvaluationEngine(settings, langflow), langflow.run_structured_prompt


EMPTY_AI = {"scope": None, "brand_lockin_signals": [], "timeline_anomalies": [], "addendum_changes": [], "personnel_qualifications": [], "sla_uptime": []}


def test_ai_brand_outside_rules_reaches_a_human_without_changing_the_verdict() -> None:
    quote = "Unit pompa menggunakan merek Grundfos CR 10 sebanyak 2 unit."
    engine, _ = _engine_with_ai(Settings.from_environment(), {**EMPTY_AI, "brand_lockin_signals": [{"quote": quote, "source": "Dokumen pemilihan", "summary": "merek"}]})
    result = engine.evaluate(EvaluationRequest(dok_pemilihan=quote, allow_external_processing=True))
    finding = next(item for item in result["findings"] if item["id"] == "SPEC-AI-BRAND-REVIEW")
    assert finding["origin"] == "ai_extraction_unconfirmed" and finding["status"] == "REVIEW"
    assert result["verdict"] == "TIDAK ADA SYARAT TERBACA"
    assert result["contextual_extraction"]["items"][0]["validation"]["status"] == "needs_human_review"


def test_ai_prompt_is_bounded_and_quotes_still_verify_against_the_full_text() -> None:
    quote = "Spesifikasi pompa wajib merek Grundfos CR 10."
    filler = "\n".join(f"Paragraf umum nomor {i} tentang tata laksana pekerjaan harian." for i in range(20_000))
    engine, call = _engine_with_ai(Settings.from_environment(), {**EMPTY_AI, "brand_lockin_signals": [{"quote": quote, "source": "x", "summary": "m"}]})
    result = engine.evaluate(EvaluationRequest(dok_pemilihan=f"{filler}\n{quote}", allow_external_processing=True))
    sent = json.loads(call.call_args[0][0])
    assert len(sent["documents"]["dok_pemilihan"]) <= AI_CONTEXT_MAX_CHARS and quote in sent["documents"]["dok_pemilihan"]
    assert result["contextual_extraction"]["rejected_quotes_count"] == 0
    assert next(step for step in result["proof_log"] if step["kind"] == "pii_redaction")["outputs"]["excerpted_for_ai"] is True


def test_ai_call_is_cancelled_when_pii_survives_redaction(monkeypatch: pytest.MonkeyPatch) -> None:
    engine, call = _engine_with_ai(Settings.from_environment(), EMPTY_AI)
    monkeypatch.setattr(engine_module, "contains_unmasked_pii", lambda _text: True)
    result = engine.evaluate(EvaluationRequest(dok_pemilihan="Syarat: NPWP.", allow_external_processing=True))
    assert not call.called and result["contextual_extraction"]["status"] == "pii_blocked"


# ------------------------------------------------------------------------ PII
@pytest.mark.parametrize(("raw", "secret"), [
    ("NIK 3171 0123 4567 0001", "3171 0123"),
    ("NIK: 3171-0123-4567-0001", "3171-0123"),
    ("Telp kantor (021) 555-1234", "555-1234"),
    ("Telp 031-8412345", "8412345"),
    ("Rek. Mandiri 140-00-1234567-8", "1234567"),
    ("Rekening BCA a.n. PT Maju 123 456 7890", "456 7890"),
    ("Direktur: Budi Santoso", "Budi Santoso"),
    ("Alamat: Jl. Merdeka No. 10 Surabaya", "Merdeka"),
])
def test_pii_formats_seen_in_real_documents_are_masked(raw: str, secret: str) -> None:
    assert secret not in mask_text(raw)


def test_rupiah_amounts_are_not_mistaken_for_nik() -> None:
    assert mask_text("Nilai kontrak 1500000000000000 rupiah") == "Nilai kontrak 1500000000000000 rupiah"


# ------------------------------------------------------------------------ API
@pytest.fixture
def app_env(tmp_path: Path):
    settings = dataclasses.replace(Settings.from_environment(), audit_log_path=tmp_path / "audit_log.jsonl", access_token="tok", session_secret="s" * 40)
    application = create_asgi_app(settings)

    def make(role: str | None = None) -> TestClient:
        client = TestClient(application, base_url="http://127.0.0.1:8000", headers={"Authorization": "Bearer tok"})
        if role:
            assert client.post("/api/auth/login", json={"role": role}).status_code == 200
        return client

    return make, tmp_path / "audit_log.jsonl"


DOC = "NIK Direktur 3171012345670001.\nPagu Anggaran Rp 1.000.000.000.\nHPS Rp 1.200.000.000.\nPenyedia wajib merek Cisco Catalyst 9300."


def test_token_without_role_cannot_read_a_role_owned_audit(app_env) -> None:
    make, _ = app_env
    audit_id = make("pokja").post("/api/audit", json={"package_name": "Rahasia", "dok_pemilihan": DOC}).json()["data"]["audit_id"]
    anonymous = make()
    assert anonymous.get(f"/api/audits/{audit_id}").status_code == 400
    assert anonymous.get(f"/api/audits/{audit_id}/proof").status_code == 400
    assert anonymous.get("/api/audits").json()["data"]["audits"] == []


def test_other_role_cannot_read_or_write_reviews(app_env) -> None:
    make, log_path = app_env
    owner = make("pokja")
    audit = owner.post("/api/audit", json={"dok_pemilihan": DOC}).json()["data"]
    body = {"audit_id": audit["audit_id"], "finding_id": audit["findings"][0]["id"], "outcome": "NOT_SUPPORTED"}
    vendor = make("vendor")
    assert vendor.post("/api/review-feedback", json=body).status_code == 400
    assert vendor.get(f"/api/review-feedback?audit_id={audit['audit_id']}").status_code == 400
    assert owner.post("/api/review-feedback", json=body).status_code == 200
    reviewed = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if '"finding.reviewed"' in line]
    assert reviewed[-1]["reviewer_role"] == "pokja"


@pytest.mark.parametrize(("path", "body"), [
    ("/api/v1/audit/minutes-eval-doc", {"tender_id": "T", "vendor_name": "PT X", "format": "markdown", "findings": [{"id": "SPEC-BRAND-LOCKIN", "clause": "x", "status": "GAP", "severity": "HIGH", "category": "Spesifikasi", "evidence": "KARANGAN", "source": "x", "review_note": "x"}]}),
    ("/api/v1/audit/clarification-doc", {"tender_id": "T", "vendor_name": "PT X", "format": "markdown", "anomalies": [{"anomaly_type": "x", "source_quote": "KARANGAN", "page_ref": "1", "description": "x"}]}),
])
def test_official_documents_refuse_caller_supplied_findings(app_env, path: str, body: dict) -> None:
    response = app_env[0]("pokja").post(path, json=body)
    assert response.status_code == 400 and "audit_id" in response.json()["error"]["message"]


def test_stored_audit_overrides_caller_findings_in_minutes(app_env) -> None:
    pokja = app_env[0]("pokja")
    audit_id = pokja.post("/api/audit", json={"dok_pemilihan": DOC}).json()["data"]["audit_id"]
    data = pokja.post("/api/v1/audit/minutes-eval-doc", json={"audit_id": audit_id, "format": "markdown", "findings": [{"id": "X", "clause": "KARANGAN", "status": "GAP", "severity": "HIGH", "category": "x", "evidence": "KARANGAN", "source": "x", "review_note": "x"}]}).json()["data"]
    assert "KARANGAN" not in base64.b64decode(data["content_base64"]).decode("utf-8")


def test_letter_follows_the_tender_stage(app_env) -> None:
    vendor = app_env[0]("vendor")
    audit_id = vendor.post("/api/audit", json={"dok_pemilihan": DOC}).json()["data"]["audit_id"]

    def letter(stage: str) -> tuple[str, str]:
        data = vendor.post("/api/v1/audit/sanggahan-doc", json={"audit_id": audit_id, "format": "markdown", "stage": stage}).json()["data"]
        assert data["source_origin"] == "audit"
        return data["filename"], base64.b64decode(data["content_base64"]).decode("utf-8")

    name, text = letter("pre_bid")
    assert name.startswith("draf-permohonan-penjelasan") and "SURAT PERMOHONAN PENJELASAN" in text and "bukan sanggah" in text
    name, text = letter("post_award")
    assert name.startswith("draf-sanggahan") and "5 hari kalender" in text
    assert vendor.post("/api/v1/audit/sanggahan-doc", json={"audit_id": audit_id, "format": "markdown", "stage": "x"}).status_code == 400


# ------------------------------------------------------------------ audit log
def test_deleting_an_audit_keeps_the_chain_valid_and_removes_the_source(app_env) -> None:
    make, log_path = app_env
    pokja = make("pokja")
    first = pokja.post("/api/audit", json={"dok_pemilihan": DOC}).json()["data"]["audit_id"]
    pokja.post("/api/audit", json={"dok_pemilihan": DOC + "\nKedua."})
    source = log_path.parent / "audit_sources" / f"{first}.txt"
    assert source.is_file()
    assert pokja.delete(f"/api/audits/{first}").status_code == 200
    assert not source.exists() and "3171012345670001" not in log_path.read_text(encoding="utf-8")
    report = pokja.get("/api/audit-log/verify").json()["data"]
    assert report["valid"] is True and report["sealed"] is True
    assert '"audit.deleted"' in log_path.read_text(encoding="utf-8")


def test_rehashing_a_changed_log_is_caught_by_the_seal(tmp_path: Path) -> None:
    path = tmp_path / "log.jsonl"
    log = AuditLog(path, seal_key=b"k" * 32)
    log.append({"event_type": "audit.completed", "audit_id": "a", "verdict": "NO-GO"})
    log.append({"event_type": "audit.completed", "audit_id": "b", "verdict": "NO-GO"})
    assert log.verify_chain()[0] is True

    previous, rewritten = "0" * 64, []
    for row in map(json.loads, path.read_text(encoding="utf-8").splitlines()):
        row["verdict"] = "GO"
        row["previous_hash"] = previous
        row.pop("hash")
        mac = row.pop("mac")
        canonical = json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
        previous = hashlib.sha256(f"{previous}|{canonical}".encode()).hexdigest()
        rewritten.append(json.dumps({**row, "hash": previous, "mac": mac}))
    path.write_text("\n".join(rewritten) + "\n", encoding="utf-8")

    valid, _, message = log.verify_chain()
    assert valid is False and "seal" in message.lower()


def test_retention_purge_keeps_chain_and_removes_source(tmp_path: Path) -> None:
    log = AuditLog(tmp_path / "log.jsonl", seal_key=b"k" * 32)
    log.append({"event_type": "audit.completed", "audit_id": "old", "created_at": "2020-01-01T00:00:00+00:00"})
    log.append({"event_type": "audit.completed", "audit_id": "new"})
    log.save_source_text("old", "teks lama", retention_days=0)
    assert log.purge_older_than(90) == 1
    assert log.get_source_text("old") is None and log.verify_chain()[0] is True


# -------------------------------------------- long, template-based documents
# Patterns below were observed in public Dokumen Pemilihan PDFs based on the LKPP model.
LONG_PREFIX = "Syarat umum pelaksanaan pekerjaan.\n\n"


@pytest.mark.parametrize("noise", [
    "JAMINAN PENAWARAN ...................... - 28 -",
    "Jaminan Pemeliharaan dari Bank ............ - 103 -",
    "GARANSI BANK sebagai JAMINAN UANG MUKA No. 123",
])
def test_contents_pages_and_bank_guarantees_are_not_requirements(engine: EvaluationEngine, noise: str) -> None:
    statuses = _statuses(engine.evaluate(EvaluationRequest(dok_pemilihan=LONG_PREFIX + noise)))
    assert "ADM-WARRANTY" not in statuses
    if "...." in noise:
        assert "ADM-BOND" not in statuses


def test_page_furniture_does_not_split_a_sentence(engine: EvaluationEngine) -> None:
    doc = "Masa sanggah ditetapkan\n- 29 -\nParaf I\nselama 2 (dua) hari kerja."
    assert _statuses(engine.evaluate(EvaluationRequest(dok_pemilihan=doc)))["PROC-TIMELINE-COMPRESSED"] == "GAP"


def test_template_rows_are_not_requirements(engine: EvaluationEngine) -> None:
    assert "ADM-NPWP" not in _statuses(engine.evaluate(EvaluationRequest(dok_pemilihan="NPWP perusahaan : _______________")))


@pytest.mark.parametrize(("doc", "finding"), [
    ("Sanggah disampaikan dalam waktu 5 (lima) hari kalender setelah pengumuman pemenang.\n\nMasa sanggah ditetapkan selama 2 hari kerja.", "PROC-TIMELINE-COMPRESSED"),
    ("Para pihak wajib mencegah benturan kepentingan.\n\nTerdapat benturan kepentingan antara direktur penyedia dan anggota Pokja.", "GOV-CONFLICT-INTEREST"),
    ("Penyedia memiliki kantor perwakilan di lokasi pekerjaan.\n\nPeserta wajib berdomisili di Kabupaten Banyumas.", "SPEC-REGIONAL-LOCKIN"),
])
def test_a_harmless_first_mention_does_not_hide_a_later_violation(engine: EvaluationEngine, doc: str, finding: str) -> None:
    assert _statuses(engine.evaluate(EvaluationRequest(dok_pemilihan=doc)))[finding] == "GAP"


def test_offset_cue_keeps_a_real_objection_period(engine: EvaluationEngine) -> None:
    doc = "Sanggah disampaikan dalam waktu 3 (tiga) hari kalender setelah pengumuman pemenang."
    assert _statuses(engine.evaluate(EvaluationRequest(dok_pemilihan=doc)))["PROC-TIMELINE-COMPRESSED"] == "GAP"


@pytest.mark.parametrize("sentence", [
    "Peserta yang terbukti melanggar ketentuan pertentangan kepentingan digugurkan sebagai peserta.",
    "Pertentangan kepentingan sebagaimana dimaksud pada angka 5.1 antara lain meliputi:",
    "Keikutsertaan yang bersangkutan tidak menimbulkan pertentangan kepentingan.",
    "Saya tidak sedang dan tidak akan terlibat pertentangan kepentingan dengan para pihak.",
])
def test_standard_conflict_of_interest_template_is_not_an_incident(engine: EvaluationEngine, sentence: str) -> None:
    assert "GOV-CONFLICT-INTEREST" not in _statuses(engine.evaluate(EvaluationRequest(dok_pemilihan=sentence)))


def test_threshold_rules_are_not_read_as_the_package_budget(engine: EvaluationEngine) -> None:
    doc = ("Untuk paket dengan nilai pagu anggaran di atas Rp50.000.000.000,00 berlaku ketentuan khusus.\n\n"
           "Untuk HPS paling sedikit di atas Rp100.000.000.000,00 berlaku ketentuan lain.\n\n"
           "2. Pagu Anggaran: Rp3.608.000.000,00\n3. Harga Perkiraan Sendiri (HPS): Rp3.466.011.009,79")
    assert "FIN-OVER-BUDGET" not in _statuses(engine.evaluate(EvaluationRequest(dok_pemilihan=doc)))
    over = doc.replace("Rp3.466.011.009,79", "Rp3.900.000.000,00")
    assert _statuses(engine.evaluate(EvaluationRequest(dok_pemilihan=over)))["FIN-OVER-BUDGET"] == "GAP"


def test_bond_requirement_skips_conditional_amounts(engine: EvaluationEngine) -> None:
    doc = ("Dalam hal nilai HPS paling sedikit di atas Rp10.000.000.000,00, Jaminan Penawaran wajib dilampirkan.\n\n"
           "Nilai Jaminan Penawaran adalah Rp 120.000.000,00.")
    evidence = "Jaminan Penawaran dari Bank Nusantara senilai Rp 130.000.000."
    assert _statuses(engine.evaluate(EvaluationRequest(dok_pemilihan=doc, pustaka=evidence)))["ADM-BOND"] == "TERPENUHI"
    conditional_only = doc.split("\n\n")[0]
    assert _statuses(engine.evaluate(EvaluationRequest(dok_pemilihan=conditional_only, pustaka=evidence)))["ADM-BOND"] == "REVIEW"


def test_distant_maximum_line_is_not_a_penalty_cap(engine: EvaluationEngine) -> None:
    filler = "\n".join(f"Ketentuan umum nomor {i}." for i in range(10))
    doc = f"Denda keterlambatan sebesar 5% per hari dari nilai kontrak.\n{filler}\nMaksimal 10% dari jumlah personel."
    assert _statuses(engine.evaluate(EvaluationRequest(contract_draft=doc, contract_value_idr=1e9)))["CON-PENALTY"] == "GAP"


def test_harshest_daily_rate_is_used(engine: EvaluationEngine) -> None:
    doc = "Denda 1/1000 per hari untuk bagian A.\n\nDenda 3/1000 per hari untuk bagian B."
    assert engine.evaluate(EvaluationRequest(contract_draft=doc, contract_value_idr=1e9))["penalty_simulation"]["contract_daily_rate"] == pytest.approx(0.003)


def test_expert_label_does_not_invent_a_certificate(engine: EvaluationEngine) -> None:
    result = engine.evaluate(EvaluationRequest(dok_pemilihan="Kualifikasi tenaga ahli: Project Manager berpengalaman."))
    finding = next(item for item in result["findings"] if item["id"] == "ADM-EXPERTS")
    assert "PMP" not in finding["clause"]


# ------------------------------------------------------- specification tables
SPEC_TABLE = """1. Compute Node A
ITEM
SPESIFIKASI
QTY
SET
Seri / Tahun Produksi Minimal 2021
5
2
Processor
Intel Xeon Gold 5318N / 5318S, 48 Core
RAM
256 GB
Power Suply
1300 - 1500 Watt
Garansi / Service
3 Tahun (Labor, Sparepart dan Suport Onsite)
Indent
10 Minggu"""


def test_spec_table_row_is_read_on_its_own(engine: EvaluationEngine) -> None:
    result = engine.evaluate(EvaluationRequest(dok_pemilihan=SPEC_TABLE))
    statuses = _statuses(result)
    assert statuses["SPEC-LOCKIN-CPU"] == "GAP" and "SPEC-BRAND-EXCEPTION" not in statuses
    cpu = next(item for item in result["findings"] if item["id"] == "SPEC-LOCKIN-CPU")
    assert len(cpu["requirement_evidence"]) < 80
    warranty = next(item for item in result["findings"] if item["id"] == "ADM-WARRANTY")
    assert "3 Tahun" in warranty["requirement_evidence"] and "Intel" not in warranty["requirement_evidence"]


def test_normal_wrapped_paragraph_stays_one_sentence(engine: EvaluationEngine) -> None:
    doc = "Masa sanggah\nuntuk paket\nini ditetapkan\noleh Pokja\nyang bertugas\nselama 2 (dua) hari kerja."
    assert _statuses(engine.evaluate(EvaluationRequest(dok_pemilihan=doc)))["PROC-TIMELINE-COMPRESSED"] == "GAP"


@pytest.mark.parametrize("sentence", [
    "Penyedia merupakan partner dari principal produk minimal Titanium Partner.",
    "Mendapat surat dukungan langsung dari Principle Indonesia.",
    "Penawaran wajib melampirkan surat penunjukan dari distributor tunggal.",
    "Penyedia harus Authorized Reseller produk yang ditawarkan.",
])
def test_principal_requirements_ask_for_review(engine: EvaluationEngine, sentence: str) -> None:
    assert _statuses(engine.evaluate(EvaluationRequest(dok_pemilihan=sentence)))["SPEC-PRINCIPAL-REVIEW"] == "REVIEW"


def test_lkpp_import_support_letter_is_not_flagged(engine: EvaluationEngine) -> None:
    sentence = "Surat dukungan dari pabrikan khusus untuk barang impor dilampirkan pada penawaran."
    assert "SPEC-PRINCIPAL-REVIEW" not in _statuses(engine.evaluate(EvaluationRequest(dok_pemilihan=sentence)))


def test_head_office_or_branch_location_requirement_is_flagged(engine: EvaluationEngine) -> None:
    sentence = "Penyedia memiliki kantor pusat atau kantor perwakilan di Jakarta."
    assert _statuses(engine.evaluate(EvaluationRequest(dok_pemilihan=sentence)))["SPEC-REGIONAL-LOCKIN"] == "GAP"

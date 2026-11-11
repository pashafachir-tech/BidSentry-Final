"""Chaos and fuzzing suite: hostile, broken and oversized inputs must never crash BidSentry.

Every case asserts a *graceful* outcome: a user-facing ValidationError (HTTP 4xx)
or a completed audit, never an unhandled exception / HTTP 500, never a hang.
"""

from __future__ import annotations

import base64
import io
import json
import os
import random
import time
import zipfile
from dataclasses import replace
from pathlib import Path

import openpyxl
import pymupdf
import pytest

from starlette.testclient import TestClient  # noqa: E402

from bidsentry.asgi import create_asgi_app  # noqa: E402
from bidsentry.audits.excel_parser import MAX_ROWS, parse_boq_excel  # noqa: E402
from bidsentry.config import Settings  # noqa: E402
from bidsentry.evaluators.engine import EvaluationEngine, EvaluationRequest  # noqa: E402
from bidsentry.services.boq_export_service import BoQExportService  # noqa: E402
from bidsentry.services.document_extraction_service import MAX_DOCUMENT_BYTES, MAX_PDF_PAGES, DocumentExtractionService  # noqa: E402
from bidsentry.types.schemas import ValidationError  # noqa: E402

EXTRACTOR = DocumentExtractionService()


def _issue(exc: ValidationError) -> str:
    return exc.details[0]["issue"]


def _pdf(pages: int, text: str = "Spesifikasi teknis server dan jadwal pemilihan.") -> bytes:
    doc = pymupdf.open()
    for index in range(pages):
        doc.new_page().insert_text((72, 72), f"Halaman {index + 1}. {text}")
    data = doc.tobytes(garbage=3, deflate=True)
    doc.close()
    return data


def _xlsx(build) -> bytes:
    workbook = openpyxl.Workbook()
    build(workbook)
    stream = io.BytesIO()
    workbook.save(stream)
    return stream.getvalue()


# --------------------------------------------------------------------------- documents
class TestDocumentChaos:
    def test_zero_byte_pdf_is_rejected_kindly(self) -> None:
        with pytest.raises(ValidationError) as caught:
            EXTRACTOR.extract("kosong.pdf", b"")
        assert _issue(caught.value) == "empty_file" and "0 byte" in caught.value.message

    def test_random_bytes_named_pdf(self) -> None:
        with pytest.raises(ValidationError) as caught:
            EXTRACTOR.extract("rusak.pdf", os.urandom(4096))
        assert _issue(caught.value) in {"corrupted_file", "extraction_failed", "no_extractable_text"}

    def test_truncated_pdf_download(self) -> None:
        data = _pdf(3)
        try:
            result = EXTRACTOR.extract("terpotong.pdf", data[: len(data) // 2])
            assert isinstance(result["text"], str)
        except ValidationError as exc:
            assert exc.message

    def test_password_protected_pdf(self) -> None:
        doc = pymupdf.open()
        doc.new_page().insert_text((72, 72), "Dokumen rahasia")
        data = doc.tobytes(encryption=pymupdf.PDF_ENCRYPT_AES_256, user_pw="rahasia", owner_pw="pemilik")
        doc.close()
        with pytest.raises(ValidationError) as caught:
            EXTRACTOR.extract("terkunci.pdf", data)
        assert _issue(caught.value) == "encrypted_pdf" and "kata sandi" in caught.value.message

    def test_scanned_pdf_never_injects_placeholder_text(self) -> None:
        doc = pymupdf.open()
        doc.new_page()
        data = doc.tobytes()
        doc.close()
        result = EXTRACTOR.extract("scan.pdf", data)
        assert result["scanned_pdf"] is True and result["text"] == ""
        assert any("OCR" in warning for warning in result["warnings"])

    def test_thousand_page_pdf_is_truncated_safely(self) -> None:
        data = _pdf(1000)
        assert len(data) < MAX_DOCUMENT_BYTES
        started = time.perf_counter()
        result = EXTRACTOR.extract("raksasa.pdf", data)
        assert time.perf_counter() - started < 30
        assert result["pages"] == 1000 and result["truncated"] is True
        assert f"Halaman {MAX_PDF_PAGES}." in result["text"] and f"Halaman {MAX_PDF_PAGES + 1}." not in result["text"]
        assert any("500 halaman" in warning for warning in result["warnings"])

    def test_oversized_upload(self) -> None:
        with pytest.raises(ValidationError) as caught:
            EXTRACTOR.extract("besar.txt", b"a" * (MAX_DOCUMENT_BYTES + 1))
        assert _issue(caught.value) == "file_too_large"

    def test_binary_disguised_as_text(self) -> None:
        with pytest.raises(ValidationError) as caught:
            EXTRACTOR.extract("bukan-teks.txt", bytes(range(256)) * 40)
        assert _issue(caught.value) == "binary_content"

    def test_huge_plain_text_is_truncated(self) -> None:
        result = EXTRACTOR.extract("panjang.txt", ("Persyaratan teknis. " * 70_000).encode())
        assert result["truncated"] is True and result["characters"] <= 1_000_000

    def test_docx_that_is_not_a_zip(self) -> None:
        with pytest.raises(ValidationError) as caught:
            EXTRACTOR.extract("palsu.docx", b"PK\x03\x04 not really a zip")
        assert _issue(caught.value) == "corrupted_file"

    def test_docx_without_document_xml(self) -> None:
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w") as archive:
            archive.writestr("readme.txt", "kosong")
        with pytest.raises(ValidationError) as caught:
            EXTRACTOR.extract("tanpa-isi.docx", stream.getvalue())
        assert _issue(caught.value) == "corrupted_file"

    def test_zip_bomb_is_refused_before_parsing(self) -> None:
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("word/document.xml", b"\x00" * (70 * 1024 * 1024))
        assert len(stream.getvalue()) < MAX_DOCUMENT_BYTES
        with pytest.raises(ValidationError) as caught:
            EXTRACTOR.extract("bom.docx", stream.getvalue())
        assert _issue(caught.value) == "expanded_file_too_large"

    def test_deeply_nested_json(self) -> None:
        result = EXTRACTOR.extract("dalam.json", ("[" * 5000 + "]" * 5000).encode())
        assert result["characters"] > 0


# ------------------------------------------------------------------------------ excel
class TestExcelChaos:
    def test_circular_reference_does_not_hang(self) -> None:
        def build(wb):
            ws = wb.active
            ws.append(["No", "Uraian Pekerjaan", "Volume", "Satuan", "Harga Satuan", "Jumlah Harga"])
            ws.append([1, "Pondasi", 2, "m3", 1_000_000, "=F3"])
            ws.append([2, "Rangka", 3, "m3", 500_000, "=F2"])
        started = time.perf_counter()
        result = parse_boq_excel(_xlsx(build))
        assert time.perf_counter() - started < 5
        assert [item["total"] for item in result["items"]] == [2_000_000, 1_500_000]  # uncached formulas fall back to vol × price

    def test_hostile_formulas_are_inert_text_and_flagged(self) -> None:
        payloads = ["=cmd|' /C calc'!A0", '=SYSTEM("rm -rf /")', "@SUM(1+1)*cmd|' /C calc'!A0", "+HYPERLINK(\"http://x\")"]

        def build(wb):
            ws = wb.active
            ws.append(["Uraian", "Volume", "Satuan", "Harga Satuan", "Jumlah"])
            for payload in payloads:
                ws.append([payload, 1, "ls", 1000, 1000])
                ws.cell(row=ws.max_row, column=1).data_type = "s"
        result = parse_boq_excel(_xlsx(build))
        assert [item["description"] for item in result["items"]] == payloads
        assert any("formula" in warning for warning in result["warnings"])

    def test_multi_sheet_without_standard_header_on_first_sheet(self) -> None:
        def build(wb):
            notes = wb.active
            notes.title = "Catatan"
            notes.append(["Dokumen ini berisi rincian anggaran"])
            boq = wb.create_sheet("Lampiran BoQ")
            for _ in range(3):
                boq.append([None])
            boq.append(["Kode", "Deskripsi Pekerjaan", "Qty", "Sat.", "Harga Satuan (Rp)", "Jumlah Harga (Rp)"])
            boq.append(["A.1", "Galian tanah", "12,5", "m3", "Rp 85.000", "Rp 1.062.500,-"])
        result = parse_boq_excel(_xlsx(build))
        assert len(result["items"]) == 1
        item = result["items"][0]
        assert item["sheet"] == "Lampiran BoQ" and item["volume"] == 12.5 and item["total"] == 1_062_500

    def test_messy_numbers_never_poison_totals(self) -> None:
        def build(wb):
            ws = wb.active
            ws.append(["Uraian", "Volume", "Satuan", "Harga Satuan", "Jumlah"])
            ws.append(["Baris teks", "dua", "ls", "abc", "tidak ada"])
            ws.append(["Baris negatif", -5, "ls", 1000, -5000])
            ws.append(["Baris miliar", 1, "ls", "1,25 miliar", None])
            ws.append(["Baris NaN", 1, "ls", float("nan"), float("inf")])
        result = parse_boq_excel(_xlsx(build))
        totals = [item["total"] for item in result["items"]]
        assert totals == [0.0, 0.0, 1_250_000_000, 0.0]
        assert result["total_idr"] == 1_250_000_000

    def test_no_header_anywhere_falls_back_to_text(self) -> None:
        def build(wb):
            wb.active.append(["Ringkasan", "tanpa", "tabel"])
        result = parse_boq_excel(_xlsx(build))
        assert result["items"] == [] and "Ringkasan" in result["text"] and result["warnings"]

    def test_row_cap(self) -> None:
        def build(wb):
            ws = wb.active
            ws.append(["Uraian", "Volume", "Satuan", "Harga Satuan", "Jumlah"])
            for index in range(MAX_ROWS + 50):
                ws.append([f"Item {index}", 1, "ls", 10, 10])
        result = parse_boq_excel(_xlsx(build))
        assert result["truncated"] is True and len(result["items"]) < MAX_ROWS

    def test_corrupted_xlsx_via_extractor(self) -> None:
        with pytest.raises(ValidationError) as caught:
            EXTRACTOR.extract("rusak.xlsx", b"PK\x03\x04garbage")
        assert _issue(caught.value) == "corrupted_file"


# ----------------------------------------------------------------------------- engine
class TestEngineChaos:
    @pytest.fixture
    def engine(self) -> EvaluationEngine:
        return EvaluationEngine(replace(Settings.from_environment(), langflow_enabled=False, llm_provider="", gemini_api_key=""))

    def test_one_megabyte_single_line_finishes_quickly(self, engine: EvaluationEngine) -> None:
        random.seed(7)
        words = ["mantan", "pejabat", "denda", "per", "hari", "wajib", "merek", "asosiasi", "regional", "pagu", "HPS", "Sertifikasi"]
        text = " ".join(random.choice(words) for _ in range(160_000))[:1_000_000]
        started = time.perf_counter()
        result = engine.evaluate(EvaluationRequest(dok_pemilihan=text))
        assert time.perf_counter() - started < 20, "regex work must stay linear in document size"
        assert result["verdict"]

    def test_garbage_document_is_not_assessable_with_guidance(self, engine: EvaluationEngine) -> None:
        random.seed(3)
        garbage = "".join(chr(random.choice([*range(0x21, 0x7E), *range(0x0400, 0x04FF), 0xFFFD])) for _ in range(20_000))
        result = engine.evaluate(EvaluationRequest(dok_pemilihan=garbage))
        assert result["risk_level"] == "NOT_ASSESSABLE"
        assert result["risk"]["label"] == "Tidak Dapat Dinilai"
        assert "OCR" in result["executive_summary"]["executive_summary"]

    def test_export_survives_control_characters_and_formula_text(self) -> None:
        audit = {"audit_id": "x", "package_name": "Paket \x0b\x1b uji", "findings": [{"id": "SPEC-LOCKIN-CPU", "clause": "=cmd|' /C calc'!A0", "status": "GAP", "requirement_evidence": "\x07bel"}], "proof_log": []}
        source = "=SYSTEM(1) \x0b | 2 unit | Rp 1.000 | Rp 2.000\n"
        result = BoQExportService().create(audit, source, role="vendor")
        workbook = openpyxl.load_workbook(io.BytesIO(base64.b64decode(result["content_base64"])))
        clause_cell = workbook["Temuan"]["C2"]
        assert clause_cell.value == "=cmd|' /C calc'!A0" and clause_cell.data_type == "s"
        assert workbook["BoQ"]["B5"].data_type == "s"


# -------------------------------------------------------------------------------- API
@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    workspace = tmp_path / "ws"
    (workspace / "web").mkdir(parents=True)
    (workspace / "index.html").write_text("<html></html>", encoding="utf-8")
    (workspace / ".env").write_text("# test\n", encoding="utf-8")
    settings = replace(
        Settings.from_environment(),
        workspace_root=workspace, static_root=workspace / "web", audit_log_path=workspace / "audit_log.jsonl",
        host="127.0.0.1", langflow_enabled=False, langflow_flow_id="", llm_provider="", gemini_api_key="",
        composio_api_key="", access_token="", pokja_pin="", vendor_pin="", session_secret="chaos-test-secret",
    )
    return TestClient(create_asgi_app(settings), base_url="http://127.0.0.1:8000", raise_server_exceptions=False)


FUZZ_BODIES: list[object] = [
    None, [], 0, -1, 1e308, "teks", True, {},
    {"audit_id": None, "findings": "bukan list", "format": ["docx"]},
    {"audit_id": "../../etc/passwd", "format": "exe"},
    {"findings": [None, 1, "x", {"id": None, "status": {"nested": True}}], "source_text": 123},
    {"package_name": "x" * 300, "dok_pemilihan": ["a"], "contract_value_idr": "nan"},
    {"dok_pemilihan": "Denda tanpa batas", "contract_value_idr": float("1e309") if False else -5},
    {"audit_id": "a", "finding_id": "b", "outcome": "SUPPORTED"},
    {"a": {"b": {"c": {"d": [1, {"e": None}]}}}},
]
POST_ROUTES = [
    "/api/audit", "/api/v1/audit/evaluate", "/api/v1/audit/sanggahan-doc", "/api/v1/audit/minutes-eval-doc",
    "/api/v1/audit/clarification-doc", "/api/v1/audit/comprehensive", "/api/export/boq", "/api/export/workbook",
    "/api/review-feedback", "/api/dispatch", "/api/auth/login",
]


@pytest.mark.parametrize("role", ["pokja", "vendor"])
def test_no_route_returns_500_for_hostile_json(client: TestClient, role: str) -> None:
    assert client.post("/api/auth/login", json={"role": role}).status_code == 200
    failures = []
    for route in POST_ROUTES:
        for body in FUZZ_BODIES:
            response = client.post(route, content=json.dumps(body), headers={"Content-Type": "application/json"})
            if response.status_code >= 500:
                failures.append((route, body, response.status_code, response.text[:200]))
    assert not failures, failures


def test_no_route_returns_500_for_malformed_transport(client: TestClient) -> None:
    client.post("/api/auth/login", json={"role": "vendor"})
    cases = [
        ("/api/audit", b"\xff\xfe\x00 not utf8", "application/json"),
        ("/api/audit", b"{\"dok_pemilihan\": ", "application/json"),
        ("/api/audit", b"dok_pemilihan=abc", "application/x-www-form-urlencoded"),
        ("/api/documents/extract?filename=x.pdf", os.urandom(2048), "application/octet-stream"),
        ("/api/documents/extract?filename=..%2F..%2Fboot.ini", b"abc", "application/octet-stream"),
        ("/api/documents/extract?filename=kosong.docx", b"", "application/octet-stream"),
    ]
    for route, body, content_type in cases:
        response = client.post(route, content=body, headers={"Content-Type": content_type})
        assert response.status_code < 500, (route, response.status_code, response.text[:200])
        assert "Traceback" not in response.text


def test_hostile_get_paths(client: TestClient) -> None:
    client.post("/api/auth/login", json={"role": "pokja"})
    for path in ["/api/audits/%00", "/api/audits/x/proof", "/api/audits/x/economics?manual_hours=-1&hourly_cost_idr=abc",
                 "/api/audits/" + "a" * 5000, "/api/audit?audit_id=", "/web/../../etc/passwd", "/api/unknown", "/api/review-feedback?audit_id=%27%22"]:
        response = client.get(path)
        assert response.status_code < 500, (path, response.status_code)


def test_oversized_payload_gets_friendly_413(client: TestClient) -> None:
    client.post("/api/auth/login", json={"role": "pokja"})
    huge = json.dumps({"dok_pemilihan": "a" * (13 * 1024 * 1024)})
    response = client.post("/api/audit", content=huge, headers={"Content-Type": "application/json"})
    assert response.status_code == 413 and "Pecah dokumen" in response.json()["error"]["message"]


def test_too_long_field_gets_friendly_message(client: TestClient) -> None:
    client.post("/api/auth/login", json={"role": "pokja"})
    response = client.post("/api/audit", json={"adendum": "a" * 1_000_001})
    assert response.status_code == 400 and "terlalu panjang" in response.json()["error"]["message"]

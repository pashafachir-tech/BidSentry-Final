from pathlib import Path
import pytest

from starlette.testclient import TestClient

from bidsentry.asgi import create_asgi_app
from bidsentry.config import Settings
from bidsentry.generators.sanggahan_builder import _eligible


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    web_dir = workspace / "web"
    web_dir.mkdir()
    (web_dir / "app.js").write_text("console.log('test');", encoding="utf-8")
    (workspace / "index.html").write_text("<html><body>Test</body></html>", encoding="utf-8")
    env_file = workspace / ".env"
    env_file.write_text("# test env\n", encoding="utf-8")
    settings = Settings(
        workspace_root=workspace,
        static_root=web_dir,
        audit_log_path=workspace / "audit_log.jsonl",
        host="127.0.0.1",
        port=8000,
        max_request_bytes=1024 * 1024,
        langflow_url="http://localhost:7860",
        langflow_flow_id="",
        langflow_api_key="",
        langflow_enabled=False,
        langflow_timeout_seconds=5.0,
        gemini_api_key="",
        gemini_model="gemini-3.8-flash",
        llm_provider="",
        llm_api_key="",
        llm_model_name="",
        watsonx_project_id="",
        watsonx_url="https://us-south.ml.cloud.ibm.com",
        composio_api_key="",
        composio_base_url="https://backend.composio.dev/api/v3.1/tools/execute/{action}",
        composio_user_id="test",
        composio_timeout_seconds=5.0,
        bob_mcp_config_path=workspace / "mcp.json",
        access_token="",
        audit_retention_days=90,
    )
    return TestClient(create_asgi_app(settings), base_url="http://127.0.0.1:8000")


def test_quote_not_in_source_rejected_in_builder():
    source_text = "BAB III. SPESIFIKASI TEKNIS: Server harus memiliki 64 core CPU dan 256GB RAM."
    
    # Finding with fabricated quote that is NOT in source text
    fake_findings = [
        {
            "id": "SPEC-LOCKIN-PROC",
            "category": "Spesifikasi",
            "clause": "Penguncian Merek Server",
            "requirement_evidence": "Server wajib merek Dell PowerEdge R750 tanpa opsi merek lain",  # NOT in source!
            "status": "GAP",
        }
    ]
    
    eligible = _eligible(fake_findings, source_text)
    # The fake quote must be rejected and excluded from eligible
    assert len(eligible) == 0, "Kutipan yang tidak ada di sumber asli harus ditolak oleh _eligible"

    # Verbatim quote that IS in source text
    real_findings = [
        {
            "id": "SPEC-LOCKIN-PROC",
            "category": "Spesifikasi",
            "clause": "Ketentuan CPU",
            "requirement_evidence": "Server harus memiliki 64 core CPU",  # Exact substring!
            "status": "GAP",
        }
    ]
    eligible_real = _eligible(real_findings, source_text)
    assert len(eligible_real) == 1, "Kutipan exact substring dari sumber asli harus diterima"
    assert eligible_real[0]["verbatim_quote"] == "Server harus memiliki 64 core CPU"


def _login(client: TestClient, role: str) -> None:
    response = client.post("/api/auth/login", json={"role": role})
    assert response.status_code == 200, response.text


def test_api_sanggahan_rejects_unverified_quote(client: TestClient):
    _login(client, "vendor")
    source_text = "BAB I. KETENTUAN UMUM: Pengadaan barang komputer kantor tahun 2026."
    payload = {
        "tender_id": "TND-TEST-001",
        "package_name": "Paket Komputer",
        "company_name": "PT Uji Coba",
        "notice_number": "NOT-001",
        "pokja_name": "Pokja Pengadaan",
        "source_text": source_text,
        "findings": [
            {
                "id": "SPEC-LOCKIN-PROC",
                "category": "Spesifikasi",
                "clause": "Penguncian Merek Khusus",
                "requirement_evidence": "Kutipan ini fiktif dan sama sekali tidak ada di dokumen sumber",
                "status": "GAP",
            }
        ],
        "format": "docx",
    }
    
    response = client.post("/api/v1/audit/sanggahan-doc", json=payload)
    assert response.status_code == 400
    data = response.json()
    assert "error" in data
    assert "ditolak" in data["error"]["message"].lower() or "tidak ditemukan" in data["error"]["message"].lower()


def test_api_sanggahan_rejects_missing_source_text(client: TestClient):
    _login(client, "vendor")
    payload = {
        "tender_id": "TND-TEST-002",
        "package_name": "Paket Server",
        "company_name": "PT Uji Coba",
        "notice_number": "NOT-002",
        "pokja_name": "Pokja Pengadaan",
        "source_text": "",  # Empty source text
        "findings": [],
        "format": "docx",
    }
    
    response = client.post("/api/v1/audit/sanggahan-doc", json=payload)
    assert response.status_code == 400
    data = response.json()
    assert "error" in data
    assert "tidak tersedia" in data["error"]["message"].lower() or "source_text" in str(data)


def test_sanggahan_requires_vendor_role_and_berita_acara_requires_pokja(client: TestClient):
    payload = {"source_text": "Denda 1/1000 per hari tanpa batas maksimal.", "findings": [], "format": "markdown"}
    assert client.post("/api/v1/audit/sanggahan-doc", json=payload).status_code == 401
    _login(client, "pokja")
    forbidden = client.post("/api/v1/audit/sanggahan-doc", json=payload)
    assert forbidden.status_code == 403
    assert forbidden.json()["error"]["code"] == "ROLE_FORBIDDEN"
    minutes = client.post("/api/v1/audit/minutes-eval-doc", json={"tender_id": "T-1", "vendor_name": "PT Uji", "format": "markdown", "findings": []})
    assert minutes.status_code == 200
    _login(client, "vendor")
    assert client.post("/api/v1/audit/minutes-eval-doc", json={"tender_id": "T-1", "vendor_name": "PT Uji", "format": "markdown"}).status_code == 403


def test_role_workspaces_are_separated_and_documents_render_engine_findings(client: TestClient):
    _login(client, "pokja")
    audit = client.post("/api/audit", json={
        "package_name": "Paket Pokja",
        "dok_pemilihan": "Spesifikasi wajib menggunakan prosesor Intel Xeon Gold 6430.\nMasa sanggah hanya 2 hari kerja.",
        "contract_draft": "Denda keterlambatan 1/1000 per hari dari nilai kontrak tanpa batas maksimal.",
    }).json()["data"]
    assert audit["owner_role"] == "pokja"
    assert audit["risk_level"] == "CRITICAL" and audit["risk"]["rule_applied"] == "R1"
    assert any(step["kind"] == "calculation" for step in audit["proof_log"])
    proof = client.get(f"/api/audits/{audit['audit_id']}/proof").json()["data"]
    assert proof["steps"] and proof["decision_table"]

    minutes = client.post("/api/v1/audit/minutes-eval-doc", json={"audit_id": audit["audit_id"], "format": "markdown"}).json()["data"]
    import base64
    text = base64.b64decode(minutes["content_base64"]).decode("utf-8")
    assert "CON-PENALTY" in text and "tanpa batas" in text and "Kutipan tidak tersedia" not in text
    assert "Kritis" in text

    _login(client, "vendor")
    rows = client.get("/api/audits").json()["data"]["audits"]
    assert all(row["audit_id"] != audit["audit_id"] for row in rows)
    assert client.get(f"/api/audits/{audit['audit_id']}").status_code == 400

    vendor_audit = client.post("/api/audit", json={
        "package_name": "Paket Vendor",
        "dok_pemilihan": "Spesifikasi wajib menggunakan prosesor Intel Xeon Gold 6430.\nGaransi minimal 12 bulan.",
        "pustaka": "Garansi pabrikan 12 bulan.",
    }).json()["data"]
    draft = client.post("/api/v1/audit/sanggahan-doc", json={"audit_id": vendor_audit["audit_id"], "format": "markdown"}).json()["data"]
    assert draft["findings_included"] == ["SPEC-LOCKIN-CPU"]
    boq = client.post("/api/export/boq", json={"audit_id": vendor_audit["audit_id"]})
    assert boq.status_code == 200 and boq.json()["data"]["filename"].endswith(".xlsx")


def test_unit_economics_and_benchmark_summary(client: TestClient):
    _login(client, "pokja")
    audit = client.post("/api/audit", json={"package_name": "Ekonomi", "dok_pemilihan": "Masa sanggah hanya 2 hari kerja."}).json()["data"]
    economics = client.get(f"/api/audits/{audit['audit_id']}/economics?manual_hours=8&hourly_cost_idr=100000").json()["data"]
    assert economics["tokens"]["basis"] == "estimated_from_document_length"
    assert economics["inference_cost_idr"] > 0
    assert economics["manual_review_cost_idr"] == 800000
    assert economics["machine_seconds"] > 0 and economics["time_reduction_factor"] > 1000
    assert economics["assumptions"]["manual_review_hours_per_package"] == 8
    assert "asumsi" in economics["caveat"]
    summary = client.get("/api/benchmark/summary").json()["data"]
    assert summary["status"] in {"ok", "not_generated"}

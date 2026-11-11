"""Every contracted route returns a payload that satisfies its Pydantic model."""

from __future__ import annotations

import base64
from dataclasses import replace
from pathlib import Path

import pytest

from starlette.testclient import TestClient  # noqa: E402

from bidsentry.api.routes import response_model_for  # noqa: E402
from bidsentry.asgi import create_asgi_app  # noqa: E402
from bidsentry.config import Settings  # noqa: E402
from bidsentry.lib.audit_log import AuditLog  # noqa: E402
from bidsentry.schemas import api as api_schemas  # noqa: E402

DOC = "Spesifikasi wajib menggunakan prosesor Intel Xeon Gold 6430.\nMasa sanggah hanya 2 hari kerja.\nRak 42U | 3 set | Rp 95.000.000 | Rp 300.000.000"


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    workspace = tmp_path / "ws"
    (workspace / "web").mkdir(parents=True)
    (workspace / "docs").mkdir()
    (workspace / "index.html").write_text("<html></html>", encoding="utf-8")
    settings = replace(
        Settings.from_environment(), workspace_root=workspace, static_root=workspace / "web",
        audit_log_path=workspace / "audit_log.jsonl", host="127.0.0.1", langflow_enabled=False, langflow_flow_id="",
        llm_provider="", gemini_api_key="", composio_api_key="", access_token="contract-token", pokja_pin="", vendor_pin="",
        session_secret="contract-secret",
    )
    # Sensitive routes (reviewer decisions, deletion) require a local browser or the access token.
    test_client = TestClient(create_asgi_app(settings), base_url="http://127.0.0.1:8000", raise_server_exceptions=False)
    test_client.headers.update({"Authorization": "Bearer contract-token"})
    return test_client


def _ok(response) -> dict:
    assert response.status_code == 200, response.text[:300]
    body = response.json()
    assert "error" not in body, body
    return body["data"]


def test_contract_map_covers_product_routes() -> None:
    covered = {
        ("GET", "/api/health"), ("GET", "/api/overview"), ("GET", "/api/audits"), ("GET", "/api/audits/x"),
        ("GET", "/api/audits/x/proof"), ("GET", "/api/audits/x/economics"), ("GET", "/api/benchmark/summary"),
        ("GET", "/api/demo/packages"), ("GET", "/api/risk/decision-table"), ("GET", "/api/review-feedback"),
        ("POST", "/api/audit"), ("POST", "/api/v1/audit/evaluate"), ("POST", "/api/v1/audit/sanggahan-doc"),
        ("POST", "/api/v1/audit/minutes-eval-doc"), ("POST", "/api/v1/audit/clarification-doc"), ("POST", "/api/export/boq"),
        ("POST", "/api/export/workbook"), ("POST", "/api/review-feedback"), ("POST", "/api/documents/extract"), ("DELETE", "/api/audits/x"),
    }
    for method, path in covered:
        assert response_model_for(method, path) is not None, (method, path)


def test_full_vendor_and_pokja_flow_satisfies_contracts(client: TestClient) -> None:
    session = _ok(client.post("/api/auth/login", json={"role": "vendor"}))
    api_schemas.SessionInfo.model_validate(session)
    api_schemas.Health.model_validate(_ok(client.get("/api/health")))
    api_schemas.DecisionTable.model_validate(_ok(client.get("/api/risk/decision-table")))
    api_schemas.DemoPackages.model_validate(_ok(client.get("/api/demo/packages")))
    api_schemas.BenchmarkSummary.model_validate(_ok(client.get("/api/benchmark/summary")))

    extracted = _ok(client.post("/api/documents/extract?filename=kak.txt", content=DOC.encode(), headers={"Content-Type": "application/octet-stream"}))
    api_schemas.ExtractionResponse.model_validate(extracted)

    audit = _ok(client.post("/api/audit", json={"package_name": "Kontrak", "dok_pemilihan": DOC}))
    api_schemas.AuditResult.model_validate(audit)
    audit_id = audit["audit_id"]
    api_schemas.AuditRecord.model_validate(_ok(client.get(f"/api/audits/{audit_id}")))
    api_schemas.ProofResponse.model_validate(_ok(client.get(f"/api/audits/{audit_id}/proof")))
    api_schemas.EconomicsResponse.model_validate(_ok(client.get(f"/api/audits/{audit_id}/economics")))
    api_schemas.AuditList.model_validate(_ok(client.get("/api/audits")))
    api_schemas.Overview.model_validate(_ok(client.get("/api/overview")))

    sanggahan = _ok(client.post("/api/v1/audit/sanggahan-doc", json={"audit_id": audit_id, "format": "docx"}))
    assert base64.b64decode(sanggahan["content_base64"])[:2] == b"PK"
    _ok(client.post("/api/export/boq", json={"audit_id": audit_id}))
    feedback = _ok(client.post("/api/review-feedback", json={"audit_id": audit_id, "finding_id": audit["findings"][0]["id"], "outcome": "NOT_SUPPORTED"}))
    assert feedback["reviewed_assessment"]["excluded_by_reviewer"]
    _ok(client.get(f"/api/review-feedback?audit_id={audit_id}"))
    _ok(client.post("/api/export/workbook", json={"kind": "review", "review": audit}))

    _ok(client.post("/api/auth/login", json={"role": "pokja"}))
    pokja_audit = _ok(client.post("/api/v1/audit/evaluate", json={"package_name": "Pokja", "dok_pemilihan": DOC}))
    _ok(client.post("/api/v1/audit/minutes-eval-doc", json={"audit_id": pokja_audit["audit_id"], "format": "docx"}))
    _ok(client.post("/api/v1/audit/clarification-doc", json={"audit_id": pokja_audit["audit_id"], "format": "markdown"}))
    deleted = _ok(client.delete(f"/api/audits/{pokja_audit['audit_id']}"))
    assert deleted == {"audit_id": pokja_audit["audit_id"], "deleted": True}


def test_legacy_audit_records_still_validate(client: TestClient, tmp_path: Path) -> None:
    """Audits written before the risk-tier refactor (score-based, no label) must stay readable."""
    log = AuditLog(tmp_path / "ws" / "audit_log.jsonl")
    log.append({
        "event_type": "audit.completed", "audit_id": "legacy-1", "package_name": "Audit lama",
        "verdict": "NO-GO", "risk": {"score": 72, "level": "CRITICAL", "method": "deterministic evidence checks"},
        "findings": [{"id": "CON-PENALTY", "status": "GAP", "clause": "Denda"}],
    })
    _ok(client.post("/api/auth/login", json={"role": "pokja"}))
    record = _ok(client.get("/api/audits/legacy-1"))
    assert record["risk_level"] == "CRITICAL"
    rows = _ok(client.get("/api/audits"))["audits"]
    assert any(row["audit_id"] == "legacy-1" and row["risk_label"] == "Kritis" for row in rows)


def test_session_cookie_secure_flag_follows_https(client: TestClient) -> None:
    plain = client.post("/api/auth/login", json={"role": "pokja"})
    assert "secure" not in plain.headers["set-cookie"].casefold()
    proxied = client.post("/api/auth/login", json={"role": "pokja"}, headers={"X-Forwarded-Proto": "https"})
    assert "secure" in proxied.headers["set-cookie"].casefold()


def test_static_asset_versions_match_package_version() -> None:
    """Every cache-busting ?v= in index.html and the JS modules must equal bidsentry.__version__,
    otherwise browsers keep serving stale modules after an update."""
    import re
    from pathlib import Path

    from bidsentry import __version__

    root = Path(__file__).resolve().parent.parent
    sources = [root / "index.html", *sorted((root / "web").glob("*.js"))]
    versions = {match for path in sources for match in re.findall(r"\?v=([0-9.]+)", path.read_text(encoding="utf-8"))}
    assert versions == {__version__}

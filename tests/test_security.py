"""Security and privacy tests for BidSentry."""

from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from starlette.testclient import TestClient

from bidsentry.asgi import create_asgi_app
from bidsentry.config import Settings
from bidsentry.evaluators.engine import EvaluationEngine, EvaluationRequest
from bidsentry.lib.audit_log import AuditLog
from bidsentry.lib.pii import mask_text
from bidsentry.services.langflow_service import LangflowService


@pytest.fixture
def base_settings(tmp_path: Path) -> Settings:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    web_dir = workspace / "web"
    web_dir.mkdir()
    (web_dir / "app.js").write_text("console.log('test');", encoding="utf-8")
    (workspace / "index.html").write_text("<html><body>Test</body></html>", encoding="utf-8")
    env_file = workspace / ".env"
    env_file.write_text("# test env\n", encoding="utf-8")
    return Settings(
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


def test_server_refuses_start_on_non_loopback_without_token(base_settings: Settings) -> None:
    settings_0000 = Settings(**{**base_settings.__dict__, "host": "0.0.0.0", "access_token": ""})
    with pytest.raises(SystemExit) as excinfo:
        create_asgi_app(settings_0000)
    assert "BIDSENTRY_ACCESS_TOKEN" in str(excinfo.value)


def test_access_token_enforcement(base_settings: Settings) -> None:
    settings_token = Settings(**{**base_settings.__dict__, "access_token": "secret-token-123"})
    app = create_asgi_app(settings_token)
    client = TestClient(app)

    # Health check is exempt
    res_health = client.get("/api/health")
    assert res_health.status_code == 200

    # Static assets are exempt so UI can prompt user
    res_index = client.get("/")
    assert res_index.status_code == 200

    # API endpoints require token
    res_unauth = client.get("/api/overview")
    assert res_unauth.status_code == 401
    assert res_unauth.json()["error"]["code"] == "UNAUTHORIZED"

    # Invalid token fails
    res_bad = client.get("/api/overview", headers={"Authorization": "Bearer wrong-token"})
    assert res_bad.status_code == 401

    # Valid Bearer token succeeds
    res_good = client.get("/api/overview", headers={"Authorization": "Bearer secret-token-123"})
    assert res_good.status_code == 200

    # Valid cookie token succeeds
    client.cookies.set("bidsentry_token", "secret-token-123")
    res_cookie = client.get("/api/overview")
    assert res_cookie.status_code == 200


def test_host_header_dns_rebinding_protection(base_settings: Settings) -> None:
    app = create_asgi_app(base_settings)
    client = TestClient(app)

    # Rebinding attempt with malicious external Host header
    res_evil = client.get("/api/health", headers={"Host": "attacker.com"})
    assert res_evil.status_code == 400
    assert res_evil.json()["error"]["code"] == "INVALID_HOST"

    # Legitimate local host header
    res_ok = client.get("/api/health", headers={"Host": "localhost:8000"})
    assert res_ok.status_code == 200


def test_sensitive_routes_guard_without_token(base_settings: Settings) -> None:
    app = create_asgi_app(base_settings)
    # Simulate client from non-loopback IP (e.g. 192.168.1.50) with valid Host header
    client = TestClient(app, client=("192.168.1.50", 54321), headers={"Host": "localhost:8000"})

    # Sensitive routes must be forbidden
    res_get_settings = client.get("/api/settings/integrations")
    assert res_get_settings.status_code == 403

    res_test_settings = client.get("/api/settings/integrations/test")
    assert res_test_settings.status_code == 403

    res_dispatch = client.post("/api/dispatch", json={"action": "test"})
    assert res_dispatch.status_code == 403

    res_del_audit = client.delete("/api/audits?audit_id=any-id")
    assert res_del_audit.status_code == 403


def test_sensitive_routes_allowed_with_token(base_settings: Settings) -> None:
    settings_token = Settings(**{**base_settings.__dict__, "access_token": "secret-456", "host": "127.0.0.1"})
    app = create_asgi_app(settings_token)
    client = TestClient(app, client=("192.168.1.50", 54321))

    # With valid token, authorized client can access integration settings even across network
    res = client.get("/api/settings/integrations", headers={"Authorization": "Bearer secret-456"})
    assert res.status_code == 200


def test_pii_masking_comprehensive() -> None:
    # 1. Email
    assert mask_text("Email panitia: pokja2026@kemenkes.go.id harap dicatat") == "Email panitia: [EMAIL-REDACTED] harap dicatat"

    # 2. Indonesian Phone Number
    assert mask_text("Kontak HP: 081234567890 dan telp +62 811-234-5678") == "Kontak HP: [PHONE-REDACTED] dan telp [PHONE-REDACTED]"

    # 3. Bank Account
    assert mask_text("No. Rekening: 1234567890123 Bank Mandiri") == "No. Rekening: [ACCOUNT-REDACTED] Bank Mandiri"
    assert mask_text("rek 9876543210 atas nama PT") == "rek [ACCOUNT-REDACTED] atas nama PT"

    # 4. Formatted NPWP
    assert mask_text("NPWP: 01.234.567.8-901.000 berlaku") == "NPWP: [NPWP-REDACTED] berlaku"

    # 5. Unformatted NPWP with label
    assert mask_text("NPWP 012345678901000 perusahaan") == "NPWP [NPWP-REDACTED] perusahaan"

    # 6. NIK with label
    assert mask_text("NIK: 3201234567890001 KTP Direktur") == "NIK: [NIK-REDACTED] KTP Direktur"

    # 7. Crucial: Bare IDR Money amounts MUST NOT be censored
    money_text = "Total BoQ 10160000000 dengan Pagu Anggaran 8500000000 dan rate 150000000"
    masked_money = mask_text(money_text)
    assert "10160000000" in masked_money
    assert "8500000000" in masked_money
    assert "150000000" in masked_money


def test_pii_masked_in_external_ai_payload(base_settings: Settings) -> None:
    langflow = LangflowService(base_settings)
    mock_call = MagicMock(return_value={"status": "success", "text": "{}"})
    langflow.run_structured_prompt = mock_call

    engine = EvaluationEngine(base_settings, langflow)
    findings = [
        {"id": "TEST-1", "clause": "NPWP 01.234.567.8-901.000", "review_note": "Kontak PIC: 081234567890 budi@pt.com"}
    ]
    req = EvaluationRequest(
        package_name="Test PII",
        dok_pemilihan="Hubungi 081234567890 atau email admin@tender.go.id. Nilai Rp 10.160.000.000.",
        allow_external_processing=True,
    )
    engine._contextual_extraction(req, findings)

    assert mock_call.called
    sent_payload = json.loads(mock_call.call_args[0][0])
    # Documents masked
    assert "[PHONE-REDACTED]" in sent_payload["documents"]["dok_pemilihan"]
    assert "[EMAIL-REDACTED]" in sent_payload["documents"]["dok_pemilihan"]
    assert "081234567890" not in sent_payload["documents"]["dok_pemilihan"]
    assert "admin@tender.go.id" not in sent_payload["documents"]["dok_pemilihan"]
    # Local findings masked
    sent_findings = sent_payload["local_findings"]
    assert "[NPWP-REDACTED]" in sent_findings[0]["clause"]
    assert "[PHONE-REDACTED]" in sent_findings[0]["review_note"]
    assert "[EMAIL-REDACTED]" in sent_findings[0]["review_note"]
    assert "081234567890" not in sent_findings[0]["review_note"]


def test_quote_unmasking_and_rejection_tracking(base_settings: Settings) -> None:
    langflow = LangflowService(base_settings)
    mock_resp = json.dumps({
        "scope": "Pengadaan Server",
        "brand_lockin_signals": [
            # Quote 1: Contains masked placeholder from prompt, matches original
            {"quote": "Wajib NPWP: [NPWP-REDACTED] pada penawaran", "source": "Dokumen pemilihan", "summary": "NPWP check"},
            # Quote 2: Hallucinated quote not present in original document
            {"quote": "Spesifikasi rahasia yang tidak pernah tertulis", "source": "Dokumen pemilihan", "summary": "Hallucinated"},
        ],
        "timeline_anomalies": [],
        "addendum_changes": [],
        "personnel_qualifications": [],
        "sla_uptime": [],
    })
    langflow.run_structured_prompt = MagicMock(return_value={"status": "success", "text": mock_resp, "provider": "mock"})

    engine = EvaluationEngine(base_settings, langflow)
    orig_text = "Dokumen pemilihan: Wajib NPWP: 01.234.567.8-901.000 pada penawaran peserta. Pengadaan Server."
    req = EvaluationRequest(
        package_name="Test Recovery",
        dok_pemilihan=orig_text,
        allow_external_processing=True,
    )
    result = engine._contextual_extraction(req, [])

    assert result["status"] == "success"
    # Quote 1 recovered with exact original unmasked NPWP
    assert len(result["items"]) == 1
    assert result["items"][0]["quote"] == "Wajib NPWP: 01.234.567.8-901.000 pada penawaran"
    # Quote 2 rejected and counted
    assert result["rejected_quotes_count"] == 1
    assert "1 kutipan AI ditolak karena tidak cocok dengan sumber." in result["message"]


def test_audit_retention_purge_and_atomic_write(tmp_path: Path) -> None:
    log_path = tmp_path / "audit_log.jsonl"
    log = AuditLog(log_path)

    now = datetime.now(timezone.utc)
    old_time_1 = (now - timedelta(days=120)).isoformat()
    old_time_2 = (now - timedelta(days=95)).isoformat()
    recent_time = (now - timedelta(days=10)).isoformat()

    # Append 3 events directly
    log.append({"audit_id": "old-1", "event_type": "audit.completed", "package_name": "Old 1", "created_at": old_time_1})
    log.append({"audit_id": "old-2", "event_type": "audit.completed", "package_name": "Old 2", "created_at": old_time_2})
    log.append({"audit_id": "recent-3", "event_type": "audit.completed", "package_name": "Recent", "created_at": recent_time})

    # Purge audits older than 90 days
    purged_count = log.purge_older_than(90)
    assert purged_count == 2

    # Verify old audits are gone, recent audit is preserved
    assert log.get_audit("old-1") is None
    assert log.get_audit("old-2") is None
    recent = log.get_audit("recent-3")
    assert recent is not None
    assert recent["package_name"] == "Recent"

    # Test atomic delete
    assert log.delete_audit("recent-3") is True
    assert log.get_audit("recent-3") is None

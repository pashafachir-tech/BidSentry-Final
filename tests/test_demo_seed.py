"""Stage runner: demo packages, one-command reset, and the demo packages endpoint."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from bidsentry.api.routes import ApiRouter
from bidsentry.app import create_application
from bidsentry.config import WORKSPACE_ROOT, Settings
from bidsentry.services.demo_service import load_packages, reset_and_seed


def _app(tmp_path: Path):
    settings = replace(
        Settings.from_environment(), audit_log_path=tmp_path / "audit_log.jsonl",
        langflow_enabled=False, langflow_flow_id="", llm_provider="", gemini_api_key="", composio_api_key="",
    )
    return create_application(settings)


def test_demo_packages_are_synthetic_and_role_specific() -> None:
    packages = {package["key"]: package for package in load_packages(WORKSPACE_ROOT)}
    assert set(packages) == {"A", "B"}
    assert (packages["A"]["role"], packages["B"]["role"]) == ("pokja", "vendor")
    assert all(package["synthetic"] and "Demo Paket" in package["request"]["package_name"] for package in packages.values())


def test_reset_backs_up_history_and_seeds_expected_stories(tmp_path: Path) -> None:
    application = _app(tmp_path)
    application.audit_log.append({"event_type": "audit.completed", "audit_id": "old", "package_name": "Riwayat lama"})
    report = reset_and_seed(application)

    backup = Path(report["backup"])
    assert (backup / "audit_log.jsonl").is_file(), "old history must be moved, not deleted"
    by_key = {item["key"]: item for item in report["seeded"]}
    assert by_key["A"]["role"] == "pokja" and by_key["A"]["risk_label"] == "Kritis"
    assert {"CON-PENALTY", "FIN-OVER-BUDGET"} <= set(by_key["A"]["findings"])
    assert by_key["B"]["role"] == "vendor"
    assert {"SPEC-LOCKIN-NETWORKING", "FIN-BOQ-ARITHMETIC"} <= set(by_key["B"]["findings"])

    rows = application.portfolio.list_audits()["audits"]
    assert sorted(row["owner_role"] for row in rows) == ["pokja", "vendor"]
    assert all(row["package_name"] != "Riwayat lama" for row in rows)


def test_boq_arithmetic_finding_reports_the_fifteen_million_difference(tmp_path: Path) -> None:
    application = _app(tmp_path)
    report = reset_and_seed(application, keep_history=True)
    vendor = next(item for item in report["seeded"] if item["key"] == "B")
    audit = application.audit_log.get_audit(vendor["audit_id"])
    finding = next(item for item in audit["findings"] if item["id"] == "FIN-BOQ-ARITHMETIC")
    assert finding["objectionable"] is True and "Rp 15.000.000" in finding["review_note"]


def test_demo_packages_route(tmp_path: Path) -> None:
    response = ApiRouter(_app(tmp_path)).dispatch("GET", "/api/demo/packages")
    assert response.status == 200
    assert len(response.body["data"]["packages"]) == 2

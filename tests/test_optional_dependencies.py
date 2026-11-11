"""The core app must run without the optional job-engine and provider packages."""

from __future__ import annotations

import subprocess
import sys
from dataclasses import replace
from pathlib import Path

from starlette.testclient import TestClient

from bidsentry.asgi import create_asgi_app
from bidsentry.config import Settings

ROOT = Path(__file__).resolve().parent.parent
OPTIONAL = ("arq", "redis", "sqlalchemy", "asyncpg", "aiosqlite", "pydantic_settings", "google.genai", "openai")

_BLOCKED_IMPORT_PROBE = f"""
import importlib.abc, sys
BLOCKED = {OPTIONAL!r}
class Block(importlib.abc.MetaPathFinder):
    def find_spec(self, name, path=None, target=None):
        if any(name == b or name.startswith(b + ".") for b in BLOCKED):
            raise ModuleNotFoundError(name)
        return None
sys.meta_path.insert(0, Block())
from dataclasses import replace
from starlette.testclient import TestClient
from bidsentry.asgi import create_asgi_app
from bidsentry.config import Settings
settings = replace(Settings.from_environment(), host="127.0.0.1", access_token="", job_engine="", llm_provider="", langflow_enabled=False)
client = TestClient(create_asgi_app(settings), base_url="http://127.0.0.1:8000")
assert client.get("/api/health").status_code == 200
login = client.post("/api/auth/login", json={{"role": "vendor"}})
assert login.status_code == 200, login.text
audit = client.post("/api/audit", json={{"package_name": "Uji", "dok_pemilihan": "Spesifikasi wajib merek Cisco tanpa padanan."}})
assert audit.status_code == 200, audit.text
print("CORE_OK")
"""


def test_core_app_runs_without_optional_packages(tmp_path: Path) -> None:
    env = {"PYTHONPATH": str(ROOT), "AUDIT_LOG_PATH": str(tmp_path / "audit.jsonl"), "SYSTEMROOT": __import__("os").environ.get("SYSTEMROOT", "")}
    result = subprocess.run([sys.executable, "-c", _BLOCKED_IMPORT_PROBE], cwd=tmp_path, env=env, capture_output=True, text=True, timeout=120)
    assert "CORE_OK" in result.stdout, result.stderr[-2000:]


def _settings(tmp_path: Path, job_engine: str) -> Settings:
    return replace(Settings.from_environment(), audit_log_path=tmp_path / "audit.jsonl", host="127.0.0.1", access_token="", job_engine=job_engine)


def _client(tmp_path: Path, job_engine: str) -> TestClient:
    # No ``with`` block, so the job-engine lifespan (database, Redis) never starts.
    return TestClient(create_asgi_app(_settings(tmp_path, job_engine)), base_url="http://127.0.0.1:8000")


def test_job_api_is_mounted_only_when_enabled(tmp_path: Path) -> None:
    disabled = _client(tmp_path, "").get("/api/v1/audit/jobs/abc")
    assert disabled.json()["error"]["code"] != "JOB_ENGINE_UNAVAILABLE"
    enabled = _client(tmp_path, "redis")
    for path in ("/api/v1/audit/jobs/abc", "/api/v1/audit/stream/abc"):
        response = enabled.get(path)
        assert response.status_code == 503, path
        assert response.json()["error"]["code"] == "JOB_ENGINE_UNAVAILABLE"

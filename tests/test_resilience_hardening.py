"""Regressions for bounded quote recovery, bounded provider calls and the cross-process audit log."""

from __future__ import annotations

import inspect
import subprocess
import sys
import threading
import time
import warnings
from dataclasses import replace
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from bidsentry.config import Settings
from bidsentry.evaluators import engine as engine_module
from bidsentry.evaluators.engine import EvaluationEngine, EvaluationRequest
from bidsentry.lib.audit_log import AuditLog
from bidsentry.lib.pii import mask_text, recover_unmasked_quote
from bidsentry.services.langflow_service import LangflowService
from bidsentry.services.watsonx_service import WATSONX_MAX_RETRIES, WATSONX_RETRY_DELAY_SECONDS, WatsonxService
from tests.test_integrations import _fake_watsonx

REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE = "Penanggung jawab penyedia: NIK Direktur: 3171012345670001, NPWP 01.234.567.8-901.000, telp 0812-3456-7890. Wajib merek Cisco Catalyst 9300."


def _watsonx_settings(tmp_path: Path) -> Settings:
    return replace(
        Settings.from_environment(), audit_log_path=tmp_path / "audit.jsonl", langflow_enabled=False, langflow_flow_id="",
        llm_provider="watsonx", watsonx_api_key="test-key", watsonx_project_id="test-project", llm_model_name="", gemini_api_key="",
        langflow_timeout_seconds=20,
    )


# ------------------------------------------------------------ quote recovery
def test_redacted_quote_maps_back_to_the_original_sentence() -> None:
    masked = mask_text(SOURCE)
    assert "3171012345670001" not in masked and "[NIK-REDACTED]" in masked
    assert recover_unmasked_quote(masked, SOURCE) == SOURCE


def test_quote_without_real_text_next_to_its_placeholders_is_not_verified() -> None:
    for quote in ("[NIK-REDACTED]", "[NIK-REDACTED][NPWP-REDACTED]", "a [NIK-REDACTED] b"):
        assert recover_unmasked_quote(quote, SOURCE) is None


def test_quote_recovery_stays_fast_however_many_placeholders_the_model_returns() -> None:
    # The wildcard regex this replaced needed more than 25 s for three placeholders on 20,000 characters.
    document = "Penyedia wajib menyampaikan dokumen penawaran sesuai jadwal. " * 40_000
    only_placeholders = "[NIK-REDACTED]" * 120 + " kalimat ini tidak ada di dokumen"
    near_miss = "Penyedia wajib [NAME-REDACTED] dokumen [NIK-REDACTED] penawaran [PHONE-REDACTED] yang tidak ada"
    started = time.perf_counter()
    assert recover_unmasked_quote(only_placeholders, document) is None
    assert recover_unmasked_quote(near_miss, document) is None
    assert time.perf_counter() - started < 2


# ------------------------------------------------------------ provider calls
def test_watsonx_client_gets_an_explicit_timeout_and_a_small_retry_budget(tmp_path: Path) -> None:
    fake = _fake_watsonx(lambda model_id, prompt: {"results": [{"generated_text": "{}"}]})
    with patch.dict(sys.modules, fake):
        result = WatsonxService(_watsonx_settings(tmp_path)).generate_json("{}", consent=True)
    assert result["status"] == "success"
    model = fake["ibm_watsonx_ai"].created_models[-1]
    timeout = model.api_client.httpx_client.timeout
    assert (timeout.read, timeout.connect) == (20.0, 10.0)
    assert model.api_client.project_id == "test-project"
    assert (model.max_retries, model.delay_time) == (WATSONX_MAX_RETRIES, WATSONX_RETRY_DELAY_SECONDS)
    assert WATSONX_MAX_RETRIES <= 3


def test_installed_watsonx_sdk_accepts_the_arguments_the_service_passes() -> None:
    """Guards the dependency floor: older SDKs have no ``httpx_client`` / ``max_retries``."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # third-party import noise is not what this test checks
        sdk = pytest.importorskip("ibm_watsonx_ai")
        httpx = pytest.importorskip("httpx")
        from ibm_watsonx_ai.foundation_models import ModelInference
        from ibm_watsonx_ai.utils.utils import HttpClientConfig

    config = HttpClientConfig(timeout=httpx.Timeout(20.0, connect=10.0))
    assert config.timeout.read == 20.0
    inspect.signature(sdk.APIClient.__init__).bind(None, credentials=None, project_id="p", httpx_client=config)
    inspect.signature(ModelInference.__init__).bind(None, model_id="m", api_client=None, max_retries=2, delay_time=0.5)


def test_audit_skips_the_ai_step_when_every_provider_slot_is_taken(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    settings = replace(_watsonx_settings(tmp_path), llm_provider="")
    langflow = LangflowService(settings)
    langflow.run_structured_prompt = MagicMock(return_value={"status": "success", "text": "{}"})  # type: ignore[method-assign]
    slots = threading.BoundedSemaphore(1)
    monkeypatch.setattr(engine_module, "_AI_SLOTS", slots)
    request = EvaluationRequest(dok_pemilihan="Masa sanggah 2 hari kerja.", allow_external_processing=True)

    assert slots.acquire(blocking=False)  # a stalled provider call holds the only slot
    started = time.perf_counter()
    busy = EvaluationEngine(settings, langflow).evaluate(request)
    assert time.perf_counter() - started < 2
    langflow.run_structured_prompt.assert_not_called()
    assert busy["contextual_extraction"]["status"] == "busy"
    assert busy["engine_mode"]["mode"] == "local_fallback"
    assert busy["verdict"] == "NO-GO"  # the local rules still ran
    slots.release()

    served = EvaluationEngine(settings, langflow).evaluate(request)
    langflow.run_structured_prompt.assert_called_once()
    assert served["contextual_extraction"]["status"] == "success"
    assert slots.acquire(timeout=2)  # the finished call gave its slot back


# ----------------------------------------------------------------- audit log
_WRITER = (
    "import sys\n"
    "from pathlib import Path\n"
    "from bidsentry.lib.audit_log import AuditLog\n"
    "log = AuditLog(Path(sys.argv[1]), seal_key=b'k' * 32)\n"
    "for index in range(int(sys.argv[3])):\n"
    "    log.append({'event_type': 'probe', 'writer': sys.argv[2], 'index': index})\n"
)


def test_two_processes_appending_keep_one_valid_chain(tmp_path: Path) -> None:
    path = tmp_path / "audit_log.jsonl"
    writers = [subprocess.Popen([sys.executable, "-c", _WRITER, str(path), name, "120"], cwd=REPO_ROOT) for name in ("api", "worker")]
    assert [writer.wait(timeout=120) for writer in writers] == [0, 0]
    valid, records, message = AuditLog(path, seal_key=b"k" * 32).verify_chain()
    assert (valid, records) == (True, 240), message


def test_append_finds_the_previous_hash_behind_a_record_larger_than_the_tail_window(tmp_path: Path) -> None:
    path = tmp_path / "log.jsonl"
    log = AuditLog(path, seal_key=b"k" * 32)
    log.append({"event_type": "audit.completed", "audit_id": "small"})
    big = log.append({"event_type": "audit.completed", "audit_id": "big", "findings": [{"evidence": "x" * 4000}] * 60})
    after = log.append({"event_type": "audit.completed", "audit_id": "after"})
    assert path.stat().st_size > 200_000 and after["previous_hash"] == big["hash"]
    assert log.verify_chain()[:2] == (True, 3)

    with path.open("a", encoding="utf-8") as stream:
        stream.write("baris rusak, bukan JSON\n")
    assert log.append({"event_type": "audit.completed", "audit_id": "last"})["previous_hash"] == after["hash"]

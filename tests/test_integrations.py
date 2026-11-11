from __future__ import annotations

import json
import os
import unittest
from dataclasses import replace
from unittest.mock import Mock, patch

from bidsentry.services import composio_dispatcher
from bidsentry.config import Settings
from bidsentry.services.langflow_service import LangflowService, strip_code_fence
from bidsentry.services.watsonx_service import WatsonxService


class FakeResponse:
    def __init__(self, body: dict):
        self.body = json.dumps(body).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self, _limit: int = -1) -> bytes:
        return self.body


class IntegrationAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.settings = Settings.from_environment()

    @patch("bidsentry.services.composio_dispatcher.urllib.request.urlopen")
    @patch.dict(os.environ, {"COMPOSIO_USER_ID": "bid-sentry-test-user", "COMPOSIO_API_KEY": "test-project-key"})
    def test_composio_executes_v31_tool_schema(self, urlopen: Mock) -> None:
        urlopen.return_value = FakeResponse({"successful": True, "data": {"documentId": "doc-1"}})
        result = composio_dispatcher._post_composio(
            "GOOGLEDOCS_CREATE_DOCUMENT_MARKDOWN",
            "test-project-key",
            {"title": "Audit", "markdown_text": "# Evidence"},
        )

        request = urlopen.call_args.args[0]
        payload = json.loads(request.data.decode("utf-8"))
        self.assertEqual(request.full_url, "https://backend.composio.dev/api/v3.1/tools/execute/GOOGLEDOCS_CREATE_DOCUMENT_MARKDOWN")
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(request.get_header("X-api-key"), "test-project-key")
        self.assertEqual(payload["user_id"], "bid-sentry-test-user")
        self.assertEqual(payload["version"], "latest")
        self.assertEqual(payload["arguments"]["markdown_text"], "# Evidence")
        self.assertEqual(result["successful"], True)

    @patch("bidsentry.services.composio_dispatcher._post_composio")
    @patch.dict(os.environ, {"COMPOSIO_API_KEY": "test-project-key"})
    def test_action_builders_use_current_google_tool_parameters(self, post: Mock) -> None:
        post.side_effect = [
            {"successful": True, "data": {"documentId": "doc-1"}},
            {"successful": True, "data": {"htmlLink": "https://calendar.google.com/event/1"}},
        ]
        result = composio_dispatcher.dispatch_tender_workspace({
            "nama_paket": "Paket uji",
        })

        calls = post.call_args_list
        self.assertEqual(calls[0].args[0], "GOOGLEDOCS_CREATE_DOCUMENT_MARKDOWN")
        self.assertIn("markdown_text", calls[0].args[2])
        self.assertEqual(calls[1].args[0], "GOOGLECALENDAR_CREATE_EVENT")
        calendar_args = calls[1].args[2]
        self.assertIn("start_datetime", calendar_args)
        self.assertTrue(calendar_args["start_datetime"].endswith("Z"))
        self.assertEqual(calendar_args["event_duration_minutes"], 30)
        gmail_args = composio_dispatcher._build_gmail_params({"email_penerima": "reviewer@example.test"})
        self.assertEqual(gmail_args["recipient_email"], "reviewer@example.test")
        self.assertNotIn("to", gmail_args)
        self.assertEqual(result["status"], "success")

    @patch("bidsentry.services.composio_dispatcher.urllib.request.urlopen")
    def test_composio_connection_test_only_lists_account_metadata(self, urlopen: Mock) -> None:
        configured = replace(
            self.settings,
            composio_api_key="test-project-key",
            composio_user_id="bid-sentry-test-user",
            composio_base_url="https://backend.composio.dev/api/v3.1/tools/execute/{action}",
        )
        urlopen.return_value = FakeResponse({
            "items": [
                {"toolkit": {"slug": "googledocs"}, "status": "ACTIVE"},
                {"toolkit": {"slug": "gmail"}, "status": "INITIALIZING"},
            ],
            "next_cursor": None,
        })

        result = composio_dispatcher.test_composio_connection(configured)

        request = urlopen.call_args.args[0]
        self.assertEqual(request.get_method(), "GET")
        self.assertIn("/api/v3.1/connected_accounts?", request.full_url)
        self.assertIn("user_ids=bid-sentry-test-user", request.full_url)
        self.assertEqual(result["status"], "connected")
        self.assertEqual(result["active_account_count"], 1)
        self.assertEqual(result["linked_toolkits"], ["GOOGLEDOCS"])

    @patch("bidsentry.services.composio_dispatcher.urllib.request.urlopen")
    def test_composio_test_skips_network_when_key_is_missing(self, urlopen: Mock) -> None:
        result = composio_dispatcher.test_composio_connection(replace(self.settings, composio_api_key=""))
        self.assertEqual(result["status"], "not_configured")
        urlopen.assert_not_called()

    @patch("bidsentry.services.langflow_service.urllib.request.urlopen")
    def test_langflow_connection_test_reads_flow_without_running_it(self, urlopen: Mock) -> None:
        configured = replace(
            self.settings,
            langflow_url="http://localhost:7860",
            langflow_flow_id="flow/for-test",
            langflow_api_key="langflow-test-key",
        )
        urlopen.return_value = FakeResponse({"id": "flow/for-test", "name": "Tender extraction"})

        result = LangflowService(configured).test_connection()

        request = urlopen.call_args.args[0]
        self.assertEqual(request.get_method(), "GET")
        self.assertEqual(request.full_url, "http://localhost:7860/api/v1/flows/flow%2Ffor-test")
        self.assertEqual(request.get_header("X-api-key"), "langflow-test-key")
        self.assertEqual(result["status"], "connected")
        self.assertEqual(result["flow_name"], "Tender extraction")


if __name__ == "__main__":
    unittest.main()


# ---------------------------------------------------------------------------
# High-fidelity provider simulation (no live credentials required)
# ---------------------------------------------------------------------------
import io as _io
import sys as _sys
import time as _time
import types as _types
import urllib.error as _urlerror

from bidsentry.evaluators.engine import EvaluationEngine, EvaluationRequest

_DOC = "Spesifikasi: unit wajib menggunakan prosesor Intel Xeon Gold 6430.\nMasa sanggah hanya 2 hari kerja."
_GRANITE_JSON = json.dumps({
    "scope": None,
    "brand_lockin_signals": [{"quote": "unit wajib menggunakan prosesor Intel Xeon Gold 6430", "source": "Dokumen pemilihan", "summary": "merek"}],
    "timeline_anomalies": [{"quote": "Masa sanggah hanya 2 hari kerja", "source": "Dokumen pemilihan", "summary": "durasi"}],
    "addendum_changes": [], "personnel_qualifications": [], "sla_uptime": [],
})
_FENCE = "`" * 3


def _fake_watsonx(behaviour, chat_behaviour=None, details=None):
    """Stand-ins for ``ibm_watsonx_ai`` (SDK 1.8 signatures).

    ``behaviour`` answers ``generate``; ``chat_behaviour`` (optional) answers
    ``chat``. Without ``chat_behaviour`` the fake has no ``chat`` method, which
    exercises the generation fallback used for models without chat support.
    """
    root = _types.ModuleType("ibm_watsonx_ai")
    foundation = _types.ModuleType("ibm_watsonx_ai.foundation_models")
    utils = _types.ModuleType("ibm_watsonx_ai.utils")
    utils_utils = _types.ModuleType("ibm_watsonx_ai.utils.utils")
    root.created_models = []  # every ModelInference the service builds, for assertions

    class Credentials:
        def __init__(self, url: str, api_key: str):
            self.url, self.api_key = url, api_key

    class HttpClientConfig:
        def __init__(self, timeout=None, limits=None):
            self.timeout, self.limits = timeout, limits

    class APIClient:
        def __init__(self, credentials=None, project_id=None, httpx_client=None):
            self.credentials, self.project_id, self.httpx_client = credentials, project_id, httpx_client

    class ModelInference:
        def __init__(self, model_id, params=None, api_client=None, max_retries=None, delay_time=None):
            self.model_id, self.api_client = model_id, api_client
            self.max_retries, self.delay_time = max_retries, delay_time
            root.created_models.append(self)

        def generate(self, prompt, params=None):
            return behaviour(self.model_id, prompt)

        def get_details(self):
            if isinstance(details, Exception):
                raise details
            return details or {"label": "granite-4-h-small"}

    if chat_behaviour is not None:
        def chat(self, messages, params=None):
            return chat_behaviour(self.model_id, messages)
        ModelInference.chat = chat

    root.Credentials = Credentials
    root.APIClient = APIClient
    foundation.ModelInference = ModelInference
    utils_utils.HttpClientConfig = HttpClientConfig
    root.foundation_models, root.utils, utils.utils = foundation, utils, utils_utils
    return {
        "ibm_watsonx_ai": root, "ibm_watsonx_ai.foundation_models": foundation,
        "ibm_watsonx_ai.utils": utils, "ibm_watsonx_ai.utils.utils": utils_utils,
    }


def _raise(exc: Exception):
    def behaviour(model_id, prompt):
        raise exc
    return behaviour


class ProviderFidelityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.watsonx_settings = replace(
            Settings.from_environment(), langflow_enabled=False, langflow_flow_id="", llm_provider="watsonx",
            watsonx_api_key="test-key", watsonx_project_id="test-project", llm_model_name="", gemini_api_key="",
            watsonx_model_id="ibm/granite-4-h-small", langflow_timeout_seconds=0.1,
        )
        self.langflow_settings = replace(
            self.watsonx_settings, llm_provider="", langflow_enabled=True, langflow_flow_id="flow-1",
            langflow_url="http://localhost:7860", langflow_timeout_seconds=5,
        )

    @staticmethod
    def _evaluate(settings):
        return EvaluationEngine(settings, LangflowService(settings)).evaluate(EvaluationRequest(dok_pemilihan=_DOC, allow_external_processing=True))

    @staticmethod
    def _ai_step(result):
        return next(step for step in result["proof_log"] if step["kind"] == "ai_call")

    def test_granite_success_records_tokens_latency_and_validates_quotes(self) -> None:
        def granite(model_id, prompt):
            _time.sleep(0.05)
            return {"model_id": model_id, "results": [{"generated_text": _FENCE + "json\n" + _GRANITE_JSON + "\n" + _FENCE, "generated_token_count": 142, "input_token_count": 1873, "stop_reason": "eos_token"}]}

        with patch.dict(_sys.modules, _fake_watsonx(granite)):
            result = self._evaluate(self.watsonx_settings)
        step = self._ai_step(result)
        self.assertEqual(step["status"], "ok")
        self.assertEqual(step["outputs"]["provider"], "watsonx")
        self.assertEqual(step["outputs"]["model_id"], "ibm/granite-4-h-small")
        self.assertEqual((step["outputs"]["input_tokens"], step["outputs"]["output_tokens"]), (1873, 142))
        self.assertGreaterEqual(step["duration_ms"], 40)
        self.assertFalse(step["outputs"]["fallback_to_local_rules"])
        self.assertEqual(result["engine_mode"]["mode"], "ai_assisted")
        statuses = {item["category"]: item["validation"]["status"] for item in result["contextual_extraction"]["items"]}
        self.assertEqual(statuses, {"brand_lockin_signals": "corroborated", "timeline_anomalies": "corroborated"})
        self.assertIn("pii_redaction", [s["kind"] for s in result["proof_log"]])

    def test_ten_second_granite_response_falls_back_within_budget(self) -> None:
        def slow(model_id, prompt):
            _time.sleep(10)
            return {"results": [{"generated_text": _GRANITE_JSON}]}

        started = _time.perf_counter()
        with patch.dict(_sys.modules, _fake_watsonx(slow)):
            result = self._evaluate(self.watsonx_settings)
        self.assertLess(_time.perf_counter() - started, 9, "the audit must not wait for the 10 s provider")
        step = self._ai_step(result)
        self.assertEqual((step["status"], step["outputs"]["status"]), ("failed", "timeout"))
        self.assertTrue(step["outputs"]["fallback_to_local_rules"])
        self.assertEqual(result["engine_mode"]["label"], "Mode Deterministik Lokal (Fallback Aktif)")
        self.assertEqual(result["verdict"], "NO-GO")  # local rules still caught lock-in and the short objection period

    def test_watsonx_rate_limit_429(self) -> None:
        with patch.dict(_sys.modules, _fake_watsonx(_raise(RuntimeError('Status code: 429, body: {"errors":[{"code":"too_many_requests"}]}')))):
            result = self._evaluate(self.watsonx_settings)
        self.assertEqual(self._ai_step(result)["outputs"]["status"], "rate_limited")
        self.assertEqual(result["engine_mode"]["provider_status"], "rate_limited")
        self.assertIn("HTTP 429", result["engine_mode"]["reason"])

    def test_watsonx_rejected_credentials(self) -> None:
        with patch.dict(_sys.modules, _fake_watsonx(_raise(RuntimeError("Status code: 401, Unauthorized")))):
            result = self._evaluate(self.watsonx_settings)
        self.assertEqual(result["engine_mode"]["provider_status"], "auth_failed")

    def test_langflow_rate_limit_429_with_retry_after(self) -> None:
        error = _urlerror.HTTPError("http://localhost:7860/api/v1/run/flow-1", 429, "Too Many Requests", {"Retry-After": "30"}, _io.BytesIO(b"{}"))
        with patch("bidsentry.services.langflow_service.urllib.request.urlopen", side_effect=error):
            result = self._evaluate(self.langflow_settings)
        step = self._ai_step(result)
        self.assertEqual((step["outputs"]["status"], step["outputs"]["http_status"], step["outputs"]["retry_after"]), ("rate_limited", 429, "30"))
        self.assertEqual(result["engine_mode"]["mode"], "local_fallback")

    def test_langflow_socket_timeout(self) -> None:
        with patch("bidsentry.services.langflow_service.urllib.request.urlopen", side_effect=TimeoutError("timed out")):
            result = self._evaluate(self.langflow_settings)
        self.assertEqual(self._ai_step(result)["outputs"]["status"], "timeout")

    def test_langflow_success_parses_real_response_shape(self) -> None:
        body = {"session_id": "s-1", "outputs": [{"inputs": {"input_value": "ECHO"}, "outputs": [{"results": {"message": {"text": _GRANITE_JSON}}}]}]}
        with patch("bidsentry.services.langflow_service.urllib.request.urlopen", return_value=FakeResponse(body)):
            result = self._evaluate(self.langflow_settings)
        step = self._ai_step(result)
        self.assertEqual((step["status"], step["outputs"]["provider"]), ("ok", "langflow"))
        self.assertEqual(result["engine_mode"]["mode"], "ai_assisted")

    def test_proof_log_shape_is_identical_across_modes(self) -> None:
        local = EvaluationEngine(replace(self.watsonx_settings, llm_provider="")).evaluate(EvaluationRequest(dok_pemilihan=_DOC))
        with patch.dict(_sys.modules, _fake_watsonx(_raise(RuntimeError("429")))):
            fallback = self._evaluate(self.watsonx_settings)
        for result in (local, fallback):
            ai = self._ai_step(result)
            self.assertTrue({"step_id", "kind", "actor", "status", "inputs", "outputs", "recorded_at"} <= set(ai))
            self.assertEqual(result["proof_log"][-1]["kind"], "decision")


class LiveWatsonxRegressionTests(unittest.TestCase):
    """Regressions captured from the live watsonx test (jp-tok, Nov 2026)."""

    def setUp(self) -> None:
        self.settings = replace(
            Settings.from_environment(), langflow_enabled=False, langflow_flow_id="", llm_provider="watsonx",
            watsonx_api_key="test-key", watsonx_project_id="test-project", llm_model_name="", gemini_api_key="",
            watsonx_model_id="mistralai/mistral-small-3-1-24b-instruct-2503", langflow_timeout_seconds=5,
            watsonx_url="https://jp-tok.ml.cloud.ibm.com",
        )

    def test_reply_that_continues_the_prompt_is_still_parsed(self) -> None:
        # Exact shape returned by the deprecated /text/generation endpoint during the live test.
        observed = "}\n" + _FENCE + "json\n" + _GRANITE_JSON + "\n" + _FENCE
        self.assertEqual(json.loads(strip_code_fence(observed)), json.loads(_GRANITE_JSON))
        self.assertEqual(json.loads(strip_code_fence("Berikut hasilnya: " + _GRANITE_JSON + " Selesai.")), json.loads(_GRANITE_JSON))

    def test_chat_api_is_preferred_and_reports_usage(self) -> None:
        calls = {"chat": 0, "generate": 0}

        def chat(model_id, messages):
            calls["chat"] += 1
            self.assertEqual([m["role"] for m in messages], ["system", "user"])
            return {"model_id": model_id, "choices": [{"message": {"content": _GRANITE_JSON}, "finish_reason": "stop"}], "usage": {"prompt_tokens": 3254, "completion_tokens": 167}}

        def generate(model_id, prompt):
            calls["generate"] += 1
            return {"results": [{"generated_text": "{}"}]}

        with patch.dict(_sys.modules, _fake_watsonx(generate, chat_behaviour=chat)):
            result = EvaluationEngine(self.settings, LangflowService(self.settings)).evaluate(EvaluationRequest(dok_pemilihan=_DOC, allow_external_processing=True))
        self.assertEqual(calls, {"chat": 1, "generate": 0})
        step = next(s for s in result["proof_log"] if s["kind"] == "ai_call")
        self.assertEqual((step["outputs"]["input_tokens"], step["outputs"]["output_tokens"]), (3254, 167))
        self.assertEqual(result["engine_mode"]["mode"], "ai_assisted")

    def test_model_not_available_in_region_is_reported_clearly(self) -> None:
        error = RuntimeError(
            "Model 'ibm/granite-3-8b-instruct' is not supported for this environment. Supported models: "
            "['ibm/granite-embedding-278m-multilingual', 'meta-llama/llama-3-3-70b-instruct', 'mistralai/mistral-small-3-1-24b-instruct-2503']"
        )
        settings = replace(self.settings, watsonx_model_id="ibm/granite-3-8b-instruct")
        with patch.dict(_sys.modules, _fake_watsonx(_raise(error), details=error)):
            connection = WatsonxService(settings).test_connection()
            result = EvaluationEngine(settings, LangflowService(settings)).evaluate(EvaluationRequest(dok_pemilihan=_DOC, allow_external_processing=True))
        self.assertEqual(connection["status"], "model_unavailable")
        self.assertTrue(connection["credentials_valid"])
        self.assertEqual(connection["region"], "jp-tok")
        self.assertEqual(connection["available_models"], ["meta-llama/llama-3-3-70b-instruct", "mistralai/mistral-small-3-1-24b-instruct-2503"])
        self.assertEqual(result["engine_mode"]["provider_status"], "model_unavailable")
        self.assertIn("WATSONX_MODEL_ID", result["engine_mode"]["reason"])


class WatsonxRegionStatusTests(unittest.TestCase):
    def _service(self, url: str) -> WatsonxService:
        return WatsonxService(replace(Settings.from_environment(), watsonx_url=url, watsonx_api_key="k", watsonx_project_id="p"))

    def test_status_reports_region_and_configured_model_without_region_warning(self) -> None:
        for url, region in (("https://jp-tok.ml.cloud.ibm.com", "jp-tok"), ("https://us-south.ml.cloud.ibm.com", "us-south")):
            status = self._service(url).status()
            self.assertEqual(status["region"], region)
            self.assertEqual(status["model_id"], "mistralai/mistral-small-3-1-24b-instruct-2503")
            self.assertNotIn("advice", status)

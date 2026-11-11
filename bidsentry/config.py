"""Central environment and path configuration for BidSentry."""

from __future__ import annotations

import ipaddress
import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]


def load_env_file(path: Path | None = None) -> None:
    """Load simple KEY=VALUE settings without overriding the process environment."""
    env_path = path or WORKSPACE_ROOT / ".env"
    if not env_path.is_file():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"\"", "'"}:
            value = value[1:-1]
        if key and key not in os.environ:
            os.environ[key] = value


def _flag(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _float_env(name: str, default: float) -> float:
    try:
        value = float(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default
    return value if value >= 0 and value == value and value != float("inf") else default


def _workspace_path(value: str | None, fallback: Path) -> Path:
    if not value:
        return fallback
    candidate = Path(value).expanduser()
    return (WORKSPACE_ROOT / candidate).resolve() if not candidate.is_absolute() else candidate.resolve()


def _validate_service_url(value: str, setting: str) -> None:
    parsed = urlparse(value)
    hostname = (parsed.hostname or "").casefold()
    try:
        parsed.port
    except ValueError as exc:
        raise ValueError(f"{setting} must include a valid port.") from exc
    if any(char.isspace() for char in value) or parsed.scheme not in {"http", "https"} or not hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError(f"{setting} must be an absolute http(s) URL without embedded credentials.")
    is_loopback = hostname in {"localhost", "host.docker.internal"} or hostname.endswith(".localhost")
    if not is_loopback:
        try:
            is_loopback = ipaddress.ip_address(hostname).is_loopback
        except ValueError:
            pass
    if parsed.scheme == "http" and not is_loopback:
        raise ValueError(f"{setting} must use HTTPS for non-local services.")


# Upper bound of document text sent to the AI provider per audit (about 12,000 tokens).
AI_CONTEXT_MAX_CHARS = 48_000


@dataclass(frozen=True)
class Settings:
    workspace_root: Path
    static_root: Path
    audit_log_path: Path
    host: str
    port: int
    max_request_bytes: int
    langflow_url: str
    langflow_flow_id: str
    langflow_api_key: str
    langflow_enabled: bool
    langflow_timeout_seconds: float
    gemini_api_key: str
    gemini_model: str
    llm_provider: str
    llm_api_key: str
    llm_model_name: str
    watsonx_project_id: str
    watsonx_url: str
    composio_api_key: str
    composio_base_url: str
    composio_user_id: str
    composio_timeout_seconds: float
    bob_mcp_config_path: Path
    access_token: str = ""
    audit_retention_days: int = 90
    watsonx_api_key: str = ""
    watsonx_model_id: str = "mistralai/mistral-small-3-1-24b-instruct-2503"
    job_engine: str = ""  # "redis" mounts the optional async job API
    pokja_pin: str = ""
    vendor_pin: str = ""
    session_secret: str = ""
    # Unit-economics assumptions (shown in the UI, overridable via env and per request)
    ai_price_usd_per_1m_input_tokens: float = 0.106
    ai_price_usd_per_1m_output_tokens: float = 0.318
    ai_price_source: str = "Daftar harga resmi IBM watsonx.ai untuk mistralai/mistral-small-3-1-24b-instruct-2503 (ibm.com/products/watsonx-ai/pricing, dicek 8 Nov 2026; indikatif, belum termasuk pajak)."
    usd_idr_rate: float = 16500.0
    manual_review_hours_per_package: float = 4.5
    manual_hourly_cost_idr: float = 75000.0

    @property
    def composio_entity_id(self) -> str:
        """Backward-compatible alias; Composio v3 calls this identifier user_id."""
        return self.composio_user_id

    @property
    def langflow_configured(self) -> bool:
        return self.langflow_enabled and bool(self.langflow_flow_id)

    @property
    def composio_configured(self) -> bool:
        return bool(self.composio_api_key)

    @property
    def gemini_configured(self) -> bool:
        return bool(self.gemini_api_key or (self.llm_provider == "gemini" and self.llm_api_key))

    @classmethod
    def from_environment(cls) -> "Settings":
        load_env_file()
        try:
            port = int(os.environ.get("PORT", os.environ.get("BRIDGE_PORT", "8000")))
            max_request_bytes = int(os.environ.get("MAX_REQUEST_BYTES", str(12 * 1024 * 1024)))
            timeout = float(os.environ.get("LANGFLOW_TIMEOUT_SECONDS", "30"))
            composio_timeout = float(os.environ.get("COMPOSIO_TIMEOUT_SECONDS", "30"))
        except ValueError as exc:
            raise ValueError("PORT, MAX_REQUEST_BYTES, and LANGFLOW_TIMEOUT_SECONDS must be numeric.") from exc
        if not 1 <= port <= 65535:
            raise ValueError("PORT must be between 1 and 65535.")
        if max_request_bytes < 1024:
            raise ValueError("MAX_REQUEST_BYTES must be at least 1024.")
        if timeout <= 0:
            raise ValueError("LANGFLOW_TIMEOUT_SECONDS must be positive.")
        if composio_timeout <= 0:
            raise ValueError("COMPOSIO_TIMEOUT_SECONDS must be positive.")

        langflow_url = os.environ.get("LANGFLOW_URL", os.environ.get("LANGFLOW_HOST", "http://localhost:7860")).rstrip("/")
        _validate_service_url(langflow_url, "LANGFLOW_URL")
        composio_base_url = os.environ.get("COMPOSIO_BASE_URL", "https://backend.composio.dev/api/v3.1/tools/execute/{action}").rstrip("/")
        _validate_service_url(composio_base_url, "COMPOSIO_BASE_URL")
        if "{action}" not in composio_base_url:
            raise ValueError("COMPOSIO_BASE_URL must include the {action} placeholder.")

        llm_provider = os.environ.get("LLM_PROVIDER", "").strip().casefold()
        if llm_provider not in {"", "openai", "gemini", "watsonx"}:
            raise ValueError("LLM_PROVIDER must be one of openai, gemini, or watsonx.")

        access_token = os.environ.get("BIDSENTRY_ACCESS_TOKEN", "").strip()
        try:
            audit_retention_days = int(os.environ.get("AUDIT_RETENTION_DAYS", "90"))
        except ValueError:
            audit_retention_days = 90

        return cls(
            workspace_root=WORKSPACE_ROOT,
            static_root=WORKSPACE_ROOT / "web",
            audit_log_path=_workspace_path(os.environ.get("AUDIT_LOG_PATH"), WORKSPACE_ROOT / "audit_log.jsonl"),
            host=os.environ.get("HOST", "127.0.0.1"),
            port=port,
            max_request_bytes=max_request_bytes,
            langflow_url=langflow_url,
            langflow_flow_id=os.environ.get("LANGFLOW_FLOW_ID", "").strip(),
            langflow_api_key=os.environ.get("LANGFLOW_APPLICATION_TOKEN", "").strip() or os.environ.get("LANGFLOW_API_KEY", "").strip(),
            langflow_enabled=_flag("LANGFLOW_ENABLED", False),
            langflow_timeout_seconds=timeout,
            gemini_api_key=os.environ.get("GEMINI_API_KEY", "").strip(),
            gemini_model=os.environ.get("GEMINI_MODEL", "gemini-3.8-flash").strip() or "gemini-3.8-flash",
            llm_provider=llm_provider,
            llm_api_key=os.environ.get("LLM_API_KEY", "").strip(),
            llm_model_name=os.environ.get("LLM_MODEL_NAME", "").strip(),
            watsonx_project_id=os.environ.get("WATSONX_PROJECT_ID", "").strip(),
            watsonx_url=os.environ.get("WATSONX_URL", "https://us-south.ml.cloud.ibm.com").strip().rstrip("/"),
            composio_api_key=os.environ.get("COMPOSIO_API_KEY", "").strip(),
            composio_base_url=composio_base_url,
            composio_user_id=os.environ.get("COMPOSIO_USER_ID", os.environ.get("COMPOSIO_ENTITY_ID", "default")).strip() or "default",
            composio_timeout_seconds=composio_timeout,
            bob_mcp_config_path=WORKSPACE_ROOT / "bob" / "mcp.json",
            access_token=access_token,
            audit_retention_days=audit_retention_days,
            watsonx_api_key=os.environ.get("WATSONX_API_KEY", "").strip(),
            watsonx_model_id=os.environ.get("WATSONX_MODEL_ID", "mistralai/mistral-small-3-1-24b-instruct-2503").strip() or "mistralai/mistral-small-3-1-24b-instruct-2503",
            job_engine=os.environ.get("BIDSENTRY_JOB_ENGINE", "").strip().casefold(),
            pokja_pin=os.environ.get("BIDSENTRY_POKJA_PIN", "").strip(),
            vendor_pin=os.environ.get("BIDSENTRY_VENDOR_PIN", "").strip(),
            session_secret=os.environ.get("BIDSENTRY_SESSION_SECRET", "").strip(),
            ai_price_usd_per_1m_input_tokens=_float_env("AI_PRICE_USD_PER_1M_INPUT_TOKENS", 0.106),
            ai_price_usd_per_1m_output_tokens=_float_env("AI_PRICE_USD_PER_1M_OUTPUT_TOKENS", 0.318),
            ai_price_source=os.environ.get("AI_PRICE_SOURCE", "").strip() or cls.ai_price_source,
            usd_idr_rate=_float_env("USD_IDR_RATE", 16500.0),
            manual_review_hours_per_package=_float_env("MANUAL_REVIEW_HOURS_PER_PACKAGE", 4.5),
            manual_hourly_cost_idr=_float_env("MANUAL_HOURLY_COST_IDR", 75000.0),
        )


__all__ = ["Settings", "load_env_file"]

"""Local integration settings editor backed by the ignored workspace .env file."""

from __future__ import annotations

import ipaddress
import os
import tempfile
from pathlib import Path
from threading import Lock
from typing import Any
from urllib.parse import urlparse

from bidsentry.config import Settings, WORKSPACE_ROOT
from bidsentry.types.schemas import ValidationError


MANAGED_DEFAULTS = {
    "LANGFLOW_ENABLED": "false",
    "LANGFLOW_URL": "http://localhost:7860",
    "LANGFLOW_FLOW_ID": "",
    "LANGFLOW_API_KEY": "",
    "LANGFLOW_TIMEOUT_SECONDS": "30",
    "COMPOSIO_API_KEY": "",
    "COMPOSIO_BASE_URL": "https://backend.composio.dev/api/v3.1/tools/execute/{action}",
    "COMPOSIO_USER_ID": "default",
    "COMPOSIO_TIMEOUT_SECONDS": "30",
    "WATSONX_API_KEY": "",
    "WATSONX_PROJECT_ID": "",
    "WATSONX_URL": "https://us-south.ml.cloud.ibm.com",
    "WATSONX_MODEL_ID": "mistralai/mistral-small-3-1-24b-instruct-2503",
}


class SettingsService:
    """Read safe integration status and atomically edit local .env values."""

    def __init__(self, env_path: Path | None = None):
        self.env_path = env_path or WORKSPACE_ROOT / ".env"
        self._lock = Lock()

    @staticmethod
    def public_settings(settings: Settings, config_file_exists: bool) -> dict[str, Any]:
        return {
            "config_file": ".env lokal",
            "config_file_exists": config_file_exists,
            "langflow": {
                "enabled": settings.langflow_enabled,
                "configured": settings.langflow_configured,
                "url": settings.langflow_url,
                "flow_id": settings.langflow_flow_id,
                "api_key_saved": bool(settings.langflow_api_key),
                "timeout_seconds": settings.langflow_timeout_seconds,
            },
            "composio": {
                "configured": settings.composio_configured,
                "api_key_saved": bool(settings.composio_api_key),
                "base_url": settings.composio_base_url,
                "user_id": settings.composio_user_id,
                "timeout_seconds": settings.composio_timeout_seconds,
            },
            "watsonx": {
                "configured": bool((getattr(settings, "watsonx_api_key", "") or getattr(settings, "llm_api_key", "")) and getattr(settings, "watsonx_project_id", "")),
                "api_key_saved": bool(getattr(settings, "watsonx_api_key", "") or getattr(settings, "llm_api_key", "")),
                "project_id": getattr(settings, "watsonx_project_id", ""),
                "url": getattr(settings, "watsonx_url", "https://us-south.ml.cloud.ibm.com"),
                "model_id": getattr(settings, "watsonx_model_id", "mistralai/mistral-small-3-1-24b-instruct-2503") or "mistralai/mistral-small-3-1-24b-instruct-2503",
            },
        }

    def save(self, payload: Any) -> Settings:
        with self._lock:
            return self._save_locked(payload)

    def _save_locked(self, payload: Any) -> Settings:
        if not isinstance(payload, dict):
            raise ValidationError("Pengaturan harus berupa objek.", [{"field": "$", "issue": "expected_object"}])

        allowed = {
            "langflow_enabled", "langflow_url", "langflow_flow_id", "langflow_api_key", "clear_langflow_api_key",
            "langflow_timeout_seconds", "composio_base_url", "composio_user_id", "composio_entity_id", "composio_api_key",
            "clear_composio_api_key", "composio_timeout_seconds",
            "watsonx_api_key", "watsonx_project_id", "watsonx_url", "watsonx_model_id", "clear_watsonx_api_key",
        }
        unknown = sorted(set(payload) - allowed)
        if unknown:
            raise ValidationError("Ada kolom pengaturan yang tidak dikenal.", [{"field": item, "issue": "unknown_field"} for item in unknown])

        values = self._current_values()
        enabled = payload.get("langflow_enabled", values["LANGFLOW_ENABLED"].lower() in {"true", "1", "yes", "on"})
        if not isinstance(enabled, bool):
            raise ValidationError("Status aktif Langflow harus berupa pilihan ya/tidak.", [{"field": "langflow_enabled", "issue": "expected_boolean"}])
        values["LANGFLOW_ENABLED"] = "true" if enabled else "false"

        string_fields = {
            "langflow_url": ("LANGFLOW_URL", 2048),
            "langflow_flow_id": ("LANGFLOW_FLOW_ID", 240),
            "langflow_api_key": ("LANGFLOW_API_KEY", 4096),
            "composio_base_url": ("COMPOSIO_BASE_URL", 2048),
            "composio_user_id": ("COMPOSIO_USER_ID", 200),
            "composio_entity_id": ("COMPOSIO_USER_ID", 200),
            "composio_api_key": ("COMPOSIO_API_KEY", 4096),
            "watsonx_api_key": ("WATSONX_API_KEY", 4096),
            "watsonx_project_id": ("WATSONX_PROJECT_ID", 240),
            "watsonx_url": ("WATSONX_URL", 2048),
            "watsonx_model_id": ("WATSONX_MODEL_ID", 200),
        }
        for field, (key, maximum) in string_fields.items():
            if field not in payload:
                continue
            value = payload[field]
            if not isinstance(value, str):
                raise ValidationError(f"'{field}' harus berupa teks.", [{"field": field, "issue": "expected_string"}])
            value = value.strip()
            if len(value) > maximum:
                raise ValidationError(f"'{field}' terlalu panjang.", [{"field": field, "issue": "too_long"}])
            if any(char in value for char in "\r\n\x00"):
                raise ValidationError(f"'{field}' berisi karakter yang tidak diizinkan.", [{"field": field, "issue": "invalid_characters"}])
            if field.endswith("_api_key") and not value:
                # An empty password input preserves the existing credential.
                continue
            values[key] = value

        for field, key in (("clear_langflow_api_key", "LANGFLOW_API_KEY"), ("clear_composio_api_key", "COMPOSIO_API_KEY"), ("clear_watsonx_api_key", "WATSONX_API_KEY")):
            clear = payload.get(field, False)
            if not isinstance(clear, bool):
                raise ValidationError(f"'{field}' harus berupa pilihan ya/tidak.", [{"field": field, "issue": "expected_boolean"}])
            if clear:
                values[key] = ""

        for field, key in (("langflow_timeout_seconds", "LANGFLOW_TIMEOUT_SECONDS"), ("composio_timeout_seconds", "COMPOSIO_TIMEOUT_SECONDS")):
            if field in payload:
                raw = payload[field]
                try:
                    seconds = float(raw)
                except (TypeError, ValueError):
                    raise ValidationError(f"'{field}' harus berupa angka.", [{"field": field, "issue": "expected_number"}]) from None
                if not 1 <= seconds <= 120:
                    raise ValidationError("Timeout harus antara 1 dan 120 detik.", [{"field": field, "issue": "out_of_range"}])
                values[key] = str(int(seconds)) if seconds.is_integer() else str(seconds)

        for key, value in values.items():
            if any(char in value for char in "\r\n\x00"):
                raise ValidationError("Pengaturan berisi karakter yang tidak diizinkan.", [{"field": key, "issue": "invalid_characters"}])

        self._validate_url(values["LANGFLOW_URL"], "langflow_url")
        if values.get("WATSONX_URL"):
            self._validate_url(values["WATSONX_URL"], "watsonx_url")
        base_url = values["COMPOSIO_BASE_URL"]
        self._validate_url(base_url, "composio_base_url")
        if "{action}" not in base_url:
            raise ValidationError("URL Composio harus memuat penanda {action}.", [{"field": "composio_base_url", "issue": "action_placeholder_required"}])
        if not values["COMPOSIO_USER_ID"]:
            raise ValidationError("User ID Composio tidak boleh kosong.", [{"field": "composio_user_id", "issue": "required"}])

        self._write_env(values)
        # A .env editor must supersede process values for managed fields;
        # unrelated process configuration remains untouched.
        for key, value in values.items():
            os.environ[key] = value
        return Settings.from_environment()

    def _current_values(self) -> dict[str, str]:
        file_values = self._read_env()
        return {key: os.environ.get(key, file_values.get(key, default)) for key, default in MANAGED_DEFAULTS.items()}

    def _read_env(self) -> dict[str, str]:
        if not self.env_path.is_file():
            example = WORKSPACE_ROOT / ".env.example"
            path = example if example.is_file() else None
        else:
            path = self.env_path
        result: dict[str, str] = {}
        if path is None:
            return result
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError as exc:
            raise ValidationError("File konfigurasi lokal tidak dapat dibaca.", [{"field": ".env", "issue": type(exc).__name__}]) from None
        for line in lines:
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, value = stripped.split("=", 1)
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in {"\"", "'"}:
                value = value[1:-1]
            result[key.strip()] = value
        return result

    def _write_env(self, values: dict[str, str]) -> None:
        try:
            old_lines = self.env_path.read_text(encoding="utf-8").splitlines() if self.env_path.is_file() else []
            if not old_lines:
                example = WORKSPACE_ROOT / ".env.example"
                if example.is_file():
                    old_lines = example.read_text(encoding="utf-8").splitlines()
            seen: set[str] = set()
            new_lines: list[str] = []
            for line in old_lines:
                stripped = line.strip()
                key = stripped.split("=", 1)[0].strip() if stripped and not stripped.startswith("#") and "=" in stripped else ""
                if key not in values:
                    new_lines.append(line)
                    continue
                if key in seen:
                    continue
                seen.add(key)
                new_lines.append(f'{key}="{values[key]}"')
            for key, value in values.items():
                if key not in seen:
                    new_lines.append(f'{key}="{value}"')
            self.env_path.parent.mkdir(parents=True, exist_ok=True)
            content = "\n".join(new_lines).rstrip() + "\n"
            fd, temp_name = tempfile.mkstemp(prefix=".env-", suffix=".tmp", dir=self.env_path.parent)
            try:
                with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
                    handle.write(content)
                    handle.flush()
                    os.fsync(handle.fileno())
                Path(temp_name).replace(self.env_path)
            finally:
                if os.path.exists(temp_name):
                    os.unlink(temp_name)
        except OSError as exc:
            raise ValidationError("File konfigurasi lokal tidak dapat disimpan.", [{"field": ".env", "issue": type(exc).__name__}]) from None

    @staticmethod
    def _validate_url(value: str, field: str) -> None:
        parsed = urlparse(value)
        hostname = (parsed.hostname or "").casefold()
        try:
            parsed.port
        except ValueError:
            raise ValidationError("URL harus berupa alamat http(s) yang valid tanpa kredensial di URL.", [{"field": field, "issue": "invalid_url"}]) from None
        is_loopback = hostname in {"localhost", "host.docker.internal"} or hostname.endswith(".localhost")
        if not is_loopback:
            try:
                is_loopback = ipaddress.ip_address(hostname).is_loopback
            except ValueError:
                pass
        if any(char.isspace() for char in value) or parsed.scheme not in {"http", "https"} or not hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValidationError("URL harus berupa alamat http(s) yang valid tanpa kredensial di URL.", [{"field": field, "issue": "invalid_url"}])
        if parsed.scheme == "http" and not is_loopback:
            raise ValidationError("URL layanan eksternal harus menggunakan HTTPS agar API key tidak dikirim tanpa enkripsi.", [{"field": field, "issue": "https_required"}])

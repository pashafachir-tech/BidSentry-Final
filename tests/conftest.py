"""Pytest configuration for BidSentry.

Only one warning is filtered, and only by exact category and message:
Starlette deprecates driving ``TestClient`` with ``httpx`` in favour of
``httpx2``. The application itself never imports httpx; it is a test-only
transport. Install ``httpx2`` in the test environment to remove this filter.

ResourceWarning and every other DeprecationWarning are deliberately NOT
filtered; ``python -X dev -m pytest`` must stay clean.
"""

from __future__ import annotations

import os

# Hermetic tests: the developer's .env may hold real watsonx / Langflow / Composio
# credentials. Pre-setting these variables (load_env_file never overrides an
# existing variable) guarantees the suite never calls a live provider or spends
# quota. Tests that need a provider configure it explicitly with mocks.
_HERMETIC_ENV = {
    "LANGFLOW_ENABLED": "false", "LANGFLOW_FLOW_ID": "", "LANGFLOW_API_KEY": "", "LANGFLOW_APPLICATION_TOKEN": "",
    "LLM_PROVIDER": "", "LLM_API_KEY": "", "LLM_MODEL_NAME": "", "GEMINI_API_KEY": "",
    "WATSONX_API_KEY": "", "WATSONX_PROJECT_ID": "", "WATSONX_MODEL_ID": "",
    "COMPOSIO_API_KEY": "", "BIDSENTRY_ACCESS_TOKEN": "", "BIDSENTRY_POKJA_PIN": "", "BIDSENTRY_VENDOR_PIN": "",
    "BIDSENTRY_SESSION_SECRET": "",
}
for _key, _value in _HERMETIC_ENV.items():
    os.environ[_key] = _value

HTTPX_TESTCLIENT_FILTER = (
    "ignore:Using `httpx` with `starlette.testclient` is deprecated"
    ":starlette.exceptions.StarletteDeprecationWarning"
)


_LOOPBACK = {"127.0.0.1", "::1", "localhost"}


def _loopback_only_connect(original):
    def connect(sock, address):  # noqa: ANN001
        host = address[0] if isinstance(address, tuple) else str(address)
        if isinstance(host, str) and host not in _LOOPBACK and not host.startswith("127."):
            raise OSError(f"Network access to {host!r} is blocked in tests; mock the provider instead.")
        return original(sock, address)
    return connect


def pytest_configure(config) -> None:  # noqa: ANN001 - pytest hook signature
    import socket

    config.addinivalue_line("filterwarnings", HTTPX_TESTCLIENT_FILTER)
    # Any test that reaches the internet fails immediately (and loudly) instead of
    # silently depending on — or billing — a live watsonx/Langflow/Composio account.
    socket.socket.connect = _loopback_only_connect(socket.socket.connect)

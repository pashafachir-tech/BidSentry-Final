"""Wrong-PIN lockout for the Pokja / Vendor login."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from bidsentry.asgi import create_asgi_app
from bidsentry.config import Settings
from bidsentry.core.auth import LOGIN_THROTTLE, AuthError, LoginThrottle, login


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return replace(
        Settings.from_environment(), audit_log_path=tmp_path / "audit.jsonl", host="127.0.0.1",
        langflow_enabled=False, langflow_flow_id="", llm_provider="", access_token="",
        pokja_pin="2468", vendor_pin="1357", session_secret="throttle-test-secret",
    )


def test_five_wrong_pins_lock_the_role_even_for_the_right_pin(settings: Settings) -> None:
    clock = FakeClock()
    throttle = LoginThrottle(clock=clock)
    for _ in range(5):
        with pytest.raises(AuthError) as wrong:
            login("pokja", "0000", settings, client="10.0.0.5", throttle=throttle)
        assert wrong.value.code == "INVALID_PIN"
    with pytest.raises(AuthError) as locked:
        login("pokja", "2468", settings, client="10.0.0.5", throttle=throttle)
    assert (locked.value.code, locked.value.status) == ("TOO_MANY_ATTEMPTS", 429)
    assert 0 < locked.value.retry_after <= 301


def test_lock_is_scoped_to_client_and_role_and_expires(settings: Settings) -> None:
    clock = FakeClock()
    throttle = LoginThrottle(clock=clock)
    for _ in range(5):
        with pytest.raises(AuthError):
            login("pokja", "0000", settings, client="10.0.0.5", throttle=throttle)
    assert login("pokja", "2468", settings, client="10.0.0.6", throttle=throttle)  # other client
    assert login("vendor", "1357", settings, client="10.0.0.5", throttle=throttle)  # other role
    clock.now += 301
    assert login("pokja", "2468", settings, client="10.0.0.5", throttle=throttle)


def test_success_resets_and_old_failures_age_out(settings: Settings) -> None:
    clock = FakeClock()
    throttle = LoginThrottle(clock=clock)
    for _ in range(4):
        with pytest.raises(AuthError):
            login("pokja", "0000", settings, client="c", throttle=throttle)
    login("pokja", "2468", settings, client="c", throttle=throttle)
    for _ in range(4):
        with pytest.raises(AuthError):
            login("pokja", "0000", settings, client="c", throttle=throttle)
    clock.now += 901  # outside the 15-minute window
    with pytest.raises(AuthError) as wrong:
        login("pokja", "0000", settings, client="c", throttle=throttle)
    assert wrong.value.code == "INVALID_PIN"


def test_api_returns_429_with_retry_after_and_logs_failures(settings: Settings) -> None:
    client = TestClient(create_asgi_app(settings), base_url="http://127.0.0.1:8000")
    try:
        for _ in range(5):
            assert client.post("/api/auth/login", json={"role": "vendor", "pin": "9999"}).status_code == 401
        blocked = client.post("/api/auth/login", json={"role": "vendor", "pin": "1357"})
        assert blocked.status_code == 429
        assert blocked.json()["error"]["code"] == "TOO_MANY_ATTEMPTS"
        assert int(blocked.headers["retry-after"]) > 0
        records = [json.loads(line) for line in settings.audit_log_path.read_text(encoding="utf-8").splitlines()]
        failures = [record for record in records if record["event_type"] == "auth.login_failed"]
        assert len(failures) == 6
        # PINs are never logged (compare field values: hex hashes may contain any digits).
        logged_values = {str(value) for record in records for key, value in record.items() if key not in {"hash", "previous_hash"}}
        assert not any("pin" in key for record in records for key in record)
        assert not logged_values & {"9999", "1357"}
    finally:
        LOGIN_THROTTLE.record_success("testclient", "vendor")

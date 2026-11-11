"""Demo-grade role login for the two BidSentry personas: Pokja and Vendor.

A user chooses a role and (when configured) enters that role's PIN. The server
issues an HMAC-signed, HttpOnly session cookie that carries only the role and an
expiry. Every role-specific endpoint checks this cookie server-side, so the
Pokja and Vendor flows are separated in the backend, not just in the UI.

PINs come from ``BIDSENTRY_POKJA_PIN`` / ``BIDSENTRY_VENDOR_PIN``. When a PIN is
unset the role can log in without one **only** while the server listens on a
loopback host (local demo). This is not a substitute for an identity provider.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import threading
import time
from enum import Enum
from typing import Any

from bidsentry.config import Settings

SESSION_COOKIE = "bidsentry_session"
SESSION_TTL_SECONDS = 8 * 3600
SECRET_FILENAME = ".bidsentry_session_secret"
_SECRET_CACHE: dict[str, bytes] = {}


class Role(str, Enum):
    POKJA = "pokja"
    VENDOR = "vendor"

    @property
    def label(self) -> str:
        return {"pokja": "Pokja Pemilihan", "vendor": "Penyedia / Vendor"}[self.value]

    @property
    def capabilities(self) -> list[str]:
        return {
            "pokja": ["audit.create", "audit.read", "document.berita_acara", "document.klarifikasi", "export.boq", "export.review"],
            "vendor": ["audit.create", "audit.read", "document.sanggahan", "export.boq", "export.review"],
        }[self.value]


class AuthError(Exception):
    def __init__(self, code: str, message: str, status: int):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status
        self.retry_after: int | None = None


def _secret(settings: Settings) -> bytes:
    """Signing key: BIDSENTRY_SESSION_SECRET, else a persisted random key.

    The fallback key is generated once and stored next to the audit log
    (owner-only permissions where the OS supports it), so a server reload does
    not log Pokja and Vendor users out in the middle of a demo or review.
    """
    configured = getattr(settings, "session_secret", "") or ""
    if configured:
        return configured.encode("utf-8")
    path = settings.audit_log_path.parent / SECRET_FILENAME
    key = str(path)
    if key in _SECRET_CACHE:
        return _SECRET_CACHE[key]
    secret: bytes | None = None
    try:
        if path.is_file():
            stored = bytes.fromhex(path.read_text(encoding="ascii").strip())
            secret = stored if len(stored) >= 32 else None
    except (OSError, ValueError):
        secret = None
    if secret is None:
        secret = secrets.token_bytes(32)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(secret.hex(), encoding="ascii")
            path.chmod(0o600)
        except OSError:
            pass  # read-only workspace: sessions last for this process only
    _SECRET_CACHE[key] = secret
    return secret


def audit_seal_key(settings: Settings) -> bytes:
    """Key for the audit log's HMAC seal, derived so it never equals the session key."""
    return hmac.new(_secret(settings), b"bidsentry-audit-log-seal", hashlib.sha256).digest()


class LoginThrottle:
    """Lock a (client, role) pair after repeated wrong PINs.

    PINs are short, so without this an exposed server could be brute-forced.
    Five failures inside 15 minutes lock that client out of that role for
    5 minutes; a successful login clears the counter. State is in memory,
    which is enough for the single-process demo server.
    """

    def __init__(self, max_failures: int = 5, window_seconds: int = 900, lock_seconds: int = 300, clock: Any = time.monotonic):
        self.max_failures = max_failures
        self.window_seconds = window_seconds
        self.lock_seconds = lock_seconds
        self._clock = clock
        self._lock = threading.Lock()
        self._failures: dict[tuple[str, str], list[float]] = {}
        self._locked_until: dict[tuple[str, str], float] = {}

    def retry_after(self, client: str, role: str) -> int:
        """Seconds until this client may try again (0 when not locked)."""
        with self._lock:
            until = self._locked_until.get((client, role), 0.0)
            remaining = until - self._clock()
            if remaining <= 0:
                self._locked_until.pop((client, role), None)
                return 0
            return int(remaining) + 1

    def record_failure(self, client: str, role: str) -> None:
        now = self._clock()
        key = (client, role)
        with self._lock:
            recent = [at for at in self._failures.get(key, []) if now - at < self.window_seconds]
            recent.append(now)
            if len(recent) >= self.max_failures:
                self._locked_until[key] = now + self.lock_seconds
                recent = []
            self._failures[key] = recent

    def record_success(self, client: str, role: str) -> None:
        with self._lock:
            self._failures.pop((client, role), None)
            self._locked_until.pop((client, role), None)


LOGIN_THROTTLE = LoginThrottle()


def _pin_for(role: Role, settings: Settings) -> str:
    return (settings.pokja_pin if role is Role.POKJA else settings.vendor_pin) or ""


def _is_loopback(host: str) -> bool:
    return host.strip().casefold() in {"127.0.0.1", "localhost", "::1"}


def pin_required(role: Role, settings: Settings) -> bool:
    return bool(_pin_for(role, settings)) or not _is_loopback(settings.host)


def login(role_value: Any, pin: Any, settings: Settings, client: str = "", throttle: LoginThrottle | None = None) -> str:
    """Validate credentials and return a signed session token.

    ``client`` identifies the caller (its IP address) for the wrong-PIN lockout.
    """
    try:
        role = Role(str(role_value or "").strip().casefold())
    except ValueError as exc:
        raise AuthError("INVALID_ROLE", "Pilih peran Pokja atau Vendor.", 400) from exc
    guard = throttle or LOGIN_THROTTLE
    expected = _pin_for(role, settings)
    if expected:
        wait = guard.retry_after(client, role.value)
        if wait:
            error = AuthError("TOO_MANY_ATTEMPTS", f"Terlalu banyak PIN salah. Coba lagi dalam {wait} detik.", 429)
            error.retry_after = wait
            raise error
        if not isinstance(pin, str) or not hmac.compare_digest(pin.strip().encode("utf-8"), expected.encode("utf-8")):
            guard.record_failure(client, role.value)
            raise AuthError("INVALID_PIN", "PIN tidak sesuai untuk peran ini.", 401)
        guard.record_success(client, role.value)
    elif not _is_loopback(settings.host):
        raise AuthError("ROLE_DISABLED", f"PIN {role.label} belum dikonfigurasi pada server non-lokal.", 403)
    return issue_token(role, settings)


def issue_token(role: Role, settings: Settings, now: float | None = None) -> str:
    payload = {"role": role.value, "exp": int((now if now is not None else time.time()) + SESSION_TTL_SECONDS), "nonce": secrets.token_hex(8)}
    body = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode("utf-8")).decode("ascii").rstrip("=")
    signature = hmac.new(_secret(settings), body.encode("ascii"), hashlib.sha256).hexdigest()
    return f"{body}.{signature}"


def role_from_token(token: str | None, settings: Settings, now: float | None = None) -> Role | None:
    if not token or "." not in token:
        return None
    body, signature = token.rsplit(".", 1)
    expected = hmac.new(_secret(settings), body.encode("ascii", "ignore"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        return None
    try:
        payload = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
        if int(payload.get("exp", 0)) < (now if now is not None else time.time()):
            return None
        return Role(payload.get("role"))
    except (ValueError, TypeError, json.JSONDecodeError):
        return None


def require_role(role: Role | str | None, *allowed: Role) -> Role:
    """Raise 401 when not logged in, 403 when logged in with the wrong role."""
    if role is None or role == "":
        raise AuthError("LOGIN_REQUIRED", "Masuk sebagai Pokja atau Vendor terlebih dahulu.", 401)
    resolved = Role(role) if not isinstance(role, Role) else role
    if resolved not in allowed:
        names = " atau ".join(item.label for item in allowed)
        raise AuthError("ROLE_FORBIDDEN", f"Fitur ini hanya untuk {names}. Anda masuk sebagai {resolved.label}.", 403)
    return resolved


def describe(role: Role | None, settings: Settings) -> dict[str, Any]:
    return {
        "authenticated": role is not None,
        "role": role.value if role else None,
        "label": role.label if role else None,
        "capabilities": role.capabilities if role else [],
        "roles": [
            {"role": item.value, "label": item.label, "pin_required": pin_required(item, settings)}
            for item in Role
        ],
    }


__all__ = ["AuthError", "Role", "SESSION_COOKIE", "audit_seal_key", "describe", "issue_token", "login", "require_role", "role_from_token"]

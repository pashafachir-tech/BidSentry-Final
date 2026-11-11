"""Append-only SHA-256 hash chain for tamper-evident audit metadata."""

from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator


GENESIS_HASH = "0" * 64
_LOCK_POLL_SECONDS = 0.02
_LOCK_TIMEOUT_SECONDS = 30.0


@dataclass(frozen=True, slots=True)
class ImmutableAuditDigest:
    """Immutable digest returned by the deterministic audit hash function."""

    previous_hash: str
    tender_id: str
    vendor_id: str
    audit_result_sha256: str
    digest: str


def compute_audit_digest(
    previous_hash: str,
    tender_id: str,
    vendor_id: str,
    audit_result_json: str | dict[str, Any],
) -> ImmutableAuditDigest:
    """Hash ``previous_hash + tender_id + vendor_id + audit_result_json``.

    Dict results are serialized using :func:`canonical_json`; callers that
    provide a JSON string are responsible for passing its canonical form.
    """

    if len(previous_hash) != 64 or any(char not in "0123456789abcdef" for char in previous_hash):
        raise ValueError("previous_hash must be a lowercase SHA-256 hex digest.")
    if not tender_id or not vendor_id:
        raise ValueError("tender_id and vendor_id must be non-empty.")
    result_json = canonical_json(audit_result_json) if isinstance(audit_result_json, dict) else audit_result_json
    if not isinstance(result_json, str):
        raise TypeError("audit_result_json must be a JSON string or dictionary.")
    result_hash = hashlib.sha256(result_json.encode("utf-8")).hexdigest()
    digest = hashlib.sha256((previous_hash + tender_id + vendor_id + result_json).encode("utf-8")).hexdigest()
    return ImmutableAuditDigest(previous_hash, tender_id, vendor_id, result_hash, digest)


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


class HashChainedAuditTrail:
    """Store hashes and verdict metadata only; source documents are never logged."""

    def __init__(self, path: Path):
        self.path = path
        self._lock = threading.Lock()

    def append(
        self,
        audit_run_id: str,
        input_payload: dict[str, Any],
        extracted_quotes: list[dict[str, Any]],
        scoring_weights: dict[str, Any],
        verdict: dict[str, Any],
    ) -> dict[str, Any]:
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with exclusive_file_lock(self.path.with_name(self.path.name + ".lock")):
                current_state = self.verify()
                if not current_state.get("valid"):
                    raise RuntimeError("Existing comprehensive audit trail failed its hash-chain verification.")
                existing = self._record_for_audit_run(audit_run_id)
                input_hash = sha256_json(input_payload)
                quotes_hash = sha256_json(extracted_quotes)
                weights_hash = sha256_json(scoring_weights)
                verdict_hash = sha256_json(verdict)
                if existing is not None:
                    expected = (
                        input_hash,
                        quotes_hash,
                        weights_hash,
                        verdict_hash,
                    )
                    observed = tuple(
                        existing.get(key)
                        for key in (
                            "input_payload_sha256",
                            "extracted_quotes_sha256",
                            "scoring_weights_sha256",
                            "verdict_sha256",
                        )
                    )
                    if observed != expected:
                        raise RuntimeError("Audit run ID already exists with different input or result hashes.")
                    return self._public_record(existing)
                previous_hash, sequence = self._last_hash_and_sequence()
                tender_id = str(input_payload.get("tender_id") or "")
                vendor_id = str(input_payload.get("vendor_id") or "")
                if not tender_id or not vendor_id:
                    raise ValueError("input_payload must include tender_id and vendor_id for the audit chain.")
                audit_result_json = canonical_json({
                    "input_payload_sha256": input_hash,
                    "extracted_quotes_sha256": quotes_hash,
                    "scoring_weights_sha256": weights_hash,
                    "verdict_sha256": verdict_hash,
                })
                record: dict[str, Any] = {
                    "schema_version": "1.0",
                    "digest_algorithm": "sha256-concatenated-v1",
                    "sequence": sequence + 1,
                    "recorded_at": datetime.now(timezone.utc).isoformat(),
                    "audit_run_id": audit_run_id,
                    "tender_id": tender_id,
                    "vendor_id": vendor_id,
                    "previous_hash": previous_hash,
                    "input_payload_sha256": input_hash,
                    "extracted_quotes_sha256": quotes_hash,
                    "scoring_weights_sha256": weights_hash,
                    "verdict_sha256": verdict_hash,
                    "audit_result_json": audit_result_json,
                }
                chain_hash = compute_audit_digest(
                    previous_hash,
                    tender_id,
                    vendor_id,
                    audit_result_json,
                ).digest
                record["chain_hash"] = chain_hash
                line = canonical_json(record) + "\n"
                with self.path.open("a", encoding="utf-8", newline="\n") as stream:
                    stream.write(line)
                    stream.flush()
                    os.fsync(stream.fileno())
                return self._public_record(record)

    def _record_for_audit_run(self, audit_run_id: str) -> dict[str, Any] | None:
        if not self.path.is_file():
            return None
        try:
            with self.path.open("r", encoding="utf-8") as stream:
                for line in stream:
                    value = json.loads(line)
                    if isinstance(value, dict) and value.get("audit_run_id") == audit_run_id:
                        return value
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, TypeError) as exc:
            raise RuntimeError("Unable to search the comprehensive audit trail.") from exc
        return None

    @staticmethod
    def _public_record(record: dict[str, Any]) -> dict[str, Any]:
        return {
            "sequence": record["sequence"],
            "previous_hash": record["previous_hash"],
            "input_payload_sha256": record["input_payload_sha256"],
            "extracted_quotes_sha256": record["extracted_quotes_sha256"],
            "scoring_weights_sha256": record["scoring_weights_sha256"],
            "verdict_sha256": record["verdict_sha256"],
            "chain_hash": record["chain_hash"],
            "verification": "hash_chain_recorded",
            "tamper_evident": True,
            "non_repudiation_guaranteed": False,
            "limitation": "Hash chain lokal mendeteksi perubahan pada rantai yang tersimpan, tetapi tanpa tanda tangan kunci eksternal atau anchor waktu pihak ketiga tidak menjamin non-repudiation.",
        }

    def verify(self) -> dict[str, Any]:
        previous = GENESIS_HASH
        checked = 0
        try:
            if not self.path.is_file():
                return {"valid": True, "records_checked": 0, "chain_head": GENESIS_HASH}
            with self.path.open("r", encoding="utf-8") as stream:
                for expected_sequence, line in enumerate(stream, 1):
                    record = json.loads(line)
                    if not isinstance(record, dict):
                        return {"valid": False, "records_checked": checked, "failed_sequence": expected_sequence, "chain_head": previous}
                    chain_hash = record.pop("chain_hash", None)
                    if not isinstance(chain_hash, str):
                        return {"valid": False, "records_checked": checked, "failed_sequence": expected_sequence, "chain_head": previous}
                    if record.get("previous_hash") != previous or record.get("sequence") != expected_sequence:
                        return {"valid": False, "records_checked": checked, "failed_sequence": expected_sequence, "chain_head": previous}
                    if record.get("digest_algorithm") == "sha256-concatenated-v1":
                        tender_id = record.get("tender_id")
                        vendor_id = record.get("vendor_id")
                        audit_result_json = record.get("audit_result_json")
                        if not all(isinstance(value, str) and value for value in (tender_id, vendor_id, audit_result_json)):
                            return {"valid": False, "records_checked": checked, "failed_sequence": expected_sequence, "chain_head": previous}
                        expected_hash = compute_audit_digest(previous, tender_id, vendor_id, audit_result_json).digest
                    else:
                        # Read legacy records created before the explicit digest formula was added.
                        expected_hash = sha256_json(record)
                    if expected_hash != chain_hash:
                        return {"valid": False, "records_checked": checked, "failed_sequence": expected_sequence, "chain_head": previous}
                    previous = chain_hash
                    checked += 1
        except (OSError, UnicodeDecodeError, ValueError, TypeError):
            return {"valid": False, "records_checked": checked, "failed_sequence": checked + 1, "chain_head": previous}
        return {"valid": True, "records_checked": checked, "chain_head": previous}

    def _last_hash_and_sequence(self) -> tuple[str, int]:
        if not self.path.is_file():
            return GENESIS_HASH, 0
        last: dict[str, Any] | None = None
        try:
            with self.path.open("r", encoding="utf-8") as stream:
                for line in stream:
                    if line.strip():
                        candidate = json.loads(line)
                        if not isinstance(candidate, dict) or not isinstance(candidate.get("chain_hash"), str):
                            raise ValueError("Existing audit trail record is invalid.")
                        last = candidate
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError) as exc:
            raise RuntimeError("Unable to read the comprehensive audit trail.") from exc
        if not last:
            return GENESIS_HASH, 0
        return str(last["chain_hash"]), int(last.get("sequence", 0))


@contextmanager
def exclusive_file_lock(path: Path) -> Iterator[None]:
    """Serialize writers across processes on Windows and POSIX hosts.

    Not re-entrant: a thread that already holds the lock must not take it again.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as stream:
        if os.name == "nt":
            import msvcrt
            stream.seek(0, os.SEEK_END)
            if stream.tell() == 0:
                stream.write(b"\0")
                stream.flush()
            # LK_LOCK sleeps a full second between attempts and gives up after ten.
            # Polling a non-blocking lock keeps a busy log responsive.
            deadline = time.monotonic() + _LOCK_TIMEOUT_SECONDS
            while True:
                stream.seek(0)
                try:
                    msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                    break
                except OSError:
                    if time.monotonic() >= deadline:
                        raise TimeoutError(f"Could not lock {path.name} within {_LOCK_TIMEOUT_SECONDS:.0f} s.") from None
                    time.sleep(_LOCK_POLL_SECONDS)
            try:
                yield
            finally:
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)

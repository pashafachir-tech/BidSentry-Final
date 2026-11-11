"""Append-only metadata audit log. Document text is deliberately excluded."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import threading
import uuid
from collections import deque
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

from bidsentry.core.audit_trail import HashChainedAuditTrail, ImmutableAuditDigest, exclusive_file_lock


TOMBSTONE = "tombstone"
_TAIL_WINDOW_BYTES = 64 * 1024


class AuditLog:
    """Hash-chained JSONL log.

    With ``seal_key`` every record also carries an HMAC, so someone who edits the
    file and recomputes the plain hashes is still caught unless they hold the key.
    Deleting an audit replaces its records with tombstones that keep the chain
    intact and leave a visible trace; the content itself is gone.
    """

    def __init__(self, path: Path, seal_key: bytes | None = None):
        self.path = path
        self.seal_key = seal_key
        self._lock = threading.Lock()

    @property
    def sealed(self) -> bool:
        return self.seal_key is not None

    def _mac(self, entry_hash: str) -> str:
        return hmac.new(self.seal_key or b"", entry_hash.encode("ascii"), hashlib.sha256).hexdigest()

    def _source_path(self, audit_id: str) -> Path | None:
        safe_name = "".join(c for c in str(audit_id) if c.isalnum() or c in ("-", "_"))
        return self.sources_dir / f"{safe_name}.txt" if safe_name else None

    def delete_source_text(self, audit_id: str) -> None:
        path = self._source_path(audit_id)
        if path is not None:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass

    @staticmethod
    def _tombstone(item: dict[str, Any]) -> dict[str, Any]:
        kept = ("schema_version", "created_at", "previous_hash", "hash", "mac", "audit_id")
        return {**{key: item[key] for key in kept if key in item}, "event_type": TOMBSTONE}

    @property
    def sources_dir(self) -> Path:
        return self.path.parent / "audit_sources"

    def save_source_text(self, audit_id: str, source_text: str, retention_days: int = 90) -> None:
        if not audit_id or not source_text:
            return
        target_dir = self.sources_dir
        target_dir.mkdir(parents=True, exist_ok=True)
        if retention_days > 0:
            cutoff = datetime.now(timezone.utc).timestamp() - (retention_days * 86400)
            try:
                for f in target_dir.glob("*.txt"):
                    if f.is_file() and f.stat().st_mtime < cutoff:
                        f.unlink(missing_ok=True)
            except OSError:
                pass
        safe_name = "".join(c for c in audit_id if c.isalnum() or c in ("-", "_"))
        if safe_name:
            source_file = target_dir / f"{safe_name}.txt"
            with self._lock:
                source_file.write_text(source_text, encoding="utf-8")

    def get_source_text(self, audit_id: str) -> str | None:
        if not audit_id:
            return None
        safe_name = "".join(c for c in audit_id if c.isalnum() or c in ("-", "_"))
        if not safe_name:
            return None
        source_file = self.sources_dir / f"{safe_name}.txt"
        if not source_file.is_file():
            return None
        try:
            return source_file.read_text(encoding="utf-8")
        except OSError:
            return None

    def has_source_text(self, audit_id: str) -> bool:
        if not audit_id:
            return False
        safe_name = "".join(c for c in audit_id if c.isalnum() or c in ("-", "_"))
        if not safe_name:
            return False
        source_file = self.sources_dir / f"{safe_name}.txt"
        return source_file.is_file() and source_file.stat().st_size > 0

    @contextmanager
    def _exclusive(self) -> Iterator[None]:
        """One writer at a time, across threads and across processes.

        The API server, the job worker and maintenance scripts can all open the
        same log. A thread lock alone lets two processes read the same previous
        hash and interleave their lines, which breaks the chain.
        """
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock, exclusive_file_lock(self.path.with_name(self.path.name + ".lock")):
            yield

    def _get_last_hash_locked(self) -> str:
        """Hash of the last valid record, read from the end of the file.

        Appends stay cheap as the log grows: only the tail is read, and the
        window widens when the last record is larger than it.
        """
        genesis = "0" * 64
        try:
            with self.path.open("rb") as stream:
                size = stream.seek(0, os.SEEK_END)
                window = _TAIL_WINDOW_BYTES
                while True:
                    start = max(0, size - window)
                    stream.seek(start)
                    lines = stream.read(size - start).split(b"\n")
                    if start > 0:
                        lines = lines[1:]  # the first piece may be the end of a longer record
                    for raw in reversed(lines):
                        try:
                            item = json.loads(raw.decode("utf-8")) if raw.strip() else None
                        except (ValueError, UnicodeDecodeError):
                            continue
                        if isinstance(item, dict) and "hash" in item:
                            return str(item["hash"])
                    if start == 0:
                        return genesis
                    window *= 4
        except OSError:
            return genesis

    def append(self, event: dict[str, Any]) -> dict[str, Any]:
        # Document text is deliberately excluded from audit_log.jsonl for privacy compliance
        cleaned_event = {k: v for k, v in event.items() if k not in ("source_text", "hash", "previous_hash", "mac")}
        created_at = datetime.now(timezone.utc).isoformat()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._exclusive():
            prev_hash = self._get_last_hash_locked()
            base_record = {
                "schema_version": "1.0",
                "created_at": created_at,
                "previous_hash": prev_hash,
                **cleaned_event,
            }
            canonical_payload = json.dumps(base_record, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
            entry_hash = hashlib.sha256(f"{prev_hash}|{canonical_payload}".encode("utf-8")).hexdigest()
            record = {**base_record, "hash": entry_hash}
            if self.seal_key is not None:
                record["mac"] = self._mac(entry_hash)
            line = json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n"
            with self.path.open("a", encoding="utf-8") as stream:
                stream.write(line)
            return record

    def verify_chain(self) -> tuple[bool, int, str]:
        """Verify cryptographic integrity of the SHA-256 hash chain.
        
        Returns (is_valid, record_count, status_message).
        """
        if not self.path.is_file():
            return True, 0, "No audit log file present."
        expected_prev = "0" * 64
        count = 0
        with self._exclusive():
            try:
                with self.path.open("r", encoding="utf-8") as stream:
                    for idx, line in enumerate(stream, start=1):
                        line = line.strip()
                        if not line:
                            continue
                        count += 1
                        try:
                            item = json.loads(line)
                        except json.JSONDecodeError as exc:
                            return False, count, f"Corrupted JSON on line {idx}: {exc}"
                        if "hash" not in item or "previous_hash" not in item:
                            return False, count, f"Missing hash chain fields on line {idx}"
                        if item["previous_hash"] != expected_prev:
                            return False, count, f"Broken chain on line {idx}: expected prev {expected_prev}, got {item['previous_hash']}"
                        actual_hash = item["hash"]
                        if item.get("event_type") != TOMBSTONE:
                            base = {k: v for k, v in item.items() if k not in ("hash", "mac")}
                            canonical_payload = json.dumps(base, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
                            recomputed = hashlib.sha256(f"{expected_prev}|{canonical_payload}".encode("utf-8")).hexdigest()
                            if recomputed != actual_hash:
                                return False, count, f"Tampered record on line {idx}: hash mismatch"
                        if self.seal_key is not None:
                            if not item.get("mac"):
                                return False, count, f"Unsealed record on line {idx}: no HMAC seal"
                            if not hmac.compare_digest(str(item["mac"]), self._mac(str(actual_hash))):
                                return False, count, f"Forged record on line {idx}: HMAC seal mismatch"
                        expected_prev = actual_hash
                return True, count, "Hash chain verified successfully."
            except OSError as exc:
                return False, count, f"IO error reading audit log: {exc}"

    def _iter_events(self):
        if not self.path.is_file():
            return
        try:
            with self.path.open("r", encoding="utf-8") as stream:
                for line in stream:
                    try:
                        item = json.loads(line)
                    except (json.JSONDecodeError, TypeError):
                        continue
                    if isinstance(item, dict) and item.get("schema_version") == "1.0":
                        yield item
        except OSError:
            return

    def recent(self, limit: int = 100) -> list[dict[str, Any]]:
        if limit <= 0 or not self.path.is_file():
            return []
        records: deque[dict[str, Any]] = deque(maxlen=limit)
        try:
            with self.path.open("r", encoding="utf-8") as stream:
                for line in stream:
                    try:
                        item = json.loads(line)
                    except (json.JSONDecodeError, TypeError):
                        continue
                    if isinstance(item, dict) and item.get("schema_version") == "1.0" and item.get("event_type") == "audit.completed":
                        records.append(item)
        except OSError:
            return []
        return list(reversed(records))

    def get_audit(self, audit_id: str) -> dict[str, Any] | None:
        if not self.path.is_file() or not audit_id:
            return None
        target = str(audit_id).strip()
        for event in reversed(list(self._iter_events())):
            if event.get("event_type") == "audit.completed" and str(event.get("audit_id", "")).strip() == target:
                if isinstance(event.get("evaluation"), dict):
                    return event["evaluation"]
                risk = event.get("risk") if isinstance(event.get("risk"), dict) else {}
                source_text = self.get_source_text(target) or event.get("source_text", "")
                has_source = bool(source_text) or bool(event.get("has_source_text"))
                internal = {"event_type", "previous_hash", "hash", "schema_version", "source_text"}
                record = {key: value for key, value in event.items() if key not in internal}
                record.update({
                    "review_role": event.get("review_role", "procurement"),
                    "risk_level": risk.get("level", "NOT_ASSESSABLE"),
                    "risk_label": risk.get("label"),
                    "risk": risk,
                    "summary": event.get("summary", {}),
                    "executive_summary": event.get("executive_summary", {}),
                    "findings": event.get("findings", []),
                    "proof_log": event.get("proof_log", []),
                    "proof_summary": event.get("proof_summary", {}),
                    "documents": self.documents_for(target),
                    "source_text": source_text,
                    "has_source_text": has_source,
                })
                return record
        return None

    def documents_for(self, audit_id: str) -> list[dict[str, Any]]:
        """Generated documents (filename, SHA-256, role) recorded for an audit."""
        return [
            {key: event.get(key) for key in ("created_at", "document_kind", "filename", "sha256", "role", "findings_included")}
            for event in self._iter_events()
            if event.get("event_type") == "document.generated" and event.get("audit_id") == audit_id
        ]

    def _write_atomic(self, lines: list[str]) -> None:
        content = "\n".join(lines) + ("\n" if lines else "")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.path.with_name(f"{self.path.name}.tmp.{uuid.uuid4().hex}")
        try:
            with temp_path.open("w", encoding="utf-8") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp_path, self.path)
        except Exception:
            if temp_path.is_file():
                try:
                    temp_path.unlink()
                except OSError:
                    pass
            raise

    def delete_audit(self, audit_id: str, actor_role: str | None = None) -> bool:
        """Remove an audit's content and source text; tombstones keep the chain verifiable."""
        if not self.path.is_file() or not audit_id:
            return False
        with self._exclusive():
            try:
                lines = self.path.read_text(encoding="utf-8").splitlines()
            except OSError:
                return False
            kept_lines = []
            found = False
            for line in lines:
                try:
                    item = json.loads(line)
                    if isinstance(item, dict) and item.get("audit_id") == audit_id and item.get("event_type") not in (TOMBSTONE, "audit.deleted"):
                        found = True
                        kept_lines.append(json.dumps(self._tombstone(item), ensure_ascii=False, separators=(",", ":")))
                        continue
                except (json.JSONDecodeError, TypeError):
                    pass
                kept_lines.append(line)
            if found:
                self._write_atomic(kept_lines)
        if found:
            self.delete_source_text(audit_id)
            self.append({"event_type": "audit.deleted", "audit_id": audit_id, "actor_role": actor_role})
        return found

    def purge_older_than(self, days: int) -> int:
        if days <= 0 or not self.path.is_file():
            return 0
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        with self._exclusive():
            try:
                lines = self.path.read_text(encoding="utf-8").splitlines()
            except OSError:
                return 0
            kept_lines = []
            purged = 0
            expired_audits: set[str] = set()
            for line in lines:
                try:
                    item = json.loads(line)
                    if isinstance(item, dict) and "created_at" in item and item.get("event_type") != TOMBSTONE:
                        created = datetime.fromisoformat(str(item["created_at"]))
                        if created.tzinfo is None:
                            created = created.replace(tzinfo=timezone.utc)
                        if created < cutoff:
                            purged += 1
                            if item.get("audit_id"):
                                expired_audits.add(str(item["audit_id"]))
                            if "hash" in item and "previous_hash" in item:
                                kept_lines.append(json.dumps(self._tombstone(item), ensure_ascii=False, separators=(",", ":")))
                            continue
                except Exception:
                    pass
                kept_lines.append(line)
            if purged > 0:
                self._write_atomic(kept_lines)
        for audit_id in expired_audits:
            self.delete_source_text(audit_id)
        return purged

    def finding_exists(self, audit_id: str, finding_id: str) -> bool:
        return any(
            event.get("event_type") == "audit.completed"
            and event.get("audit_id") == audit_id
            and isinstance(event.get("findings"), list)
            and any(isinstance(item, dict) and item.get("id") == finding_id for item in event["findings"])
            for event in self._iter_events()
        )

    def feedback_snapshot(self, audit_id: str = "") -> dict[str, Any]:
        eligible: set[tuple[str, str]] = set()
        latest: dict[tuple[str, str], dict[str, Any]] = {}
        for event in self._iter_events():
            event_type = event.get("event_type")
            current_id = str(event.get("audit_id", ""))
            if event_type == "audit.completed" and current_id:
                findings = event.get("findings") if isinstance(event.get("findings"), list) else []
                eligible.update(
                    (current_id, str(finding["id"]))
                    for finding in findings
                    if isinstance(finding, dict) and finding.get("id")
                )
            elif event_type == "finding.reviewed" and current_id and event.get("finding_id"):
                if event.get("outcome") not in {"SUPPORTED", "NEEDS_MORE_INFO", "NOT_SUPPORTED"}:
                    continue
                latest[(current_id, str(event["finding_id"]))] = {
                    "outcome": event.get("outcome"),
                    "recorded_at": event.get("created_at", ""),
                }

        valid_latest = {key: value for key, value in latest.items() if key in eligible}
        counts = {outcome: 0 for outcome in ("SUPPORTED", "NEEDS_MORE_INFO", "NOT_SUPPORTED")}
        for value in valid_latest.values():
            if value.get("outcome") in counts:
                counts[value["outcome"]] += 1

        audit_outcomes = {
            finding_id: value
            for (item_id, finding_id), value in valid_latest.items()
            if audit_id and item_id == audit_id
        }
        total = len(eligible)
        reviewed = len(valid_latest)
        return {
            "audit_id": audit_id or None,
            "outcomes": audit_outcomes,
            "pilot": {
                "audits_with_findings": len({item_id for item_id, _ in eligible}),
                "eligible_findings": total,
                "reviewed_findings": reviewed,
                "coverage_percent": round(reviewed * 100 / total) if total else None,
                "outcome_counts": counts,
            },
            "note": "Catatan reviewer yang dimasukkan pengguna; bukan akurasi, adjudikasi independen, atau metrik dampak.",
        }


__all__ = ["AuditLog", "HashChainedAuditTrail", "ImmutableAuditDigest", "TOMBSTONE"]

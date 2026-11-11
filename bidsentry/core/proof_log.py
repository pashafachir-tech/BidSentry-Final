"""Per-audit proof ledger: extraction -> AI call -> Python calculation -> decision -> document.

The ledger is the evidence a reviewer (or a jury) can inspect to see that the
language model only extracted quotes, that Python did the arithmetic, and which
rule produced the final risk tier. It never stores raw document text: inputs
are recorded as numbers, short verbatim quotes, hashes and counts.
"""

from __future__ import annotations

import hashlib
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterator

from bidsentry.schemas.findings import ProofKind, ProofStep

MAX_QUOTE_CHARS = 300


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def short_quote(text: str | None) -> str | None:
    if not text:
        return None
    flat = " ".join(str(text).split())
    return flat if len(flat) <= MAX_QUOTE_CHARS else flat[: MAX_QUOTE_CHARS - 1] + "…"


class ProofLog:
    """Append-only, in-memory ledger serialised into the audit result."""

    def __init__(self) -> None:
        self._steps: list[ProofStep] = []

    def record(
        self,
        kind: ProofKind,
        title: str,
        *,
        actor: str,
        inputs: dict[str, Any] | None = None,
        outputs: dict[str, Any] | None = None,
        formula: str | None = None,
        note: str | None = None,
        status: str = "ok",
        duration_ms: float | None = None,
    ) -> str:
        sequence = len(self._steps) + 1
        step_id = f"S{sequence:02d}"
        self._steps.append(ProofStep(
            step_id=step_id,
            sequence=sequence,
            kind=kind,
            title=title,
            actor=actor,
            status=status,  # type: ignore[arg-type]
            duration_ms=round(duration_ms, 3) if duration_ms is not None else None,
            inputs=inputs or {},
            outputs=outputs or {},
            formula=formula,
            note=note,
            recorded_at=datetime.now(timezone.utc).isoformat(),
        ))
        return step_id

    @contextmanager
    def timed(self) -> Iterator[dict[str, float]]:
        """Measure a block; the caller reads ``box['ms']`` after the block."""
        box: dict[str, float] = {}
        started = time.perf_counter()
        try:
            yield box
        finally:
            box["ms"] = (time.perf_counter() - started) * 1000

    def calculation(self, title: str, *, rule: str, formula: str, inputs: dict[str, Any], outputs: dict[str, Any], actor: str = "python:evaluation_engine") -> str:
        return self.record("calculation", title, actor=actor, inputs={"rule": rule, **inputs}, outputs=outputs, formula=formula)

    def to_list(self) -> list[dict[str, Any]]:
        return [step.model_dump(mode="json") for step in self._steps]

    def summary(self) -> dict[str, Any]:
        kinds: dict[str, int] = {}
        for step in self._steps:
            kinds[step.kind] = kinds.get(step.kind, 0) + 1
        ai_calls = [step for step in self._steps if step.kind == "ai_call"]
        return {
            "steps": len(self._steps),
            "by_kind": kinds,
            "ai_calls": len([step for step in ai_calls if step.status == "ok"]),
            "ai_providers": sorted({str(step.outputs.get("provider")) for step in ai_calls if step.outputs.get("provider")}),
            "python_calculations": kinds.get("calculation", 0),
        }


__all__ = ["ProofLog", "sha256_text", "short_quote"]

"""Thin service boundary between the audit controller and the evaluation engine."""

from __future__ import annotations

from typing import Any

from bidsentry.evaluators.engine import EvaluationEngine, EvaluationRequest


class AuditService:
    def __init__(self, engine: EvaluationEngine | None = None):
        self.engine = engine or EvaluationEngine()

    def audit(self, request: EvaluationRequest | dict[str, Any]) -> dict[str, Any]:
        model = request if isinstance(request, EvaluationRequest) else EvaluationRequest.model_validate(request)
        return self.engine.evaluate(model)


__all__ = ["AuditService"]

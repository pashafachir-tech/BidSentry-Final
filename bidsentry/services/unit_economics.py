"""Per-audit unit economics computed from real telemetry plus explicit assumptions.

Nothing here is a marketing constant. Inference cost uses the token counts the
provider reported for this audit; when no AI call was made, tokens are
*estimated* from the characters that would be sent (≈ 4 characters per token)
and the result is labelled as an estimate. Prices, the exchange rate, manual
review hours and the hourly labour cost are assumptions the user can see and
change in the UI; every response echoes the assumptions it used.
"""

from __future__ import annotations

import math
from typing import Any

from bidsentry.config import AI_CONTEXT_MAX_CHARS, Settings

CHARS_PER_TOKEN = 4.0
PROMPT_OVERHEAD_TOKENS = 1_200      # instructions + schema in the extraction prompt
OUTPUT_TOKENS_ESTIMATE = 600        # typical structured extraction response


def _positive(value: Any, default: float, *, maximum: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(number) or number < 0:
        return default
    return min(number, maximum)


def compute(audit: dict[str, Any], settings: Settings, *, manual_hours: Any = None, hourly_cost_idr: Any = None, packages_per_year: Any = None) -> dict[str, Any]:
    assumptions = {
        "price_usd_per_1m_input_tokens": settings.ai_price_usd_per_1m_input_tokens,
        "price_usd_per_1m_output_tokens": settings.ai_price_usd_per_1m_output_tokens,
        "usd_idr_rate": settings.usd_idr_rate,
        "manual_review_hours_per_package": _positive(manual_hours, settings.manual_review_hours_per_package, maximum=200),
        "manual_hourly_cost_idr": _positive(hourly_cost_idr, settings.manual_hourly_cost_idr, maximum=10_000_000),
        "packages_per_year": int(_positive(packages_per_year, 1_000, maximum=1_000_000)),
        "price_source": settings.ai_price_source,
    }

    calls = [step for step in audit.get("proof_log", []) if step.get("kind") == "ai_call" and step.get("status") == "ok"]
    input_tokens = sum(int(step.get("outputs", {}).get("input_tokens") or 0) for step in calls)
    output_tokens = sum(int(step.get("outputs", {}).get("output_tokens") or 0) for step in calls)
    if calls and (input_tokens or output_tokens):
        token_basis = "measured"
    else:
        characters = sum(int(value.get("characters", 0)) for step in audit.get("proof_log", []) if step.get("kind") == "input" for value in step.get("inputs", {}).values() if isinstance(value, dict))
        input_tokens = int(min(characters, AI_CONTEXT_MAX_CHARS) / CHARS_PER_TOKEN) + PROMPT_OVERHEAD_TOKENS
        output_tokens = OUTPUT_TOKENS_ESTIMATE
        token_basis = "estimated_from_document_length"

    usd = input_tokens / 1e6 * assumptions["price_usd_per_1m_input_tokens"] + output_tokens / 1e6 * assumptions["price_usd_per_1m_output_tokens"]
    inference_idr = usd * assumptions["usd_idr_rate"]

    # Fresh results carry performance.engine_duration_ms; audits read back from the log store it top-level.
    engine_ms = float((audit.get("performance") or {}).get("engine_duration_ms") or audit.get("engine_duration_ms") or 0)
    ai_ms = sum(float(step.get("duration_ms") or 0) for step in calls)
    # The engine duration is measured around the whole audit, AI call included; adding
    # the call again would count it twice. ``ai_ms`` only covers logs without an engine figure.
    machine_seconds = max(engine_ms, ai_ms) / 1000
    manual_cost = assumptions["manual_review_hours_per_package"] * assumptions["manual_hourly_cost_idr"]
    yearly = assumptions["packages_per_year"]
    return {
        "audit_id": audit.get("audit_id"),
        "tokens": {"input": input_tokens, "output": output_tokens, "basis": token_basis, "ai_calls": len(calls)},
        "inference_cost_idr": round(inference_idr, 2),
        "inference_cost_usd": round(usd, 6),
        "machine_seconds": round(machine_seconds, 6),
        "manual_review_cost_idr": round(manual_cost),
        "manual_review_seconds": round(assumptions["manual_review_hours_per_package"] * 3600),
        "time_reduction_factor": round(assumptions["manual_review_hours_per_package"] * 3600 / machine_seconds) if machine_seconds > 0 else None,
        "annual": {
            "packages": yearly,
            "inference_cost_idr": round(inference_idr * yearly),
            "manual_review_cost_idr": round(manual_cost * yearly),
            "manual_hours": round(assumptions["manual_review_hours_per_package"] * yearly),
        },
        "assumptions": assumptions,
        "caveat": (
            "Biaya inferensi dihitung dari token " + ("terukur pada audit ini" if token_basis == "measured" else "yang diestimasi dari panjang dokumen (AI tidak dipanggil)")
            + ". Harga, kurs, jam kerja manual, dan tarif per jam adalah asumsi yang dapat diubah; jam kerja manual belum divalidasi pilot. "
            "Mesin tidak menggantikan waktu verifikasi manusia atas setiap temuan."
        ),
    }


__all__ = ["compute"]

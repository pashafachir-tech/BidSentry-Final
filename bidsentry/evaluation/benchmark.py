"""Unified, honest benchmark over every labelled fixture set in ``data/``.

Design choices (so the numbers can be defended in Q&A):

* **Unit of evaluation** – a *red flag*: a finding with status GAP or EXPIRING.
  REVIEW ("bukti belum lengkap") is reported separately as an evidence request,
  not counted as a positive prediction.
* **Matching** – by canonical rule *family* from the rule catalog, so a correct
  detection is not scored as a miss because a label used an older ID
  (``FIN-HPS-OVER-PAGU`` vs ``FIN-OVER-BUDGET``). Strict raw-ID metrics are
  reported alongside so the effect of the mapping is visible.
* **Aggregation** – micro-averaged (pooled TP/FP/FN) with Wilson 95% intervals;
  with n this small the interval matters more than the point estimate.
* **Provenance** – every suite declares whether it was used while writing the
  rules. Only data never used for tuning can support an accuracy claim, and
  this repository currently has none that is both independent and real-world.
"""

from __future__ import annotations

import json
import math
import statistics
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

from bidsentry.config import Settings
from bidsentry.evaluators.engine import EvaluationEngine, EvaluationRequest
from bidsentry.evaluators.rule_catalog import family_of

ROOT = Path(__file__).resolve().parents[2]
FLAG_STATUSES = {"GAP", "EXPIRING"}


@dataclass(frozen=True)
class Suite:
    key: str
    title: str
    path: str
    provenance: str
    independent: bool
    real_world: bool
    mode: str = "flags"  # "flags" = red-flag detection, "recognition" = requirement recognition


SUITES: tuple[Suite, ...] = (
    Suite("dev_regression", "Development regression (24 dokumen)", "data/benchmark",
          "In-sample: dokumen ini dipakai saat menyusun dan menyetel aturan regex.", False, False),
    Suite("traps_v2", "Traps v2 (10 dokumen jebakan)", "data/test_traps_v2",
          "Disusun tim setelah perbaikan bug false positive; dipakai sebagai regression guard.", False, False),
    Suite("blind_v1", "Blind v1 (10 dokumen)", "data/test_blind",
          "Disusun tim (scripts/generate_blind_set.py). Setelah putaran pertama engine dikalibrasi pada set ini (lihat docs/BENCHMARK_RESULTS.md), jadi tidak lagi independen.", False, False),
    Suite("narrative_budget", "Narasi anggaran (5 dokumen)", "data/test_narrative_budget",
          "Disusun tim untuk menguji angka pagu/BoQ dalam prosa bebas. Miss budget_03 dilihat lalu diperbaiki secara umum (normalizer Rupiah + batas kata kunci), jadi set ini juga in-sample.", False, False),
    Suite("sample_fixtures", "Fixture sintetis (2 paket)", "data/sample_tenders",
          "Fixture regresi sintetis untuk SBU kedaluwarsa dan jaminan penawaran.", False, False),
    Suite("public_lpse", "Halaman LPSE publik (1 dokumen nyata)", "data/public_lpse",
          "Satu halaman pengumuman LPSE nyata, dianotasi satu orang. Mengukur pengenalan syarat, bukan deteksi pelanggaran.", True, True, "recognition"),
)


# Disagreements between a label and the configured rule that we refuse to "fix" by
# bending the engine toward the label; they are surfaced in the report instead.
LABEL_NOTES: dict[str, str] = {
    "budget_03_prose_hps_over_pagu": (
        "Dokumen menulis 'pemasukan penawaran 6 hari kerja'. Aturan memakai ambang 7 hari kerja "
        "(config/rules.yaml), sehingga engine menandai PROC-TIMELINE, sedangkan label tidak. Dihitung sebagai FP "
        "sampai ahli pengadaan memutuskan ambang yang benar untuk metode pemilihan paket ini."
    ),
    "budget_02_prose_within_budget": (
        "Verdict BELUM CUKUP BUKTI karena NPWP/NIB diminta tetapi bukti penyedia tidak dilampirkan; label mengharapkan GO."
    ),
}


@dataclass
class Case:
    case_id: str
    request: dict[str, Any]
    expected: dict[str, str]           # raw label id -> expected status
    forbidden: list[str] = field(default_factory=list)
    expected_verdict: str | None = None
    is_trap: bool = False


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _request_fields(raw: dict[str, Any]) -> dict[str, Any]:
    allowed = set(EvaluationRequest.model_fields)
    return {key: value for key, value in raw.items() if key in allowed}


def _forbidden_ids(raw: Any) -> list[str]:
    output = []
    for item in raw or []:
        output.append(item.get("id") if isinstance(item, dict) else str(item))
    return [item for item in output if item]


def load_cases(suite: Suite) -> Iterator[Case]:
    base = ROOT / suite.path
    if suite.key == "dev_regression":
        for label_path in sorted(base.glob("*.labels.json")):
            label = _load_json(label_path)
            request = _request_fields(label.get("input", {}))
            expected = {item["id"]: item.get("status", "GAP") for item in label.get("expected_findings", [])}
            yield Case(label.get("id", label_path.stem), request, expected, _forbidden_ids(label.get("forbidden_findings")), label.get("expected_verdict"), bool(label.get("is_trap")))
    elif suite.key == "sample_fixtures":
        for truth_path in sorted(base.glob("fixture_*/ground_truth.json")):
            truth = _load_json(truth_path)
            folder = truth_path.parent
            request = {
                "package_name": truth["fixture_id"], "contract_value_idr": 1_000_000_000,
                "dok_pemilihan": (folder / "dok_pemilihan.txt").read_text(encoding="utf-8"),
                "pustaka": (folder / "bukti_penyedia.txt").read_text(encoding="utf-8"),
                "bid_deadline": truth.get("bid_deadline"),
            }
            yield Case(truth["fixture_id"], request, {item: "GAP" for item in truth.get("expected_issue_ids", [])})
    elif suite.key == "public_lpse":
        for truth_path in sorted(base.glob("*/ground_truth.json")):
            truth = _load_json(truth_path)
            request = {"package_name": truth["fixture_id"], "dok_pemilihan": (truth_path.parent / "procurement_requirements.txt").read_text(encoding="utf-8")}
            yield Case(truth["fixture_id"], request, {item: "RECOGNIZED" for item in truth.get("expected_check_ids", [])})
    else:
        for path in sorted(base.glob("*.json")):
            data = _load_json(path)
            expected = data.get("expected_findings", {})
            if isinstance(expected, list):
                expected = {item["id"]: item.get("status", "GAP") for item in expected}
            yield Case(data.get("id", path.stem), _request_fields(data.get("request", {})), dict(expected), _forbidden_ids(data.get("forbidden_findings")), data.get("expected_verdict"), bool(data.get("is_trap")))


def wilson_interval(successes: int, total: int, z: float = 1.96) -> tuple[float, float] | None:
    if total <= 0:
        return None
    p = successes / total
    denominator = 1 + z * z / total
    centre = (p + z * z / (2 * total)) / denominator
    margin = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denominator
    return round(max(0.0, centre - margin), 4), round(min(1.0, centre + margin), 4)


def _prf(tp: int, fp: int, fn: int) -> dict[str, Any]:
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
    f1 = 2 * precision * recall / (precision + recall) if precision and recall else (0.0 if precision is not None and recall is not None else None)
    return {
        "tp": tp, "fp": fp, "fn": fn,
        "precision": round(precision, 4) if precision is not None else None,
        "recall": round(recall, 4) if recall is not None else None,
        "f1": round(f1, 4) if f1 is not None else None,
        "precision_ci95": wilson_interval(tp, tp + fp),
        "recall_ci95": wilson_interval(tp, tp + fn),
    }


def evaluate_case(engine: EvaluationEngine, case: Case, mode: str) -> dict[str, Any]:
    started = time.perf_counter()
    result = engine.evaluate(EvaluationRequest(**case.request))
    latency_ms = (time.perf_counter() - started) * 1000
    findings = result["findings"]
    if mode == "recognition":
        predicted_raw = {item["id"] for item in findings}
        expected_raw = set(case.expected)
    else:
        # A flag held at REVIEW only because its numeric threshold is unverified is still a detection.
        predicted_raw = {item["id"] for item in findings if item["status"] in FLAG_STATUSES or item.get("threshold_unverified")}
        expected_raw = {code for code, status in case.expected.items() if str(status).upper() in FLAG_STATUSES}
    predicted_family = {family_of(code) for code in predicted_raw}
    expected_family = {family_of(code) for code in expected_raw}
    forbidden_family = {family_of(code) for code in case.forbidden}
    review_prompts = sorted(item["id"] for item in findings if item["status"] == "REVIEW" and family_of(item["id"]) not in expected_family)
    return {
        "case_id": case.case_id,
        "is_trap": case.is_trap,
        "expected_verdict": case.expected_verdict,
        "actual_verdict": result["verdict"],
        "verdict_match": case.expected_verdict is None or result["verdict"] == case.expected_verdict,
        "risk_level": result["risk_level"],
        "expected": sorted(expected_family),
        "predicted": sorted(predicted_family),
        "true_positive": sorted(predicted_family & expected_family),
        "false_positive": sorted(predicted_family - expected_family),
        "false_negative": sorted(expected_family - predicted_family),
        "forbidden_hit": sorted(predicted_family & forbidden_family),
        "strict": {"tp": len(predicted_raw & expected_raw), "fp": len(predicted_raw - expected_raw), "fn": len(expected_raw - predicted_raw)},
        "evidence_requests": review_prompts,
        "latency_ms": round(latency_ms, 3),
    }


def run_suite(engine: EvaluationEngine, suite: Suite) -> dict[str, Any]:
    loaded = list(load_cases(suite))
    cases = [evaluate_case(engine, case, suite.mode) for case in loaded]
    tp = sum(len(case["true_positive"]) for case in cases)
    fp = sum(len(case["false_positive"]) for case in cases)
    fn = sum(len(case["false_negative"]) for case in cases)
    strict = [case["strict"] for case in cases]
    with_verdict = [case for case in cases if case["expected_verdict"] is not None]
    traps = [case for case in cases if case["is_trap"]]
    return {
        "suite": suite.key,
        "title": suite.title,
        "path": suite.path,
        "provenance": suite.provenance,
        "independent_of_rule_tuning": suite.independent,
        "real_world_documents": suite.real_world,
        "mode": suite.mode,
        "documents": len(cases),
        "document_characters": [sum(len(str(value)) for key, value in case.request.items() if key in {"dok_pemilihan", "adendum", "pustaka", "contract_draft"} and value) for case in loaded],
        "family": _prf(tp, fp, fn),
        "strict_id": _prf(sum(s["tp"] for s in strict), sum(s["fp"] for s in strict), sum(s["fn"] for s in strict)),
        "verdict_accuracy": round(sum(case["verdict_match"] for case in with_verdict) / len(with_verdict), 4) if with_verdict else None,
        "verdict_correct": sum(case["verdict_match"] for case in with_verdict),
        "verdict_total": len(with_verdict),
        "traps_without_false_positive": sum(1 for case in traps if not case["false_positive"]),
        "trap_documents": len(traps),
        "documents_with_false_positive": sum(1 for case in cases if case["false_positive"]),
        "evidence_requests": sum(len(case["evidence_requests"]) for case in cases),
        "median_latency_ms": sorted(case["latency_ms"] for case in cases)[len(cases) // 2] if cases else None,
        "cases": cases,
    }


def run_all(settings: Settings | None = None) -> dict[str, Any]:
    engine = EvaluationEngine(settings or Settings.from_environment())
    suites = [run_suite(engine, suite) for suite in SUITES]
    flag_suites = [suite for suite in suites if suite["mode"] == "flags"]
    pooled = _prf(
        sum(suite["family"]["tp"] for suite in flag_suites),
        sum(suite["family"]["fp"] for suite in flag_suites),
        sum(suite["family"]["fn"] for suite in flag_suites),
    )
    held_out = [suite for suite in flag_suites if suite["suite"] != "dev_regression"]
    pooled_non_dev = _prf(
        sum(suite["family"]["tp"] for suite in held_out),
        sum(suite["family"]["fp"] for suite in held_out),
        sum(suite["family"]["fn"] for suite in held_out),
    )
    return {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "engine": "deterministic rules only (AI extraction disabled)",
        "unit": "red flag = finding with status GAP or EXPIRING, or REVIEW held only because its numeric threshold is unverified; matched by rule family",
        "suites": suites,
        "pooled_all_synthetic": {**pooled, "documents": sum(suite["documents"] for suite in flag_suites)},
        "pooled_excluding_dev_regression": {**pooled_non_dev, "documents": sum(suite["documents"] for suite in held_out)},
        "independent_real_world_documents": sum(suite["documents"] for suite in suites if suite["independent_of_rule_tuning"] and suite["real_world_documents"]),
        "claim_guidance": (
            "Semua set deteksi red flag disusun tim dan pernah dipakai saat pengembangan. Angka ini adalah uji regresi, "
            "bukan estimasi akurasi lapangan. Klaim akurasi memerlukan dokumen tender nyata berlabel independen (rencana pilot 5 rekanan)."
        ),
    }


def _pct(value: float | None) -> str:
    return "—" if value is None else f"{value * 100:.1f}%"


def _ci(value: tuple[float, float] | None) -> str:
    return "—" if not value else f"{value[0] * 100:.0f}–{value[1] * 100:.0f}%"


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Laporan Benchmark BidSentry",
        "",
        f"_Dihasilkan otomatis oleh `scripts/run_benchmarks.py` pada {report['generated_at']}. Jangan edit manual._",
        "",
        f"**Mesin:** {report['engine']}. **Unit:** {report['unit']}.",
        "",
        f"> {report['claim_guidance']}",
        "",
        "## Ringkasan untuk slide",
        "",
        "| Set | Dokumen | Precision (95% CI) | Recall (95% CI) | F1 | False positive | Verdict benar | Independen dari pengembangan? |",
        "| --- | ---: | --- | --- | ---: | ---: | --- | --- |",
    ]
    for suite in report["suites"]:
        family = suite["family"]
        verdict = f"{suite['verdict_correct']}/{suite['verdict_total']}" if suite["verdict_total"] else "—"
        lines.append(
            f"| {suite['title']} | {suite['documents']} | {_pct(family['precision'])} ({_ci(family['precision_ci95'])}) | "
            f"{_pct(family['recall'])} ({_ci(family['recall_ci95'])}) | {_pct(family['f1'])} | {family['fp']} | {verdict} | "
            f"{'Ya' if suite['independent_of_rule_tuning'] else 'Tidak'} |"
        )
    pooled, non_dev = report["pooled_all_synthetic"], report["pooled_excluding_dev_regression"]
    lines += [
        "",
        f"- **Gabungan semua set sintetis** ({pooled['documents']} dokumen): precision {_pct(pooled['precision'])} ({_ci(pooled['precision_ci95'])}), "
        f"recall {_pct(pooled['recall'])} ({_ci(pooled['recall_ci95'])}), **{pooled['fp']} false positive**, {pooled['fn']} false negative.",
        f"- **Tanpa set development** ({non_dev['documents']} dokumen): precision {_pct(non_dev['precision'])} ({_ci(non_dev['precision_ci95'])}), "
        f"recall {_pct(non_dev['recall'])} ({_ci(non_dev['recall_ci95'])}), {non_dev['fp']} false positive, {non_dev['fn']} false negative.",
        f"- **Dokumen nyata yang independen dari tuning:** {report['independent_real_world_documents']} (halaman LPSE publik; mengukur pengenalan syarat, bukan deteksi pelanggaran).",
        f"- **Panjang dokumen uji:** median {int(statistics.median([chars for suite in report['suites'] for chars in suite['document_characters']]))} karakter. Dokumen tender nyata umumnya puluhan hingga ratusan halaman, sehingga set ini menguji pola klausul, bukan dokumen utuh.",
        f"- **Permintaan bukti tambahan** (status REVIEW di luar label, tidak dihitung sebagai positif): {sum(suite['evidence_requests'] for suite in report['suites'])}.",
        "",
        "## Pengaruh pemetaan ID (strict vs family)",
        "",
        "| Set | Precision strict-ID | Recall strict-ID | Precision family | Recall family |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for suite in report["suites"]:
        lines.append(f"| {suite['title']} | {_pct(suite['strict_id']['precision'])} | {_pct(suite['strict_id']['recall'])} | {_pct(suite['family']['precision'])} | {_pct(suite['family']['recall'])} |")
    lines += ["", "Strict-ID menghitung label lama (mis. `FIN-HPS-OVER-PAGU`) sebagai miss walau engine mendeteksi konsep yang sama (`FIN-OVER-BUDGET`).", ""]
    lines += ["## Kesalahan yang tersisa (apa adanya)", ""]
    any_error = False
    for suite in report["suites"]:
        for case in suite["cases"]:
            if case["false_positive"] or case["false_negative"] or not case["verdict_match"]:
                any_error = True
                parts = []
                if case["false_positive"]:
                    parts.append("FP: " + ", ".join(f"`{item}`" for item in case["false_positive"]))
                if case["false_negative"]:
                    parts.append("FN: " + ", ".join(f"`{item}`" for item in case["false_negative"]))
                if not case["verdict_match"]:
                    parts.append(f"verdict {case['actual_verdict']} (label {case['expected_verdict']})")
                lines.append(f"- **{suite['title']} / {case['case_id']}** — " + "; ".join(parts))
    if not any_error:
        lines.append("- Tidak ada kesalahan pada set yang tersedia (ingat: semua set pernah dilihat saat pengembangan).")
    lines += ["", "## Label yang perlu ditinjau ahli", ""]
    lines += [f"- **{case_id}** — {note}" for case_id, note in LABEL_NOTES.items()]
    lines += ["", "## Asal-usul tiap set", ""]
    for suite in report["suites"]:
        lines.append(f"- **{suite['title']}** (`{suite['path']}`): {suite['provenance']}")
    lines += [
        "",
        "## Cara menjalankan ulang",
        "",
        "```bash",
        "python scripts/run_benchmarks.py",
        "```",
        "",
    ]
    return "\n".join(lines)


__all__ = ["SUITES", "render_markdown", "run_all", "run_suite", "wilson_interval"]

#!/usr/bin/env python3
"""Run every labelled benchmark suite and write the report used for the final slide.

Outputs:
    docs/BENCHMARK_REPORT.md        human-readable report (slide table + errors)
    docs/benchmark_results.json     full machine-readable results

Exit code is non-zero when ``--min-pooled-f1`` is given and not met (CI guard).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bidsentry.evaluation.benchmark import render_markdown, run_all  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--min-pooled-f1", type=float, default=None, help="Fail when pooled family F1 falls below this value.")
    parser.add_argument("--no-write", action="store_true", help="Print the summary without writing report files.")
    args = parser.parse_args()

    report = run_all()
    if not args.no_write:
        (ROOT / "docs" / "BENCHMARK_REPORT.md").write_text(render_markdown(report), encoding="utf-8")
        (ROOT / "docs" / "benchmark_results.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    print(f"{'Set':<40} {'Dok':>4} {'P':>7} {'R':>7} {'F1':>7} {'FP':>4} {'FN':>4} {'Verdict':>8}")
    for suite in report["suites"]:
        family = suite["family"]
        fmt = lambda value: "  —  " if value is None else f"{value * 100:5.1f}%"  # noqa: E731
        verdict = f"{suite['verdict_correct']}/{suite['verdict_total']}" if suite["verdict_total"] else "—"
        print(f"{suite['title']:<40} {suite['documents']:>4} {fmt(family['precision']):>7} {fmt(family['recall']):>7} {fmt(family['f1']):>7} {family['fp']:>4} {family['fn']:>4} {verdict:>8}")
    pooled = report["pooled_all_synthetic"]
    print(f"\nPooled (all synthetic): P={pooled['precision']} R={pooled['recall']} F1={pooled['f1']} FP={pooled['fp']} FN={pooled['fn']}")
    print(report["claim_guidance"])
    if args.min_pooled_f1 is not None and (pooled["f1"] or 0) < args.min_pooled_f1:
        print(f"FAIL: pooled F1 {pooled['f1']} < {args.min_pooled_f1}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

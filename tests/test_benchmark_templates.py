"""Benchmark integrity: dynamic report numbers, honest provenance, regression guard."""

from __future__ import annotations

import inspect
import re

from bidsentry.evaluation import benchmark
from bidsentry.evaluation.benchmark import SUITES, render_markdown, run_all, wilson_interval


def test_report_template_has_no_hardcoded_percentages() -> None:
    source = inspect.getsource(render_markdown)
    for line in source.splitlines():
        stripped = line.strip()
        if stripped.startswith(('"|', "'|", 'f"|', "f'|")):
            assert not re.findall(r"\b\d+\.\d+%", stripped), f"Hard-coded percentage in template row: {stripped}"
            assert not re.findall(r"\(\d+/\d+\)", stripped), f"Hard-coded ratio in template row: {stripped}"


def test_every_suite_declares_provenance_and_only_real_independent_data_is_marked_so() -> None:
    for suite in SUITES:
        assert suite.provenance
        if suite.independent:
            assert suite.real_world, "Only real, untuned documents may be marked independent"


def test_wilson_interval_is_bounded() -> None:
    low, high = wilson_interval(9, 10)
    assert 0.0 <= low < 0.9 < high <= 1.0
    assert wilson_interval(0, 0) is None


def test_benchmark_regression_guard() -> None:
    report = run_all()
    by_key = {suite["suite"]: suite for suite in report["suites"]}
    # Development and trap suites must stay clean; they are regression guards, not accuracy claims.
    assert by_key["dev_regression"]["family"]["fp"] == 0
    assert by_key["traps_v2"]["family"]["fp"] == 0
    assert by_key["traps_v2"]["traps_without_false_positive"] == by_key["traps_v2"]["trap_documents"]
    pooled = report["pooled_all_synthetic"]
    assert pooled["f1"] is not None and pooled["f1"] >= 0.9
    assert "bukan estimasi akurasi lapangan" in report["claim_guidance"]
    assert benchmark.FLAG_STATUSES == {"GAP", "EXPIRING"}

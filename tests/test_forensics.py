"""Tests for deterministic contract difference forensics and baseline_contract integration."""

from __future__ import annotations

import unittest

from bidsentry.evaluators.engine import EvaluationEngine, EvaluationRequest
from bidsentry.forensics.contract_diff import diff_contracts


class ForensicsBaselineDiffTests(unittest.TestCase):
    def test_diff_contracts_detects_omitted_clause_and_modifications(self) -> None:
        baseline = (
            "Pasal 1: Lingkup Pekerjaan\n"
            "Pasal 2: Ketentuan Denda Keterlambatan adalah 1/1000 per hari dengan batas maksimal 5%.\n"
            "Pasal 3: Garansi diberikan selama 12 bulan sejak serah terima.\n"
        )
        submitted = (
            "Pasal 1: Lingkup Pekerjaan\n"
            "Pasal 2: Ketentuan Denda Keterlambatan adalah 1/1000 per hari tanpa batas maksimal.\n"
        )
        result = diff_contracts(baseline, submitted)
        self.assertEqual(result["status"], "compared")
        self.assertGreater(result["change_count"], 0)

        # Warranty topic was in baseline but omitted in submitted
        topic_signals = {item["topic"]: item["signal"] for item in result.get("findings", [])}
        self.assertIn("WARRANTY", topic_signals)
        self.assertEqual(topic_signals["WARRANTY"], "BASELINE_TOPIC_NOT_LOCATED")
        self.assertIn("LIQUIDATED_DAMAGES", topic_signals)
        self.assertEqual(topic_signals["LIQUIDATED_DAMAGES"], "TOPIC_TEXT_DIFFERS")

    def test_engine_integrates_baseline_contract_diff_when_provided(self) -> None:
        engine = EvaluationEngine()
        baseline = "Pasal 10: Garansi pemeliharaan berlaku selama 365 hari kalender."
        draft = "Pasal 10: Garansi pemeliharaan berlaku selama 180 hari kalender."

        req = EvaluationRequest(
            package_name="Uji Forensik Baseline",
            dok_pemilihan="Syarat Umum",
            contract_draft=draft,
            baseline_contract=baseline,
        )
        result = engine.evaluate(req)

        self.assertIn("contract_baseline_diff", result)
        diff_res = result["contract_baseline_diff"]
        self.assertEqual(diff_res["status"], "compared")
        self.assertEqual(diff_res["baseline_line_count"], 1)
        self.assertEqual(diff_res["submitted_line_count"], 1)

    def test_engine_omits_baseline_contract_diff_when_not_provided(self) -> None:
        engine = EvaluationEngine()
        req = EvaluationRequest(
            package_name="Tanpa Baseline",
            dok_pemilihan="Syarat Umum",
        )
        result = engine.evaluate(req)
        self.assertNotIn("contract_baseline_diff", result)

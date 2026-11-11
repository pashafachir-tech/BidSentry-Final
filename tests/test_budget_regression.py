"""Regression tests for budget parsing, NameError fixes, and API error envelopes."""

from __future__ import annotations

import unittest
from unittest.mock import patch
from bidsentry.evaluators.engine import EvaluationEngine, EvaluationRequest
from bidsentry.app import create_application
from bidsentry.config import Settings
from bidsentry.api.routes import ApiRouter


class TestBudgetEngineRegression(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = EvaluationEngine()

    def test_case_a_over_budget_nameerror_fixed(self) -> None:
        doc = "Pagu Rp 1.000.000.000\nTotal BoQ Rp 1.200.000.000\nMasa penawaran 7 hari kerja, masa sanggah 5 hari kerja."
        res = self.engine.evaluate(EvaluationRequest(package_name="Paket Uji A", dok_pemilihan=doc))
        self.assertEqual(res["verdict"], "NO-GO")
        finding_ids = [f["id"] for f in res["findings"]]
        self.assertIn("FIN-OVER-BUDGET", finding_ids)
        finding = next(f for f in res["findings"] if f["id"] == "FIN-OVER-BUDGET")
        self.assertIn(finding["requirement_evidence"], doc)
        self.assertIn(finding["evidence"], doc)

    def test_case_b_over_budget_nameerror_fixed(self) -> None:
        doc = "Pagu DIPA sebesar Rp 3.000.000.000. HPS ditetapkan sebesar Rp 3.400.000.000.\nMasa penawaran 7 hari kerja, masa sanggah 5 hari kerja."
        res = self.engine.evaluate(EvaluationRequest(package_name="Paket Uji B", dok_pemilihan=doc))
        self.assertEqual(res["verdict"], "NO-GO")
        finding_ids = [f["id"] for f in res["findings"]]
        self.assertIn("FIN-OVER-BUDGET", finding_ids)
        finding = next(f for f in res["findings"] if f["id"] == "FIN-OVER-BUDGET")
        self.assertIn(finding["requirement_evidence"], doc)
        self.assertIn(finding["evidence"], doc)

    def test_pagu_without_boq_does_not_crash(self) -> None:
        doc = "Pagu DIPA sebesar Rp 5.000.000.000. Masa penawaran 7 hari kerja, masa sanggah 5 hari kerja."
        res = self.engine.evaluate(EvaluationRequest(package_name="Paket Pagu Saja", dok_pemilihan=doc))
        self.assertNotEqual(res["verdict"], "CRASH")
        finding_ids = [f["id"] for f in res["findings"]]
        self.assertNotIn("FIN-OVER-BUDGET", finding_ids)

    def test_boq_under_pagu_no_overbudget_finding(self) -> None:
        doc = "Pagu Rp 2.000.000.000\nTotal BoQ Rp 1.800.000.000\nMasa penawaran 7 hari kerja, masa sanggah 5 hari kerja."
        res = self.engine.evaluate(EvaluationRequest(package_name="Paket Hemat", dok_pemilihan=doc))
        finding_ids = [f["id"] for f in res["findings"]]
        self.assertNotIn("FIN-OVER-BUDGET", finding_ids)

    def test_normative_hps_pagu_guideline_no_finding(self) -> None:
        doc_1 = "Sesuai regulasi LKPP, HPS tidak boleh melebihi pagu. Masa penawaran 7 hari kerja, masa sanggah 5 hari kerja."
        res_1 = self.engine.evaluate(EvaluationRequest(package_name="Normative 1", dok_pemilihan=doc_1))
        self.assertNotIn("FIN-OVER-BUDGET", [f["id"] for f in res_1["findings"]])

        doc_2 = "Ketentuan pengadaan: hps tidak melebihi pagu. Masa penawaran 7 hari kerja, masa sanggah 5 hari kerja."
        res_2 = self.engine.evaluate(EvaluationRequest(package_name="Normative 2", dok_pemilihan=doc_2))
        self.assertNotIn("FIN-OVER-BUDGET", [f["id"] for f in res_2["findings"]])

    def test_arbitrary_noisy_inputs_do_not_crash(self) -> None:
        noisy_inputs = ["", "Pagu", "HPS", "Pagu Rp", "Rp 1.000.000.000", "99999999999", "   \n\n\t  "]
        for inp in noisy_inputs:
            with self.subTest(input=inp):
                res = self.engine.evaluate(EvaluationRequest(package_name="Noisy", dok_pemilihan=inp))
                self.assertIsInstance(res, dict)
                self.assertIn("verdict", res)


class TestApiUnexpectedExceptionHandling(unittest.TestCase):
    def test_api_returns_structured_error_on_engine_failure(self) -> None:
        settings = Settings.from_environment()
        app = create_application(settings)
        router = ApiRouter(app)

        with patch.object(app.audit.audit_service, "audit", side_effect=RuntimeError("Simulated engine fault")):
            response = router.dispatch(
                "POST",
                "/api/audit",
                payload={"package_name": "Crash Test", "dok_pemilihan": "Pagu Rp 1000"},
            )
            self.assertEqual(response.status, 500)
            self.assertIn("error", response.body)
            self.assertEqual(response.body["error"]["code"], "INTERNAL_ERROR")
            self.assertIn("meta", response.body)
            self.assertIn("request_id", response.body["meta"])
            self.assertIsInstance(response.body["error"].get("details"), list)


if __name__ == "__main__":
    unittest.main()

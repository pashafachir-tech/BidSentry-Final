from __future__ import annotations

import unittest
from datetime import datetime, timezone
from decimal import Decimal

from bidsentry.audits.financial import audit_boq
from bidsentry.evaluators.grounded_checker import GroundedChecker
from bidsentry.forensics.metadata import compare_vendor_metadata
from bidsentry.schemas.comprehensive import BoQLineItem, CandidateEvaluation, PageChunk


class ComprehensiveAuditModuleTests(unittest.TestCase):
    def test_boq_flags_arithmetic_mismatch_and_unbalanced_price(self) -> None:
        item = BoQLineItem(
            item_code="BOQ-04",
            description="Pekerjaan Server Rack 42U",
            volume=Decimal("4"),
            unit="Unit",
            unit_price_offered=Decimal("25000000"),
            total_offered=Decimal("120000000"),
            hps_unit_price=Decimal("22000000"),
            source_quote="Pekerjaan Server Rack 42U | Volume: 4 Unit | Harga Satuan: Rp 25.000.000 | Total: Rp 120.000.000",
            page_ref="Page 14",
        )
        result = audit_boq([item])
        self.assertTrue(result["arithmetic_errors_detected"])
        self.assertTrue(result["unbalanced_pricing_detected"])
        self.assertEqual(result["line_item_anomalies"][0]["calculated_total"], 100000000)

    def test_ungrounded_quote_is_downgraded_to_zero_confidence(self) -> None:
        candidate = CandidateEvaluation(
            clause_id="KO-01",
            requirement="Ketentuan denda keterlambatan",
            status="POTENTIAL_GAP",
            verbatim_quote="denda dibatasi 5% dari kontrak",
            page_ref="Page 58",
            confidence=0.93,
        )
        finding = GroundedChecker.validate_candidate(candidate, [PageChunk(page_ref="Page 58", text="Denda sebesar 1/1000 per hari.")])
        self.assertEqual(finding.status, "UNVERIFIED_HALLUCINATION")
        self.assertEqual(finding.confidence, 0.0)

    def test_exact_quote_without_page_locator_is_assigned_to_source_page(self) -> None:
        candidate = CandidateEvaluation(
            clause_id="KO-02",
            requirement="Ketentuan jaminan penawaran",
            status="POTENTIAL_MATCH",
            verbatim_quote="Jaminan Penawaran berlaku 60 hari.",
            page_ref=None,
            confidence=0.82,
        )
        finding = GroundedChecker.validate_candidate(candidate, [PageChunk(page_ref="Page 12", text="Jaminan Penawaran berlaku 60 hari.")])
        self.assertEqual(finding.status, "POTENTIAL_MATCH")
        self.assertEqual(finding.page_ref, "Page 12")

    def test_metadata_collusion_screen_flags_shared_id_and_close_submissions(self) -> None:
        vendors = [
            {
                "vendor_id": "vendor-a",
                "vendor_name": "Vendor A",
                "submission_timestamp": datetime(2026, 10, 26, 10, 0, tzinfo=timezone.utc),
                "document_metadata": {"author": "Shared Operator", "document_uuid_sha256": "same-pdf-id"},
            },
            {
                "vendor_id": "vendor-b",
                "vendor_name": "Vendor B",
                "submission_timestamp": datetime(2026, 10, 26, 10, 5, tzinfo=timezone.utc),
                "document_metadata": {"author": "Shared Operator", "document_uuid_sha256": "same-pdf-id"},
            },
        ]
        result = compare_vendor_metadata(vendors)
        signals = {item["signal"] for item in result["alerts"]}
        self.assertIn("MATCHING_PDF_DOCUMENT_ID", signals)
        self.assertIn("CLOSE_SUBMISSION_TIMESTAMPS", signals)
        self.assertIn("SHARED_AUTHOR_PROFILE", signals)


if __name__ == "__main__":
    unittest.main()

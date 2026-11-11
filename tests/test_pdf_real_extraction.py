"""Tests validating extraction and deterministic evaluation on real multi-page PDF documents."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import unittest
from bidsentry.services.document_extraction_service import DocumentExtractionService
from bidsentry.evaluators.engine import EvaluationEngine, EvaluationRequest

PDF_DIR = ROOT / "data" / "sample_tenders" / "pdf_tenders"


class RealPdfExtractionTests(unittest.TestCase):
    def setUp(self):
        self.extractor = DocumentExtractionService()
        self.engine = EvaluationEngine()

    def test_extract_multipage_rab_pdf(self):
        pdf_path = PDF_DIR / "paket_konstruksi_rab_kompleks.pdf"
        self.assertTrue(pdf_path.is_file(), f"File {pdf_path} not found")
        content = pdf_path.read_bytes()

        result = self.extractor.extract(pdf_path.name, content)
        self.assertIn("filename", result)
        self.assertIn("text", result)
        text = result["text"]

        # Assert key table lines extracted across pages
        self.assertIn("Mobilisasi dan Demobilisasi", text)
        self.assertIn("Galian Saluran Drainase", text)
        self.assertIn("Lapis Pondasi Agregat", text)
        self.assertIn("Laston Lapis Aus (AC-WC)", text)
        self.assertIn("10.238.418.000", text)
        self.assertGreater(result["characters"], 500)

    def test_evaluate_extracted_kak_pdf_catches_fatal_flaws(self):
        pdf_path = PDF_DIR / "paket_pengadaan_it_server_kak.pdf"
        self.assertTrue(pdf_path.is_file(), f"File {pdf_path} not found")
        content = pdf_path.read_bytes()

        result = self.extractor.extract(pdf_path.name, content)
        text = result["text"]

        # Run evaluation on extracted PDF text
        request = EvaluationRequest(
            package_name="Pengadaan Server Data Center",
            dok_pemilihan=text,
            pustaka="",
        )
        eval_res = self.engine.evaluate(request)

        # Must flag NO-GO due to vendor lock-in, compressed timeline, and uncapped penalty
        self.assertEqual(eval_res["verdict"], "NO-GO")
        finding_ids = {f["id"] for f in eval_res["findings"]}
        self.assertTrue("SPEC-LOCKIN-CPU" in finding_ids or "SPEC-LOCKIN-MGMT" in finding_ids)
        self.assertIn("CON-PENALTY", finding_ids)
        self.assertIn("PROC-TIMELINE-COMPRESSED", finding_ids)

    def test_extract_real_boq_excel_file(self):
        excel_path = ROOT / "data" / "sample_tenders" / "rab_konstruksi_boq.xlsx"
        self.assertTrue(excel_path.is_file(), f"Excel file {excel_path} not found")
        content = excel_path.read_bytes()

        result = self.extractor.extract(excel_path.name, content)
        self.assertEqual(result["extraction_mode"], "excel_table_parser")
        self.assertEqual(result.get("excel_items_count"), 5)
        text = result["text"]
        self.assertIn("Mobilisasi dan Demobilisasi", text)
        self.assertIn("Perkerasan Aspal Laston", text)
        self.assertIn("2.478.000.000", text)

    def test_scanned_pdf_detection_and_fallback(self):
        # Create a synthetic 1-page PDF containing minimal or zero text layer
        import pymupdf
        doc = pymupdf.open()
        doc.new_page(width=595, height=842)
        # Empty text on page, simulating a scanned document
        pdf_bytes = doc.tobytes()
        doc.close()

        result = self.extractor.extract("dokumen_scan_lpse.pdf", pdf_bytes)
        self.assertTrue(result["scanned_pdf"])
        self.assertEqual(result["extraction_mode"], "scanned_no_text_layer")
        # No placeholder text may be injected into the audited document.
        self.assertEqual(result["text"], "")
        self.assertTrue(any("OCR" in warning for warning in result["warnings"]))


if __name__ == "__main__":
    unittest.main()

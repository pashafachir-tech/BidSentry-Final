"""Optional DOCX/PDF rendering helpers used by document draft generators."""

from __future__ import annotations

import io
import re
from collections.abc import Iterable
from typing import Any
from xml.sax.saxutils import escape


class DocumentGenerationError(RuntimeError):
    """A requested document format could not be rendered."""


def require_docx():
    try:
        from docx import Document
    except ImportError as exc:
        raise DocumentGenerationError("DOCX export requires python-docx; install project requirements.") from exc
    return Document


def render_pdf(title: str, paragraphs: Iterable[str], tables: list[list[list[str]]] | None = None) -> bytes:
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    except ImportError as exc:
        raise DocumentGenerationError("PDF export requires reportlab; install project requirements.") from exc
    output = io.BytesIO()
    document = SimpleDocTemplate(output, pagesize=A4, rightMargin=18 * mm, leftMargin=18 * mm, topMargin=18 * mm, bottomMargin=18 * mm)
    styles = getSampleStyleSheet()
    story: list[Any] = [Paragraph(escape(title), styles["Title"]), Spacer(1, 6 * mm)]
    for paragraph in paragraphs:
        story.append(Paragraph(_safe_text(paragraph), styles["BodyText"]))
        story.append(Spacer(1, 3 * mm))
    for rows in tables or []:
        cell_data = [[Paragraph(_safe_text(cell), styles["BodyText"]) for cell in row] for row in rows]
        table = Table(cell_data, repeatRows=1, hAlign="LEFT")
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E8EEF5")),
            ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#9AA8B6")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ]))
        story.extend([table, Spacer(1, 4 * mm)])
    try:
        document.build(story)
    except Exception as exc:
        raise DocumentGenerationError("PDF draft could not be rendered.") from exc
    return output.getvalue()


def _safe_text(value: str) -> str:
    # Escape markup before translating newlines into reportlab paragraph breaks.
    return escape(str(value)).replace("\n", "<br/>")


def clean_cell(value: Any, maximum: int = 1200) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()[:maximum]


_STATUS_LABELS = {
    "TERPENUHI": "Terpenuhi",
    "GAP": "Kesenjangan",
    "EXPIRING": "Segera berakhir",
    "SUPERSEDED": "Diubah adendum",
    "REVIEW": "Perlu diperiksa",
    "MATH_MISMATCH": "Selisih aritmetika",
    "REVIEW_REQUIRED": "Perlu diperiksa",
}


def normalize_finding(item: dict[str, Any]) -> dict[str, str]:
    """Map both evaluation-engine findings and forensic anomalies to one row shape.

    Engine findings use ``id/clause/requirement_evidence/evidence/review_note``;
    forensic anomalies use ``anomaly_type/source_quote/page_ref/description``.
    Generators must go through this function so neither shape renders empty.
    """
    code = item.get("id") or item.get("anomaly_type") or item.get("signal") or item.get("type") or "TEMUAN"
    title = item.get("clause") or item.get("title") or item.get("anomaly_type") or item.get("signal") or "Temuan"
    quote = (
        item.get("verbatim_quote") or item.get("source_quote") or item.get("requirement_evidence")
        or (item.get("evidence") if item.get("evidence") and not str(item.get("evidence")).startswith("Belum ada bukti") else None)
        or "Kutipan tidak tersedia."
    )
    locator = item.get("source") or item.get("page_ref") or item.get("evidence_source") or "Lokator tidak tersedia"
    status = str(item.get("status") or "").upper()
    reviewer = item.get("reviewer_outcome") or item.get("reviewer_status")
    return {
        "code": clean_cell(code, 80),
        "title": clean_cell(title, 240),
        "status": status,
        "status_label": _STATUS_LABELS.get(status, status.title() if status else "Perlu diperiksa"),
        "severity": clean_cell(item.get("severity") or "", 20),
        "quote": clean_cell(quote, 900),
        "locator": clean_cell(locator, 200),
        "note": clean_cell(item.get("review_note") or item.get("description") or item.get("interpretation") or "Cocokkan dengan dokumen sumber dan kriteria paket.", 700),
        "legal_reference": clean_cell(item.get("legal_reference") or "", 900),
        "reviewer": clean_cell(reviewer or "[Keputusan reviewer]", 80),
    }

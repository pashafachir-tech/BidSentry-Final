"""Create readable, dependency-free XLSX exports for reviewers and executives."""

from __future__ import annotations

import base64
import io
import math
import zipfile
from datetime import datetime, timezone
from typing import Any
from xml.sax.saxutils import escape

from bidsentry.types.schemas import ValidationError


_STATUS_LABELS = {
    "TERPENUHI": "Terpenuhi",
    "GAP": "Perlu perhatian",
    "EXPIRING": "Segera kedaluwarsa",
    "SUPERSEDED": "Digantikan adendum",
    "REVIEW": "Perlu ditinjau",
}
_RISK_LABELS = {"NOT_ASSESSABLE": "Tidak Dapat Dinilai", "LOW": "Rendah", "MEDIUM": "Sedang", "HIGH": "Tinggi", "CRITICAL": "Kritis"}
_STYLE_BY_STATUS = {"TERPENUHI": 12, "GAP": 10, "EXPIRING": 11, "SUPERSEDED": 13, "REVIEW": 9}
_STYLE_BY_RISK = {"NOT_ASSESSABLE": 9, "LOW": 12, "MEDIUM": 11, "HIGH": 10, "CRITICAL": 10}
_COLUMNS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def _safe_text(value: Any) -> str:
    text = str(value if value is not None else "")
    text = "".join(
        char for char in text
        if char in "\t\n\r" or 0x20 <= ord(char) <= 0xD7FF or 0xE000 <= ord(char) <= 0xFFFD or 0x10000 <= ord(char) <= 0x10FFFF
    )
    return text[:32000]


def _column_name(index: int) -> str:
    result = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        result = _COLUMNS[remainder] + result
    return result


def _cell_xml(reference: str, value: Any, style: int = 0) -> str:
    style_attr = f' s="{style}"' if style else ""
    if value is None or value == "":
        return f'<c r="{reference}"{style_attr}/>'
    if isinstance(value, bool):
        return f'<c r="{reference}"{style_attr} t="b"><v>{1 if value else 0}</v></c>'
    if isinstance(value, (int, float)) and math.isfinite(float(value)):
        return f'<c r="{reference}"{style_attr}><v>{value}</v></c>'
    text = escape(_safe_text(value)).replace("\n", "&#10;").replace("\r", "&#13;")
    return f'<c r="{reference}"{style_attr} t="inlineStr"><is><t xml:space="preserve">{text}</t></is></c>'


def _sheet_xml(
    rows: list[list[tuple[Any, int]]],
    widths: list[int],
    *,
    merges: list[str] | None = None,
    filter_ref: str | None = None,
    freeze: tuple[int, int, str] | None = None,
    long_text_row: int | None = None,
) -> str:
    row_xml: list[str] = []
    for row_index, cells in enumerate(rows, start=1):
        rendered = "".join(_cell_xml(f"{_column_name(index)}{row_index}", value, style) for index, (value, style) in enumerate(cells, start=1))
        if row_index == long_text_row:
            text_length = max((len(_safe_text(value)) for value, _ in cells), default=0)
            height = min(400, max(72, math.ceil(text_length / 260) * 15 + 24))
        elif row_index >= 8:
            line_count = max(
                (math.ceil(len(_safe_text(value)) / max(12, int(widths[index - 1] * 1.2))) for index, (value, _) in enumerate(cells, start=1)),
                default=1,
            )
            height = min(150, max(30, line_count * 14 + 10))
        else:
            height = 24
        row_xml.append(f'<row r="{row_index}" customHeight="1" ht="{height}">{rendered}</row>')
    cols = "".join(f'<col min="{i}" max="{i}" width="{width}" customWidth="1"/>' for i, width in enumerate(widths, start=1))
    pane = ""
    if freeze:
        x_split, y_split, top_left = freeze
        active_pane = "bottomRight" if x_split and y_split else "bottomLeft" if y_split else "topRight"
        pane = f'<pane xSplit="{x_split}" ySplit="{y_split}" topLeftCell="{top_left}" activePane="{active_pane}" state="frozen"/>'
        pane += f'<selection pane="{active_pane}" activeCell="{top_left}" sqref="{top_left}"/>'
    merge_xml = ""
    if merges:
        merge_items = "".join('<mergeCell ref="' + ref + '"/>' for ref in merges)
        merge_xml = f'<mergeCells count="{len(merges)}">{merge_items}</mergeCells>'
    filter_xml = f'<autoFilter ref="{filter_ref}"/>' if filter_ref else ""
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f'<sheetViews><sheetView showGridLines="0">{pane}</sheetView></sheetViews>'
        '<sheetFormatPr defaultRowHeight="24"/><cols>' + cols + '</cols><sheetData>'
        + "".join(row_xml) + "</sheetData>" + filter_xml + merge_xml
        + '<pageMargins left="0.3" right="0.3" top="0.5" bottom="0.5" header="0.2" footer="0.2"/>'
        + '<pageSetup orientation="landscape" fitToWidth="1" fitToHeight="0"/></worksheet>'
    )


def _styles_xml() -> str:
    return '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <numFmts count="1"><numFmt numFmtId="164" formatCode="&quot;Rp&quot; #,##0"/></numFmts>
  <fonts count="3">
    <font><sz val="10"/><name val="Aptos"/><color rgb="FF3F453B"/></font>
    <font><b/><sz val="18"/><name val="Aptos Display"/><color rgb="FF27332D"/></font>
    <font><b/><sz val="10"/><name val="Aptos"/><color rgb="FFFFFFFF"/></font>
  </fonts>
  <fills count="8">
    <fill><patternFill patternType="none"/></fill>
    <fill><patternFill patternType="gray125"/></fill>
    <fill><patternFill patternType="solid"><fgColor rgb="FF46584B"/><bgColor indexed="64"/></patternFill></fill>
    <fill><patternFill patternType="solid"><fgColor rgb="FFEAF0E9"/><bgColor indexed="64"/></patternFill></fill>
    <fill><patternFill patternType="solid"><fgColor rgb="FFFFF6DD"/><bgColor indexed="64"/></patternFill></fill>
    <fill><patternFill patternType="solid"><fgColor rgb="FFFBE9E6"/><bgColor indexed="64"/></patternFill></fill>
    <fill><patternFill patternType="solid"><fgColor rgb="FFFFF0D8"/><bgColor indexed="64"/></patternFill></fill>
    <fill><patternFill patternType="solid"><fgColor rgb="FFF0F0EC"/><bgColor indexed="64"/></patternFill></fill>
  </fills>
  <borders count="2">
    <border><left/><right/><top/><bottom/><diagonal/></border>
    <border><left style="thin"><color rgb="FFE2E5DE"/></left><right style="thin"><color rgb="FFE2E5DE"/></right><top style="thin"><color rgb="FFE2E5DE"/></top><bottom style="thin"><color rgb="FFE2E5DE"/></bottom><diagonal/></border>
  </borders>
  <cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
  <cellXfs count="15">
    <xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"><alignment vertical="top"/></xf>
    <xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0"><alignment vertical="center"/></xf>
    <xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"><alignment vertical="center"/></xf>
    <xf numFmtId="0" fontId="0" fillId="3" borderId="1" xfId="0"><alignment vertical="center"/></xf>
    <xf numFmtId="0" fontId="0" fillId="3" borderId="1" xfId="0"><alignment vertical="center" wrapText="1"/></xf>
    <xf numFmtId="0" fontId="0" fillId="4" borderId="1" xfId="0"><alignment vertical="top" wrapText="1"/></xf>
    <xf numFmtId="0" fontId="2" fillId="2" borderId="0" xfId="0"><alignment vertical="center"/></xf>
    <xf numFmtId="0" fontId="2" fillId="2" borderId="1" xfId="0"><alignment vertical="center" wrapText="1"/></xf>
    <xf numFmtId="0" fontId="0" fillId="0" borderId="1" xfId="0"><alignment vertical="top" wrapText="1"/></xf>
    <xf numFmtId="0" fontId="0" fillId="4" borderId="1" xfId="0"><alignment vertical="center" wrapText="1"/></xf>
    <xf numFmtId="0" fontId="0" fillId="5" borderId="1" xfId="0"><alignment vertical="center" wrapText="1"/></xf>
    <xf numFmtId="0" fontId="0" fillId="6" borderId="1" xfId="0"><alignment vertical="center" wrapText="1"/></xf>
    <xf numFmtId="0" fontId="0" fillId="3" borderId="1" xfId="0"><alignment vertical="center" wrapText="1"/></xf>
    <xf numFmtId="0" fontId="0" fillId="7" borderId="1" xfId="0"><alignment vertical="center" wrapText="1"/></xf>
    <xf numFmtId="164" fontId="0" fillId="3" borderId="1" xfId="0" applyNumberFormat="1"><alignment vertical="center"/></xf>
  </cellXfs>
  <cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>
</styleSheet>'''


class WorkbookExportService:
    """Builds a compact executive workbook without storing uploaded documents."""

    def create(self, payload: Any) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise ValidationError("Permintaan ekspor Excel tidak valid.", [{"field": "$", "issue": "expected_object"}])
        kind = payload.get("kind")
        if kind == "review":
            review = payload.get("review")
            if not isinstance(review, dict):
                raise ValidationError("Hasil review tidak tersedia untuk diekspor.", [{"field": "review", "issue": "expected_object"}])
            include_ai = payload.get("include_ai_insights", False) is True
            sheets = [("Risk Review", self._review_sheet(review))]
            if include_ai:
                sheets.append(("AI Insights", self._insights_sheet(review)))
            filename = "bidsentry-risk-review-" + datetime.now().strftime("%Y%m%d-%H%M") + ".xlsx"
        elif kind == "register":
            audits = payload.get("audits", [])
            if not isinstance(audits, list) or any(not isinstance(row, dict) for row in audits):
                raise ValidationError("Data register audit tidak valid.", [{"field": "audits", "issue": "expected_list_of_objects"}])
            sheets = [("Register Audit", self._register_sheet(audits))]
            filename = "bidsentry-register-audit-" + datetime.now().strftime("%Y%m%d-%H%M") + ".xlsx"
        else:
            raise ValidationError("Pilih jenis laporan Excel yang tersedia.", [{"field": "kind", "issue": "invalid_value"}])

        content = self._xlsx(sheets)
        return {
            "filename": filename,
            "content_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "content_base64": base64.b64encode(content).decode("ascii"),
        }

    @staticmethod
    def _review_sheet(review: dict[str, Any]) -> dict[str, Any]:
        role = "Tim hukum" if review.get("review_role") == "legal" else "Tim pengadaan"
        risk = str(review.get("risk_level", "")).upper()
        findings = review.get("findings", [])
        if not isinstance(findings, list):
            findings = []
        findings = [item for item in findings if isinstance(item, dict)]
        if review.get("review_role") == "legal":
            findings = [item for item in findings if str(item.get("category", "")).lower() == "kontrak"]
        total_findings = len(findings)
        exported_findings = findings[:300]
        counts = {
            "total": total_findings,
            "review": sum(1 for item in findings if str(item.get("status", "REVIEW")).upper() in {"REVIEW", "GAP", "EXPIRING"}),
        }
        verdict = str(review.get("verdict") or "REVIEW_REQUIRED").upper()
        status_label = "Perlu review manusia" if verdict in {"REVIEW_REQUIRED", "REVIEW"} else verdict.replace("_", " ").title()
        contract_value = review.get("contract_value_idr")
        has_contract_value = isinstance(contract_value, (int, float)) and not isinstance(contract_value, bool) and math.isfinite(float(contract_value)) and contract_value > 0
        rows: list[list[tuple[Any, int]]] = [
            [("BidSentry | Risk Review", 1)],
            [("Ringkasan untuk pimpinan · dibuat " + datetime.now(timezone.utc).astimezone().strftime("%d %b %Y %H:%M %Z"), 2)],
            [("Nama paket", 3), (_safe_text(review.get("package_name") or "Audit dokumen"), 4), ("ID paket", 3), (_safe_text(review.get("tender_id") or review.get("audit_id") or "—"), 4), ("Peran", 3), (role, 4), ("Status", 3), (status_label, 4)],
            [("Instansi", 3), (_safe_text(review.get("agency") or "—"), 4), ("Nilai kontrak / penawaran", 3), (contract_value if has_contract_value else "—", 14 if has_contract_value else 4), ("Tingkat risiko", 3), (_RISK_LABELS.get(risk, risk or "Perlu ditinjau"), _STYLE_BY_RISK.get(risk, 9)), ("Aturan keputusan", 3), (_safe_text((review.get("risk") or {}).get("rule_applied") or "—"), 4)],
            [("Perlu ditinjau", 3), (counts["review"], 4), ("Sinyal terdeteksi", 3), (counts["total"], 4), ("Ditampilkan", 3), (min(total_findings, 300), 4)],
            [("Batas penggunaan", 3), ("Indeks triase dan sinyal aturan; bukan verdict kepatuhan, opini hukum, atau temuan fraud. Skor 0 bukan bukti paket bebas risiko. Verifikasi sumber asli sebelum bertindak.", 5)],
            [("Batas ekspor", 3), (f"Menampilkan 300 dari {total_findings} sinyal; buka aplikasi untuk meninjau daftar lengkap." if total_findings > 300 else "Semua sinyal review yang tersedia ditampilkan.", 5)],
            [("TEMUAN UTAMA & LANGKAH REVIEW", 6)],
            [("ID", 7), ("Area", 7), ("Klausul / isu", 7), ("Status", 7), ("Sumber syarat", 7), ("Kutipan syarat", 7), ("Sumber bukti", 7), ("Bukti terdeteksi", 7), ("Langkah verifikasi", 7)],
        ]
        for item in exported_findings:
            status = str(item.get("status", item.get("severity", "REVIEW"))).upper()
            rows.append([
                (_safe_text(item.get("id", "")), 8),
                (_safe_text(item.get("category", "Review")), 8),
                (_safe_text(item.get("clause", item.get("category", "Sinyal review"))), 8),
                (_STATUS_LABELS.get(status, status), _STYLE_BY_STATUS.get(status, 9)),
                (_safe_text(item.get("source", "")), 8),
                (_safe_text(item.get("requirement_evidence", "")), 8),
                (_safe_text(item.get("evidence_source", item.get("source", ""))), 8),
                (_safe_text(item.get("evidence", "")), 8),
                (_safe_text(item.get("review_note", "Periksa dokumen asli dan versi yang berlaku.")), 8),
            ])
        if not findings:
            rows.append([("—", 8), ("—", 8), ("Belum ada sinyal aturan lokal", 8), ("Perlu pemeriksaan manual", 9), ("—", 8), ("Tidak ada kecocokan yang ditampilkan.", 8), ("—", 8), ("Periksa dokumen asli.", 8), ("Ketiadaan sinyal bukan bukti pemenuhan.", 8)])
        return {
            "rows": rows,
            "widths": [12, 17, 35, 19, 30, 44, 30, 44, 48],
            "merges": ["A1:I1", "A2:I2", "B6:I6", "B7:I7", "A8:I8"],
            "filter_ref": f"A9:I{len(rows)}",
            "freeze": (2, 9, "C10"),
        }

    @staticmethod
    def _insights_sheet(review: dict[str, Any]) -> dict[str, Any]:
        integration = review.get("integrations", {})
        langflow = integration.get("langflow", {}) if isinstance(integration, dict) else {}
        if not isinstance(langflow, dict):
            langflow = {}
        status = langflow.get("status", "not_requested")
        advisory = langflow.get("advisory")
        ai_text = advisory if isinstance(advisory, str) and advisory.strip() else langflow.get("message") or "AI Insights belum dijalankan. Hasil aturan lokal tetap tersedia; tidak ada keluaran AI pada audit ini."
        role = str(review.get("review_role", "procurement"))
        role_label = "Tim hukum" if role == "legal" else "Tim pengadaan"
        findings = review.get("findings", [])
        findings = [item for item in findings if isinstance(item, dict)] if isinstance(findings, list) else []
        if role == "legal":
            findings = [item for item in findings if str(item.get("category", "")).lower() == "kontrak"]
        total_findings = len(findings)
        rows: list[list[tuple[Any, int]]] = [
            [("BidSentry | AI Insights", 1)],
            [("Saran analisis untuk ditinjau manusia · AI tidak menetapkan keputusan", 2)],
            [("Nama paket", 3), (_safe_text(review.get("package_name") or "Audit dokumen"), 4), ("", 0), ("Fokus reviewer", 3), (role_label, 4), ("", 0)],
            [("Status analisis", 3), ("Selesai" if status == "success" and advisory else "Belum dijalankan / tidak tersedia", 4)],
            [("INSIGHT LANGFLOW", 6)],
            [(_safe_text(ai_text), 5)],
            [("Batas ekspor", 3), (f"Menampilkan 100 dari {total_findings} sinyal; buka aplikasi untuk meninjau daftar lengkap." if total_findings > 100 else "Semua sinyal lokal yang tersedia ditampilkan.", 5)],
            [("PRIORITAS VERIFIKASI DARI ATURAN LOKAL", 6)],
            [("ID", 7), ("Area", 7), ("Sinyal", 7), ("Rujukan", 7), ("Kutipan / bukti", 7), ("Langkah berikutnya", 7)],
        ]
        for item in findings[:100]:
            if role == "legal":
                action = "Periksa redaksi dan perubahan terhadap versi berlaku; eskalasikan pertanyaan kepada penasihat hukum."
            else:
                action = "Cocokkan bukti dengan syarat dan adendum; catat apakah bukti cukup atau perlu diminta."
            citation = item.get("evidence_source") or item.get("source") or "Rujukan belum ditentukan"
            excerpt = item.get("evidence") or item.get("requirement_evidence") or item.get("review_note") or "Periksa dokumen asli."
            rows.append([
                (_safe_text(item.get("id", "")), 8),
                (_safe_text(item.get("category", "Review")), 8),
                (_safe_text(item.get("clause", "Sinyal review")), 8),
                (_safe_text(citation), 8),
                (_safe_text(excerpt), 8),
                (_safe_text(action), 8),
            ])
        if not findings:
            rows.append([("—", 8), ("—", 8), ("Belum ada sinyal lokal untuk peran ini", 8), ("—", 8), ("Periksa dokumen sumber", 8), ("Ketiadaan sinyal bukan bukti aman atau terpenuhi.", 8)])
        return {
            "rows": rows,
            "widths": [12, 18, 37, 38, 58, 58],
            "merges": ["A1:F1", "A2:F2", "B3:C3", "E3:F3", "B4:F4", "A5:F5", "A6:F6", "B7:F7", "A8:F8"],
            "filter_ref": f"A9:F{len(rows)}",
            "freeze": (1, 9, "B10"),
            "long_text_row": 6,
        }

    @staticmethod
    def _register_sheet(audits: list[dict[str, Any]]) -> dict[str, Any]:
        rows: list[list[tuple[Any, int]]] = [
            [("BidSentry | Register Audit", 1)],
            [("Ringkasan audit lokal dan prioritas pemeriksaan", 2)],
            [("Catatan", 3), ("Tingkat risiko ditentukan tabel keputusan deterministik (R0–R6). Data sumber dokumen tidak termasuk dalam register ini.", 5)],
            [("", 0)],
            [("DAFTAR PAKET", 6)],
            [("Nama paket", 7), ("ID paket", 7), ("Tanggal", 7), ("Instansi", 7), ("Penyedia", 7), ("Nilai kontrak / penawaran (Rp)", 7), ("Aturan keputusan", 7), ("Tingkat risiko", 7), ("Status review", 7), ("Jumlah temuan", 7), ("Sumber data", 7)],
        ]
        for item in audits[:1000]:
            level = str(item.get("risk_level", "MEDIUM")).upper()
            findings = item.get("findings", [])
            summary = item.get("summary", {})
            finding_count = len(findings) if isinstance(findings, list) else (summary.get("findings", 0) if isinstance(summary, dict) else 0)
            contract_value = item.get("contract_value_idr")
            has_contract_value = isinstance(contract_value, (int, float)) and not isinstance(contract_value, bool) and math.isfinite(float(contract_value)) and contract_value > 0
            rows.append([
                (_safe_text(item.get("package_name", "")), 8),
                (_safe_text(item.get("tender_id") or item.get("audit_id", "")), 8),
                (_safe_text(item.get("created_at", "")), 8),
                (_safe_text(item.get("agency", "")), 8),
                (_safe_text(item.get("vendor_name", "")), 8),
                (contract_value if has_contract_value else "—", 14 if has_contract_value else 8),
                (_safe_text((item.get("risk") or {}).get("rule_applied") or "—"), 8),
                (_RISK_LABELS.get(level, level), _STYLE_BY_RISK.get(level, 9)),
                (_safe_text(item.get("verdict", "REVIEW_REQUIRED")), 8),
                (finding_count, 8),
                ("Metadata audit lokal", 8),
            ])
        if len(rows) == 6:
            rows.append([("Belum ada paket pada filter ini.", 8)])
        return {
            "rows": rows,
            "widths": [42, 20, 23, 28, 28, 19, 14, 18, 22, 16, 24],
            "merges": ["A1:K1", "A2:K2", "B3:K3", "A5:K5"],
            "filter_ref": f"A6:K{len(rows)}",
            "freeze": (2, 6, "C7"),
        }

    @staticmethod
    def _xlsx(sheets: list[tuple[str, dict[str, Any]]]) -> bytes:
        workbook = io.BytesIO()
        with zipfile.ZipFile(workbook, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            sheet_count = len(sheets)
            overrides = "".join(
                f'<Override PartName="/xl/worksheets/sheet{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
                for i in range(1, sheet_count + 1)
            )
            archive.writestr("[Content_Types].xml", '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>' + overrides + '</Types>')
            archive.writestr("_rels/.rels", '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')
            workbook_sheets = []
            relationships = []
            for index, (name, spec) in enumerate(sheets, start=1):
                workbook_sheets.append(f'<sheet name="{escape(name)}" sheetId="{index}" r:id="rId{index}"/>')
                relationships.append(f'<Relationship Id="rId{index}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{index}.xml"/>')
                archive.writestr(f"xl/worksheets/sheet{index}.xml", _sheet_xml(spec["rows"], spec["widths"], merges=spec.get("merges"), filter_ref=spec.get("filter_ref"), freeze=spec.get("freeze"), long_text_row=spec.get("long_text_row")))
            relationships.append(f'<Relationship Id="rId{sheet_count + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>')
            archive.writestr("xl/workbook.xml", '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><bookViews><workbookView/></bookViews><sheets>' + "".join(workbook_sheets) + '</sheets><calcPr calcId="191029"/></workbook>')
            archive.writestr("xl/_rels/workbook.xml.rels", '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">' + "".join(relationships) + '</Relationships>')
            archive.writestr("xl/styles.xml", _styles_xml())
        return workbook.getvalue()

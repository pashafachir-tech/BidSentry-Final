"""Consultant-grade BoQ workbook with live formulas, cross-checked by the Python calculator.

Sheets:

* ``Rekapitulasi``   – audit recap: package, risk tier and rule, BoQ totals as
                       formulas, pagu vs BoQ, finding counts per status.
* ``BoQ``            – one row per line item. *Jumlah hitung* is
                       ``=PRODUCT(volume, harga satuan)``, *Selisih* and the
                       Excel status are formulas; *Cek Python* is the
                       independent result of :func:`audit_boq`.
* ``Temuan``         – every finding with status, quote and decision column.
* ``Jejak Hitungan`` – every calculation step of the audit proof log.

Columns are sized from their rendered content so Excel never shows ``###``.
"""

from __future__ import annotations

import base64
import io
import json
from datetime import datetime
from typing import Any

from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE

from bidsentry.audits.financial import audit_boq, parse_boq_text
from bidsentry.schemas.comprehensive import BoQLineItem

FORMULA_TRIGGERS = ("=", "+", "-", "@", "\t", "\r")
XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
IDR_FORMAT = '"Rp" #,##0;[Red]-"Rp" #,##0'
STATUS_LABELS = {"TERPENUHI": "Terpenuhi", "GAP": "Kesenjangan", "EXPIRING": "Segera berakhir", "SUPERSEDED": "Diubah adendum", "REVIEW": "Perlu diperiksa"}
ROLE_LABELS = {"pokja": "Pokja Pemilihan", "vendor": "Penyedia / Vendor"}


def _display_width(value: Any, number_format: str | None) -> int:
    """Approximate rendered character width of a cell value."""
    if value is None:
        return 0
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if number_format and "Rp" in number_format:
            return len(f"Rp {abs(value):,.0f}") + (1 if value < 0 else 0)
        if number_format and "%" in number_format:
            return 8
        return len(f"{value:,.2f}".rstrip("0").rstrip("."))
    text = str(value)
    if text.startswith("="):
        return 0  # formula width is estimated from its numeric inputs below
    return max((len(line) for line in text.splitlines()), default=0)


class BoQExportService:
    def create(self, audit: dict[str, Any], source_text: str, *, role: str | None = None) -> dict[str, Any]:
        from openpyxl import Workbook
        from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
        from openpyxl.utils import get_column_letter
        from openpyxl.worksheet.page import PageMargins

        items: list[BoQLineItem] = parse_boq_text(source_text or "")
        python_check = audit_boq(items)
        line_checks = python_check.get("line_item_checks", [])
        mismatches = sum(1 for check in line_checks if check.get("math_status") == "MATH_MISMATCH")

        workbook = Workbook()
        thin = Side(style="thin", color="B8C2CC")
        border = Border(left=thin, right=thin, top=thin, bottom=thin)
        head_fill = PatternFill("solid", fgColor="1E293B")
        head_font = Font(bold=True, color="FFFFFF", size=11, name="Calibri")
        body_font = Font(size=11, name="Calibri")
        bold = Font(size=11, name="Calibri", bold=True)
        title_font = Font(size=16, name="Calibri", bold=True, color="1E293B")
        warn_fill = PatternFill("solid", fgColor="FDE2E1")
        total_fill = PatternFill("solid", fgColor="E2E8F0")
        wrap_top = Alignment(wrap_text=True, vertical="top")
        top = Alignment(vertical="top")
        widths: dict[str, dict[int, int]] = {}

        def put(sheet: Any, row: int, column: int, value: Any, *, fmt: str | None = None, font: Any = body_font, fill: Any = None, wrap: bool = False, framed: bool = True, measure: bool = True, formula: bool = False) -> Any:
            """Write a cell. Only ``formula=True`` values may become formulas.

            Text that comes from tender documents is untrusted: control characters
            are stripped (they make the file unopenable) and text that starts with
            a formula trigger (=, +, -, @) is stored as a literal string, so a
            document line such as ``=cmd|'/c calc'!A1`` can never execute.
            """
            if isinstance(value, str):
                value = ILLEGAL_CHARACTERS_RE.sub("", value)[:32000]
            cell = sheet.cell(row=row, column=column, value=value)
            if isinstance(value, str) and not formula and value.startswith(FORMULA_TRIGGERS):
                cell.data_type = "s"
            cell.font = font
            if fmt:
                cell.number_format = fmt
            if fill:
                cell.fill = fill
            if framed:
                cell.border = border
            cell.alignment = wrap_top if wrap else top
            sheet_widths = widths.setdefault(sheet.title, {})
            if measure:
                sheet_widths[column] = max(sheet_widths.get(column, 0), min(_display_width(value, fmt), 60))
            return cell

        def header_row(sheet: Any, row: int, labels: list[str]) -> None:
            for column, label in enumerate(labels, start=1):
                cell = put(sheet, row, column, label, font=head_font, fill=head_fill)
                cell.alignment = Alignment(wrap_text=True, vertical="center", horizontal="center")
            sheet.row_dimensions[row].height = 32

        def fit(sheet: Any, minimum: int = 8, overrides: dict[int, int] | None = None) -> None:
            for column, width in widths.get(sheet.title, {}).items():
                final = (overrides or {}).get(column, max(minimum, width + 3))
                sheet.column_dimensions[get_column_letter(column)].width = final

        def page_setup(sheet: Any, title: str) -> None:
            sheet.page_setup.orientation = "landscape"
            sheet.page_setup.paperSize = sheet.PAPERSIZE_A4
            sheet.page_setup.fitToWidth, sheet.page_setup.fitToHeight = 1, 0
            sheet.sheet_properties.pageSetUpPr.fitToPage = True
            sheet.page_margins = PageMargins(left=0.5, right=0.5, top=0.7, bottom=0.7)
            sheet.oddHeader.center.text = f"BidSentry · {title}"
            sheet.oddFooter.right.text = "Halaman &P dari &N"
            sheet.sheet_view.showGridLines = False

        # ------------------------------------------------------------------ BoQ
        boq = workbook.active
        boq.title = "BoQ"
        put(boq, 1, 1, "RINCIAN BILL OF QUANTITIES (BoQ)", font=title_font, framed=False, measure=False)
        put(boq, 2, 1, f"{audit.get('package_name') or '—'} · {audit.get('tender_id') or audit.get('audit_id') or ''}", framed=False, measure=False)
        headers = ["No", "Uraian Pekerjaan", "Volume", "Satuan", "Harga Satuan", "Jumlah Tertulis", "Jumlah Hitung", "Selisih", "Status (Excel)", "Cek Python", "HPS Satuan", "Rasio thd HPS", "Kutipan Sumber"]
        header_at = 4
        header_row(boq, header_at, headers)
        first = header_at + 1
        for offset, item in enumerate(items):
            r = first + offset
            check = line_checks[offset] if offset < len(line_checks) else {}
            mismatch = check.get("math_status") == "MATH_MISMATCH"
            fill = warn_fill if mismatch else None
            unit_price, stated, volume = float(item.unit_price_offered), float(item.total_offered), float(item.volume)
            put(boq, r, 1, offset + 1, fill=fill)
            put(boq, r, 2, item.description, fill=fill, wrap=True)
            put(boq, r, 3, volume, fmt="#,##0" if volume.is_integer() else "#,##0.00", fill=fill)
            put(boq, r, 4, item.unit, fill=fill)
            put(boq, r, 5, unit_price, fmt=IDR_FORMAT, fill=fill)
            put(boq, r, 6, stated, fmt=IDR_FORMAT, fill=fill)
            put(boq, r, 7, f"=PRODUCT(C{r},E{r})", fmt=IDR_FORMAT, fill=fill, formula=True)
            put(boq, r, 8, f"=F{r}-G{r}", fmt=IDR_FORMAT, fill=fill, formula=True)
            put(boq, r, 9, f'=IF(ABS(H{r})>1,"SELISIH","SESUAI")', fill=fill, formula=True)
            put(boq, r, 10, "SELISIH" if mismatch else "SESUAI", fill=fill)
            put(boq, r, 11, float(item.hps_unit_price) if item.hps_unit_price is not None else None, fmt=IDR_FORMAT, fill=fill)
            put(boq, r, 12, f'=IF(AND(ISNUMBER(K{r}),K{r}>0),E{r}/K{r},"")', fmt="0.0%", fill=fill, formula=True)
            put(boq, r, 13, item.source_quote or "", fill=fill, wrap=True)
            # Formula columns are as wide as the largest value they can produce.
            for column, estimate in ((7, volume * unit_price), (8, abs(stated - volume * unit_price))):
                widths["BoQ"][column] = max(widths["BoQ"].get(column, 0), _display_width(estimate, IDR_FORMAT))
            widths["BoQ"][9] = max(widths["BoQ"].get(9, 0), 8)
        last = first + max(len(items), 1) - 1
        total_row = last + 1
        if items:
            put(boq, total_row, 2, "JUMLAH", font=bold, fill=total_fill)
            for column in (1, 3, 4, 5, 9, 10, 11, 12, 13):
                put(boq, total_row, column, None, fill=total_fill)
            for column, letter in ((6, "F"), (7, "G"), (8, "H")):
                put(boq, total_row, column, f"=SUM({letter}{first}:{letter}{last})", fmt=IDR_FORMAT, font=bold, fill=total_fill, formula=True)
            grand = sum(float(item.total_offered) for item in items)
            for column in (6, 7):
                widths["BoQ"][column] = max(widths["BoQ"][column], _display_width(grand * 1.2, IDR_FORMAT))
        else:
            put(boq, first, 2, "Tidak ada baris BoQ terstruktur yang terbaca. Format yang didukung: 'Uraian | 10 unit | Rp harga satuan | Rp jumlah | Rp HPS satuan'.", wrap=True)
        fit(boq, overrides={2: min(max(widths["BoQ"].get(2, 20) + 3, 28), 48), 13: 55})
        boq.freeze_panes = boq.cell(row=first, column=3)
        boq.auto_filter.ref = f"A{header_at}:M{last}"
        page_setup(boq, "Rincian BoQ")

        # -------------------------------------------------------- Rekapitulasi
        recap = workbook.create_sheet("Rekapitulasi", 0)
        risk = audit.get("risk") or {}
        over = next((step for step in audit.get("proof_log", []) if step.get("inputs", {}).get("rule") == "FIN-OVER-BUDGET"), None)
        pagu = (over or {}).get("inputs", {}).get("pagu_idr")
        boq_stated = (over or {}).get("inputs", {}).get("total_boq_idr")
        put(recap, 1, 1, "REKAPITULASI AUDIT BoQ & DOKUMEN", font=title_font, framed=False, measure=False)
        info = [
            ("Paket", audit.get("package_name") or "—"),
            ("Kode tender", audit.get("tender_id") or "—"),
            ("ID audit BidSentry", audit.get("audit_id") or "—"),
            ("Diunduh oleh peran", ROLE_LABELS.get(role or "", role or "—")),
            ("Tanggal unduh", datetime.now().strftime("%d-%m-%Y %H:%M")),
            ("Tingkat risiko", f"{risk.get('label') or audit.get('risk_level') or '—'} (aturan {risk.get('rule_applied') or '—'})"),
            ("Verdict sistem", audit.get("verdict") or "—"),
        ]
        row = 3
        for label, value in info:
            put(recap, row, 1, label, font=bold)
            put(recap, row, 2, str(value))
            row += 1
        row += 1
        header_row(recap, row, ["Perhitungan", "Nilai", "Sumber"])
        row += 1
        boq_ref = "BoQ!"
        calc_rows: list[tuple[str, Any, str | None, str]] = [
            ("Jumlah baris BoQ", len(items), "0", "Dokumen sumber (baris berformat tabel)"),
            ("Total jumlah tertulis", f"={boq_ref}F{total_row}" if items else 0, IDR_FORMAT, "Rumus SUM lembar BoQ"),
            ("Total jumlah hitung (volume × harga)", f"={boq_ref}G{total_row}" if items else 0, IDR_FORMAT, "Rumus PRODUCT lalu SUM"),
            ("Selisih total", f"={boq_ref}H{total_row}" if items else 0, IDR_FORMAT, "Tertulis − hitung"),
            ("Baris selisih menurut Excel", f'=COUNTIF({boq_ref}I{first}:I{last},"SELISIH")' if items else 0, "0", "Rumus COUNTIF"),
            ("Baris selisih menurut Python", mismatches, "0", "bidsentry.audits.financial.audit_boq"),
            ("Pagu anggaran terbaca", pagu if pagu is not None else "tidak terbaca", IDR_FORMAT if pagu is not None else None, "Ekstraksi aturan dari Dokumen Pemilihan"),
            ("Total BoQ/HPS tertulis di dokumen", boq_stated if boq_stated is not None else "tidak terbaca", IDR_FORMAT if boq_stated is not None else None, "Ekstraksi aturan dari Dokumen Pemilihan"),
        ]
        pagu_row = row + 6
        boq_row = row + 7
        calc_rows.append(("Selisih terhadap pagu", f"=B{boq_row}-B{pagu_row}" if pagu is not None and boq_stated is not None else "—", IDR_FORMAT, "Total BoQ/HPS − pagu"))
        for label, value, fmt, source in calc_rows:
            put(recap, row, 1, label)
            put(recap, row, 2, value, fmt=fmt, font=bold, formula=isinstance(value, str) and value.startswith("="))
            if isinstance(value, str) and value.startswith("="):
                widths["Rekapitulasi"][2] = max(widths["Rekapitulasi"].get(2, 0), _display_width(max(float(pagu or 0), float(boq_stated or 0), sum(float(i.total_offered) for i in items)) * 1.2, IDR_FORMAT))
            put(recap, row, 3, source)
            row += 1
        row += 1
        header_row(recap, row, ["Status temuan", "Jumlah", "Keterangan"])
        row += 1
        findings = audit.get("findings", [])
        for code, label in STATUS_LABELS.items():
            put(recap, row, 1, label)
            put(recap, row, 2, f'=COUNTIF(Temuan!D:D,"{label}")', fmt="0", font=bold, formula=True)
            put(recap, row, 3, "Dihitung dari lembar Temuan")
            row += 1
        row += 1
        put(recap, row, 1, "Catatan", font=bold, framed=False)
        put(recap, row, 2, python_check.get("interpretation", "") + " Tingkat risiko ditentukan tabel keputusan deterministik; lihat lembar Jejak Hitungan.", wrap=True, framed=False)
        recap.row_dimensions[row].height = 48
        fit(recap, overrides={2: max(widths["Rekapitulasi"].get(2, 20) + 3, 24), 3: 44})
        recap.column_dimensions["A"].width = 38
        page_setup(recap, "Rekapitulasi Audit")

        # --------------------------------------------------------------- Temuan
        sheet = workbook.create_sheet("Temuan")
        header_row(sheet, 1, ["No", "Kode", "Ketentuan", "Status", "Keparahan", "Kutipan sumber", "Lokasi", "Rujukan kandidat (verifikasi hukum)", "Keputusan reviewer"])
        for index, finding in enumerate(findings, start=1):
            r = index + 1
            status = STATUS_LABELS.get(str(finding.get("status")), str(finding.get("status") or ""))
            fill = warn_fill if finding.get("status") == "GAP" else None
            values = [index, finding.get("id"), finding.get("clause"), status, finding.get("severity"), finding.get("requirement_evidence") or finding.get("evidence"), finding.get("source"), finding.get("legal_reference"), ""]
            for column, value in enumerate(values, start=1):
                put(sheet, r, column, value, fill=fill, wrap=column in (3, 6, 8))
        fit(sheet, overrides={3: 36, 6: 55, 8: 45, 9: 22})
        sheet.freeze_panes = "C2"
        page_setup(sheet, "Daftar Temuan")

        # ------------------------------------------------------- Jejak Hitungan
        trace = workbook.create_sheet("Jejak Hitungan")
        header_row(trace, 1, ["Langkah", "Jenis", "Judul", "Pelaksana", "Rumus / aturan", "Input", "Output"])
        for r, step in enumerate(audit.get("proof_log", []), start=2):
            values = [step.get("step_id"), step.get("kind"), step.get("title"), step.get("actor"), step.get("formula") or "",
                      json.dumps(step.get("inputs", {}), ensure_ascii=False, default=str), json.dumps(step.get("outputs", {}), ensure_ascii=False, default=str)]
            for column, value in enumerate(values, start=1):
                put(trace, r, column, value, wrap=True)
        fit(trace, overrides={3: 40, 4: 30, 5: 50, 6: 60, 7: 60})
        page_setup(trace, "Jejak Hitungan")

        workbook.active = 0
        stream = io.BytesIO()
        workbook.save(stream)
        package = (audit.get("tender_id") or audit.get("audit_id") or "audit").replace(" ", "-")[:40]
        return {
            "filename": f"bidsentry-boq-{package}.xlsx",
            "content_type": XLSX_MIME,
            "content_base64": base64.b64encode(stream.getvalue()).decode("ascii"),
            "line_items": len(items),
            "python_mismatches": mismatches,
            "calculated_subtotal_idr": float(python_check.get("calculated_line_subtotal") or 0),
        }


__all__ = ["BoQExportService"]

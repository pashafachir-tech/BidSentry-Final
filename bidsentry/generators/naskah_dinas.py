"""python-docx building blocks for Indonesian official-letter layout (tata naskah dinas).

Layout conventions used: A4, margins 2.5 cm (left 3 cm), Arial 12 pt, 1.15
spacing, justified body, letterhead with a rule beneath, a Nomor / Sifat /
Lampiran / Hal block, addressee, numbered body, signature block, and a page
number footer. Every page carries a "DRAF" header because BidSentry output
must be reviewed and signed by an authorised person before use.
"""

from __future__ import annotations

import io
from collections.abc import Sequence
from typing import Any

from bidsentry.generators._document_support import require_docx

FONT = "Arial"
DRAFT_HEADER = "DRAF — dihasilkan BidSentry, wajib ditinjau dan disahkan pejabat berwenang sebelum digunakan"
REGULATION_BASIS = (
    "Peraturan Presiden Nomor 16 Tahun 2018 tentang Pengadaan Barang/Jasa Pemerintah sebagaimana telah diubah "
    "dengan Peraturan Presiden Nomor 12 Tahun 2021 (dan perubahan berikutnya yang berlaku pada tanggal paket)"
)


def _oxml():
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    return OxmlElement, qn


class OfficialDocument:
    """Thin wrapper that applies the house style consistently."""

    def __init__(self) -> None:
        Document = require_docx()
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        from docx.shared import Cm, Pt

        self._Pt, self._Cm, self._align = Pt, Cm, WD_ALIGN_PARAGRAPH
        self.doc = Document()
        section = self.doc.sections[0]
        section.page_height, section.page_width = Cm(29.7), Cm(21.0)
        section.top_margin = section.bottom_margin = Cm(2.5)
        section.left_margin, section.right_margin = Cm(3.0), Cm(2.5)
        normal = self.doc.styles["Normal"]
        normal.font.name, normal.font.size = FONT, Pt(12)
        _, qn = _oxml()
        normal.element.rPr.rFonts.set(qn("w:eastAsia"), FONT)
        normal.paragraph_format.space_after = Pt(4)
        normal.paragraph_format.line_spacing = 1.15
        header = section.header.paragraphs[0]
        header.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        run = header.add_run(DRAFT_HEADER)
        run.font.size, run.italic = Pt(8), True
        self._page_number_footer(section)

    # -------------------------------------------------------------- structure
    def letterhead(self, lines: Sequence[str], subtitle: Sequence[str] = ()) -> None:
        for index, text in enumerate(lines):
            paragraph = self.doc.add_paragraph()
            paragraph.alignment = self._align.CENTER
            paragraph.paragraph_format.space_after = self._Pt(0)
            run = paragraph.add_run(text.upper())
            run.bold, run.font.size = True, self._Pt(14 if index == 0 else 12)
        for text in subtitle:
            paragraph = self.doc.add_paragraph()
            paragraph.alignment = self._align.CENTER
            paragraph.paragraph_format.space_after = self._Pt(0)
            paragraph.add_run(text).font.size = self._Pt(10)
        rule = self.doc.add_paragraph()
        self._bottom_border(rule, size=18)

    def title(self, text: str, number_line: str | None = None) -> None:
        paragraph = self.doc.add_paragraph()
        paragraph.alignment = self._align.CENTER
        paragraph.paragraph_format.space_before = self._Pt(10)
        paragraph.paragraph_format.space_after = self._Pt(0)
        run = paragraph.add_run(text.upper())
        run.bold, run.underline = True, True
        if number_line:
            number = self.doc.add_paragraph(number_line)
            number.alignment = self._align.CENTER

    def letter_meta(self, rows: Sequence[tuple[str, str]], place_date: str) -> None:
        table = self.doc.add_table(rows=0, cols=4)
        table.autofit = True
        for index, (label, value) in enumerate(rows):
            cells = table.add_row().cells
            cells[0].text, cells[1].text, cells[2].text = label, ":", value
            cells[3].text = place_date if index == 0 else ""
        self._widths(table, (2.2, 0.4, 7.4, 5.5))
        self._no_borders(table)
        self.doc.add_paragraph()

    def addressee(self, lines: Sequence[str]) -> None:
        for index, line in enumerate(lines):
            paragraph = self.doc.add_paragraph(("Yth. " if index == 0 else "") + line)
            paragraph.paragraph_format.space_after = self._Pt(0)
        self.doc.add_paragraph()

    def body(self, text: str, *, indent_first: bool = True, bold: bool = False) -> Any:
        paragraph = self.doc.add_paragraph()
        paragraph.alignment = self._align.JUSTIFY
        if indent_first:
            paragraph.paragraph_format.first_line_indent = self._Cm(1.25)
        paragraph.add_run(text).bold = bold
        return paragraph

    def heading(self, text: str) -> None:
        paragraph = self.doc.add_paragraph()
        paragraph.paragraph_format.space_before = self._Pt(8)
        run = paragraph.add_run(text)
        run.bold = True

    def numbered(self, number: str, text: str, *, level: int = 0, bold: bool = False) -> Any:
        paragraph = self.doc.add_paragraph()
        paragraph.alignment = self._align.JUSTIFY
        paragraph.paragraph_format.left_indent = self._Cm(0.75 + 0.75 * level)
        paragraph.paragraph_format.first_line_indent = self._Cm(-0.75)
        paragraph.add_run(f"{number}\t")
        paragraph.add_run(text).bold = bold
        return paragraph

    def quote(self, text: str, source: str | None = None) -> None:
        paragraph = self.doc.add_paragraph()
        paragraph.alignment = self._align.JUSTIFY
        paragraph.paragraph_format.left_indent = self._Cm(1.5)
        paragraph.paragraph_format.right_indent = self._Cm(1.0)
        run = paragraph.add_run(f"“{text}”")
        run.italic = True
        if source:
            cite = paragraph.add_run(f"  ({source})")
            cite.font.size = self._Pt(10)

    def label_value(self, label: str, value: str, *, level: int = 1) -> None:
        paragraph = self.doc.add_paragraph()
        paragraph.alignment = self._align.JUSTIFY
        paragraph.paragraph_format.left_indent = self._Cm(0.75 * (level + 1))
        paragraph.add_run(f"{label}: ").bold = True
        paragraph.add_run(value)

    def grid(self, headers: Sequence[str], rows: Sequence[Sequence[str]], widths_cm: Sequence[float]) -> None:
        table = self.doc.add_table(rows=1, cols=len(headers))
        table.style = "Table Grid"
        for cell, label in zip(table.rows[0].cells, headers):
            cell.text = ""
            run = cell.paragraphs[0].add_run(label)
            run.bold, run.font.size = True, self._Pt(10)
            self._shade(cell, "E7ECF3")
        for row in rows:
            cells = table.add_row().cells
            for cell, value in zip(cells, row):
                cell.text = ""
                cell.paragraphs[0].add_run(str(value)).font.size = self._Pt(10)
        self._widths(table, widths_cm)
        self._repeat_header(table)
        self.doc.add_paragraph()

    def signature(self, place_date: str, closing: str, name: str, position: str, *, stamp_note: str | None = None) -> None:
        table = self.doc.add_table(rows=1, cols=2)
        self._no_borders(table)
        right = table.rows[0].cells[1]
        right.text = ""
        lines = [place_date, closing, "", "", stamp_note or "", "", name, position]
        for index, line in enumerate(lines):
            paragraph = right.paragraphs[0] if index == 0 else right.add_paragraph()
            paragraph.alignment = self._align.CENTER
            paragraph.paragraph_format.space_after = self._Pt(0)
            run = paragraph.add_run(line)
            if index == 6:
                run.bold, run.underline = True, True
            if stamp_note and index == 4:
                run.font.size, run.italic = self._Pt(9), True
        self._widths(table, (7.75, 7.75))

    def committee_signatures(self, members: Sequence[tuple[str, str]]) -> None:
        from docx.enum.table import WD_ROW_HEIGHT_RULE

        self.grid(("No.", "Nama", "Jabatan dalam Pokja", "Tanda Tangan"), [(str(i), name, role, "") for i, (name, role) in enumerate(members, 1)], (1.2, 5.5, 4.8, 4.0))
        table = self.doc.tables[-1]
        for row in list(table.rows)[1:]:
            row.height, row.height_rule = self._Cm(1.4), WD_ROW_HEIGHT_RULE.AT_LEAST

    def note(self, text: str) -> None:
        paragraph = self.doc.add_paragraph()
        paragraph.alignment = self._align.JUSTIFY
        run = paragraph.add_run(text)
        run.font.size, run.italic = self._Pt(9), True

    def to_bytes(self) -> bytes:
        stream = io.BytesIO()
        self.doc.save(stream)
        return stream.getvalue()

    # ------------------------------------------------------------ low level
    def _page_number_footer(self, section: Any) -> None:
        OxmlElement, qn = _oxml()
        paragraph = section.footer.paragraphs[0]
        paragraph.alignment = self._align.CENTER
        run = paragraph.add_run()
        run.font.size = self._Pt(9)
        for kind, text in (("begin", None), (None, "PAGE"), ("end", None)):
            if kind:
                element = OxmlElement("w:fldChar")
                element.set(qn("w:fldCharType"), kind)
            else:
                element = OxmlElement("w:instrText")
                element.set(qn("xml:space"), "preserve")
                element.text = text
            run._r.append(element)

    def _bottom_border(self, paragraph: Any, size: int = 12) -> None:
        OxmlElement, qn = _oxml()
        p_pr = paragraph._p.get_or_add_pPr()
        borders = OxmlElement("w:pBdr")
        bottom = OxmlElement("w:bottom")
        for key, value in (("w:val", "double"), ("w:sz", str(size)), ("w:space", "1"), ("w:color", "000000")):
            bottom.set(qn(key), value)
        borders.append(bottom)
        p_pr.append(borders)

    def _no_borders(self, table: Any) -> None:
        OxmlElement, qn = _oxml()
        tbl_pr = table._tbl.tblPr
        borders = OxmlElement("w:tblBorders")
        for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
            element = OxmlElement(f"w:{edge}")
            element.set(qn("w:val"), "nil")
            borders.append(element)
        tbl_pr.append(borders)

    def _shade(self, cell: Any, fill: str) -> None:
        OxmlElement, qn = _oxml()
        shading = OxmlElement("w:shd")
        shading.set(qn("w:val"), "clear")
        shading.set(qn("w:color"), "auto")
        shading.set(qn("w:fill"), fill)
        cell._tc.get_or_add_tcPr().append(shading)

    def _repeat_header(self, table: Any) -> None:
        OxmlElement, qn = _oxml()
        tr_pr = table.rows[0]._tr.get_or_add_trPr()
        header = OxmlElement("w:tblHeader")
        header.set(qn("w:val"), "true")
        tr_pr.append(header)

    def _widths(self, table: Any, widths_cm: Sequence[float]) -> None:
        for row in table.rows:
            for cell, width in zip(row.cells, widths_cm):
                cell.width = self._Cm(width)


__all__ = ["OfficialDocument", "REGULATION_BASIS"]

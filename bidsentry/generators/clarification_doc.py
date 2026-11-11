"""Generate formal draft clarification requests from evidence-backed findings."""

from __future__ import annotations

import io
from html import escape
from collections.abc import Sequence
from typing import Any

from bidsentry.generators._document_support import clean_cell, render_pdf, require_docx


def build_clarification_markdown(
    tender_id: str,
    vendor_name: str,
    anomalies: Sequence[dict[str, Any]],
) -> str:
    """Build a formal, editable Markdown technical clarification draft."""

    lines = [
        "# SURAT PERMINTAAN KLARIFIKASI TEKNIS/HARGA",
        "",
        f"**Paket/Tender:** {_markdown_cell(tender_id)}  ",
        f"**Peserta:** {_markdown_cell(vendor_name)}  ",
        "**Nomor:** [diisi oleh pejabat berwenang]  ",
        "**Tanggal:** [diisi]",
        "",
        "Kepada Yth.  ",
        "Pimpinan Penyedia  ",
        "Di tempat",
        "",
        "> Berdasarkan telaah awal atas dokumen penawaran, kami meminta penjelasan atas butir berikut. Draf ini harus ditinjau dan disahkan Pokja Pemilihan; klarifikasi tidak mengubah kriteria atau substansi penawaran.",
        "",
        "| No./Temuan | Halaman & bukti | Hal yang diklarifikasi | Jawaban peserta |",
        "| --- | --- | --- | --- |",
    ]
    for index, item in enumerate(anomalies, 1):
        kind = item.get("anomaly_type") or item.get("signal") or item.get("type") or "Temuan"
        quote = item.get("source_quote") or item.get("verbatim_quote") or "Kutipan sumber belum diverifikasi."
        page_ref = item.get("page_ref") or "Tidak tersedia"
        prompt = item.get("clarification_question") or item.get("description") or item.get("details") or "Mohon berikan penjelasan dan bukti pendukung."
        lines.append(
            f"| {index}. {_markdown_cell(kind)} | {_markdown_cell(page_ref)} — {_markdown_cell(quote)} | {_markdown_cell(prompt)} | [Diisi peserta] |"
        )
    lines.extend([
        "",
        "**Dokumen/bukti pendukung yang disampaikan peserta:** [Nama dokumen, tanggal, dan halaman]",
        "",
        "**Batas waktu dan kanal penyampaian:** [diisi sesuai jadwal dan Dokumen Pemilihan]",
        "",
        "Hormat kami,  ",
        "Pokja Pemilihan  ",
        "[Nama dan tanda tangan pejabat berwenang]",
        "",
    ])
    return "\n".join(lines)


def build_clarification_html(
    tender_id: str,
    vendor_name: str,
    anomalies: Sequence[dict[str, Any]],
) -> str:
    """Build an HTML clarification draft with escaped source evidence."""

    rows: list[str] = []
    for index, item in enumerate(anomalies, 1):
        kind = item.get("anomaly_type") or item.get("signal") or item.get("type") or "Temuan"
        quote = item.get("source_quote") or item.get("verbatim_quote") or "Kutipan sumber belum diverifikasi."
        page_ref = item.get("page_ref") or "Tidak tersedia"
        prompt = item.get("clarification_question") or item.get("description") or item.get("details") or "Mohon berikan penjelasan dan bukti pendukung."
        rows.append(
            "<tr>"
            f"<td>{index}. {escape(clean_cell(kind, 120))}</td>"
            f"<td>{escape(clean_cell(page_ref, 100))}<br>{escape(clean_cell(quote, 1000))}</td>"
            f"<td>{escape(clean_cell(prompt, 800))}</td><td>[Diisi peserta]</td>"
            "</tr>"
        )
    return (
        "<!doctype html><html lang=\"id\"><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\"><title>Permintaan Klarifikasi</title></head><body>"
        "<h1>SURAT PERMINTAAN KLARIFIKASI TEKNIS/HARGA</h1>"
        f"<p><strong>Paket/Tender:</strong> {escape(clean_cell(tender_id, 200))}<br>"
        f"<strong>Peserta:</strong> {escape(clean_cell(vendor_name, 240))}<br>"
        "<strong>Nomor:</strong> [diisi oleh pejabat berwenang] &nbsp; <strong>Tanggal:</strong> [diisi]</p>"
        "<p>Kepada Yth.<br>Pimpinan Penyedia<br>Di tempat</p>"
        "<p>Berdasarkan telaah awal atas dokumen penawaran, kami meminta penjelasan atas butir berikut. Draf ini harus ditinjau dan disahkan Pokja Pemilihan; klarifikasi tidak mengubah kriteria atau substansi penawaran.</p>"
        "<table border=\"1\" cellspacing=\"0\" cellpadding=\"6\"><thead><tr><th>No./Temuan</th><th>Halaman &amp; bukti</th><th>Hal yang diklarifikasi</th><th>Jawaban peserta</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
        "<p><strong>Dokumen/bukti pendukung:</strong> [Nama dokumen, tanggal, dan halaman]</p>"
        "<p><strong>Batas waktu dan kanal:</strong> [diisi sesuai jadwal dan Dokumen Pemilihan]</p>"
        "<p>Hormat kami,<br>Pokja Pemilihan<br><br>[Nama dan tanda tangan pejabat berwenang]</p>"
        "</body></html>"
    )


def build_clarification_docx(
    tender_id: str,
    vendor_name: str,
    anomalies: Sequence[dict[str, Any]],
) -> bytes:
    Document = require_docx()
    document = Document()
    document.add_heading("SURAT PERMINTAAN KLARIFIKASI TEKNIS/HARGA", 0)
    document.add_paragraph(f"Paket/Tender: {clean_cell(tender_id, 200)}")
    document.add_paragraph(f"Peserta: {clean_cell(vendor_name, 240)}")
    document.add_paragraph("Nomor: [diisi oleh pejabat berwenang]    Tanggal: [diisi]")
    document.add_paragraph("Kepada Yth.\nPimpinan Penyedia\nDi tempat")
    document.add_paragraph(
        "Berdasarkan telaah awal atas dokumen penawaran, kami meminta penjelasan atas butir berikut. "
        "Permintaan ini merupakan draf untuk ditinjau dan disahkan oleh Pokja Pemilihan; bukan perubahan "
        "kriteria atau kesempatan untuk mengubah substansi penawaran."
    )
    table = document.add_table(rows=1, cols=4)
    table.style = "Table Grid"
    for cell, label in zip(table.rows[0].cells, ("No./Temuan", "Halaman & bukti", "Hal yang diklarifikasi", "Jawaban peserta")):
        cell.text = label
    for index, item in enumerate(anomalies, 1):
        row = table.add_row().cells
        kind = clean_cell(item.get("anomaly_type") or item.get("signal") or item.get("type") or "Temuan", 120)
        quote = clean_cell(item.get("source_quote") or item.get("verbatim_quote") or "Kutipan sumber belum diverifikasi.", 1000)
        page_ref = clean_cell(item.get("page_ref") or "Tidak tersedia", 100)
        prompt = clean_cell(item.get("clarification_question") or item.get("description") or item.get("details") or "Mohon berikan penjelasan dan bukti pendukung.", 800)
        row[0].text = f"{index}. {kind}"
        row[1].text = f"{page_ref}\n{quote}"
        row[2].text = prompt
        row[3].text = "[Diisi peserta]"
    document.add_paragraph("Dokumen/bukti pendukung yang disampaikan peserta:")
    document.add_paragraph("[Nama dokumen, tanggal, dan halaman]")
    document.add_paragraph("Batas waktu dan kanal penyampaian: [diisi sesuai jadwal dan Dokumen Pemilihan].")
    document.add_paragraph("Hormat kami,\nPokja Pemilihan\n\n[Nama dan tanda tangan pejabat berwenang]")
    stream = io.BytesIO()
    document.save(stream)
    return stream.getvalue()


def build_clarification_pdf(tender_id: str, vendor_name: str, anomalies: Sequence[dict[str, Any]]) -> bytes:
    rows = [["No./Temuan", "Halaman & bukti", "Hal yang diklarifikasi", "Jawaban peserta"]]
    for index, item in enumerate(anomalies, 1):
        kind = clean_cell(item.get("anomaly_type") or item.get("signal") or item.get("type") or "Temuan", 120)
        quote = clean_cell(item.get("source_quote") or item.get("verbatim_quote") or "Kutipan sumber belum diverifikasi.", 1000)
        page_ref = clean_cell(item.get("page_ref") or "Tidak tersedia", 100)
        prompt = clean_cell(item.get("clarification_question") or item.get("description") or item.get("details") or "Mohon berikan penjelasan dan bukti pendukung.", 800)
        rows.append([f"{index}. {kind}", f"{page_ref}\n{quote}", prompt, "[Diisi peserta]"])
    return render_pdf(
        "SURAT PERMINTAAN KLARIFIKASI TEKNIS/HARGA",
        [f"Paket/Tender: {clean_cell(tender_id, 200)}", f"Peserta: {clean_cell(vendor_name, 240)}", "Nomor: [diisi oleh pejabat berwenang]    Tanggal: [diisi]", "Draf permintaan klarifikasi untuk ditinjau dan disahkan Pokja Pemilihan. Klarifikasi tidak mengubah kriteria atau substansi penawaran."],
        [rows],
    )


def _markdown_cell(value: Any) -> str:
    text = clean_cell(value, 1000)
    return text.replace("\\", "\\\\").replace("|", "\\|").replace("`", "\\`").replace("\n", " ")

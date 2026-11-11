"""Generate a draft Berita Acara Hasil Evaluasi (BAHE) with evidence rows.

Rows come from :func:`normalize_finding`, so engine findings (``clause`` /
``requirement_evidence``) and forensic anomalies (``anomaly_type`` /
``source_quote``) both render with their real title, quote and status.
"""

from __future__ import annotations

from collections.abc import Sequence
from html import escape
from typing import Any

from bidsentry.generators._document_support import clean_cell, normalize_finding, render_pdf
from bidsentry.generators.naskah_dinas import REGULATION_BASIS, OfficialDocument
from bidsentry.generators.sanggahan_builder import STATUS_PHRASE, citations_for

_DISCLAIMER = (
    "Draf ini menyajikan catatan pemeriksaan berbasis bukti untuk verifikasi dan pengesahan manusia. "
    "Sinyal otomatis bukan keputusan lulus/gugur, kesimpulan pelanggaran, atau penetapan persekongkolan."
)
_HEADERS = ("No.", "Kode / temuan", "Status", "Bukti / lokasi", "Catatan pemeriksaan", "Keputusan Pokja")


def _contextual_citations(findings: Sequence[dict[str, Any]]) -> list[dict[str, str]]:
    """Unique citations for findings that still need Pokja attention, in first-seen order."""
    seen: set[str] = set()
    output: list[dict[str, str]] = []
    for item in findings:
        if not isinstance(item, dict) or item.get("status") not in {"GAP", "EXPIRING", "REVIEW"}:
            continue
        for citation in citations_for(item):
            if citation.get("formal") and citation["formal"] not in seen and citation.get("status") != "PERLU_VERIFIKASI_HUKUM":
                seen.add(citation["formal"])
                output.append(citation)
    return output


def _rows(findings: Sequence[dict[str, Any]]) -> list[dict[str, str]]:
    return [normalize_finding(item) for item in findings if isinstance(item, dict)]


def _risk_line(risk: dict[str, Any] | None) -> str | None:
    if not risk or not risk.get("label"):
        return None
    return f"Tingkat risiko sistem: {clean_cell(risk.get('label'), 40)} (aturan {clean_cell(risk.get('rule_applied'), 8)}). {clean_cell(risk.get('rationale'), 400)}"


def _meta_lines(tender_id: str, vendor_name: str, meta: dict[str, Any] | None) -> list[str]:
    meta = meta or {}
    lines = [f"Paket/Tender: {clean_cell(meta.get('package_name') or tender_id, 240)}"]
    if meta.get("package_name") and tender_id:
        lines.append(f"Kode tender: {clean_cell(tender_id, 200)}")
    if meta.get("pokja_name"):
        lines.append(f"Pokja: {clean_cell(meta['pokja_name'], 240)}")
    lines.append(f"Peserta: {clean_cell(vendor_name, 240)}")
    if meta.get("audit_id"):
        lines.append(f"ID audit BidSentry: {clean_cell(meta['audit_id'], 80)}")
    lines.append("Nomor: [diisi]    Tanggal: [diisi]")
    return lines


def build_minutes_markdown(
    tender_id: str,
    vendor_name: str,
    findings: Sequence[dict[str, Any]],
    legal_mappings: Sequence[dict[str, Any]] = (),
    *,
    risk: dict[str, Any] | None = None,
    meta: dict[str, Any] | None = None,
) -> str:
    """Build a portable Markdown BAHE review draft."""
    lines = ["# BERITA ACARA HASIL EVALUASI (DRAF)", ""]
    lines += [f"**{line.split(':', 1)[0]}:**{line.split(':', 1)[1]}  " for line in _meta_lines(tender_id, vendor_name, meta)]
    lines += ["", f"> {_DISCLAIMER}", ""]
    if (risk_text := _risk_line(risk)):
        lines += [f"**{risk_text}**", ""]
    lines += ["| " + " | ".join(_HEADERS) + " |", "| " + " | ".join("---" for _ in _HEADERS) + " |"]
    for index, row in enumerate(_rows(findings), 1):
        lines.append(
            f"| {index} | {_markdown_cell(row['code'] + ' — ' + row['title'])} | {_markdown_cell(row['status_label'])} | "
            f"{_markdown_cell(row['locator'] + ' — ' + row['quote'])} | {_markdown_cell(row['note'])} | {_markdown_cell(row['reviewer'])} |"
        )
    references = [row for row in _rows(findings) if row["legal_reference"]]
    if references or legal_mappings:
        lines += ["", "## Rujukan hukum kandidat (perlu verifikasi hukum)", ""]
        for row in references:
            lines.append(f"- **{_markdown_cell(row['code'])}:** {_markdown_cell(row['legal_reference'])}")
        for item in legal_mappings:
            refs = item.get("candidate_references") or []
            titles = "; ".join(str(ref.get("title") or "") for ref in refs) or "Belum dipetakan"
            lines.append(f"- **{_markdown_cell(item.get('signal') or 'Temuan')}:** {_markdown_cell(titles)}")
            for question in item.get("review_questions", [])[:4]:
                lines.append(f"  - {_markdown_cell(question)}")
    lines += [
        "", "## Catatan dan kesimpulan Pokja", "", "[Diisi setelah verifikasi]", "",
        "## Anggota Pokja Pemilihan", "", "1. [Nama / tanda tangan]", "2. [Nama / tanda tangan]", "3. [Nama / tanda tangan]", "",
    ]
    return "\n".join(lines)


def build_minutes_html(
    tender_id: str,
    vendor_name: str,
    findings: Sequence[dict[str, Any]],
    legal_mappings: Sequence[dict[str, Any]] = (),
    *,
    risk: dict[str, Any] | None = None,
    meta: dict[str, Any] | None = None,
) -> str:
    """Build an HTML BAHE draft with escaped evidence values."""
    body_rows = "".join(
        "<tr>"
        f"<td>{index}</td><td><strong>{escape(row['code'])}</strong><br>{escape(row['title'])}</td><td>{escape(row['status_label'])}</td>"
        f"<td>{escape(row['locator'])}<br>{escape(row['quote'])}</td><td>{escape(row['note'])}</td><td>{escape(row['reviewer'])}</td>"
        "</tr>"
        for index, row in enumerate(_rows(findings), 1)
    )
    references = "".join(f"<li><strong>{escape(row['code'])}:</strong> {escape(row['legal_reference'])}</li>" for row in _rows(findings) if row["legal_reference"])
    for item in legal_mappings:
        refs = item.get("candidate_references") or []
        title_text = "; ".join(clean_cell(ref.get("title"), 220) for ref in refs) or "Belum dipetakan"
        questions = "".join(f"<li>{escape(clean_cell(question, 500))}</li>" for question in item.get("review_questions", [])[:4])
        references += f"<li><strong>{escape(clean_cell(item.get('signal') or 'Temuan', 120))}:</strong> {escape(title_text)}<ul>{questions}</ul></li>"
    meta_html = "<br>".join(escape(line) for line in _meta_lines(tender_id, vendor_name, meta))
    risk_html = f"<p><strong>{escape(text)}</strong></p>" if (text := _risk_line(risk)) else ""
    return (
        "<!doctype html><html lang=\"id\"><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\"><title>BAHE (Draf)</title></head><body>"
        f"<h1>BERITA ACARA HASIL EVALUASI (DRAF)</h1><p>{meta_html}</p><p>{escape(_DISCLAIMER)}</p>{risk_html}"
        "<table border=\"1\" cellspacing=\"0\" cellpadding=\"6\"><thead><tr>" + "".join(f"<th>{escape(h)}</th>" for h in _HEADERS) + "</tr></thead>"
        f"<tbody>{body_rows}</tbody></table>"
        + (f"<h2>Rujukan hukum kandidat (perlu verifikasi hukum)</h2><ul>{references}</ul>" if references else "")
        + "<h2>Catatan dan kesimpulan Pokja</h2><p>[Diisi setelah verifikasi]</p>"
        "<h2>Anggota Pokja Pemilihan</h2><ol><li>[Nama / tanda tangan]</li><li>[Nama / tanda tangan]</li><li>[Nama / tanda tangan]</li></ol>"
        "</body></html>"
    )


def build_minutes_docx(
    tender_id: str,
    vendor_name: str,
    findings: Sequence[dict[str, Any]],
    legal_mappings: Sequence[dict[str, Any]] = (),
    *,
    risk: dict[str, Any] | None = None,
    meta: dict[str, Any] | None = None,
) -> bytes:
    """Berita Acara Hasil Evaluasi in official-letter layout, ready for Pokja signatures."""
    meta = meta or {}
    rows = _rows(findings)
    doc = OfficialDocument()
    doc.letterhead(
        ["[KEMENTERIAN / LEMBAGA / PEMERINTAH DAERAH]", "UNIT KERJA PENGADAAN BARANG/JASA", f"KELOMPOK KERJA PEMILIHAN {clean_cell(meta.get('pokja_name') or '', 120).upper()}".strip()],
        ["[Alamat kantor] · Telp. [nomor] · Laman [alamat LPSE]"],
    )
    doc.title("Berita Acara Hasil Evaluasi", "Nomor: [nomor BA]")
    package = clean_cell(meta.get("package_name") or tender_id, 240)
    doc.body(
        "Pada hari ini [hari], tanggal [tanggal] bulan [bulan] tahun [tahun], bertempat di [tempat], Kelompok Kerja Pemilihan "
        f"telah melaksanakan evaluasi dokumen untuk paket {package} (kode tender {clean_cell(tender_id, 120)}) dengan peserta {clean_cell(vendor_name, 240)}."
    )
    doc.heading("A. DASAR")
    doc.numbered("1.", REGULATION_BASIS + ".")
    doc.numbered("2.", "Peraturan Lembaga Kebijakan Pengadaan Barang/Jasa Pemerintah tentang pedoman pelaksanaan pengadaan melalui penyedia yang berlaku, serta Dokumen Pemilihan paket beserta adendumnya.")
    contextual = _contextual_citations(findings)
    for number, citation in enumerate(contextual, start=3):
        doc.numbered(f"{number}.", f"{citation['formal']}, yang pada pokoknya mengatur bahwa {citation['substance']} [{STATUS_PHRASE.get(citation['status'], 'wajib diverifikasi ahli hukum')}].")
    doc.heading("B. HASIL PEMERIKSAAN BERBANTU SISTEM")
    if (risk_text := _risk_line(risk)):
        doc.body(risk_text, indent_first=False, bold=True)
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["status_label"]] = counts.get(row["status_label"], 0) + 1
    if counts:
        doc.body("Ringkasan status: " + "; ".join(f"{label} {count}" for label, count in counts.items()) + ".", indent_first=False)
    doc.grid(
        ("No.", "Kode / ketentuan", "Status", "Bukti dan lokasi", "Keputusan Pokja"),
        [(str(i), f"{r['code']}\n{r['title']}", r["status_label"], f"{r['quote']}\n({r['locator']})", r["reviewer"] if r["reviewer"] != "[Keputusan reviewer]" else "") for i, r in enumerate(rows, 1)]
        or [("—", "Tidak ada temuan", "—", "—", "")],
        (1.0, 4.0, 2.2, 6.0, 2.3),
    )
    references = [item for item in findings if isinstance(item, dict) and item.get("status") in {"GAP", "EXPIRING", "REVIEW"} and citations_for(item)]
    if references or legal_mappings:
        doc.heading("C. DASAR HUKUM PER TEMUAN (STATUS VERIFIKASI DICANTUMKAN)")
        for index, item in enumerate(references, 1):
            formal = "; ".join(f"{c.get('formal', '')} [{STATUS_PHRASE.get(c.get('status', ''), 'wajib diverifikasi ahli hukum')}]" for c in citations_for(item))
            doc.numbered(f"{index}.", f"{clean_cell(item.get('id'), 80)}: {formal}")
        for item in legal_mappings:
            refs = item.get("candidate_references") or []
            names = "; ".join(clean_cell(ref.get("title"), 220) for ref in refs) or "Belum dipetakan"
            doc.numbered("•", f"{clean_cell(item.get('signal'), 120)}: {names}")
    doc.heading("D. KESIMPULAN")
    doc.body("[Diisi Pokja Pemilihan setelah memverifikasi setiap kutipan terhadap dokumen asli. Hasil sistem bukan keputusan lulus/gugur dan tidak menggantikan pertimbangan Pokja.]")
    doc.body("Demikian Berita Acara ini dibuat dengan sebenarnya untuk dipergunakan sebagaimana mestinya.")
    doc.heading("KELOMPOK KERJA PEMILIHAN")
    doc.committee_signatures([("[Nama, NIP]", "Ketua"), ("[Nama, NIP]", "Sekretaris"), ("[Nama, NIP]", "Anggota")])
    if meta.get("audit_id"):
        doc.note(f"Referensi jejak audit BidSentry: {meta['audit_id']}. Rincian ekstraksi, kalkulasi, dan aturan keputusan dapat ditelusuri pada aplikasi.")
    return doc.to_bytes()


def build_minutes_pdf(
    tender_id: str,
    vendor_name: str,
    findings: Sequence[dict[str, Any]],
    legal_mappings: Sequence[dict[str, Any]] = (),
    *,
    risk: dict[str, Any] | None = None,
    meta: dict[str, Any] | None = None,
) -> bytes:
    rows = [list(_HEADERS)]
    for index, row in enumerate(_rows(findings), 1):
        rows.append([str(index), f"{row['code']}\n{row['title']}", row["status_label"], f"{row['locator']}\n{row['quote']}", row["note"], row["reviewer"]])
    paragraphs = [*_meta_lines(tender_id, vendor_name, meta), _DISCLAIMER]
    if (risk_text := _risk_line(risk)):
        paragraphs.append(risk_text)
    paragraphs += [
        "Rujukan kandidat (perlu verifikasi hukum): " + ("; ".join(f"{row['code']}: {row['legal_reference']}" for row in _rows(findings) if row["legal_reference"]) or "Belum dipetakan."),
        "Catatan dan kesimpulan Pokja: [diisi setelah verifikasi]",
        "Anggota Pokja Pemilihan: [Nama / tanda tangan]",
    ]
    return render_pdf("BERITA ACARA HASIL EVALUASI (DRAF)", paragraphs, [rows])


def _markdown_cell(value: Any) -> str:
    text = clean_cell(value, 1000)
    return text.replace("\\", "\\\\").replace("|", "\\|").replace("`", "\\`").replace("\n", " ")

"""Build an editable bidder objection draft from verified source quotations."""

from __future__ import annotations

from html import escape
from typing import Any

from bidsentry.evaluators.rule_catalog import get_rule
from bidsentry.generators._document_support import clean_cell, render_pdf
from bidsentry.generators.naskah_dinas import REGULATION_BASIS, OfficialDocument


_EXCLUDED_REVIEW_OUTCOMES = {"NOT_SUPPORTED", "IGNORED"}
# Fallback for findings whose code is not in the rule catalog (e.g. hand-written rows).
_TENDER_CATEGORIES = (
    "spesifikasi", "jadwal", "integritas", "keuangan", "kontrak",
    "diskrimin", "persaingan", "kolusi", "anti-kompetitif", "administrasi", "kualifikasi", "adendum",
)


def _is_tender_document_issue(item: dict[str, Any]) -> bool:
    """Only gaps in the tender document can be objected to; bidder credentials cannot."""
    if item.get("party"):
        return item.get("party") == "tender_document"
    try:
        return get_rule(str(item.get("id", ""))).party == "tender_document"
    except KeyError:
        category = str(item.get("issue_type", item.get("category", ""))).casefold()
        return any(word in category for word in _TENDER_CATEGORIES)


def _quote_of(item: dict[str, Any]) -> str | None:
    quote = item.get("verbatim_quote") or item.get("source_quote")
    if not quote:
        req = item.get("requirement_evidence")
        if isinstance(req, (list, tuple)) and len(req) >= 2 and isinstance(req[1], str):
            quote = req[1]
        elif isinstance(req, str):
            quote = req
    if not quote:
        ev = item.get("evidence")
        if isinstance(ev, (list, tuple)) and len(ev) >= 2 and isinstance(ev[1], str):
            quote = ev[1]
        elif isinstance(ev, str):
            quote = ev
    return quote if isinstance(quote, str) and quote.strip() else None


def _eligible(items: list[dict[str, Any]], source_text: str) -> list[dict[str, Any]]:
    """Keep confirmed tender-document gaps whose quote is verbatim in the source.

    Excluded: findings that are not GAP (TERPENUHI/REVIEW/EXPIRING/SUPERSEDED),
    the bidder's own credential findings, findings a reviewer marked
    NOT_SUPPORTED, and any finding whose quote is not in the source text.
    """
    output: list[dict[str, Any]] = []
    clean_source = " ".join(source_text.split()).casefold()
    for item in items:
        if not isinstance(item, dict):
            continue
        status = str(item.get("status") or "GAP").upper()
        if status != "GAP":
            continue
        if str(item.get("reviewer_outcome") or item.get("reviewer_status") or "").upper() in _EXCLUDED_REVIEW_OUTCOMES:
            continue
        if not _is_tender_document_issue(item):
            continue
        quote = _quote_of(item)
        if quote and (" ".join(quote.split()).casefold() in clean_source or quote in source_text):
            output.append({**item, "verbatim_quote": quote})
    return output


# Peraturan LKPP 12/2021: only bidders who submitted an offer may object, through SPSE,
# within 5 calendar days after the winner is announced. Before that the channel is
# the Pemberian Penjelasan stage, so a pre-bid letter must not be called a sanggah.
LETTER_STAGES: dict[str, dict[str, str]] = {
    "pre_bid": {
        "title": "SURAT PERMOHONAN PENJELASAN",
        "subject": "Permohonan Penjelasan atas Dokumen Pemilihan",
        "phrase": "permohonan penjelasan",
        "section": "POKOK PERMOHONAN PENJELASAN",
        "quote_label": "Ketentuan yang dimohonkan penjelasan (kutipan persis)",
        "filename": "draf-permohonan-penjelasan",
        "procedure": "Sampaikan melalui fitur Pemberian Penjelasan pada SPSE sebelum batas akhir tahap tersebut. Surat ini bukan sanggah; sanggah baru tersedia setelah pengumuman pemenang.",
    },
    "post_award": {
        "title": "SURAT SANGGAHAN",
        "subject": "Sanggahan atas Penetapan Pemenang",
        "phrase": "sanggahan",
        "section": "POKOK SANGGAHAN",
        "quote_label": "Ketentuan yang disanggah (kutipan persis)",
        "filename": "draf-sanggahan",
        "procedure": "Sanggah hanya dapat diajukan peserta yang menyampaikan penawaran, melalui SPSE, dalam 5 hari kalender setelah pengumuman pemenang. Pastikan alasannya termasuk penyimpangan ketentuan dan prosedur, kesalahan evaluasi, rekayasa persaingan, atau penyalahgunaan wewenang.",
    },
}


def _addressee(pokja_name: str, prefix: str) -> str:
    """Name the addressee once, whether or not the input already says "Pokja"."""
    name = (pokja_name or "").strip()
    if not name:
        return f"{prefix} [nama Pokja/instansi]"
    return name if name.casefold().startswith(("pokja", "kelompok kerja")) else f"{prefix} {name}"


STATUS_PHRASE = {
    "DIPERIKSA_NASKAH": "telah dicocokkan dengan naskah peraturan",
    "DIPERIKSA_SEKUNDER": "dikonfirmasi sumber sekunder; cocokkan dengan naskah resmi",
    "PERLU_VERIFIKASI_HUKUM": "wajib diverifikasi ahli hukum",
}


def citations_for(item: dict[str, Any]) -> list[dict[str, str]]:
    """Structured citations for a finding: from the finding itself or the rule catalog."""
    basis = item.get("legal_basis")
    if isinstance(basis, list) and basis and all(isinstance(entry, dict) for entry in basis):
        return basis
    try:
        return [citation.as_dict() for citation in get_rule(str(item.get("id", ""))).legal_basis]
    except KeyError:
        return []


def _candidate_legal_citations(items: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Legal basis per finding, in formal citation style, each with its verification status."""
    if not items:
        return []
    citations: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in items:
        for citation in citations_for(item):
            reference = citation.get("formal") or f"{citation.get('article', '')} {citation.get('instrument', '')}".strip()
            if reference and reference not in seen:
                seen.add(reference)
                citations.append({
                    "reference": reference,
                    "provision": f"{citation.get('substance', '')} [{STATUS_PHRASE.get(citation.get('status', ''), 'wajib diverifikasi ahli hukum')}]",
                    "status": citation.get("status", "PERLU_VERIFIKASI_HUKUM"),
                })
    signals = " ".join(f"{item.get('issue_type', item.get('category', ''))} {item.get('review_note', '')}" for item in items).casefold()
    if any(word in signals for word in ("kolusi", "persekongkol", "persaingan", "kartel", "bid rigging")):
        citations.append({
            "reference": "UU 5/1999, Pasal 22 (larangan persekongkolan tender)",
            "provision": "Cantumkan hanya jika fakta pendukung dan unsur pasal ditelaah secara terpisah. Kemiripan dokumen atau hubungan entitas saja bukan kesimpulan pelanggaran. Naskah: https://peraturan.bpk.go.id/Details/45280/uu-no-5-tahun-1999",
            "status": "PERLU_VERIFIKASI_HUKUM",
        })
    if not citations:
        citations.append({
            "reference": "Perpres 16/2018 sebagaimana diubah dengan Perpres 12/2021 dan Perpres 46/2025, Pasal 6 (prinsip pengadaan)",
            "provision": "Rujukan awal untuk ditelaah terhadap fakta dan dokumen paket; tidak menyatakan bahwa suatu pelanggaran telah terjadi. Naskah konsolidasi LKPP: https://jdih.lkpp.go.id/regulation/konsolidasi/konsolidasi-nomor-46-tahun-2025",
            "status": "PERLU_VERIFIKASI_HUKUM",
        })
    return citations


def build_sanggahan_markdown(
    *, tender_id: str, package_name: str, company_name: str, notice_number: str,
    pokja_name: str, source_text: str, findings: list[dict[str, Any]],
    legal_citations: list[dict[str, str]] | None = None,
    stage: str = "pre_bid",
) -> str:
    """Return a formal draft; only exact, source-verified quotes are included."""
    eligible = _eligible(findings, source_text)
    letter = LETTER_STAGES[stage]
    rows: list[str] = [
        f"# {letter['title']}", "",
        "Nomor: [diisi]  ", "Lampiran: [diisi]  ", f"Perihal: {letter['subject']}", "",
        "Kepada Yth.  ", f"{_addressee(pokja_name, 'Pokja Pemilihan')}  ", "di tempat", "",
        "Dengan hormat,", "",
        f"Kami, {company_name or '[nama perusahaan]'}, peserta pada paket {package_name or '[nama paket]'} (nomor tender {tender_id or '[nomor tender]'}; pengumuman {notice_number or '[nomor pengumuman]'}), menyampaikan {letter['phrase']} berikut untuk ditelaah sesuai dokumen dan jadwal resmi.", "",
    ]
    if eligible:
        for index, item in enumerate(eligible, 1):
            title = clean_cell(item.get("clause") or item.get("category") or item.get("id") or "Ketentuan yang dipersoalkan", 240)
            quote = clean_cell(item["verbatim_quote"], 1200)
            locator = clean_cell(item.get("source") or item.get("page_ref") or "Lokator tidak tercantum", 200)
            concern = clean_cell(item.get("objection_reason") or item.get("review_note") or item.get("evidence") or "Mohon penjelasan atas dasar dan penerapan ketentuan ini.", 1000)
            rows.extend([f"## {index}. {title}", "", f"> {quote}", "", f"Sumber: {locator}", "", f"Hal yang dimohonkan penjelasan: {concern}", "", "Mohon Pokja menjelaskan dasar, penerapan yang sama kepada seluruh peserta, dan dokumen/ketentuan yang menjadi rujukan.", ""])
    else:
        rows.extend(["Belum ada temuan dengan kutipan persis dari dokumen sumber yang dapat dimasukkan. Lengkapi temuan dan dokumen sumber sebelum membuat surat.", ""])
    citations = _candidate_legal_citations(eligible) + (legal_citations or [])
    if citations:
        rows.extend(["## Rujukan awal untuk diverifikasi reviewer", ""])
        for citation in citations:
            reference = clean_cell(citation.get("reference", ""), 240)
            clause = clean_cell(citation.get("provision", ""), 800)
            if reference:
                rows.append(f"- {reference}{': ' + clause if clause else ''}")
        rows.append("")
    rows.extend([
        "Permohonan ini didasarkan pada salinan dokumen yang tersedia kepada kami. Mohon konfirmasi versi yang berlaku, nomor halaman, dan jadwal sebelum surat digunakan.", "",
        f"Tata cara: {letter['procedure']}", "",
        "Demikian kami sampaikan. Atas perhatian dan penjelasan Pokja, kami ucapkan terima kasih.", "",
        "Hormat kami,", "", "[Nama dan jabatan penandatangan]", company_name or "[Nama perusahaan]", "", "DRAF UNTUK DITINJAU: periksa kelayakan prosedural, tenggat, fakta, kutipan, dasar hukum, kewenangan, dan tanda tangan sebelum diajukan.", "",
    ])
    return "\n".join(rows)


def build_sanggahan_docx(
    *, tender_id: str, package_name: str, company_name: str, notice_number: str,
    pokja_name: str, source_text: str, findings: list[dict[str, Any]],
    legal_citations: list[dict[str, str]] | None = None,
    stage: str = "pre_bid",
) -> bytes:
    """Letter to the Pokja in official layout; only verified tender-document gaps are included."""
    eligible = _eligible(findings, source_text)
    letter = LETTER_STAGES[stage]
    doc = OfficialDocument()
    company = company_name or "[NAMA BADAN USAHA]"
    doc.letterhead([company], ["[Alamat lengkap perusahaan] · Telp. [nomor] · Surel [alamat surel]", "NPWP [nomor] · NIB [nomor]"])
    doc.letter_meta(
        [("Nomor", "[nomor surat perusahaan]"), ("Sifat", "Segera"), ("Lampiran", f"{len(eligible)} (berkas bukti kutipan)" if eligible else "-"), ("Hal", letter["subject"])],
        "[Kota], [tanggal bulan tahun]",
    )
    doc.addressee([_addressee(pokja_name, "Kelompok Kerja Pemilihan"), "di tempat"])
    doc.body(
        f"Yang bertanda tangan di bawah ini, [nama penanggung jawab] selaku [jabatan] {company}, peserta pemilihan pada paket "
        f"{package_name or '[nama paket]'} (kode tender {tender_id or '[kode tender]'}; pengumuman {notice_number or '[nomor pengumuman]'}), "
        f"dengan ini menyampaikan {letter['phrase']} atas ketentuan Dokumen Pemilihan sebagai berikut."
    )
    doc.heading("I. DASAR PENGAJUAN")
    doc.numbered("1.", REGULATION_BASIS + ", khususnya prinsip efisien, efektif, transparan, terbuka, bersaing, adil, dan akuntabel.")
    doc.numbered("2.", "Dokumen Pemilihan paket beserta adendumnya, termasuk jadwal dan tata cara yang tercantum di dalamnya.")
    for number, citation in enumerate(_candidate_legal_citations(eligible), start=3):
        doc.numbered(f"{number}.", f"{citation['reference']}, yang pada pokoknya mengatur bahwa {citation['provision']}.")
    doc.heading(f"II. {letter['section']}")
    if eligible:
        citations = {c["reference"]: c for c in _candidate_legal_citations(eligible)}
        for index, item in enumerate(eligible, 1):
            title = clean_cell(item.get("clause") or item.get("category") or item.get("id") or "Ketentuan yang dipersoalkan", 240)
            doc.numbered(f"{index}.", title, bold=True)
            doc.label_value(letter["quote_label"], "")
            doc.quote(clean_cell(item["verbatim_quote"], 1200), clean_cell(item.get("source") or item.get("page_ref") or "lokasi pada Dokumen Pemilihan", 200))
            doc.label_value("Alasan", clean_cell(item.get("objection_reason") or item.get("review_note") or "Mohon penjelasan dasar dan penerapan ketentuan ini.", 1000))
            for citation in citations_for(item):
                doc.label_value(
                    "Dasar hukum",
                    f"{citation.get('formal', '')}: {citation.get('substance', '')} [{STATUS_PHRASE.get(citation.get('status', ''), 'wajib diverifikasi ahli hukum')}]",
                )
        extra = [c for c in (legal_citations or []) if c.get("reference") and c["reference"] not in citations]
        for citation in extra:
            doc.label_value("Rujukan tambahan pemohon", clean_cell(citation["reference"], 300))
    else:
        doc.body("Belum ada temuan dengan kutipan persis dari Dokumen Pemilihan yang dapat dimasukkan. Lengkapi temuan sebelum surat diajukan.")
    doc.heading("III. PERMOHONAN")
    doc.numbered("1.", "Memberikan penjelasan tertulis atas dasar dan penerapan setiap ketentuan pada Bagian II yang berlaku sama bagi seluruh peserta.")
    doc.numbered("2.", "Melakukan perbaikan Dokumen Pemilihan melalui adendum apabila ketentuan tersebut terbukti membatasi persaingan atau tidak sesuai ketentuan.")
    doc.numbered("3.", "Menyesuaikan jadwal pemilihan sepanjang diperlukan agar seluruh peserta memperoleh waktu yang cukup.")
    doc.body(f"Demikian {letter['phrase']} ini kami sampaikan berdasarkan salinan dokumen yang kami terima. Atas perhatian dan tindak lanjut Pokja Pemilihan, kami ucapkan terima kasih.")
    doc.signature("[Kota], [tanggal bulan tahun]", f"Hormat kami,\n{company}", "[Nama Penanggung Jawab]", "[Jabatan]", stamp_note="meterai dan cap perusahaan")
    doc.note(f"Catatan peninjauan (hapus sebelum dikirim): {letter['procedure']} Periksa kebenaran fakta, kutipan, nomor pasal, kewenangan penanda tangan, dan lampiran bukti. Draf ini disusun dari kutipan yang telah dicocokkan persis dengan teks sumber.")
    return doc.to_bytes()


def build_sanggahan_html(**kwargs: Any) -> str:
    markdown = build_sanggahan_markdown(**kwargs)
    paragraphs = "".join(f"<p>{escape(line[2:] if line.startswith(('> ', '# ', '- ')) else line)}</p>" for line in markdown.splitlines() if line)
    title = LETTER_STAGES[kwargs.get("stage", "pre_bid")]["title"].title()
    return f"<!doctype html><html lang=\"id\"><meta charset=\"utf-8\"><title>{title}</title><body>" + paragraphs + "</body></html>"


def build_sanggahan_pdf(**kwargs: Any) -> bytes:
    markdown = build_sanggahan_markdown(**kwargs)
    return render_pdf(LETTER_STAGES[kwargs.get("stage", "pre_bid")]["title"], [line.removeprefix("# ").removeprefix("> ") for line in markdown.splitlines() if line], None)

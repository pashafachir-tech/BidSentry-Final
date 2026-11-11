"""Conservative mapping of evidence signals to potentially relevant rules.

The mapper does not determine a statutory violation, rejection ground, or legal
standing. Applicability must be checked against the procurement date, funding,
method, tender document, amendments, and currently effective rule text.
"""

from __future__ import annotations

from typing import Any


LEGAL_REFERENCES: dict[str, dict[str, Any]] = {
    "PERPRES_PROCUREMENT_CURRENT": {
        "title": "Perpres 16/2018 sebagaimana diubah dengan Perpres 12/2021 dan Perpres 46/2025 (naskah konsolidasi)",
        "jurisdiction": "Indonesia",
        "url": "https://jdih.lkpp.go.id/regulation/konsolidasi/konsolidasi-nomor-46-tahun-2025",
        "status": "berlaku_per_2026-10-26",
        "caveat": "Periksa aturan peralihan, tanggal paket, sumber dana, dan ketentuan khusus sebelum menggunakan pasal tertentu.",
    },
    "PERPRES_PASAL_51": {
        "title": "Perpres 16/2018 sebagaimana diubah, Pasal 51",
        "jurisdiction": "Indonesia",
        "url": "https://jdih.lkpp.go.id/regulation/konsolidasi/konsolidasi-nomor-46-tahun-2025",
        "status": "context_dependent",
        "caveat": "Pasal 51 tidak diperlakukan sebagai klausul gugur umum; pastikan rumusan konsolidasi dan konteks kegagalan tender untuk paket ini.",
    },
    "SDP_LKPP_4_2024": {
        "title": "Peraturan LKPP Nomor 4 Tahun 2024 dan model Dokumen Pemilihan terkait",
        "jurisdiction": "Indonesia",
        "url": "https://jdih.lkpp.go.id/admin/uploads/documents/Peraturan%20Lembaga%20Nomor%204%20Tahun%202024_2556_1.pdf",
        "status": "reference_requires_tender_match",
        "caveat": "Pilih lampiran/model dan ketentuan yang benar-benar digunakan atau dirujuk dalam Dokumen Pemilihan paket.",
    },
    "UU_5_1999_PASAL_22": {
        "title": "UU 5/1999 Pasal 22 tentang persekongkolan tender",
        "jurisdiction": "Indonesia",
        "url": "https://peraturan.bpk.go.id/Details/45280/uu-no-5-tahun-1999",
        "status": "berlaku_dengan_perubahan_dan_putusan_terkait",
        "caveat": "Sinyal kemiripan atau hubungan entitas tidak memenuhi unsur pasal dengan sendirinya; asesmen penegakan hukum berada pada otoritas berwenang.",
    },
    "KPPU_RULES_STATUS_1_2023": {
        "title": "Peraturan KPPU Nomor 1 Tahun 2023 tentang pencabutan pedoman Pasal 22 KPPU Nomor 2 Tahun 2010",
        "jurisdiction": "Indonesia",
        "url": "https://peraturan.bpk.go.id/Details/255158/peraturan-kppu-no-1-tahun-2023",
        "status": "berlaku",
        "caveat": "Rujukan status ini mencegah penggunaan pedoman 2010 yang telah dicabut; bukan penilaian unsur pelanggaran tender.",
    },
}

_SIGNAL_MAP: dict[str, tuple[str, ...]] = {
    "MATH_MISMATCH": ("SDP_LKPP_4_2024",),
    "BOQ-SUBTOTAL": ("SDP_LKPP_4_2024",),
    "HARGA_TIMPANG_HIGH": ("SDP_LKPP_4_2024",),
    "HARGA_TIMPANG_LOW": ("SDP_LKPP_4_2024",),
    "HARGA_TIMPANG_LOW_NO_COST_ANALYSIS": ("SDP_LKPP_4_2024",),
    "HIGH_SIMILARITY_REVIEW": ("UU_5_1999_PASAL_22",),
    "SHARED_AUTHOR_PROFILE": ("UU_5_1999_PASAL_22",),
    "SHARED_PDF_PRODUCER": ("UU_5_1999_PASAL_22",),
    "SHARED_MACHINE_FINGERPRINT": ("UU_5_1999_PASAL_22",),
    "SHARED_SOFTWARE_BUILD": ("UU_5_1999_PASAL_22",),
    "MATCHING_PDF_DOCUMENT_ID": ("UU_5_1999_PASAL_22",),
    "MATCHING_PDF_CREATION_TIMESTAMP": ("UU_5_1999_PASAL_22",),
    "MATCHING_PDF_MODIFICATION_TIMESTAMP": ("UU_5_1999_PASAL_22",),
    "CLOSE_SUBMISSION_TIMESTAMPS": ("UU_5_1999_PASAL_22",),
    "SHARED_ENTITY_NETWORK": ("UU_5_1999_PASAL_22",),
    "TENDER_FAILED": ("PERPRES_PASAL_51",),
    "MISSING_REQUIRED_DOCUMENT": ("PERPRES_PROCUREMENT_CURRENT", "SDP_LKPP_4_2024"),
}


def map_finding(finding: dict[str, Any]) -> dict[str, Any]:
    """Attach candidate reference metadata while preserving the evidence row."""
    signal = str(finding.get("anomaly_type") or finding.get("signal") or finding.get("screening_result") or finding.get("type") or "UNKNOWN")
    reference_ids = _SIGNAL_MAP.get(signal, ())
    if signal == "HIGH_SIMILARITY_REVIEW" or signal == "SHARED_ENTITY_NETWORK":
        reference_ids = ("UU_5_1999_PASAL_22",)
    if "UU_5_1999_PASAL_22" in reference_ids:
        reference_ids = (*reference_ids, "KPPU_RULES_STATUS_1_2023")
    references = [LEGAL_REFERENCES[item] | {"reference_id": item} for item in reference_ids]
    return {
        "signal": signal,
        "evidence_id": finding.get("item_code") or finding.get("evidence_id"),
        "page_ref": finding.get("page_ref"),
        "source_quote": finding.get("source_quote") or finding.get("verbatim_quote"),
        "legal_review_status": "POTENTIAL_RELEVANCE" if references else "NO_PREMAPPED_REFERENCE",
        "candidate_references": references,
        "review_questions": _review_questions(signal, bool(references)),
        "automatic_rejection": False,
        "finding": finding,
    }


def map_findings(findings: list[dict[str, Any]]) -> dict[str, Any]:
    mapped = [map_finding(item) for item in findings]
    return {
        "status": "review_candidates" if mapped else "no_findings",
        "as_of": "2026-10-26",
        "finding_count": len(mapped),
        "mapped_findings": mapped,
        "references": LEGAL_REFERENCES,
        "interpretation": "Pemetaan rujukan bersifat navigasi telaah. Tidak menyatakan pelanggaran, dasar gugur, atau hasil sanggah; penilai hukum wajib memastikan naskah dan sumber yang berlaku.",
    }


def _review_questions(signal: str, mapped: bool) -> list[str]:
    questions = ["Apakah bukti berasal dari dokumen asli dan locator halamannya sudah diverifikasi?"]
    if signal.startswith("HARGA_TIMPANG") or signal == "MATH_MISMATCH":
        questions.extend(["Apakah HPS, satuan, volume, dan mata uang pada dokumen sumber telah dicocokkan?", "Apakah Dokumen Pemilihan menetapkan konsekuensi dan proses klarifikasi yang relevan?"])
    elif signal in {"HIGH_SIMILARITY_REVIEW", "SHARED_ENTITY_NETWORK", "SHARED_AUTHOR_PROFILE", "SHARED_PDF_PRODUCER", "SHARED_MACHINE_FINGERPRINT", "SHARED_SOFTWARE_BUILD", "MATCHING_PDF_DOCUMENT_ID", "MATCHING_PDF_CREATION_TIMESTAMP", "MATCHING_PDF_MODIFICATION_TIMESTAMP", "CLOSE_SUBMISSION_TIMESTAMPS"}:
        questions.extend(["Apakah ada bukti komunikasi, kendali bersama, atau tindakan terkoordinasi selain kecocokan teknis?", "Apakah sumber independen dan penjelasan wajar telah diperiksa?"])
    elif signal == "TENDER_FAILED":
        questions.append("Apakah syarat dan dasar kegagalan tender dalam ketentuan konsolidasi serta Dokumen Pemilihan telah diverifikasi?")
    if not mapped:
        questions.append("Tambahkan rujukan aturan yang tepat dan versi Dokumen Pemilihan sebelum membuat kesimpulan hukum.")
    return questions

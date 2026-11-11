from __future__ import annotations

import json
from io import BytesIO
from pathlib import Path

from docx import Document

from bidsentry.evaluators.engine import EvaluationEngine, EvaluationRequest
from bidsentry.evaluators.grounded_checker import verify_grounded_citation
from bidsentry.forensics.adendum_diff import diff_addendum
from bidsentry.generators.sanggahan_builder import build_sanggahan_docx, build_sanggahan_markdown


ROOT = Path(__file__).resolve().parents[1]


def test_supported_quotation_must_be_an_exact_source_substring() -> None:
    text = "Status pajak sesuai bukti resmi."
    assert verify_grounded_citation(text, "pajak sesuai") == (True, 1.0)
    assert verify_grounded_citation(text, "status pajak berlaku") == (False, 0.0)
    assert verify_grounded_citation(text, None) == (False, 0.0)


def test_public_lpse_kswp_wording_is_detected_without_claiming_validation() -> None:
    source = "Mempunyai status valid keterangan Wajib Pajak berdasarkan hasil Konfirmasi Status Wajib Pajak."
    result = EvaluationEngine().evaluate(EvaluationRequest(dok_pemilihan=source))
    finding = next(item for item in result["findings"] if item["id"] == "ADM-KSWP")
    assert finding["status"] == "REVIEW"
    assert "belum diverifikasi" in finding["review_note"]


def test_uncapped_penalty_exposes_contract_excess_over_illustrative_cap() -> None:
    clause = "Denda keterlambatan sebesar 2/1000 dari nilai kontrak setiap hari keterlambatan."
    result = EvaluationEngine().evaluate(EvaluationRequest(
        contract_value_idr=1_000_000_000,
        contract_draft=clause,
    ))
    penalty = result["penalty_simulation"]
    assert penalty["uncapped_clause_detected"] is True
    assert "CRITICAL_POISON_PILL" in penalty["alerts"]
    assert [row["delay_days"] for row in penalty["scenarios"]] == [10, 30, 50]
    assert [row["contract_clause_amount_idr"] for row in penalty["scenarios"]] == [20_000_000, 60_000_000, 100_000_000]
    assert result["executive_summary"]["potential_financial_exposure_idr"] == 50_000_000
    assert penalty["assumptions"]["illustrative_cap_percentage"] == 0.05


def test_addendum_marks_modified_and_removed_requirements() -> None:
    result = diff_addendum(
        "Peserta wajib memiliki SBU BG002 yang berlaku.\nPenawaran berlaku 90 hari.",
        "Peserta wajib memiliki SBU BG002 yang berlaku minimal 30 hari.",
    )
    assert result["counts"]["MODIFIED"] == 1
    assert result["counts"]["REVOKED"] == 1
    changed = next(row for row in result["changes"] if row["change_status"] == "MODIFIED")
    assert changed["original_requirement"] and changed["adendum_requirement"]


def test_sanggahan_docx_contains_verified_quote_and_candidate_law_references() -> None:
    quote = "SBU BG002 dipersyaratkan untuk paket ini."
    findings = [{"category": "Administrasi", "clause": "SBU", "requirement_evidence": quote}]
    draft = build_sanggahan_markdown(
        tender_id="LPSE-TEST", package_name="Paket uji", company_name="Penyedia uji",
        notice_number="", pokja_name="", source_text=quote, findings=findings,
    )
    docx = build_sanggahan_docx(
        tender_id="LPSE-TEST", package_name="Paket uji", company_name="Penyedia uji",
        notice_number="", pokja_name="", source_text=quote, findings=findings,
    )
    docx_text = "\n".join(paragraph.text for paragraph in Document(BytesIO(docx)).paragraphs)
    assert quote in draft and quote in docx_text
    assert "Perpres 16/2018" in draft and "Pasal 6" in draft
    assert "tidak menyatakan bahwa suatu pelanggaran telah terjadi" in draft


def test_sanggahan_only_adds_competition_law_candidate_for_relevant_signal() -> None:
    quote = "Peserta terkait dengan penyedia lain."
    draft = build_sanggahan_markdown(
        tender_id="LPSE-TEST", package_name="Paket uji", company_name="Penyedia uji",
        notice_number="", pokja_name="", source_text=quote,
        findings=[{"category": "Kolusi", "requirement_evidence": quote}],
    )
    assert "UU 5/1999, Pasal 22" in draft
    assert "bukan kesimpulan pelanggaran" in draft


def test_langflow_export_is_valid_json_with_connected_chat_model_path() -> None:
    flow = json.loads((ROOT / "langflow" / "tender_extraction_flow.json").read_text(encoding="utf-8"))
    nodes = flow["data"]["nodes"]
    edges = flow["data"]["edges"]
    ids = {node["id"] for node in nodes}
    assert len(ids) == len(nodes)
    assert all(edge["source"] in ids and edge["target"] in ids for edge in edges)
    assert any(node.get("data", {}).get("type") == "LanguageModelComponent" for node in nodes)
    assert len(edges) >= 3


def test_langflow_prompt_escapes_literal_json_braces() -> None:
    flow = json.loads((ROOT / "langflow" / "tender_extraction_flow.json").read_text(encoding="utf-8"))
    prompt_node = next(node for node in flow["data"]["nodes"] if node.get("data", {}).get("type") == "Prompt")
    prompt = prompt_node["data"]["node"]["template"]["template"]["value"]

    rendered = prompt.format()

    assert '{{"scope"' in prompt
    assert '{"scope": string or null' in rendered
    assert "{{" not in rendered


def test_brand_lockin_detection_flags_exclusive_hardware_specifications() -> None:
    text = "Prosesor per Node: 2 x Intel Xeon Scalable Gen 5 (Emerald Rapids), mendukung UPI 4.0. GPU: NVIDIA H100 SXM5."
    result = EvaluationEngine().evaluate(EvaluationRequest(dok_pemilihan=text))
    finding_ids = {f["id"] for f in result["findings"]}
    assert "SPEC-LOCKIN-CPU" in finding_ids
    assert "SPEC-LOCKIN-GPU" in finding_ids
    cpu_finding = next(f for f in result["findings"] if f["id"] == "SPEC-LOCKIN-CPU")
    assert cpu_finding["status"] == "GAP"
    assert cpu_finding["severity"] == "HIGH"
    assert "Pasal 19" in cpu_finding["legal_reference"]
    assert "Pasal 19 ayat (2)" in cpu_finding["legal_reference"]
    assert cpu_finding["legal_verification"] == "DIPERIKSA_NASKAH"
    assert cpu_finding["objectionable"] is True


def test_compressed_procurement_timeline_flags_short_bidding_and_objection_periods() -> None:
    text = "Masa penyusunan dokumen penawaran: 3 hari kerja. Masa sanggah: 3 hari kerja."
    result = EvaluationEngine().evaluate(EvaluationRequest(dok_pemilihan=text))
    finding = next(f for f in result["findings"] if f["id"] == "PROC-TIMELINE-COMPRESSED")
    assert finding["status"] == "GAP"
    assert finding["severity"] == "HIGH"
    assert "Nomor 12 Tahun 2021" in finding["legal_reference"]
    assert finding["legal_verification"] == "PERLU_VERIFIKASI_HUKUM"  # schedule minimums not yet confirmed
    assert finding["calculation_ref"]
    assert "7 hari kerja" in finding["review_note"]
    assert "5 hari kalender" in finding["review_note"]
    assert result["verdict"] == "NO-GO"


def test_deepseek_erp_financial_fatal_flaws_detection() -> None:
    text = (
        "Pagu Anggaran : Rp 8.500.000.000,-\n"
        "TOTAL BIAYA (A + B) : 10.160.000.000\n"
        "SELISIH (OVER BUDGET) : (1.660.000.000)\n"
        "1. Mark-up Tarif Man-Month: Tarif Solution Architect sebesar Rp 150.000.000/man-month dan Project Manager Rp 120.000.000/man-month berada ±250–300% di atas standar rata-rata industri nasional (IKINDO) yang berkisar Rp 40.000.000–Rp 60.000.000/man-month.\n"
        "2. Duplikasi Lisensi: Pos 'Lisensi Core ERP — Tahun Pertama' (Rp 1.200.000.000) dan Pos 'Biaya Pemeliharaan Berkala (Tahun Pertama)' (Rp 480.000.000) berpotensi tumpang tindih (double counting), karena biaya pemeliharaan tahun pertama umumnya sudah mencakup hak penggunaan lisensi.\n"
        "Kualifikasi Personel: Project Manager (PMP / PRINCE2), Solution Architect (TOGAF / ERP Architect), sertifikasi modul ERP.\n"
    )
    result = EvaluationEngine().evaluate(EvaluationRequest(package_name="Implementasi ERP", dok_pemilihan=text))
    finding_ids = {f["id"] for f in result["findings"]}

    assert "FIN-OVER-BUDGET" in finding_ids
    assert "FIN-MARKUP-RATE" in finding_ids
    assert "FIN-DOUBLE-LICENSE" in finding_ids
    assert "ADM-EXPERTS" in finding_ids

    over_budget = next(f for f in result["findings"] if f["id"] == "FIN-OVER-BUDGET")
    assert over_budget["status"] == "GAP"
    assert over_budget["severity"] == "HIGH"
    assert "10.160.000.000" in over_budget["review_note"]
    assert "8.500.000.000" in over_budget["review_note"]

    markup = next(f for f in result["findings"] if f["id"] == "FIN-MARKUP-RATE")
    assert markup["status"] == "GAP"
    assert markup["severity"] == "HIGH"
    assert "150.000.000" in markup["review_note"]
    assert "INKINDO" in markup["review_note"]

    double_lic = next(f for f in result["findings"] if f["id"] == "FIN-DOUBLE-LICENSE")
    assert double_lic["status"] == "GAP"
    assert double_lic["severity"] == "HIGH"
    assert "1.200.000.000" in double_lic["review_note"]
    assert "double counting" in double_lic["review_note"]

    experts = next(f for f in result["findings"] if f["id"] == "ADM-EXPERTS")
    assert experts["status"] == "REVIEW"
    assert experts["severity"] == "MEDIUM"

    assert result["verdict"] == "NO-GO"
    assert result["risk_level"] == "CRITICAL"
    assert result["risk"]["rule_applied"] == "R1"
    assert "risk_score" not in result


def test_modular_data_center_regional_and_incumbent_lockin() -> None:
    text = (
        "Persyaratan: Sertifikat Keanggotaan Asosiasi Data Center Regional Jawa Barat (ADCR-Jabar) status Gold Partner minimal 3 tahun terakhir.\n"
        "Pengalaman kerja serupa: Pembangunan Modular Data Center Tier 3 dengan kapasitas tepat 50 rack dan menggunakan sistem pendinginan in-row chilled water merek tertentu (sebutkan merek inkumben) di Jawa Barat.\n"
        "Catatan: Hanya pengalaman yang memenuhi SEMUA kriteria di atas yang akan dianggap valid. Pengalaman dengan kapasitas 40 atau 60 rack tidak akan diterima.\n"
    )
    result = EvaluationEngine().evaluate(EvaluationRequest(package_name="Data Center Tier 3", dok_pemilihan=text))
    finding_ids = {f["id"] for f in result["findings"]}

    assert "SPEC-REGIONAL-LOCKIN" in finding_ids
    assert "SPEC-INCUMBENT-LOCKIN" in finding_ids

    reg = next(f for f in result["findings"] if f["id"] == "SPEC-REGIONAL-LOCKIN")
    assert reg["status"] == "GAP"
    assert reg["severity"] == "HIGH"
    assert "ADCR-Jabar" in (reg["requirement_evidence"] or "")
    assert "diskriminatif" in reg["review_note"]

    inc = next(f for f in result["findings"] if f["id"] == "SPEC-INCUMBENT-LOCKIN")
    assert inc["status"] == "GAP"
    assert inc["severity"] == "HIGH"
    assert "Pasal 19" in inc["legal_reference"]

    assert result["verdict"] == "NO-GO"


def test_managed_soc_conflict_of_interest_and_unrealistic_timeline() -> None:
    text = (
        "Kriteria: Surat rekomendasi dari Ir. [Nama], mantan Kepala Divisi TI Bank periode 2019–2023.\n"
        "Fase 4: Implementasi Arsitektur Zero-Trust Seluruh Komponen SOC dalam 7 hari kalender.\n"
        "Kualifikasi Personel: SOC Manager CISSP/CISM, Tier-3 GCIH/GCFA/OSCP, Tier-2 CEH/CySA+.\n"
    )
    result = EvaluationEngine().evaluate(EvaluationRequest(package_name="Managed SOC", dok_pemilihan=text))
    finding_ids = {f["id"] for f in result["findings"]}

    assert "GOV-CONFLICT-INTEREST" in finding_ids
    assert "PROC-UNREALISTIC-TIMELINE" in finding_ids
    assert "ADM-EXPERTS" in finding_ids

    coi = next(f for f in result["findings"] if f["id"] == "GOV-CONFLICT-INTEREST")
    assert coi["status"] == "GAP"
    assert coi["severity"] == "HIGH"
    assert "benturan kepentingan" in coi["review_note"]

    unr = next(f for f in result["findings"] if f["id"] == "PROC-UNREALISTIC-TIMELINE")
    assert unr["status"] == "GAP"
    assert unr["severity"] == "HIGH"
    assert "zero-trust" in (unr["requirement_evidence"] or "").casefold()
    assert "7 hari kalender" in unr["review_note"]

    assert result["verdict"] == "NO-GO"


def test_probe_engine_13_audit_scenarios() -> None:
    engine = EvaluationEngine()

    # P1: Clean integrity pact wording must not trigger COI, verdict BELUM CUKUP BUKTI for missing NPWP
    r1 = engine.evaluate(EvaluationRequest(dok_pemilihan="Peserta menyatakan tidak ada benturan kepentingan dengan Pokja.\nPenyedia wajib menyerahkan NPWP."))
    assert "GOV-CONFLICT-INTEREST" not in {f["id"] for f in r1["findings"]}
    assert r1["verdict"] == "BELUM CUKUP BUKTI"

    # P2: Generic sentence with no numbers must not trigger overbudget finding or fabricate numbers
    r2 = engine.evaluate(EvaluationRequest(dok_pemilihan="HPS tidak boleh melebihi pagu anggaran yang tersedia."))
    assert "FIN-OVER-BUDGET" not in {f["id"] for f in r2["findings"]}
    assert r2["findings"] == []
    assert r2["verdict"] in ("GO", "TIDAK ADA SYARAT TERBACA")

    # P3: SBU issued 2023, valid until 2030 -> picked 2030 expiry date
    r3 = engine.evaluate(EvaluationRequest(dok_pemilihan="Peserta wajib memiliki SBU.", pustaka="SBU diterbitkan 12 Januari 2023, berlaku sampai 12 Januari 2030", bid_deadline="1 Juni 2026"))
    sbu = next(f for f in r3["findings"] if f["id"] == "ADM-SBU")
    assert sbu["status"] == "TERPENUHI"
    assert "2030" in sbu["review_note"]
    assert r3["verdict"] == "GO"

    # P4: 12 months == 1 year warranty
    r4 = engine.evaluate(EvaluationRequest(dok_pemilihan="Garansi minimal 1 tahun.", pustaka="Garansi 12 bulan."))
    war = next(f for f in r4["findings"] if f["id"] == "ADM-WARRANTY")
    assert war["status"] == "TERPENUHI"
    assert r4["verdict"] == "GO"

    # P5: KSWP 'tidak terkonfirmasi' -> GAP/HIGH
    r5 = engine.evaluate(EvaluationRequest(dok_pemilihan="Wajib melampirkan KSWP.", pustaka="KSWP: tidak terkonfirmasi"))
    kswp = next(f for f in r5["findings"] if f["id"] == "ADM-KSWP")
    assert kswp["status"] == "GAP"
    assert r5["verdict"] == "NO-GO"

    # P6: the regulated 1 per mille rate with no stated cap asks for review; "tanpa batas" is a confirmed gap
    r6a = engine.evaluate(EvaluationRequest(dok_pemilihan="Denda keterlambatan 1/1000 per hari dari nilai kontrak."))
    pen_a = next(f for f in r6a["findings"] if f["id"] == "CON-PENALTY")
    assert pen_a["status"] == "REVIEW"
    assert r6a["verdict"] == "BELUM CUKUP BUKTI"

    r6b = engine.evaluate(EvaluationRequest(dok_pemilihan="Denda keterlambatan 1/1000 per hari dari nilai kontrak tanpa batas maksimal.", contract_value_idr=1_000_000_000))
    pen_b = next(f for f in r6b["findings"] if f["id"] == "CON-PENALTY")
    assert pen_b["status"] == "GAP"
    assert r6b["verdict"] == "NO-GO"

    # P7: Requirements uploaded, zero evidence uploaded -> BELUM CUKUP BUKTI, NOT GO
    r7 = engine.evaluate(EvaluationRequest(dok_pemilihan="Wajib melampirkan NPWP.\nWajib SBU.\nWajib jaminan penawaran 1%.\nWajib KSWP.\nGaransi 2 tahun."))
    assert r7["verdict"] == "BELUM CUKUP BUKTI"
    assert all(f["status"] == "REVIEW" for f in r7["findings"])

    # P8: Bid bond amount extracted cleanly (85M, not HPS 8.5M)
    r8 = engine.evaluate(EvaluationRequest(dok_pemilihan="Jaminan penawaran sebesar Rp 85.000.000 (1% dari HPS Rp 8.500.000.000).", pustaka="Jaminan penawaran Rp 85.000.000 dari Bank X"))
    bnd = next(f for f in r8["findings"] if f["id"] == "ADM-BOND")
    assert bnd["status"] == "TERPENUHI"
    assert "85,000,000" in bnd["review_note"]
    assert r8["verdict"] == "GO"

    # P9: Wrapped multiline NPWP correctly detected
    r9 = engine.evaluate(EvaluationRequest(dok_pemilihan="Wajib NPWP.", pustaka="Kami melampirkan NPWP perusahaan:\n01.234.567.8-901.000"))
    npw = next(f for f in r9["findings"] if f["id"] == "ADM-NPWP")
    assert npw["status"] == "TERPENUHI"
    assert r9["verdict"] == "GO"

    # P10: Dynamic billing rate markup without fabricated numbers or fake positions
    r10 = engine.evaluate(EvaluationRequest(dok_pemilihan="Solution Architect Rp 100.000.000 per bulan"))
    mrk = next(f for f in r10["findings"] if f["id"] == "FIN-MARKUP-RATE")
    assert mrk["status"] == "GAP"
    assert "100.000.000" in mrk["review_note"]
    assert "150.000.000" not in mrk["review_note"]
    assert "Project Manager" not in mrk["review_note"]
    assert r10["verdict"] == "NO-GO"

    # P11: Timeline 3 days not softened by "clean baseline"
    r11 = engine.evaluate(EvaluationRequest(dok_pemilihan="Dokumen ini clean baseline.\npenyusunan dokumen penawaran hanya 3 hari kerja"))
    tm = next(f for f in r11["findings"] if f["id"] == "PROC-TIMELINE-COMPRESSED")
    assert tm["status"] == "REVIEW" and tm["threshold_unverified"] is True
    assert r11["verdict"] == "BELUM CUKUP BUKTI"

    # P12: Sanggahan draft contains specifications and timeline objections, excludes bidder's expired SBU
    src12 = ("Spesifikasi wajib Intel Xeon Emerald Rapids.\nmasa sanggah hanya 2 hari kerja\nWajib SBU.")
    r12 = engine.evaluate(EvaluationRequest(dok_pemilihan=src12, pustaka="SBU berlaku sampai 1 Januari 2020"))
    md = build_sanggahan_markdown(
        tender_id="T1", package_name="P", company_name="PT A", notice_number="N", pokja_name="Pokja",
        source_text=src12, findings=r12["findings"],
    )
    assert "Penguncian Merek Prosesor" in md
    assert "Jadwal lelang mepet" in md
    assert "Masa berlaku SBU" not in md

    # P13: Clean input without false positives
    r13 = engine.evaluate(EvaluationRequest(adendum="Perubahan jadwal pemasukan penawaran."))
    assert r13["findings"] == []
    assert r13["verdict"] in ("GO", "TIDAK ADA SYARAT TERBACA")

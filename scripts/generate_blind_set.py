#!/usr/bin/env python3
"""Generate an independent blind test dataset (10 cases) for BidSentry evaluation.

This blind set is created independently of the 24-document development/tuning set
to provide an honest, unbiased assessment of generalizability.
"""

from __future__ import annotations

import json
from pathlib import Path

OUT_DIR = Path(__file__).resolve().parent.parent / "data" / "test_blind"
OUT_DIR.mkdir(parents=True, exist_ok=True)

BLIND_DOCS = [
    {
        "id": "blind_01_konstruksi_standar_clean",
        "title": "Rehabilitasi Gedung Kantor Pemerintah Daerah (Patuh & Bersih)",
        "is_trap": False,
        "request": {
            "package_name": "Pekerjaan Rehabilitasi Gedung Bappeda Provinsi",
            "tender_id": "TND-REHAB-2026-01",
            "pokja_name": "Pokja Pemilihan Konstruksi Wilayah I",
            "company_name": "PT Cipta Graha Mandiri",
            "contract_value_idr": 4500000000,
            "bid_deadline": "10 November 2026",
            "dok_pemilihan": """KERANGKA ACUAN KERJA & SPESIFIKASI TEKNIS
Paket: Rehabilitasi Gedung Kantor Bappeda
Pagu Anggaran: Rp 4.500.000.000,- (Empat Koma Lima Miliar Rupiah)
HPS: Rp 4.420.000.000,-

BAB IV. JADWAL PENGADAAN
1. Masa penyusunan dan pengunggahan penawaran diberikan selama 8 hari kerja sejak pengumuman lelang.
2. Masa sanggah terhadap penetapan pemenang pemilihan diberikan selama 5 hari kerja penuh melalui sistem SPSE.

BAB V. SYARAT KUALIFIKASI PENYEDIA
1. Memiliki Nomor Induk Berusaha (NIB) berbasis risiko yang masih berlaku.
2. Memiliki NPWP Perusahaan dan konfirmasi status wajib pajak (KSWP) berstatus valid.
3. Memiliki Sertifikat Badan Usaha (SBU) Jasa Pelaksana Konstruksi Gedung Perkantoran (BG004/BG009) yang masih berlaku.""",
            "pustaka": """DOKUMEN KUALIFIKASI PENYEDIA
1. Nomor Induk Berusaha (NIB): 9120005678912 terdaftar resmi OSS Kementerian Investasi/BKPM.
2. NPWP Perusahaan: 01.445.678.9-012.000 (status KSWP valid tercatat di DJP).
3. SBU BG004 terbit 12 Januari 2024, masa berlaku sampai dengan 12 Januari 2029.""",
            "contract_draft": """BAB XI. DENDA DAN SANKSI KETERLAMBATAN
1. Keterlambatan pelaksanaan pekerjaan dikenakan denda sebesar 1/1000 (satu per mil) dari nilai kontrak per hari keterlambatan.
2. Batas maksimal denda keterlambatan ditetapkan sebesar 5% (lima persen) dari nilai kontrak pekerjaan.""",
        },
        "expected_verdict": "GO",
        "expected_findings": {
            "ADM-NPWP": "TERPENUHI",
            "ADM-NIB": "TERPENUHI",
            "ADM-SBU": "TERPENUHI",
        },
        "forbidden_findings": ["SPEC-LOCKIN-PROC", "PROC-TIMELINE-SANGGAH", "PROC-TIMELINE-PREP", "CON-PENALTY", "FIN-HPS-OVER-PAGU"],
    },
    {
        "id": "blind_02_pengadaan_laptop_lockin_intel",
        "title": "Pengadaan Laptop Dinas dengan Penguncian Merek Intel Tanpa Opsi Setara",
        "is_trap": False,
        "request": {
            "package_name": "Pengadaan Laptop Mobilitas Pegawai",
            "tender_id": "TND-LAPTOP-2026-09",
            "dok_pemilihan": """BAB III. SPESIFIKASI TEKNIS PERALATAN
1. Unit laptop wajib menggunakan prosesor Intel Core Ultra 7 155H 16-Core dengan Intel AI Boost NPU.
2. Tidak menerima prosesor dari pabrikan lain seperti AMD Ryzen demi keseragaman arsitektur komputasi kantor.
3. Kapasitas RAM 32GB LPDDR5X-7467 MHz onboard.""",
            "contract_draft": "Denda keterlambatan 1/1000 per hari dengan batas maksimal 5 persen.",
        },
        "expected_verdict": "NO-GO",
        "expected_findings": {
            "SPEC-LOCKIN-PROC": "GAP",
        },
        "forbidden_findings": [],
    },
    {
        "id": "blind_03_konsultansi_jadwal_mepet",
        "title": "Kajian Penataan Ruang dengan Jadwal Penawaran dan Sanggah Sangat Mepet",
        "is_trap": False,
        "request": {
            "package_name": "Kajian Teknis Tata Ruang Wilayah",
            "tender_id": "TND-TTRU-2026-44",
            "dok_pemilihan": """BAB II. JADWAL PELAKSANAAN SELEKSI
1. Pemberian penjelasan dan masa pemasukan dokumen penawaran teknis dibatasi hanya selama 4 hari kerja.
2. Masa sanggah hasil kualifikasi diberikan selama 2 hari kerja setelah berita acara pengumuman diterbitkan.""",
            "contract_draft": "Denda 1/1000 per hari maksimal 5 persen.",
        },
        "expected_verdict": "NO-GO",
        "expected_findings": {
            "PROC-TIMELINE-PREP": "GAP",
            "PROC-TIMELINE-SANGGAH": "GAP",
        },
        "forbidden_findings": [],
    },
    {
        "id": "blind_04_alkes_denda_tanpa_batas",
        "title": "Pengadaan CT Scan Rumah Sakit dengan Klausul Denda Tanpa Batas Maksimal",
        "is_trap": False,
        "request": {
            "package_name": "Pengadaan Diagnostic Imaging CT-Scan 128 Slices",
            "tender_id": "TND-ALKES-2026-11",
            "contract_value_idr": 12500000000,
            "dok_pemilihan": "Spesifikasi alat diagnostik rumah sakit standar internasional.",
            "contract_draft": """BAB XIV. SANKSI KETERLAMBATAN
1. Apabila Penyedia gagal menyelesaikan serah terima tepat waktu, dikenakan denda keterlambatan sebesar 1/1000 per hari dari total nilai kontrak tanpa batas maksimal denda kumulatif.""",
        },
        "expected_verdict": "NO-GO",
        "expected_findings": {
            "CON-PENALTY": "GAP",
        },
        "forbidden_findings": [],
    },
    {
        "id": "blind_05_outsourcing_pakta_integritas_trap",
        "title": "Dokumen Jasa Kebersihan Menyebutkan Pakta Integritas (Trap Case - Sah)",
        "is_trap": True,
        "request": {
            "package_name": "Layanan Kebersihan dan Keamanan Gedung Kantor",
            "tender_id": "TND-CLEAN-2026-05",
            "dok_pemilihan": """BAB I. KETENTUAN UMUM DAN INTEGRITAS
1. Seluruh peserta tender wajib menandatangani pakta integritas resmi LKPP.
2. Peserta menyatakan bebas dari benturan kepentingan dengan PPK, Pokja Pemilihan, maupun Pejabat Penatausahaan Keuangan.
3. Masa penawaran 8 hari kerja dan masa sanggah 5 hari kerja.""",
            "pustaka": "NIB 9120009988776 aktif. NPWP 02.345.678.9-031.000.",
            "contract_draft": "Denda keterlambatan 1/1000 per hari maksimal 5% dari nilai kontrak.",
        },
        "expected_verdict": "GO",
        "expected_findings": {},
        "forbidden_findings": ["GOV-CONFLICT-INTEREST", "SPEC-LOCKIN-PROC", "PROC-TIMELINE-SANGGAH", "CON-PENALTY"],
    },
    {
        "id": "blind_06_jasa_erp_over_budget",
        "title": "Pengadaan ERP dengan Rincian BoQ Melebihi Pagu Anggaran",
        "is_trap": False,
        "request": {
            "package_name": "Pengembangan Sistem Informasi Manajemen Keuangan ERP",
            "tender_id": "TND-ERP-2026-88",
            "dok_pemilihan": """BAB V. ALOKASI ANGGARAN DAN RINCIAN BIAYA
1. Pagu Anggaran yang tersedia pada DIPA Satker adalah sebesar Rp 5.000.000.000,- (Lima Miliar Rupiah).
2. Berdasarkan hasil rekapitulasi perhitungan teknis Bill of Quantities (BoQ), total rincian biaya kebutuhan mencapai Rp 6.250.000.000,- (Enam Koma Dua Puluh Lima Miliar Rupiah).
3. Jadwal pemasukan penawaran 7 hari kerja dan sanggah 5 hari kerja.""",
            "contract_draft": "Denda keterlambatan 1/1000 per hari maksimal 5%.",
        },
        "expected_verdict": "NO-GO",
        "expected_findings": {
            "FIN-HPS-OVER-PAGU": "GAP",
        },
        "forbidden_findings": [],
    },
    {
        "id": "blind_07_sewa_kendaraan_equivalent_trap",
        "title": "Penyebutan Tipe Kendaraan Disertai Klausul Kesetaraan (Trap Case - Sah)",
        "is_trap": True,
        "request": {
            "package_name": "Sewa Kendaraan Operasional Lapangan",
            "tender_id": "TND-FLEET-2026-17",
            "dok_pemilihan": """BAB III. SPESIFIKASI ARMADA
1. Kebutuhan kendaraan operasional berupa tipe MPV 7-Seater sekelas Toyota Innova Zenix atau kendaraan sejenis yang setara (equivalent).
2. Mesin kapasitas 2.000 cc bensin atau hybrid efisiensi tinggi.
3. Masa penawaran 7 hari kerja, masa sanggah 5 hari kerja.""",
            "contract_draft": "Denda 1/1000 per hari dengan batas maksimal 5 persen.",
        },
        "expected_verdict": "GO",
        "expected_findings": {},
        "forbidden_findings": ["SPEC-LOCKIN-PROC", "SPEC-LOCKIN-GPU"],
    },
    {
        "id": "blind_08_meubeler_sbu_hampir_kadaluwarsa",
        "title": "Penyedia Melampirkan SBU yang Masa Berlakunya Kurang dari 30 Hari",
        "is_trap": False,
        "request": {
            "package_name": "Pengadaan Meubeler Kantor dan Ruang Rapat",
            "tender_id": "TND-FURN-2026-22",
            "bid_deadline": "20 Oktober 2026",
            "dok_pemilihan": """BAB IV. PERSYARATAN KUALIFIKASI
1. Penyedia wajib memiliki Sertifikat Badan Usaha (SBU) yang masih berlaku pada saat batas akhir pemasukan penawaran.""",
            "pustaka": """LAMPIRAN KREDENSIAL PENYEDIA
1. Nomor Pokok Wajib Pajak: 01.222.333.4-555.000 status aktif.
2. Sertifikat Badan Usaha SBU terbit tanggal 28 Oktober 2023, berlaku sampai dengan 28 Oktober 2026.""",
            "contract_draft": "Denda 1/1000 per hari maksimal 5%.",
        },
        "expected_verdict": "BELUM CUKUP BUKTI",
        "expected_findings": {
            "ADM-SBU": "EXPIRING",
        },
        "forbidden_findings": [],
    },
    {
        "id": "blind_09_konsultan_billing_rate_tinggi",
        "title": "Tarif Remunerasi Man-Month Tenaga Ahli Melambung Melebihi Standar INKINDO",
        "is_trap": False,
        "request": {
            "package_name": "Jasa Konsultansi Pengawasan Jalan Tol Trans Regional",
            "tender_id": "TND-ROAD-2026-90",
            "dok_pemilihan": """BAB VI. KEBUTUHAN PERSONEL DAN BIAYA LANGSUNG PERSONEL
1. Posisi Senior Project Manager: Billing rate ditetapkan sebesar Rp 140.000.000 per bulan.
2. Posisi Lead Highway Engineer: Billing rate ditetapkan sebesar Rp 110.000.000 per bulan.
3. Masa penawaran 7 hari kerja dan masa sanggah 5 hari kerja.""",
            "contract_draft": "Denda 1/1000 per hari maksimal 5%.",
        },
        "expected_verdict": "NO-GO",
        "expected_findings": {
            "FIN-BILLING-RATE": "GAP",
        },
        "forbidden_findings": [],
    },
    {
        "id": "blind_10_dokumen_narasi_lepas_tanpa_pasal",
        "title": "Dokumen Narasi Lepas Rapat Koordinasi Tanpa Ketentuan Syarat Pengadaan",
        "is_trap": True,
        "request": {
            "package_name": "Notulensi Diskusi Koordinasi Rencana Kerja",
            "tender_id": "NOTE-KOORD-2026",
            "dok_pemilihan": """NOTULENSI RAPAT KOORDINASI INTERNAL
Hari/Tanggal: Senin, 14 Juli 2026
Agenda: Pembahasan awal rencana pengadaan sarana kerja semester II.
Hasil Pembahasan:
- Tim sepakat untuk menyusun kerangka acuan kerja pada bulan depan.
- Perlu konsultasi lanjutan dengan bagian perlengkapan mengenai estimasi biaya.
- Rapat ditutup pukul 16.30 WIB.""",
            "contract_draft": "",
            "pustaka": "",
        },
        "expected_verdict": "TIDAK ADA SYARAT TERBACA",
        "expected_findings": {},
        "forbidden_findings": ["SPEC-LOCKIN-PROC", "PROC-TIMELINE-SANGGAH", "CON-PENALTY"],
    },
]

def main():
    print(f"Generating {len(BLIND_DOCS)} independent blind test files in {OUT_DIR}...")
    for item in BLIND_DOCS:
        file_path = OUT_DIR / f"{item['id']}.json"
        file_path.write_text(json.dumps(item, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"  [+] Wrote: {file_path.name}")
    print(f"Successfully generated {len(BLIND_DOCS)} blind evaluation documents.")

if __name__ == "__main__":
    main()

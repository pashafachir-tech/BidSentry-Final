"""Create 24 synthetic benchmark held-out documents with ground truth labels."""

from __future__ import annotations

import json
from pathlib import Path

BENCHMARK_DIR = Path("data/benchmark")
BENCHMARK_DIR.mkdir(parents=True, exist_ok=True)

DOCS = [
    {
        "id": "doc_01_clean_ict_procurement",
        "title": "Pengadaan Server Standar dengan Klausul Setara",
        "description": "Jebakan: Prosesor Intel Xeon disebut tetapi dengan klausul 'atau setara'. NPWP & NIB valid. Jadwal 14 hari.",
        "input": {
            "package_name": "Pengadaan Komputer Server Kanwil",
            "dok_pemilihan": "Persyaratan Teknis Server:\n1. Menggunakan prosesor Intel Xeon Scalable atau setara yang setara performanya.\n2. Waktu penyusunan dan pemasukan penawaran diberikan selama 14 hari kerja.\n3. Wajib melampirkan Nomor Induk Berusaha (NIB) dan NPWP aktif.",
            "pustaka": "Dokumen Kualifikasi:\nNPWP: 01.234.567.8-901.000\nNomor Induk Berusaha (NIB): 9120001234567 terbit dan aktif.",
        },
        "labels": {
            "expected_findings": [
                {"id": "ADM-NPWP", "status": "TERPENUHI"},
                {"id": "ADM-NIB", "status": "TERPENUHI"}
            ],
            "forbidden_findings": ["SPEC-LOCKIN-CPU", "PROC-TIMELINE-COMPRESSED"],
            "expected_verdict": "GO",
            "is_trap": True,
            "trap_reason": "Menyebut Intel Xeon namun diikuti frasa 'atau setara', jadwal lelang longgar 14 hari."
        }
    },
    {
        "id": "doc_02_brand_lockin_cpu_only",
        "title": "Penguncian Spesifikasi CPU Intel Emerald Rapids",
        "description": "Pelanggaran spesifikasi: CPU dikunci ke arsitektur eksklusif tanpa padanan.",
        "input": {
            "package_name": "Pengadaan Compute Node AI",
            "dok_pemilihan": "Spesifikasi Server Utama:\nWajib menggunakan prosesor Intel Xeon Emerald Rapids dengan interkoneksi UPI 4.0 dan fitur Intel VMD aktif tanpa alternatif merk lain.",
            "pustaka": "Brosur penawaran server sesuai spek.",
        },
        "labels": {
            "expected_findings": [
                {"id": "SPEC-LOCKIN-CPU", "status": "GAP"}
            ],
            "forbidden_findings": [],
            "expected_verdict": "NO-GO",
            "is_trap": False
        }
    },
    {
        "id": "doc_03_brand_lockin_gpu_with_equiv",
        "title": "Penyebutan GPU NVIDIA dengan Alternatif Setara",
        "description": "Jebakan: GPU NVIDIA H100 disebut namun membuka alternatif setara.",
        "input": {
            "package_name": "Pengadaan Server Pemrosesan Visual",
            "dok_pemilihan": "Unit Grafis Komputasi:\nAkselerator grafis NVIDIA H100 SXM5 atau akselerator grafis pabrikan lain yang setara performa komputasinya.\nWajib memiliki NPWP.",
            "pustaka": "NPWP: 02.456.789.1-012.000 aktif.",
        },
        "labels": {
            "expected_findings": [
                {"id": "ADM-NPWP", "status": "TERPENUHI"}
            ],
            "forbidden_findings": ["SPEC-LOCKIN-GPU"],
            "expected_verdict": "GO",
            "is_trap": True,
            "trap_reason": "Menyebut NVIDIA H100 namun dengan klausul 'atau akselerator grafis pabrikan lain yang setara'."
        }
    },
    {
        "id": "doc_04_brand_lockin_gpu_strict",
        "title": "Penguncian GPU NVIDIA H100 SXM5 dan NVLink 4.0",
        "description": "Pelanggaran spesifikasi: GPU dikunci tanpa klausul setara.",
        "input": {
            "package_name": "Cluster Server High Performance Computing",
            "dok_pemilihan": "Spesifikasi GPU Node:\nWajib dilengkapi 8x NVIDIA H100 SXM5 80GB dengan koneksi interkoneksi NVLink 4.0 antar GPU.",
            "pustaka": "",
        },
        "labels": {
            "expected_findings": [
                {"id": "SPEC-LOCKIN-GPU", "status": "GAP"}
            ],
            "forbidden_findings": [],
            "expected_verdict": "NO-GO",
            "is_trap": False
        }
    },
    {
        "id": "doc_05_compressed_timeline_bid_prep",
        "title": "Jadwal Pemasukan Penawaran Terlalu Mepet 3 Hari",
        "description": "Pelanggaran jadwal: Batas pemasukan penawaran hanya 3 hari kerja.",
        "input": {
            "package_name": "Pengadaan Jaringan Komputer Dinas",
            "dok_pemilihan": "Jadwal Pengadaan:\npemasukan penawaran hanya 3 hari kerja sejak pengumuman lelang.",
            "pustaka": "",
        },
        "labels": {
            "expected_findings": [
                {"id": "PROC-TIMELINE-COMPRESSED", "status": "GAP"}
            ],
            "forbidden_findings": [],
            "expected_verdict": "NO-GO",
            "is_trap": False
        }
    },
    {
        "id": "doc_06_sufficient_timeline_8days",
        "title": "Jadwal Pemilihan Cukup Sesuai Pedoman LKPP",
        "description": "Kasus negatif: Jadwal pemasukan 8 hari kerja (standar minimal LKPP 7 hari).",
        "input": {
            "package_name": "Pengadaan Kabel Fiber Optik",
            "dok_pemilihan": "Ketentuan Pelaksanaan Lelang:\nWaktu penyusunan dan pemasukan penawaran diberikan selama 8 hari kerja sesuai batas wajar regulasi pengadaan.",
            "pustaka": "",
        },
        "labels": {
            "expected_findings": [],
            "forbidden_findings": ["PROC-TIMELINE-COMPRESSED"],
            "expected_verdict": "GO",
            "is_trap": True,
            "trap_reason": "Waktu penawaran 8 hari kerja memenuhi standar LKPP (minimal 7 hari kerja)."
        }
    },
    {
        "id": "doc_07_compressed_sanggah_timeline",
        "title": "Masa Sanggah Terlalu Singkat 2 Hari Kerja",
        "description": "Pelanggaran jadwal: Masa sanggah hanya 2 hari kerja (standar minimal 5 hari).",
        "input": {
            "package_name": "Revitalisasi Jaringan Kampus",
            "dok_pemilihan": "Tahapan Lelang:\nPengumuman pemenang lelang dan masa sanggah hanya 2 hari kerja.",
            "pustaka": "",
        },
        "labels": {
            "expected_findings": [
                {"id": "PROC-TIMELINE-COMPRESSED", "status": "GAP"}
            ],
            "forbidden_findings": [],
            "expected_verdict": "NO-GO",
            "is_trap": False
        }
    },
    {
        "id": "doc_08_normative_integrity_no_coi",
        "title": "Pakta Integritas Bebas Benturan Kepentingan",
        "description": "Jebakan: Teks menyatakan bebas benturan kepentingan, bukan pelanggaran.",
        "input": {
            "package_name": "Jasa Pemeliharaan Sistem Informasi",
            "dok_pemilihan": "Pakta Integritas:\nPeserta membuat pernyataan resmi bebas dari benturan kepentingan dengan pejabat pengadaan maupun Pokja Pemilihan.\nWajib melampirkan NPWP.",
            "pustaka": "NPWP terlampir: 01.999.888.7-654.000",
        },
        "labels": {
            "expected_findings": [
                {"id": "ADM-NPWP", "status": "TERPENUHI"}
            ],
            "forbidden_findings": ["GOV-CONFLICT-INTEREST"],
            "expected_verdict": "GO",
            "is_trap": True,
            "trap_reason": "Frasa 'bebas dari benturan kepentingan' adalah komitmen integritas, bukan indikasi pelanggaran."
        }
    },
    {
        "id": "doc_09_actual_coi_recom_letter",
        "title": "Syarat Rekomendasi Mantan Pejabat Internal",
        "description": "Pelanggaran integritas: Wajib surat rekomendasi mantan pejabat internal.",
        "input": {
            "package_name": "Konsultansi Tata Kelola TI",
            "dok_pemilihan": "Persyaratan Khusus Kualifikasi:\nPeserta wajib menyertakan surat rekomendasi dari mantan Kepala Divisi TI yang terafiliasi dengan pemberi kerja.",
            "pustaka": "",
        },
        "labels": {
            "expected_findings": [
                {"id": "GOV-CONFLICT-INTEREST", "status": "GAP"}
            ],
            "forbidden_findings": [],
            "expected_verdict": "NO-GO",
            "is_trap": False
        }
    },
    {
        "id": "doc_10_normative_pagu_guideline",
        "title": "Pedoman Umum HPS Tidak Boleh Melebihi Pagu",
        "description": "Jebakan: Kalimat normatif aturan bahwa HPS tidak boleh melebihi pagu tanpa angka defisit.",
        "input": {
            "package_name": "Pengadaan Alat Tulis Kantor",
            "dok_pemilihan": "Petunjuk Umum Pengadaan:\nDalam menyusun penawaran, HPS tidak boleh melebihi pagu anggaran yang telah disahkan.",
            "pustaka": "",
        },
        "labels": {
            "expected_findings": [],
            "forbidden_findings": ["FIN-OVER-BUDGET"],
            "expected_verdict": "TIDAK ADA SYARAT TERBACA",
            "is_trap": True,
            "trap_reason": "Kalimat normatif pedoman HPS tidak memuat angka defisit/over budget."
        }
    },
    {
        "id": "doc_11_actual_overbudget_boq",
        "title": "Total BoQ Melebihi Pagu Anggaran Riil",
        "description": "Pelanggaran finansial: Total BoQ melebihi Pagu Anggaran dengan nominal eksplisit.",
        "input": {
            "package_name": "Pembangunan Data Center Mini",
            "dok_pemilihan": "Rincian Anggaran Paket:\nPagu Anggaran : Rp 4.000.000.000\nTOTAL BIAYA BoQ : Rp 5.200.000.000\nSELISIH (OVER BUDGET) : Rp 1.200.000.000",
            "pustaka": "",
        },
        "labels": {
            "expected_findings": [
                {"id": "FIN-OVER-BUDGET", "status": "GAP"}
            ],
            "forbidden_findings": [],
            "expected_verdict": "NO-GO",
            "is_trap": False
        }
    },
    {
        "id": "doc_12_reasonable_billing_rates",
        "title": "Tarif Remunerasi Tenaga Ahli Sesuai Standar INKINDO",
        "description": "Kasus negatif: Billing rate konsultan masih dalam batas wajar standar nasional.",
        "input": {
            "package_name": "Kajian Blueprint Enterprise Architecture",
            "dok_pemilihan": "Komponen Biaya Personel:\nSolution Architect Rp 45.000.000 per bulan, Project Manager Rp 40.000.000 per bulan sesuai pedoman standar INKINDO.",
            "pustaka": "",
        },
        "labels": {
            "expected_findings": [],
            "forbidden_findings": ["FIN-MARKUP-RATE"],
            "expected_verdict": "GO",
            "is_trap": True,
            "trap_reason": "Tarif konsultan 40-45 juta per bulan berada dalam koridor standar kewajaran INKINDO."
        }
    },
    {
        "id": "doc_13_markup_billing_rate_pm",
        "title": "Mark-Up Tarif Remunerasi Project Manager",
        "description": "Pelanggaran finansial: Tarif Project Manager melonjak tinggi di atas standar wajar.",
        "input": {
            "package_name": "Pengembangan Portal Layanan Satu Data",
            "dok_pemilihan": "Komponen Biaya Tenaga Ahli:\nProject Manager sebesar Rp 140.000.000 per bulan untuk durasi 6 bulan.",
            "pustaka": "",
        },
        "labels": {
            "expected_findings": [
                {"id": "FIN-MARKUP-RATE", "status": "GAP"}
            ],
            "forbidden_findings": [],
            "expected_verdict": "NO-GO",
            "is_trap": False
        }
    },
    {
        "id": "doc_14_double_counted_license_maint",
        "title": "Duplikasi Biaya Lisensi dan Pemeliharaan Tahun Pertama",
        "description": "Pelanggaran finansial: Tagihan lisensi dan pemeliharaan berpotensi double counting.",
        "input": {
            "package_name": "Pengadaan Lisensi Database Cluster",
            "dok_pemilihan": "Rincian Biaya Perangkat Lunak:\nPos Lisensi Core ERP Rp 1.000.000.000 dan Biaya Pemeliharaan Berkala Rp 350.000.000 tahun pertama sudah termasuk lisensi.",
            "pustaka": "",
        },
        "labels": {
            "expected_findings": [
                {"id": "FIN-DOUBLE-LICENSE", "status": "GAP"}
            ],
            "forbidden_findings": [],
            "expected_verdict": "NO-GO",
            "is_trap": False
        }
    },
    {
        "id": "doc_15_uncapped_penalty_contract",
        "title": "Klausul Denda Keterlambatan Tanpa Batas Maksimum",
        "description": "Pelanggaran klausul: Denda tanpa batas maksimum (poison pill).",
        "input": {
            "package_name": "Pekerjaan Instalasi Generator",
            "dok_pemilihan": "Syarat Khusus Kontrak:\nDenda keterlambatan ditetapkan sebesar 1/1000 per hari dari nilai kontrak tanpa batas maksimal denda.",
            "contract_draft": "Denda keterlambatan 1/1000 per hari dari nilai kontrak.",
            "pustaka": "",
        },
        "labels": {
            "expected_findings": [
                {"id": "CON-PENALTY", "status": "GAP"}
            ],
            "forbidden_findings": [],
            "expected_verdict": "NO-GO",
            "is_trap": False
        }
    },
    {
        "id": "doc_16_capped_penalty_contract",
        "title": "Klausul Denda Standar dengan Batas Maksimal 5 Persen",
        "description": "Jebakan: Denda memiliki batas maksimal 5% sesuai regulasi LKPP.",
        "input": {
            "package_name": "Pengadaan Meubelair Kantor",
            "dok_pemilihan": "Ketentuan Kontrak:\nDenda keterlambatan sebesar 1/1000 per hari dengan batas maksimal denda 5% dari nilai kontrak.",
            "contract_draft": "Denda keterlambatan sebesar 1/1000 per hari dengan batas maksimal 5% dari nilai kontrak.",
            "pustaka": "",
        },
        "labels": {
            "expected_findings": [],
            "forbidden_findings": ["CON-PENALTY"],
            "expected_verdict": "GO",
            "is_trap": True,
            "trap_reason": "Denda memiliki plafon maksimal 5% sehingga tidak merupakan uncapped poison pill."
        }
    },
    {
        "id": "doc_17_sbu_expired",
        "title": "Masa Berlaku SBU Penyedia Telah Kedaluwarsa",
        "description": "Kekurangan kualifikasi penyedia: SBU sudah kedaluwarsa pada tahun 2022.",
        "input": {
            "package_name": "Pembangunan Gedung Arsip Digital",
            "dok_pemilihan": "Syarat Kualifikasi:\nPeserta wajib memiliki SBU bidang konstruksi yang masih berlaku.",
            "pustaka": "Sertifikat Badan Usaha (SBU) diterbitkan tanggal 10 Maret 2019, berlaku sampai 10 Maret 2022.",
        },
        "labels": {
            "expected_findings": [
                {"id": "ADM-SBU", "status": "GAP"}
            ],
            "forbidden_findings": [],
            "expected_verdict": "NO-GO",
            "is_trap": False
        }
    },
    {
        "id": "doc_18_sbu_valid_broken_lines",
        "title": "SBU Aktif dengan Garis Teks Terpotong Karakter Baris Baru",
        "description": "Teks ekstraksi PDF: Tanggal berlaku terpisah baris baru dan berlaku hingga 2030.",
        "input": {
            "package_name": "Pekerjaan Mekanikal Elektrikal",
            "dok_pemilihan": "Persyaratan Dokumen:\nPeserta wajib melampirkan SBU elektrikal.",
            "pustaka": "Lampiran Dokumen Perusahaan:\nSertifikat Badan Usaha (SBU) registrasi aktif\nberlaku sampai dengan\n25 Desember 2030 oleh LPJK.",
        },
        "labels": {
            "expected_findings": [
                {"id": "ADM-SBU", "status": "TERPENUHI"}
            ],
            "forbidden_findings": [],
            "expected_verdict": "GO",
            "is_trap": False
        }
    },
    {
        "id": "doc_19_kswp_valid_labeled",
        "title": "Status KSWP Valid Terkonfirmasi",
        "description": "Pemenuhan kewajiban pajak: Bukti KSWP terkonfirmasi aktif.",
        "input": {
            "package_name": "Pengadaan Seragam Pegawai",
            "dok_pemilihan": "Syarat Administrasi:\nWajib melampirkan Konfirmasi Status Wajib Pajak (KSWP).",
            "pustaka": "Bukti Layanan Pajak:\nKonfirmasi Status Wajib Pajak (KSWP): Status Valid Terkonfirmasi.",
        },
        "labels": {
            "expected_findings": [
                {"id": "ADM-KSWP", "status": "TERPENUHI"}
            ],
            "forbidden_findings": [],
            "expected_verdict": "GO",
            "is_trap": False
        }
    },
    {
        "id": "doc_20_kswp_invalid",
        "title": "Status KSWP Tidak Terkonfirmasi pada Sistem DJP",
        "description": "Kegagalan administrasi pajak: KSWP berstatus tidak terkonfirmasi.",
        "input": {
            "package_name": "Pengadaan Jasa Keamanan Gedung",
            "dok_pemilihan": "Syarat Kualifikasi:\nWajib melampirkan KSWP valid.",
            "pustaka": "Surat Keterangan Fiskal:\nStatus KSWP: tidak terkonfirmasi oleh Kantor Pelayanan Pajak.",
        },
        "labels": {
            "expected_findings": [
                {"id": "ADM-KSWP", "status": "GAP"}
            ],
            "forbidden_findings": [],
            "expected_verdict": "NO-GO",
            "is_trap": False
        }
    },
    {
        "id": "doc_21_warranty_12_months_vs_1_year",
        "title": "Pemenuhan Garansi 12 Bulan Memenuhi Syarat 1 Tahun",
        "description": "Jebakan ekuivalensi: Garansi 1 tahun dipenuhi dengan penawaran 12 bulan.",
        "input": {
            "package_name": "Pengadaan Switch Core Jaringan",
            "dok_pemilihan": "Syarat Dukungan Pabrikan:\nGaransi resmi perangkat minimal 1 tahun.",
            "pustaka": "Surat Jaminan Distributor:\nGaransi pabrikan diberikan selama 12 bulan purna jual.",
        },
        "labels": {
            "expected_findings": [
                {"id": "ADM-WARRANTY", "status": "TERPENUHI"}
            ],
            "forbidden_findings": [],
            "expected_verdict": "GO",
            "is_trap": True,
            "trap_reason": "Durasi garansi 12 bulan secara waktu setara dengan 1 tahun."
        }
    },
    {
        "id": "doc_22_warranty_deficient",
        "title": "Durasi Garansi Penawaran Kurang dari Ketentuan Syarat",
        "description": "Kekurangan penawaran: Syarat 3 tahun hanya ditawar 12 bulan.",
        "input": {
            "package_name": "Pengadaan Alat Pendingin Precision Data Center",
            "dok_pemilihan": "Syarat Teknis Utama:\nGaransi purna jual unit minimal 3 tahun.",
            "pustaka": "Brosur dan Surat Jaminan:\nGaransi kompresor dan sparepart 12 bulan.",
        },
        "labels": {
            "expected_findings": [
                {"id": "ADM-WARRANTY", "status": "GAP"}
            ],
            "forbidden_findings": [],
            "expected_verdict": "NO-GO",
            "is_trap": False
        }
    },
    {
        "id": "doc_23_empty_no_requirements",
        "title": "Dokumen Pengantar Umum Tanpa Syarat Pengadaan",
        "description": "Kasus negatif: Dokumen hanya berisi kata pengantar dan narasi umum tanpa klausul evaluasi.",
        "input": {
            "package_name": "Pengantar Renstra Institusi",
            "dok_pemilihan": "Dokumen ini merupakan pengantar rencana kerja tahunan lembaga pemerintah untuk sosialisasi umum.",
            "pustaka": "",
        },
        "labels": {
            "expected_findings": [],
            "forbidden_findings": [],
            "expected_verdict": "TIDAK ADA SYARAT TERBACA",
            "is_trap": True,
            "trap_reason": "Tidak memuat klausul persyaratan pengadaan apa pun."
        }
    },
    {
        "id": "doc_24_discriminatory_regional_assoc",
        "title": "Syarat Asosiasi Regional Diskriminatif ADCR-Jabar",
        "description": "Pelanggaran kualifikasi: Mewajibkan keanggotaan asosiasi lokal tertentu.",
        "input": {
            "package_name": "Pembangunan Fasilitas Modular Data Center",
            "dok_pemilihan": "Persyaratan Kualifikasi Tambahan:\nPenyedia wajib memiliki keanggotaan asosiasi regional ADCR-Jabar berstatus Gold Partner aktif.",
            "pustaka": "",
        },
        "labels": {
            "expected_findings": [
                {"id": "SPEC-REGIONAL-LOCKIN", "status": "GAP"}
            ],
            "forbidden_findings": [],
            "expected_verdict": "NO-GO",
            "is_trap": False
        }
    }
]

for doc in DOCS:
    doc_id = doc["id"]
    text_path = BENCHMARK_DIR / f"{doc_id}.txt"
    json_path = BENCHMARK_DIR / f"{doc_id}.labels.json"
    
    # Store complete input payload in text file with clear readable structure
    content_lines = [
        f"=== ID: {doc_id}",
        f"=== TITLE: {doc['title']}",
        f"=== PACKAGE: {doc['input']['package_name']}",
        "--- DOK_PEMILIHAN ---",
        doc["input"]["dok_pemilihan"],
        "--- PUSTAKA ---",
        doc["input"].get("pustaka", ""),
        "--- CONTRACT_DRAFT ---",
        doc["input"].get("contract_draft", ""),
        "--- ADENDUM ---",
        doc["input"].get("adendum", ""),
    ]
    text_path.write_text("\n".join(content_lines), encoding="utf-8")
    
    # Write labels
    labels_payload = {
        "id": doc_id,
        "title": doc["title"],
        "description": doc["description"],
        "input": doc["input"],
        "expected_findings": doc["labels"]["expected_findings"],
        "forbidden_findings": doc["labels"].get("forbidden_findings", []),
        "expected_verdict": doc["labels"]["expected_verdict"],
        "is_trap": doc["labels"].get("is_trap", False),
        "trap_reason": doc["labels"].get("trap_reason"),
    }
    json_path.write_text(json.dumps(labels_payload, indent=2, ensure_ascii=False), encoding="utf-8")

print(f"Successfully generated {len(DOCS)} held-out benchmark documents in {BENCHMARK_DIR}/")

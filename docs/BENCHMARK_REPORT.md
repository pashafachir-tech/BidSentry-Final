# Laporan Benchmark BidSentry

_Dihasilkan otomatis oleh `scripts/run_benchmarks.py` pada 2026-11-09T19:08:43+0700. Jangan edit manual._

**Mesin:** deterministic rules only (AI extraction disabled). **Unit:** red flag = finding with status GAP or EXPIRING, or REVIEW held only because its numeric threshold is unverified; matched by rule family.

> Semua set deteksi red flag disusun tim dan pernah dipakai saat pengembangan. Angka ini adalah uji regresi, bukan estimasi akurasi lapangan. Klaim akurasi memerlukan dokumen tender nyata berlabel independen (rencana pilot 5 rekanan).

## Ringkasan untuk slide

| Set | Dokumen | Precision (95% CI) | Recall (95% CI) | F1 | False positive | Verdict benar | Independen dari pengembangan? |
| --- | ---: | --- | --- | ---: | ---: | --- | --- |
| Development regression (24 dokumen) | 24 | 100.0% (77–100%) | 100.0% (77–100%) | 100.0% | 0 | 23/24 | Tidak |
| Traps v2 (10 dokumen jebakan) | 10 | 100.0% (34–100%) | 100.0% (34–100%) | 100.0% | 0 | 10/10 | Tidak |
| Blind v1 (10 dokumen) | 10 | 100.0% (61–100%) | 100.0% (61–100%) | 100.0% | 0 | 10/10 | Tidak |
| Narasi anggaran (5 dokumen) | 5 | 75.0% (30–95%) | 100.0% (44–100%) | 85.7% | 1 | 4/5 | Tidak |
| Fixture sintetis (2 paket) | 2 | 100.0% (34–100%) | 100.0% (34–100%) | 100.0% | 0 | — | Tidak |
| Halaman LPSE publik (1 dokumen nyata) | 1 | 100.0% (34–100%) | 100.0% (34–100%) | 100.0% | 0 | — | Ya |

- **Gabungan semua set sintetis** (51 dokumen): precision 96.3% (82–99%), recall 100.0% (87–100%), **1 false positive**, 0 false negative.
- **Tanpa set development** (27 dokumen): precision 92.9% (69–99%), recall 100.0% (77–100%), 1 false positive, 0 false negative.
- **Dokumen nyata yang independen dari tuning:** 1 (halaman LPSE publik; mengukur pengenalan syarat, bukan deteksi pelanggaran).
- **Panjang dokumen uji:** median 269 karakter. Dokumen tender nyata umumnya puluhan hingga ratusan halaman, sehingga set ini menguji pola klausul, bukan dokumen utuh.
- **Permintaan bukti tambahan** (status REVIEW di luar label, tidak dihitung sebagai positif): 4.

## Pengaruh pemetaan ID (strict vs family)

| Set | Precision strict-ID | Recall strict-ID | Precision family | Recall family |
| --- | ---: | ---: | ---: | ---: |
| Development regression (24 dokumen) | 100.0% | 100.0% | 100.0% | 100.0% |
| Traps v2 (10 dokumen jebakan) | 100.0% | 100.0% | 100.0% | 100.0% |
| Blind v1 (10 dokumen) | 33.3% | 28.6% | 100.0% | 100.0% |
| Narasi anggaran (5 dokumen) | 75.0% | 100.0% | 75.0% | 100.0% |
| Fixture sintetis (2 paket) | 100.0% | 100.0% | 100.0% | 100.0% |
| Halaman LPSE publik (1 dokumen nyata) | 100.0% | 100.0% | 100.0% | 100.0% |

Strict-ID menghitung label lama (mis. `FIN-HPS-OVER-PAGU`) sebagai miss walau engine mendeteksi konsep yang sama (`FIN-OVER-BUDGET`).

## Kesalahan yang tersisa (apa adanya)

- **Development regression (24 dokumen) / doc_05_compressed_timeline_bid_prep** — verdict BELUM CUKUP BUKTI (label NO-GO)
- **Narasi anggaran (5 dokumen) / budget_02_prose_within_budget** — verdict BELUM CUKUP BUKTI (label GO)
- **Narasi anggaran (5 dokumen) / budget_03_prose_hps_over_pagu** — FP: `PROC-TIMELINE`

## Label yang perlu ditinjau ahli

- **budget_03_prose_hps_over_pagu** — Dokumen menulis 'pemasukan penawaran 6 hari kerja'. Aturan memakai ambang 7 hari kerja (config/rules.yaml), sehingga engine menandai PROC-TIMELINE, sedangkan label tidak. Dihitung sebagai FP sampai ahli pengadaan memutuskan ambang yang benar untuk metode pemilihan paket ini.
- **budget_02_prose_within_budget** — Verdict BELUM CUKUP BUKTI karena NPWP/NIB diminta tetapi bukti penyedia tidak dilampirkan; label mengharapkan GO.

## Asal-usul tiap set

- **Development regression (24 dokumen)** (`data/benchmark`): In-sample: dokumen ini dipakai saat menyusun dan menyetel aturan regex.
- **Traps v2 (10 dokumen jebakan)** (`data/test_traps_v2`): Disusun tim setelah perbaikan bug false positive; dipakai sebagai regression guard.
- **Blind v1 (10 dokumen)** (`data/test_blind`): Disusun tim (scripts/generate_blind_set.py). Setelah putaran pertama engine dikalibrasi pada set ini (lihat docs/BENCHMARK_RESULTS.md), jadi tidak lagi independen.
- **Narasi anggaran (5 dokumen)** (`data/test_narrative_budget`): Disusun tim untuk menguji angka pagu/BoQ dalam prosa bebas. Miss budget_03 dilihat lalu diperbaiki secara umum (normalizer Rupiah + batas kata kunci), jadi set ini juga in-sample.
- **Fixture sintetis (2 paket)** (`data/sample_tenders`): Fixture regresi sintetis untuk SBU kedaluwarsa dan jaminan penawaran.
- **Halaman LPSE publik (1 dokumen nyata)** (`data/public_lpse`): Satu halaman pengumuman LPSE nyata, dianotasi satu orang. Mengukur pengenalan syarat, bukan deteksi pelanggaran.

## Cara menjalankan ulang

```bash
python scripts/run_benchmarks.py
```

# BidSentry (v4.2)
### Platform Intelijen Audit Pengadaan & Sintesis Forensik Lintas-Dokumen Tender Publik

[![Continuous Integration](https://github.com/pashafachir-tech/BidSentry/actions/workflows/ci.yml/badge.svg)](https://github.com/pashafachir-tech/BidSentry/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688.svg)](https://fastapi.tiangolo.com)
[![IBM watsonx](https://img.shields.io/badge/IBM-watsonx.ai-052FAD.svg)](https://www.ibm.com/watsonx)
[![Tests Passing](https://img.shields.io/badge/tests-318%20passed-brightgreen.svg)](tests/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## 📌 Sekilas Masalah: Realitas Pengadaan Publik Indonesia

Setiap tahunnya, pengadaan barang dan jasa pemerintah (PBJP) di Indonesia mengelola anggaran lebih dari **Rp1.259,2 Triliun** (Siaran Pers LKPP No. 01/SP-Ses.3/01/2025). Namun, proses evaluasi dokumen tender masih dilakukan secara terpisah dan manual:
- ⏳ **Tantangan Review Manual**: Proses penelaahan dokumen Kerangka Acuan Kerja (KAK), spesifikasi teknis, Berita Acara Adendum, dan Bill of Quantities (BoQ) membutuhkan pembacaan mendalam lintas berkas; estimasi waktu review manual belum diverifikasi secara empiris.
- ⚠️ **Kecurangan & Celah Hukum Tersembunyi**: Praktik penguncian merek (*brand lock-in* eksklusif tanpa opsi setara), jadwal lelang yang sengaja dipersingkat (*compressed timeline*), denda keterlambatan tanpa batas (*uncapped poison pill*), serta pembengkakan anggaran (*over-budget* BoQ) sering kali luput dari pengawasan karena terselip di antara tumpukan dokumen yang berbeda.
- 🔄 **Ketidaksinkronan Antar-Berkas yang Terabaikan**: Dokumen pengadaan tidak pernah berdiri sendiri. Benturan data antara apa yang disyaratkan di KAK, apa yang ditawarkan penyedia di BoQ, apa yang diubah di Adendum, dan apa yang disepakati di draf kontrak sering kali tidak terdeteksi sebelum kontrak ditandatangani.
- ⚖️ **Asimetri Informasi Pelaku Usaha**: Peserta tender dan UMKM sering kali gugur bukan karena mutu teknis, melainkan karena jebakan klausul administratif atau ketiadaan waktu menyusun draf sanggahan resmi sesuai batas waktu LKPP.

### 📊 Landasan Masalah & Data Kuantitatif Resmi

Pengembangan BidSentry berpijak pada data resmi instansi audit dan pengawas pengadaan nasional:

1. **Volume Pasar Pengadaan (LKPP)**:
   * Total Rencana Umum Pengadaan (RUP) nasional TA 2024 tercatat sebesar **Rp1.259,2 Triliun** (Siaran Pers LKPP No. 01/SP-Ses.3/01/2025).
   * Ekosistem penyedia didominasi oleh pelaku usaha kecil, dengan **396.648 UMK terdaftar di SIKaP LKPP** (81% dari total seluruh pelaku usaha terdaftar).

2. **Temuan Audit Anggaran & BoQ (BPK RI - IHPS I 2024)**:
   * BPK mengungkap permasalahan **kekurangan volume pekerjaan/barang senilai Rp1,02 Triliun** (1.200 temuan pada 531 instansi) serta **kelebihan pembayaran senilai Rp156,96 Miliar** (401 temuan). Angka ini menunjukkan skala kerugian di hilir; kekurangan volume umumnya ditemukan saat pelaksanaan, sehingga BidSentry menyasar pencegahan di tahap dokumen, bukan pemeriksaan fisik pekerjaan.

3. **Persekongkolan Tender (KPPU RI)**:
   * Berdasarkan Laporan Tahunan KPPU, dugaan persekongkolan tender (Pasal 22 UU No. 5/1999) secara konsisten mendominasi laporan persaingan usaha nasional, mencapai **71% dari seluruh laporan yang diterima**.

4. **Kerentanan Korupsi Sektor PBJ (KPK RI)**:
   * Data penanganan perkara KPK (2004–2025) mencatat **25,03% kasus korupsi (446 dari 1.782 perkara)** berkaitan langsung dengan pengadaan barang dan jasa.
   * Survei Penilaian Integritas (SPI) 2024 KPK menemukan risiko benturan kepentingan tinggi, dengan **49% responden mengonfirmasi adanya indikasi pemenang tender yang telah diatur**.

**BidSentry** hadir sebagai solusi kecerdasan buatan hibrida (*Local-First Deterministic Engine + IBM watsonx.ai*) yang mengkorelasikan seluruh berkas tender dalam satu ruang kerja intelijen: throughput mesin lokal terukur (latensi eksekusi `engine_duration_ms` pada benchmark); estimasi waktu review manual belum diverifikasi, dengan jaminan kutipan bukti 100% persis (*exact substring verification*).

---

## 🚀 Fitur Unggulan Utama

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│               SINTESIS FORENSIK BERKAS PROYEK PENGADAAN (BIDSENTRY v4.2)               │
├────────────────────────────────────────────────────────────────────────────────────────┤
│   [ KAK / SPESIFIKASI ] ───► [ HPS & RINCIAN BoQ ] ───► [ PENAWARAN PENYEDIA ]        │
│             │                            │                          │                  │
│             └──────────────┬─────────────┴──────────────┬───────────┘                  │
│                            ▼                            ▼                              │
│               [ ADENDUM BAPP PENGADAAN ] ───► [ DRAF SURAT PERJANJIAN (SPK) ]          │
│                                          │                                             │
│                                          ▼                                             │
│      ┌──────────────────────────────────────────────────────────────────────────┐      │
│      │ 1. MERANGKUP APA: Resume Ruang Lingkup, Pagu Anggaran, & Peta 5 Berkas   │      │
│      │ 2. KELEMAHAN: Celah Regulasi, Kualifikasi Kedaluwarsa, & Poison Pills   │      │
│      │ 3. KETIDAKSINKRONAN: Benturan KAK vs BoQ, Perubahan Adendum, & Timeline │      │
│      └──────────────────────────────────────────────────────────────────────────┘      │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

### 1. 📑 Sintesis Forensik Lintas-Dokumen (Cross-Document Intelligence)
Dokumen dalam satu paket pengadaan saling berhubungan erat. Di bawah riwayat audit, BidSentry menyediakan modul sintesis eksekutif otomatis yang membedah proyek ke dalam **3 Pilar Forensik**:
- **Pilar A: Merangkup Apa (Lingkup & Profil Proyek)**:
  - Menyajikan ringkasan ruang lingkup pekerjaan utama (*Scope of Work*) yang dianalisis mesin.
  - Memetakan nilai pagu anggaran/HPS serta status keterkaitan 5 berkas utama: KAK & Spesifikasi Teknis, HPS & BoQ/RAB, Dokumen Penawaran Penyedia, Berita Acara Adendum (BAPP), dan Draf Kontrak SPK.
- **Pilar B: Kelemahan & Celah Regulasi (Vulnerabilities)**:
  - Deteksi otomatis indikasi penguncian merek spesifik yang berpotensi melanggar **Pasal 19 ayat (2) Perpres 16/2018 sebagaimana diubah terakhir dengan Perpres 46/2025**. Pengecualian suku cadang, bagian sistem yang sudah ada, dan katalog elektronik ditandai perlu telaah, bukan pelanggaran.
  - Peringatan dokumen kualifikasi yang absen atau izin operasional yang mendekati masa kedaluwarsa ($\le$ 30 hari).
  - Peringatan klausul denda tanpa batas maksimal (*Poison Pill*) beserta simulasi nominal paparan risiko keuangan (*Financial Exposure*).
- **Pilar C: Ketidaksinkronan Antar-Berkas (Cross-Document Discrepancies)**:
  - **Benturan KAK vs Penawaran/BoQ**: Spesifikasi yang diminta pada KAK tidak diimbangi surat dukungan atau bukti kesetaraan pada berkas penawaran rekanan.
  - **Benturan Adendum vs Syarat Awal (*Contract Dilution*)**: Deteksi klausul yang diubah, digugurkan, atau dilonggarkan secara sepihak melalui Berita Acara Adendum dibandingkan dokumen pemilihan awal.
  - **Benturan Jadwal & Batas Waktu**: Masa sanggah di bawah **5 hari kalender setelah pengumuman pemenang (Lampiran Peraturan LKPP 12/2021)** menjadi temuan. Masa penawaran yang pendek hanya ditandai perlu telaah, karena angka minimumnya tidak ditemukan pada naskah regulasi.

### 2. 🔗 Matriks Keterlacakan Silang Antar-Dokumen (Traceability Matrix)
Tabel visual interaktif yang memetakan perjalanan setiap ketentuan penting:
$$\text{Ketentuan KAK Awal} \quad\longrightarrow\quad \text{Modifikasi Adendum} \quad\longrightarrow\quad \text{Respon Bukti Penyedia} \quad\longrightarrow\quad \text{Status Forensik Sinkronisasi}$$
Auditor dan reviewer dapat langsung melihat apakah suatu syarat berstatus `TERPENUHI · SINKRON`, `KESENJANGAN / BENTURAN`, atau `DIUBAH ADENDUM`.

### 3. 📁 Manajemen Proyek Berbasis Folder & Antarmuka Modern
- **Sidebar Folder Proyek**: Bilah navigasi kiri ditata layaknya penjelajah proyek rapi dengan tombol **`+ Add new project`**, badge jumlah proyek aktif, dot indikator risiko tender, dan pemilihan instan.
- **Dukungan Dark Mode Menyeluruh**: Desain antarmuka responsif yang nyaman di mata dengan palet tema gelap kontras tinggi tanpa kebocoran warna terang.

### 4. 🎯 Peran Pengguna Ganda (Dual-Perspective Mode)
Pengguna dapat berganti sudut pandang dengan satu klik di topbar:
* **Mode Panitia / Pokja**:
  - Evaluasi kepatuhan rekanan terhadap regulasi pengadaan.
  - Skrining potensi kolusi dan kesamaan dokumen (UU 5/1999 Pasal 22) tersedia lewat API `/api/v1/audit/comprehensive`; belum ada di antarmuka.
  - Generator draf **Berita Acara Hasil Evaluasi** berformat DOCX dari audit tersimpan.
* **Mode Peserta / Vendor**:
  - *Pre-flight bid check* sebelum submit ke portal LPSE untuk memastikan tidak ada berkas yang kurang.
  - Generator surat sesuai tahap tender, dengan kutipan persis: **Permohonan Penjelasan** sebelum penawaran, atau **Sanggahan** setelah pengumuman pemenang (hanya peserta yang menyampaikan penawaran, melalui SPSE, 5 hari kalender).

---

## 💡 Kedalaman Teknologi & Pengamanan Data

### 🛡️ 1. Keamanan Kriptografis: SHA-256 Hash Chained Audit Trail
* **Bahasa Awam (Buku Kas Digital Bersegel Anti-Manipulasi)**:  
  Sama seperti buku kas notaris yang setiap halamannya distempel dan diparaf berantai, setiap kali audit dijalankan atau catatan reviewer ditambahkan, sistem mencatatnya dalam rantai segel digital. Jika ada yang mengubah hasil vonis langsung di berkas log, verifikasi gagal dan tab jejak audit menampilkan peringatan integritas (*tamper-evident*). Penghapusan audit yang sah meninggalkan jejak, tidak memutus rantai.
* **Bahasa Teknis**:  
  Setiap entri log audit diikat secara berantai menggunakan algoritma kriptografis SHA-256 ([`bidsentry/lib/audit_log.py`](bidsentry/lib/audit_log.py) dan [`bidsentry/core/audit_trail.py`](bidsentry/core/audit_trail.py) via fungsi `verify_chain()`). Setiap record memuat `previous_hash`, `hash`, dan segel HMAC (`mac`), sehingga menghitung ulang hash saja tidak cukup untuk memalsukan log. Status dicek saat server mulai dan lewat `GET /api/audit-log/verify`. Kunci segel tersimpan di server, jadi pihak yang menguasai server tetap harus ditangani dengan kontrol akses.

### 🔒 2. Sensor Data Pribadi Otomatis (Deterministic PII Scrubbing)
* **Bahasa Awam (Penghapus Data Pribadi Otomatis)**:  
  Dokumen tender sering kali memuat KTP pengurus atau buku rekening bank. Sebelum dokumen dikirim atau diproses oleh kecerdasan buatan, sistem secara otomatis menyamarkan data pribadi tersebut demi mematuhi UU Perlindungan Data Pribadi (UU PDP).
* **Bahasa Teknis**:  
  Modul redaksi deterministik ([`bidsentry/lib/pii.py`](bidsentry/lib/pii.py)) menyensor NIK (16 digit, termasuk format berspasi atau bertanda hubung), NPWP, nomor rekening berlabel, telepon seluler dan kantor, email, serta nama dan alamat yang berlabel sebelum naskah dikirim ke model. Bila pola PII masih terdeteksi, panggilan AI dibatalkan. Nama dan alamat tanpa label belum tersensor.

### 🤖 3. Model Fondasi via IBM watsonx.ai
* **Bahasa Awam (AI Khusus Dokumen Regulasi & Bisnis)**:  
  AI hanya dipakai untuk menemukan kutipan klausul di dokumen, lewat platform enterprise **IBM watsonx.ai**. Setiap kutipan dicek persis ada di naskah asli, lalu dinilai ulang oleh aturan Python. Merek yang tidak ada di daftar aturan tetap ditampilkan sebagai kandidat untuk dicek manusia. AI tidak pernah memutuskan risiko atau menghitung angka.
* **Bahasa Teknis**:  
  Terintegrasi via SDK `ibm-watsonx-ai` ([`WatsonxService`](bidsentry/services/watsonx_service.py)) memakai watsonx Chat API dengan temperatur 0 (model default `mistralai/mistral-small-3-1-24b-instruct-2503`, dapat diganti via `WATSONX_MODEL_ID`), cuplikan maksimal 48.000 karakter per audit, pra-pemeriksaan guardrail lokal, serta mekanisme fallback anggun ke mesin aturan lokal dan visual pipeline Langflow ([`tender_extraction_flow.json`](langflow/tender_extraction_flow.json)).

### ✍️ 4. Grounded Legal Generator (Exact Substring Verification)
* **Bahasa Awam (Kutipan Selalu Bisa Ditelusuri)**:
  Setiap kutipan dokumen di surat sanggahan dan Berita Acara harus berupa kalimat yang benar-benar ada di dokumen tender. Kutipan yang tidak ditemukan persis di naskah ditolak. Dasar hukum diambil dari katalog aturan, bukan dikarang AI, dan setiap pasal diberi status verifikasi: **diperiksa dari naskah**, **diperiksa dari sumber sekunder**, atau **perlu verifikasi hukum**. Pasal berstatus terakhir wajib dicek ahli hukum sebelum dokumen dikirim.
* **Bahasa Teknis**:  
  Berita Acara, surat klarifikasi, dan surat ke Pokja mengambil temuan dari audit tersimpan; kutipan yang tidak cocok persis (*exact substring*) dengan teks sumber audit ditolak.

### ⚖️ 5. Keadilan Algoritmik UMKM (Algorithmic Fairness)
* Indeks risiko eksekusi proyek (modul API, belum di antarmuka) menormalkan setiap komponen terhadap nilai tender, sehingga penyedia kecil tidak otomatis dinilai lebih berisiko hanya karena skala usahanya. Indeks ini adalah triase, bukan probabilitas, dan tidak menggantikan ketentuan pencadangan paket untuk usaha kecil (**Pasal 65 Perpres 12/2021**). Relaksasi persyaratan kualifikasi khusus UMKM **belum** diimplementasikan sebagai aturan.

---

## 💼 Model Bisnis & Aksesibilitas (Micro-SaaS)

BidSentry mengadopsi model **Lean Micro-Utility & Micro-SaaS** yang membumi dan dirancang tanpa friksi birokrasi bagi ekosistem pengadaan barang/jasa:

| Skema Layanan | Sasaran Pengguna | Biaya & Model Pembayaran | Fitur & Benefit Inklusif |
| :--- | :--- | :--- | :--- |
| **Pay-Per-Audit (QRIS Instant)** | Kontraktor CV / UMKM (H-1 lelang) | **Rp 5.000 / 10 kali audit** (efektif **Rp 500 / dokumen**) | Scan kilat KAK/BoQ, validasi 31 aturan deterministik, verifikasi batas denda & over-budget. |
| **Vendor Pro (Langganan)** | Kontraktor Aktif LPSE (Rutin lelang) | **Rp 300.000 / bulan** (setara **Rp 10.000 / hari**) | Kuota 30 tender/bln, deteksi klausul diskriminatif, generator draf surat penjelasan/sanggahan (.docx). |
| **BUMD / BLUD Pilot** | RSUD BLUD / BUMD Daerah / Satuan Pengawas | **Rp 800.000 / bulan** (setara **Rp 9,6 Jt / thn** — SPK Langsung) | Kuota 100 dokumen/bln, audit BoQ vs HPS, skrining kolusi (rencana antarmuka, kini lewat API), generator Berita Acara (.docx). |

> **Status implementasi:** harga di atas adalah hipotesis. Pembayaran QRIS, kuota, dan akun per pelanggan belum dibangun; versi ini memakai dua peran per server. Dalam mode SaaS dokumen diproses di server BidSentry, sedangkan mode lokal tersedia untuk instalasi mandiri.

### 🧭 Matriks Lanskap Kompetitif Singkat

| Alternatif Solusi | Cakupan Analisis | Kelemahan Utama | Posisi BidSentry (Neuro-Symbolic + IBM watsonx.ai) |
| :--- | :--- | :--- | :--- |
| **SPSE / LPSE LKPP** | Repositori transaksi lelang | Tidak ada engine audit isi dokumen | **Mitra Komplementer**: Audit mandiri pre-flight pra-submit berkas ke SPSE |
| **Platform Info Tender (TenderPlus, dsb.)** | Notifikasi peluang lelang | Hanya scraping judul & pagu luar | **Audit Kedalaman Teknis**: Membedah detail KAK, BoQ Excel, dan draf kontrak |
| **Enterprise AI Global (Luminance, Kira)** | Kontrak korporasi global | Ratusan juta/thn, buta hukum Perpres LKPP | **Spesifik Regulasi Lokal**: Selaras Perpres 12/2021 dengan harga mikro QRIS |
| **Generic LLM Chatbot (ChatGPT, Claude)** | Analisis teks umum | Risiko halusinasi hitung BoQ & bocor data rahasia | **Grounded & Terlindungi**: Verifikasi matematika deterministik + PII Scrubber lokal |

*Rincian analisis unit economics, TAM/SAM/SOM, dan parit pertahanan kompetitif (*moat*) disajikan lengkap pada [**docs/MONETIZATION_STRATEGY.md**](docs/MONETIZATION_STRATEGY.md).*

## 📊 Hasil Benchmark & Pengujian Nyata

Angka dihasilkan otomatis oleh `python scripts/run_benchmarks.py` ke [docs/BENCHMARK_REPORT.md](docs/BENCHMARK_REPORT.md) (micro-average, interval Wilson 95%, pencocokan per *rule family*). Aplikasi menampilkan ringkasan yang sama secara langsung pada kartu **Validasi Empiris**.

| Ringkasan (51 dokumen sintetis berlabel) | Nilai |
| :--- | :--- |
| Precision | 96,3% (CI 95% 82–99%) |
| Recall | 100% (CI 95% 87–100%) |
| False positive / false negative | 1 / 0 |
| Dokumen nyata yang independen dari pengembangan | 1 (halaman LPSE publik, 253 karakter) |
| Median panjang dokumen uji | sekitar 270 karakter |

> **Cara membaca angka ini:** semua set deteksi red flag disusun tim dan pernah dilihat saat pengembangan, sehingga angka di atas adalah **uji regresi**, bukan estimasi akurasi lapangan. Satu false positive yang tersisa (`budget_03`, jadwal 6 hari kerja terhadap ambang 7) adalah perbedaan label yang dicatat di laporan, bukan disembunyikan. Set ini menguji pola klausul pendek, bukan dokumen utuh. Klaim akurasi memerlukan dokumen tender nyata berlabel independen (rencana pilot 5 rekanan). Verdict `doc_05` kini sengaja berbeda dari label lamanya: masa penawaran pendek menjadi BELUM CUKUP BUKTI karena ambangnya tidak ditemukan di regulasi. Hasil pada 4 PDF tender publik dicatat di [REAL_DOCUMENT_TEST.md](docs/REAL_DOCUMENT_TEST.md) dan belum diperiksa pihak independen.

### ⚠️ Batasan yang Diketahui (Known Limitations)
- **Data uji belum independen**: lihat catatan di atas; belum ada korpus dokumen tender nyata berlabel independen.
- **Cakupan Aturan Berbasis Pola Teks**: Deteksi didasarkan pada ekspresi reguler dan pencocokan leksikal deklaratif; belum mencakup inferensi semantik mendalam tanpa model bahasa.
- **Daftar Merek Terbatas**: Di luar aturan TI, merek dikenali dari daftar `brand_watchlist` di `config/rules.yaml` dan hanya memicu telaah manusia. Merek di luar daftar perlu ekstraksi AI agar muncul sebagai kandidat.
- **Belum Ada OCR**: PDF hasil pindai belum dapat diaudit, dan ukuran unggahan dibatasi 8 MB.
- **Akun Pengguna**: Pemisahan baru per peran (Pokja/Vendor), belum per orang atau per organisasi.
- **Dukungan Bahasa Dokumen**: Utamanya dioptimalkan untuk bahasa Indonesia pengadaan (istilah LPSE, KAK, HPS, DIPA); belum mencakup dokumen berbahasa Inggris penuh selain frasa kunci jadwal dan ekuivalensi dasar.
- **Deteksi Diskriminasi Regional Terbatas**: Baru mencakup pola pembatasan domisili, keanggotaan asosiasi, dan kantor cabang spesifik wilayah tertentu.
- **Lokasi pemrosesan AI**: ekstraksi AI bersifat opsional dan hanya berjalan setelah pengguna memberi persetujuan per audit. Teks yang sudah disensor PII-nya diproses di proyek IBM watsonx.ai region Tokyo (`jp-tok`), yaitu di luar Indonesia. Organisasi yang memakai BidSentry perlu memastikan hal ini sesuai kebijakan transfer data lintas negara (UU 27/2022 tentang Pelindungan Data Pribadi, Pasal 56). Tanpa persetujuan, seluruh analisis berjalan lokal tanpa mengirim data keluar.
- **Ketahanan Prompt Injection**: Engine aturan lokal 100% kebal prompt injection karena bersifat deterministik tanpa LLM; namun jalur LLM eksternal opsional (watsonx/Langflow) hanya dilindungi oleh penyensoran pola PII dan validasi kutipan exact substring sebelum inferensi.

---

## ⚡ Panduan Memulai Cepat (Quickstart)

### Prasyarat
- Python 3.11 atau lebih baru
- Sistem Operasi: Windows, macOS, atau Linux

### Instalasi & Menjalankan Server

```bash
# 1. Clone repositori
git clone https://github.com/pashafachir-tech/BidSentry.git
cd BidSentry

# 2. Pasang dependensi inti (tambahkan requirements-dev.txt untuk tes & lint)
pip install -r requirements.txt

# 3. Jalankan server lokal
python server.py
```

Buka peramban Anda di **`http://127.0.0.1:8000`**.  
Sistem berjalan secara mandiri (*zero-build step*) tanpa perlu instalasi Node.js atau kompilasi frontend yang rumit.

---

## 🎤 Demo Panggung (Stage Runner)

```bash
# Pindahkan riwayat audit lama ke backups/ lalu siapkan dua paket demo sintetis
python scripts/seed_demo.py
python server.py
```

| Tombol | Aksi |
| :---: | :--- |
| `1` | Masuk sebagai **Pokja** dan buka **Paket A** (konstruksi: HPS melampaui pagu + denda tanpa batas → Risiko Kritis) |
| `2` | Masuk sebagai **Vendor** dan buka **Paket B** (jaringan: lock-in merek + selisih BoQ Rp15.000.000 → Risiko Tinggi) |
| `Esc` | Tutup dialog/overlay |

Tombol tidak aktif saat sedang mengetik di form. Paket demo berjalan tanpa pengiriman teks ke provider AI. Untuk menunjukkan watsonx langsung, jalankan audit baru dengan persetujuan AI lalu buka tab jejak audit; `python scripts/verify_watsonx.py --generate` memeriksa koneksi sebelum tampil.

---

## 🧪 Rangkaian Pengujian Mandiri (318 Test Cases)

Seluruh komponen dapat diverifikasi secara independen oleh juri teknis melalui perintah berikut:

```bash
# 1. Seluruh unit, integration, chaos/fuzzing, dan contract test (hermetik: koneksi internet diblokir)
python -X dev -m pytest tests/

# 2. Seluruh benchmark berlabel (menulis docs/BENCHMARK_REPORT.md)
python scripts/run_benchmarks.py

# 3. Verifikasi status integrasi IBM watsonx (exit 0 aman); tambahkan --generate untuk satu panggilan model nyata
python scripts/verify_watsonx.py

# 4. Ekstraksi PDF nyata & BoQ Excel
python -m pytest tests/test_pdf_real_extraction.py -v

# 5. Uji end-to-end di browser (login -> Demo A Pokja -> jejak audit -> Demo B Vendor)
#    sekaligus memperbarui docs/screenshots/ (butuh: pip install playwright && playwright install chromium)
python scripts/capture_screenshots.py
```

> Satu-satunya warning yang difilter adalah peringatan Starlette agar `TestClient` memakai `httpx2` (tertulis di `tests/conftest.py`); filter itu dapat dihapus setelah `httpx2` dipasang di lingkungan test.

> **Tangkapan layar hasil uji E2E:** [login peran](docs/screenshots/01_login_peran.png) · [command center Pokja](docs/screenshots/02_command_center_pokja.png) · [hasil Demo A](docs/screenshots/03_hasil_pokja_demo_a.png) · [jejak audit AI → Python](docs/screenshots/04_jejak_audit_ai_python.png) · [hasil Demo B Vendor](docs/screenshots/05_hasil_vendor_demo_b.png).

---

## 📚 Dokumentasi Teknis & Produk

- 💰 [**Strategi Monetisasi & Micro-SaaS**](docs/MONETIZATION_STRATEGY.md) — Model Micro-Utility & Micro-SaaS, pricing eceran QRIS, proyeksi bottom-up TAM/SAM/SOM, dan lanskap kompetitor.
- 🏗️ [**Peta Arsitektur**](docs/ARCHITECTURE.md) — Struktur arsitektur backend, konsolidasi modul finansial, dan data flow.
- 🧠 [**Model & System Card**](docs/MODEL_CARD.md) — Kebijakan vonis deterministik, mitigasi bias etika, dan batasan operasional.
- 📊 [**Laporan Benchmark Resmi**](docs/BENCHMARK_REPORT.md) — Angka terkini yang dihasilkan otomatis dan dijaga CI.
- 🔬 [**Riwayat Benchmark per Iterasi**](docs/BENCHMARK_RESULTS.md) — Catatan historis per dokumen uji dan mitigasi false positive.
- 📝 [**Catatan Perubahan**](docs/CHANGELOG.md) — Riwayat versi dari v2.0 hingga v4.1.
- 🏛️ [**Analisis Komparatif Kompetitif**](docs/COMPETITIVE_COMPARISON.md) — Matriks perbandingan objektif vs Review Manual, Software Kontrak Global, dan Chatbot LLM Generik.

---

## 🏛️ Lisensi & Kepatuhan Regulasi Nasional

Proyek ini dilisensikan di bawah lisensi **[MIT](LICENSE)**.  
Seluruh logika evaluasi dan modul forensik dirancang merujuk pada regulasi Republik Indonesia:
- **Perpres No. 16 Tahun 2018** sebagaimana diubah dengan **Perpres No. 12 Tahun 2021** dan **Perpres No. 46 Tahun 2025** tentang Pengadaan Barang/Jasa Pemerintah.
- **UU No. 5 Tahun 1999 Pasal 22** tentang Larangan Praktik Monopoli dan Persaingan Usaha Tidak Sehat.
- **UU No. 27 Tahun 2022** tentang Pelindungan Data Pribadi (UU PDP).
- **Peraturan LKPP No. 12 Tahun 2021** sebagaimana diubah dengan **Peraturan LKPP No. 4 Tahun 2024** tentang Pedoman Pelaksanaan Pengadaan Barang/Jasa Pemerintah Melalui Penyedia.

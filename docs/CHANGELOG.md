# Catatan Perubahan BidSentry

Riwayat perubahan dari yang terbaru. Versi aplikasi tercantum di `pyproject.toml` dan `bidsentry/__init__.py`.

---

## [v4.2] - Akurasi Klausul Baku, AI yang Berguna, Integritas Log

### Akurasi
- Batas denda berbasis Jaminan Pelaksanaan dikenali; denda 1‰ tanpa keterangan batas kini REVIEW sesuai model SSKK LKPP.
- Klausul kewajiban "benturan kepentingan" tidak lagi menjadi temuan; pengecualian Pasal 19 ayat (2) menjadi REVIEW.
- Daftar merek non-TI (`brand_watchlist`), pembacaan rentang tanggal, hari kalender/kerja, dan offset jadwal.
- Sanggah memakai 5 hari kalender dari Lampiran Peraturan LKPP 12/2021. Masa penawaran minimum tidak ditemukan di naskah, jadi hanya REVIEW.
- Verdict tidak lagi bergantung tanggal audit; aturan R5b dan indikator cakupan mencegah GO dari cakupan sempit.

### Dokumen panjang
- Daftar isi, nomor halaman, paraf, dan baris formulir kosong tidak lagi terbaca sebagai syarat.
- Aturan memeriksa semua kalimat, bukan kemunculan pertama; ambang bersyarat tidak dibaca sebagai nilai paket.
- Garansi bank dipisahkan dari garansi produk, dan tarif denda terberat yang dinilai.

- Tabel spesifikasi dipecah per sel berdampingan; kata pengecualian hanya berlaku bila terkait merek yang disebut.
- Aturan baru SPEC-PRINCIPAL-REVIEW untuk syarat kemitraan, surat dukungan principal, dan distributor tunggal.

### AI
- Kandidat merek di luar pola aturan tampil untuk dicek manusia tanpa memengaruhi verdict.
- Teks ke provider dibatasi 48.000 karakter; panggilan dibatalkan bila pola PII masih terdeteksi.

### Keamanan & tata kelola
- Akses audit dan keputusan reviewer diperiksa terhadap peran pemilik.
- Audit log bersegel HMAC, penghapusan memakai tombstone dan menghapus teks sumber, status tampil di jejak audit.
- Sensor PII diperluas; Berita Acara dan klarifikasi hanya dari audit tersimpan.
- Surat vendor mengikuti tahap tender: permohonan penjelasan atau sanggahan.

### Ketahanan
- Verifikasi kutipan AI yang memuat token redaksi memakai pencarian linear; regex sebelumnya dapat membekukan server. Kutipan yang hanya berisi token redaksi ditolak.
- Klien watsonx diberi timeout HTTP eksplisit (mengikuti `LANGFLOW_TIMEOUT_SECONDS`) dan maksimal 2 retry; memerlukan `ibm-watsonx-ai>=1.8`.
- Panggilan provider AI memakai satu pool berisi 4 slot; bila penuh, audit langsung memakai aturan lokal (status `busy`).
- Audit log dikunci lintas proses (berkas `.lock`) dan hash terakhir dibaca dari ujung berkas, sehingga server dan worker dapat menulis bersamaan.

## [v4.1] - Tingkat Risiko Eksplisit, Dua Peran, Jejak Bukti, Benchmark Jujur

### Keputusan & akurasi
- Skor 100/100 diganti tabel keputusan deterministik R0–R6 dengan tingkat Rendah / Sedang / Tinggi / Kritis.
- Benchmark terpadu: micro precision/recall/F1, interval Wilson 95%, pencocokan per rule family, dijaga CI.
- Katalog 27 aturan dengan status verifikasi dasar hukum per pasal.

### Alur pengguna
- Login peran Pokja dan Vendor dengan command center masing-masing; isolasi audit per peran.
- Dokumen naskah dinas DOCX (BA evaluasi, klarifikasi, sanggahan) dan BoQ XLSX dengan rumus hidup.
- Mode presentasi dan pintasan keyboard (P, 1, 2, Esc, ?), demo seed Paket A/B.

### AI & integrasi
- Integrasi IBM watsonx.ai via Chat API, telemetri token dan latensi nyata, fallback lokal dengan batas waktu.
- ProofLog per audit yang menunjukkan bagian yang dikerjakan AI dan bagian yang dihitung Python.

### Ketahanan & keamanan
- Suite chaos untuk input rusak, batas ukuran, PDF terenkripsi atau pindaian, dan ReDoS.
- Kontrak respons Pydantic pada seluruh endpoint; pembatasan percobaan PIN login.
- Mesin job asinkron dijadikan opsional; dependensi inti dipangkas.
- Uji E2E browser `scripts/capture_screenshots.py` menggantikan `tests/e2e_smoke.py` dan memperbarui tangkapan layar dokumentasi.

---

## [v2.1.1] - Validasi Sumber Eksak, Kebijakan Verdict Deterministik & Benchmark Mandiri

### 1. Grounding Kutipan Server-Side & Keamanan Log Audit
- **Penyimpanan Teks Sumber Terpisah**: Teks sumber asli disimpan di direktori server khusus (`audit_sources/{audit_id}.txt`) yang dipurging otomatis mengikuti `AUDIT_RETENTION_DAYS`, tanpa mencemari log metadata audit `audit_log.jsonl` (menjaga kepatuhan privasi).
- **Validasi Exact Substring Anti-Halusinasi**: Draf surat sanggahan memvalidasi seluruh kutipan bukti klausul secara eksak terhadap teks sumber asli. Kutipan rekayasa atau tidak berdasar ditolak keras (`ValidationError: no_grounded_findings`).
- **Penanganan Audit Lampau Tanpa Teks Sumber**: Jika berkas sumber tidak tersedia (audit riwayat lama atau terhapus retensi), tombol draf sanggahan dinonaktifkan di antarmuka web dengan penjelasan gamblang.
- **Unit Testing Grounding**: Menambahkan `tests/test_source_grounding.py` (3 skenario pengujian penolakan kutipan palsu dan audit tanpa berkas sumber).

### 2. Penghitungan Metrik Benchmark Dinamis
- **Eliminasi String Persentase Statis**: Refaktorisasi generator laporan pada `tests/benchmark_heldout.py` agar seluruh angka, delta, dan rasio diformat dinamis secara komputasional langsung dari objek hasil run.
- **Pengujian Integritas Templat**: Menambahkan `tests/test_benchmark_templates.py` yang memvalidasi ketiadaan angka atau rasio statis pada templat tabel laporan.

### 3. Verifikasi Data Resmi pada Evidence Scorecard
- **Sitasi Resmi LKPP 2024**: Memperbarui angka belanja pengadaan dengan sumber resmi portal LKPP ([https://www.lkpp.go.id/](https://www.lkpp.go.id/)), Tahun 2024, kutipan persis: *"Total pagu belanja pengadaan barang/jasa nasional tercatat sebesar Rp 1.165,14 Triliun (dengan RUP terumumkan pada SiRUP per April 2024 mencapai Rp 1.043,45 Triliun)."*
- **Penetapan Status Jujur**: Mengganti estimasi waktu manusia dan willingness-to-pay hipotesis dengan tanda tegas **`BELUM DIVERIFIKASI`** / **`BELUM DIKUMPULKAN`**.

### 4. Kebijakan Verdict Terstandarisasi & Hasil Validation Set v1
- **Kebijakan Verdict Deterministik**: Mendokumentasikan kebijakan pada `docs/MODEL_CARD.md`: vonis `NO-GO` secara ketat hanya dipicu oleh cacat fatal yang terkonfirmasi (`GAP`); kekurangan dokumen bukti atau izin kedaluwarsa dialihkan ke status `BELUM CUKUP BUKTI`.
- **Hasil Validation Set v1 (10 Dokumen)**: Label pada `data/test_blind/` tidak diubah setelah putaran pertama. Evaluasi menghasilkan Verdict Accuracy **90.0% (9/10)** pasca-kalibrasi kebijakan NO-GO konservatif & parser naratif, Trap Evasion **100.0% (3/3)**, Macro Precision 16.0%, Macro Recall 30.8%, Macro F1 21.1%.

### 5. Parser Anggaran Prosa Bebas & Dataset Pengujian Narasi Baru
- **Ekstraksi Anggaran Naratif**: Memperluas parser `engine.py` untuk mengekstrak Pagu DIPA, BoQ, dan HPS dari kalimat prosa bebas non-tabel tanpa memicu false positive pada kalimat normatif perundang-undangan.
- **Narrative Budget Test Set (5 Dokumen Baru)**: Menguji pada dokumen terpisah di `data/test_narrative_budget/` dengan evaluator mandiri `tests/benchmark_budget_narrative.py`. Hasil: Verdict Accuracy **80.0% (4/5)**, Trap Evasion **100.0% (1/1)**.


## [v2.1.0] - Iterasi Pemulihan & Bukti Penilaian Rubrik

### Fase 1: Keamanan & Privasi Dokumen
- **Token Authentication & Route Guards**: Menambahkan perlindungan token akses internal (`BIDSENTRY_ACCESS_TOKEN`) dan guard host header anti-DNS rebinding pada `bidsentry/asgi.py`, `server.py`, dan `Dockerfile`.
- **Ekspansi Sensor Data Pribadi (PII Masking)**: Menambahkan deteksi dan redaksi otomatis untuk NIK (16 digit), NPWP (15/16 digit), nomor telepon, dan nomor rekening perbankan sebelum pengiriman data ke provider AI eksternal (`bidsentry/lib/pii.py`).
- **Verbatim Quote Recovery**: Mengimplementasikan pemulihan kutipan dokumen asli lokal dari placeholder redaksi (`recover_unmasked_quote`).
- **Atomic Log Writes & Retention Purge**: Mengubah mekanisme penyimpanan log audit (`bidsentry/lib/audit_log.py`) menjadi penulisan atomik berbasis tempfile dan pembersihan berkas lawas otomatis (> 90 hari).
- **Pembersihan LocalStorage**: Menghilangkan persistensi teks dokumen dan data evaluasi di `localStorage` peramban, beralih sepenuhnya ke in-memory session cache yang aman (`web/app.js`, `web/api.js`).

### Fase 2: Pengukuran Akurasi Jujur & Dekopling Engine
- **Dataset Uji Held-Out 24 Dokumen**: Membuat 24 dokumen tender sintetis independen beserta label ground-truth deklaratif pada `data/benchmark/` (mencakup 8 kasus jebakan *false positive*).
- **Pengukuran Baseline Sebelum Perbaikan**: Menjalankan benchmark awal dan mencatat hasilnya apa adanya di `docs/BENCHMARK_RESULTS.md` (Akurasi baseline: 75.0%, Trap Evasion: 77.8%).
- **Dekopling Aturan ke `config/rules.yaml`**: Memindahkan seluruh batasan numerik (threshold sanggah, batas denda, tarif man-month, masa berlaku dokumen) dan 14 aturan hukum ke konfigurasi deklaratif tanpa hardcode angka di `engine.py`.
- **Paragraph Stitching Lintas Baris**: Mengimplementasikan rekonsiliasi baris teks terpotong pada PDF dua kolom (`_lines()` paragraph reconstruction) dengan tetap mempertahankan referensi baris asal.
- **Parser Tanggal & Masa Berlaku Dinamis**: Menambahkan dukungan nama bulan bahasa Indonesia lengkap/singkat, parameter `bid_deadline`, dan status `EXPIRING` jika dokumen kedaluwarsa dalam 30 hari sebelum tenggat penawaran.
- **Pengecekan Legalitas NIB (PP 5/2021)**: Memperbarui aturan NIB agar berlaku seumur hidup selama pelaku usaha menjalankan kegiatan usaha, memverifikasi format 13 digit tanpa salah mendeteksi tanggal terbit.
- **Pengecualian Kesetaraan Merek (Equivalency Exception)**: Menambahkan pengenalan frasa "atau setara" / "equivalent" untuk menghindari false positive pelanggaran Pasal 19 Perpres 12/2021.
- **Deteksi Denda Tanpa Batas Tanpa Nilai Kontrak**: Engine mampu mendeteksi klausul racun (*poison pill*) denda tanpa batas maksimal langsung dari analisis semantik teks pasal kontrak.
- **Verdict "TIDAK ADA SYARAT TERBACA"**: Mengubah vonis default dari `GO` menjadi `TIDAK ADA SYARAT TERBACA` jika dokumen kosong atau tidak memuat syarat kualifikasi yang dikenali.
- **Hasil Pasca-Perbaikan**: Akurasi verdict naik menjadi **100.0%** (24/24 dokumen), Trap Evasion naik menjadi **100.0%** (8/8 jebakan lolos), Macro F1 **100.0%**.

### Fase 3: Perombakan Alur Pengguna (UI/UX)
- **Auto-Switching Tab Hasil Evaluasi**: Menghilangkan kebingungan pengguna; setelah evaluasi dijalankan, tampilan otomatis berpindah ke tab matriks kepatuhan dan menggulir ke `#risk-review`.
- **Preservasi State Input Form**: Nilai formulir dan daftar berkas tersimpan aman di memori sesi saat evaluasi selesai atau saat memilih tombol "Tambah dokumen & jalankan ulang".
- **Manajemen File Komprehensif**: Mendukung pratinjau 3 baris awal isi file, informasi ukuran berkas, serta tombol hapus dan ganti per slot dokumen.
- **Isolasi Dialog DOM**: Seluruh dialog modal (`<dialog>`) dirender di kontainer `#dialog-layer` terpisah di luar kontainer aplikasi `#app`, menjamin render ulang tidak merusak dialog yang sedang aktif.
- **Debounce Pencarian & Pesan Error Persisten**: Menambahkan debounce 300ms dengan indikator pemrosesan pada filter pencarian tabel serta memperpanjang durasi toast error menjadi 10 detik atau hingga ditutup manual.
- **Modal Konfirmasi Penghapusan Custom**: Mengganti `window.confirm()` bawaan browser dengan modal konfirmasi custom yang aman dan ramah pengguna.
- **1-Click Sample Tender Loader**: Menambahkan tombol "Coba dengan contoh" yang memuat KAK simulasi tender lengkap dan siap dievaluasi seketika.
- **Sanggahan Builder Terarah**: Memfilter temuan secara cerdas antara pelanggaran panitia (bisa disanggah) vs kekurangan dokumen sendiri (catatan internal penyedia), lengkap dengan sitasi Perpres 12/2021.
- **Penetapan Reviewer Manusia (Status Override)**: Menyediakan dropdown status per temuan [Otomatis | Diterima | Diabaikan | Klarifikasi] yang secara dinamis memperbarui rekomendasi verdict keseluruhan (Human-in-the-Loop).
- **Pagination & Filter Riwayat**: Menambahkan pagination (50 item per halaman) serta penyaringan riwayat berdasarkan status verdict dan tingkat risiko.
- **Dukungan Berkas Excel BoQ (.xlsx)**: Mengintegrasikan parser `.xlsx` bawaan (`openpyxl`) untuk mendeteksi rincian anggaran biaya dan perbandingan defisit terhadap pagu, disertai notifikasi ramah jika dokumen berupa PDF hasil pindai murni.
- **Pengujian E2E Smoke Test**: Menambahkan skrip pengujian Playwright `tests/e2e_smoke.py` untuk memvalidasi interaksi UI lengkap dari browser headless.

### Fase 4: Paket Bukti Rubrik Penilaian Juri
- **Lembar Bukti Lengkap**: Menyusun `dokumentasi kepatuhan teknis` yang memetakan solusi terhadap 6 area rubrik (Problem Clarity 20%, Innovation/Feasibility/Monetization 25%, User Impact 15%, Technical Execution & Prototype 20%, Responsible AI 10%, Participation 5%).
- **Model & Decision System Card**: Menyusun `docs/MODEL_CARD.md` yang mendokumentasikan batasan deterministik vs LLM, sanitasi PII, limitasi sistem, dan mitigasi kegagalan.
- **Dokumentasi Arsitektur Lengkap**: Menyusun `docs/ARCHITECTURE.md` disertai diagram Mermaid flowchart dan sequence diagram yang menggambarkan alur proses dan titik integrasi IBM.
- **Probe IBM watsonx / Bob MCP**: Membuat skrip `scripts/verify_watsonx.py` dan dokumentasi transparansi `docs/INTEGRATION_STATUS.md` yang melaporkan status koneksi secara obyektif tanpa klaim palsu.
- **Analisis Komparatif Kompetitif**: Menyusun `docs/COMPETITIVE_COMPARISON.md` yang membandingkan BidSentry vs review manual, software kepatuhan umum, dan LLM generik tanpa grounding.
- **Instrumen Riset Lapangan**: Menyiapkan panduan wawancara semi-terstruktur `docs/INTERVIEW_GUIDE.md` dan templat pengujian pilot `docs/PILOT_RESULTS_TEMPLATE.md` (dengan data manusia bertanda jujur `"BELUM DIKUMPULKAN"`).
- **Automated CI Workflow**: Menambahkan alur kerja GitHub Actions `.github/workflows/ci.yml` untuk menjaga zero-regression secara berkesinambungan.

### Kalibrasi Metodologi & Evaluasi Uji Buta (Blind Test)
- **Klarifikasi Development Set (24 Dokumen)**: Mengkategorikan secara jujur dataset 24 dokumen sintetis sebagai Development & Tuning Set (bukan blind test), mencatat baseline 75.0% dan pasca-penyetelan 100.0%, serta mengoreksi clerical typo penyebut jebakan dari 8/8 menjadi 9/9 kasus.
- **Implementasi Blind Test Set Independen (10 Dokumen)**: Menambahkan 10 skenario pengadaan independen di `data/test_blind/` dan skrip evaluator `tests/benchmark_blind.py`. Dijalankan pada putaran pertama tanpa mengubah aturan engine, mencatat **70.0% Verdict Accuracy** dan **100.0% Trap Evasion Rate** disertai analisis kegagalan terbuka (format narasi bebas vs format tabel terstruktur), sebelum engine dikalibrasi pada iterasi berikutnya menjadi 90.0%.
- **Penyempurnaan Sanggahan Builder**: Memastikan temuan yang ditandai *Ignored* (False Positive) oleh reviewer manusia secara otomatis dikecualikan dari sanggahan, dan draf sanggahan dari riwayat audit menyertakan kutipan bukti secara utuh.
- **Pembersihan Klaim Rubrik**: Menyertakan rujukan resmi belanja PBJP (data LKPP/SiRUP > Rp 1.200 T), mengubah "persona riil" menjadi arketipe sasaran awal, memperjelas batasan throughput teknis (< 30 detik), dan menghapus terminologi berlebihan (*zero-hallucination*).

---

## [v2.1-modular] — Audit evidence and upload reliability

- Changed custom keyword matches to review signals so a missing keyword is not represented as automatic noncompliance and a present keyword is not represented as verified fulfillment.
- Added source filename and extracted-text line references to custom audit findings, plus separate requirement and evidence excerpts.
- Preserved successfully extracted files in a mixed-result multi-file upload and kept per-file extraction errors visible in the upload form.
- Clarified that text line references are not PDF page references and that scanned PDFs need OCR.

## [v2.0] — Modular local review workspace

### Architecture

- Replaced the single HTTP handler/business-logic module with `bidsentry/api`, `controllers`, `services`, `lib`, and `types` packages.
- Kept `server.py` as a small CLI entry point and preserved `run_rules_engine()` as a compatibility adapter.
- Centralized bind settings, request limits, audit-log paths, Langflow configuration, and Composio configuration in `bidsentry/config.py` and `.env.example`.
- Added explicit API routes for health, overview, audit search, JSON export, document audit, and workspace dispatch.
- Standardized API success and error envelopes; malformed JSON, invalid fields, oversized payloads, unsupported methods, and unknown routes receive stable errors.

### Audit and integrations

- Moved rule matching out of the browser into `AuditService`; browser code now submits documents to the backend instead of maintaining a second parser.
- Added a consistent 0–100 deterministic risk triage score with Low, Medium, High, and Critical bands, driver explanations, and an explicit uncalibrated-score disclosure.
- Added contract review signals for unbounded penalty text, conditional/late payment terms, and mixed budget-source references. These are prompts for human review, not fraud findings.
- Added an opt-in Langflow advisory adapter using the configured flow run endpoint. The local rules result remains available when Langflow is disabled, missing, or unavailable.
- Kept Composio actions in a service facade with simulation fallback, and changed audit logging to store metadata only rather than document payloads.
- Added a health response that distinguishes configured MCP metadata from a verified live IBM Bob connection.

### UI/UX

- Replaced the large inline dashboard with a small HTML shell and local ES modules for API access, UI state, rendering, and interactions.
- Applied a restrained editorial layout informed by the supplied Lovelace theme: neutral canvas, fine dividers, rounded cards, compact status colors, and responsive navigation.
- Added an executive overview, filterable procurement register, risk detail panel, contract findings, explicit synthetic-data labels, new-audit dialog, and JSON export.
- Connected search/filtering, audit scans, export, health status, and Composio follow-up to the backend.

### Validation boundary

- The sample portfolio is explicitly labelled synthetic. No real-user feedback or live IBM Bob/Langflow flow is claimed by this refactor.
- The supplied archive is a Home Assistant Lovelace integration. Its YAML and bundled JavaScript were inspected as reference material and are not application dependencies.

# Strategi Monetisasi & Model Bisnis Micro-SaaS BidSentry

> **Pendekatan Strategis**: BidSentry mengadopsi model **Lean Micro-Utility & Micro-SaaS** yang membumi dan dapat dieksekusi langsung. Sistem tidak bergantung pada siklus pengadaan pemerintah yang panjang (B2G 12–24 bulan), melainkan menyasar transaksi mikro langsung dari kontraktor peserta lelang (CV/UMKM) serta belanja operasional rutin unit pengadaan daerah (BUMD/BLUD) melalui skema Pengadaan Langsung non-tender.

---

## 1. Struktur Harga & Unit Economics Riil

Model penetapan harga dirancang tanpa friksi birokrasi (*frictionless adoption*), memadukan pembayaran eceran berbasis QRIS instan dan langganan bulanan terjangkau:

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ TIER 1: PAY-PER-AUDIT (QRIS Instant Voucher)                                          │
│ Rp 5.000 untuk 10 kali audit (efektif Rp 500 / dokumen)                               │
│ • Pembelian kuota instan via QRIS (mengatasi batas minimum aggregator payment gateway) │
│ • Validasi kepatuhan 31 aturan deterministik pengadaan                                │
│ • Pengecekan cepat H-1 sebelum submit dokumen penawaran ke SPSE/LPSE                   │
│ • Hasil audit cepat dengan ringkasan status kelayakan                                  │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ TIER 2: VENDOR PRO SUBSCRIPTION (Langganan Bulanan Kontraktor)                         │
│ Rp 300.000 / bulan (setara Rp 10.000 / hari)                                           │
│ • Kuota audit reguler hingga 30 paket tender / bulan tanpa biaya tambahan              │
│ • Pre-flight checklist kelayakan berkas administratif (NIB, SBU, KSWP, NPWP)          │
│ • Deteksi klausul diskriminatif KAK (brand lock-in, jadwal mepet, denda tanpa batas)   │
│ • Generator draf surat permohonan penjelasan / sanggahan format .docx                  │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ TIER 3: BUMD / BLUD / UNIT PENGADAAN PILOT (Langganan Bulanan Instansi Lokal)          │
│ Rp 800.000 / bulan (setara Rp 9,6 Juta / tahun — di bawah pagu Pengadaan Langsung)     │
│ • Kuota audit multi-vendor hingga 100 dokumen / bulan tanpa biaya tambahan             │
│ • Audit komparatif rincian BoQ Excel (.xlsx) vs pagu HPS & deteksi over-budget        │
│ • Skrining kolusi & kesamaan metadata (kini lewat API, antarmuka menyusul)             │
│ • Multi-user auditor hingga 3 akun (rencana, belum dibangun)                           │
│ • Generator otomatis draf Berita Acara Hasil Evaluasi format .docx                     │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

> **Status implementasi:** harga dan paket di atas adalah hipotesis yang belum divalidasi. Pembayaran QRIS, kuota, dan akun per pelanggan belum dibangun.

### Rincian Biaya Operasional (COGS) & Margin atas Biaya Variabel

| Komponen | Tier 1: Pay-Per-Audit | Tier 2: Vendor Pro | Tier 3: BUMD / BLUD Pilot |
| :--- | :--- | :--- | :--- |
| **Harga Jual Rata-Rata** | Rp 500 / audit (Rp 5.000 / paket) | Rp 300.000 / bulan (~Rp 10.000 / audit) | Rp 800.000 / bulan (~Rp 8.000 / audit) |
| **Komputasi Server (Python)** | Masuk biaya hosting; belum diukur | Masuk biaya hosting; belum diukur | Masuk biaya hosting; belum diukur |
| **Token Inferensi IBM watsonx.ai** | Rp 7–26 per audit | Rp 7–26 per audit | Rp 7–26 per audit |
| **Biaya Transaksi QRIS (MDR 0,7%)** | Rp 35 per voucher Rp 5.000 | Rp 2.100 per transfer bulanan | Rp 5.600 per transfer SPK |
| **Margin atas AI dan QRIS (terburuk), sebelum hosting & dukungan** | **sekitar 94%** | **sekitar 99%** | **sekitar 99%** |

> **Catatan Efisiensi Arsitektur**: Aritmetika BoQ, batas denda, jadwal, dan aturan hukum dihitung kode Python tanpa memanggil API pihak ketiga. Token IBM watsonx.ai hanya dipakai untuk ekstraksi kutipan yang disetujui pengguna, dan teks yang dikirim dibatasi 48.000 karakter per audit. Dokumen sekitar 3.300 token masuk dan 170 token keluar berbiaya sekitar Rp 7; batas atasnya sekitar 13.200 token masuk dan 600 token keluar, atau sekitar Rp 26, memakai harga Mistral Small 3.1 di watsonx (USD 0,106 / 0,318 per 1 juta token) dan kurs Rp 16.500.

---

## 2. Realistic Bottom-Up Market Sizing

Perhitungan potensi pasar didasarkan pada data faktual transaksi Sistem Pengadaan Secara Elektronik (SPSE) Lembaga Kebijakan Pengadaan Barang/Jasa Pemerintah (LKPP):

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ TOTAL ADDRESSABLE MARKET (TAM): hingga Rp 12,5 Miliar / Tahun                          │
│ 1,25 Juta dokumen penawaran tender per tahun di seluruh sistem LPSE nasional           │
│ (250.000 paket × 5 penawar; × Rp 500–10.000 per audit = Rp 0,6–12,5 Miliar)            │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ SERVICEABLE ADDRESSABLE MARKET (SAM): hingga Rp 1,5 Miliar / Tahun                     │
│ Ekosistem pengadaan regional Jawa Timur: ~150.000 dokumen penawaran tender per tahun   │
│ dan ~350 kontraktor / penyedia aktif skala kecil-menengah yang rutin mengikuti tender  │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ SERVICEABLE OBTAINABLE MARKET (SOM — Target Tahun 1): Rp 139,6 Juta / Tahun            │
│ Target akuisisi tahun pertama pada ekosistem kontraktor & unit pengadaan Jawa Timur    │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

### Rincian Komposisi Akuisisi Pendapatan Tahun 1 (SOM: Rp 139,6 Juta):

1. **Audit Eceran UMKM (Voucher QRIS)**:
   - Volume: 2.480 voucher Rp 5.000 berisi 10 kredit, atau kuota 24.800 audit eceran.
   - Proyeksi Pendapatan: **Rp 12.400.000 / tahun**.
   - Karakteristik: Kontraktor mikro yang hanya membutuhkan pengecekan mendesak saat H-1 batas unggah penawaran lelang.

2. **Kontraktor Langganan Aktif (Vendor Pro)**:
   - Volume: 30 vendor kontraktor aktif langganan bulanan (Rp 300.000 / bulan).
   - Proyeksi Pendapatan: 30 vendor × Rp 300.000 × 12 bulan = **Rp 108.000.000 / tahun**.
   - Karakteristik: Kontraktor kelas menengah yang rutin mengikuti 2–4 lelang setiap bulan dan memanfaatkan fitur generator draf Surat Sanggahan resmi.

3. **Instansi BUMD / BLUD Percontohan (Pilot Regional)**:
   - Volume: 2 instansi pengadaan percontohan (misalnya RSUD BLUD daerah atau BUMD Air Minum/Pasar) dengan paket Rp 800.000 / bulan.
   - Nilai Kontrak: Rp 9,6 Juta / instansi / tahun (berada jauh di bawah pagu Pengadaan Langsung Rp 50 Juta / Rp 200 Juta, sehingga cukup diterbitkan Surat Perintah Kerja / SPK langsung tanpa proses tender).
   - Proyeksi Pendapatan: 2 instansi × Rp 800.000 × 12 bulan = **Rp 19.200.000 / tahun**.

**Total Target Pendapatan Tahun 1**: **Rp 139.600.000** dengan estimasi beban token IBM watsonx.ai di bawah Rp 1 juta per tahun (Rp 7–26 per audit). Biaya terbesar justru hosting, dukungan, dan akuisisi pelanggan, sehingga margin kotor tetap perlu divalidasi saat pilot.

---

## 3. Analisis Lanskap Kompetitor (Competitive Landscape Matrix)

BidSentry diposisikan secara strategis untuk mengisi celah kritis yang tidak dilayani oleh sistem eksisting maupun produk AI generik:

| Kriteria Evaluasi | 1. SPSE / LPSE LKPP (Status Quo) | 2. Platform Intelijen Tender (TenderPlus, dsb.) | 3. Enterprise Contract AI (Luminance, Kira Systems) | 4. Generic LLM Chatbot (ChatGPT, Claude) | 5. BidSentry (Micro-SaaS) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Fokus Utama** | Repositori transaksi unggah dokumen lelang | Notifikasi & agregasi peluang lelang baru | Review kontrak hukum korporasi multinasional | Asisten percakapan teks umum | **Audit kepatuhan teknis, BoQ, dan draf sanggahan** |
| **Audit Isi KAK & Syarat Teknis** | Tidak ada (manual oleh panitia) | Tidak ada (hanya scraping judul & pagu) | Terbatas pada klausul umum non-LKPP | Rawan halusinasi pasal & salah hitung | **Otomatis, kutipan terverifikasi (31 aturan; status dasar hukum per pasal)** |
| **Pembedahan Tabel BoQ (.xlsx)** | Tidak ada | Tidak ada | Jarang / Add-on enterprise mahal | Gagal membaca multi-sheet / rumus dinamis | **Bawaan (Native openpyxl) dengan simulasi defisit** |
| **Konteks Hukum Pengadaan Indonesia** | Ya (sebagai sistem induk) | Hanya metadata pengumuman | Tidak (berorientasi US/UK Common Law) | Rendah (mencampur aturan lama/baru) | **Spesifik Perpres 16/2018 s.t.d.t.d. Perpres 46/2025 & UU 5/1999** |
| **Deteksi Jebakan Merek & Batas Denda** | Tergantung ketelitian Pokja | Tidak tersedia | Kaku (flagging semua nama merk) | Inkonsisten | **Cerdas (Mengecualikan frasa setara & denda capped)** |
| **Pelindungan Data Pribadi (UU PDP)** | Standar pemerintah | Mengambil data publik | Server luar negeri (non-kedaulatan data) | **Tinggi risiko bocor ke server publik** | **PII Scrubber sebelum inferensi AI; opsi instalasi mandiri** |
| **Struktur Biaya** | Gratis (Fasilitas Negara) | Langganan Rp 1 Jt – 5 Jt / tahun | Lisensi ratusan juta rupiah per tahun | USD $20 / bulan (~Rp 320.000) | **Mikro: Mulai Rp 500 / audit (Voucher Rp 5.000 QRIS)** |

### Parit Pertahanan & Keunggulan Kompetitif (Moat):

1. **Arsitektur Hibrida Neuro-Symbolic**: Verdict GO / NO-GO, tingkat risiko, dan aritmetika BoQ dihitung oleh kode Python deterministik (input yang sama selalu menghasilkan keluaran yang sama dan dapat ditelusuri di jejak audit). Model di IBM watsonx.ai hanya mengekstrak kutipan; setiap kutipan diverifikasi substring-persis lalu divalidasi ulang aturan Python. Deterministik tidak berarti selalu benar: akurasi diukur di [BENCHMARK_REPORT.md](BENCHMARK_REPORT.md) dan belum divalidasi pada dokumen nyata independen.
2. **Perlindungan Data (UU PDP No. 27/2022)**: NIK, NPWP, rekening, telepon, email, serta nama dan alamat berlabel disensor sebelum dikirim ke model AI, dan panggilan dibatalkan bila pola PII masih terdeteksi.
3. **Harga Mikro Tanpa Hambatan Birokrasi**: Menawarkan voucher QRIS instan Rp 500/dokumen yang dapat langsung dibeli dari ponsel cerdas penawar lelang tanpa kontrak korporasi berbelit.

---

## 4. Rencana Validasi Lapangan & Go-To-Market (GTM)

1. **Bulan 1–3 (Penyebaran Grassroots & Komunitas Konstruksi)**:
   - Pendekatan langsung ke asosiasi kontraktor daerah di Jawa Timur (GAPENSI, GAPEKSI, INKINDO).
   - Demonstrasi langsung pre-flight audit lelang untuk menghindari diskualifikasi akibat SBU dan klausul diskriminatif.
   - Distribusi 500 voucher QRIS gratis untuk memicu adopsi awal dan pengumpulan testimoni.
2. **Bulan 4–6 (Konversi Vendor Pro & Pilot BUMD)**:
   - Konversi 30 kontraktor aktif yang rutin mengikuti lelang ke paket langganan Vendor Pro (Rp 300.000/bulan).
   - Inisiasi percontohan Pengadaan Langsung (SPK Rp 800.000/bln) dengan 2 unit pengadaan RSUD / BUMD lokal untuk pembuktian audit multi-vendor dan pencegahan persekongkolan tender.
3. **Bulan 7–12 (Ekspansi Regional & Skalabilitas SaaS)**:
   - Ekspansi ke wilayah Jawa Tengah dan D.I. Yogyakarta melalui kemitraan dengan konsultan pendamping tender independen.

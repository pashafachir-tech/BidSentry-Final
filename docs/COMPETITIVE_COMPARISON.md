# Analisis Komparatif: BidSentry vs Alternatif Solusi

Dokumen ini membandingkan BidSentry secara obyektif dan jujur terhadap tiga pendekatan alternatif yang umum ditemui dalam proses review dokumen pengadaan barang/jasa publik di Indonesia:
1. **Review Manual oleh Pokja / Legal Vendor**
2. **Perangkat Lunak Kepatuhan / Kontrak Komersial Generik (Enterprise Contract AI)**
3. **Chatbot LLM Publik Umum (ChatGPT / Claude / Gemini tanpa Grounding Khusus)**

---

## 1. Matriks Perbandingan Fitur dan Kapabilitas

| Dimensi Evaluasi | Review Manual (Eksisting) | Software Kepatuhan Generik | LLM Chatbot Publik | BidSentry (v2.1) |
| :--- | :--- | :--- | :--- | :--- |
| **Kecepatan Triage (100+ Hal KAK)** | 4 – 8 Jam per dokumen | 2 – 5 Menit | 1 – 3 Menit | **< 30 Detik** (Hasil instan) |
| **Kesesuaian Regulasi Indonesia (Perpres 12/2021 & LKPP)** | Tinggi (bergantung kompetensi reviewer) | Rendah (dirancang untuk hukum Anglo-Saxon/US) | Sedang (cenderung mencampuradukkan aturan lama/baru) | **Tinggi & Deterministik** (14 aturan spesifik Perpres 12/2021) |
| **Risiko Halusinasi Hukum** | Nihil (manusia) | Rendah (ekstraksi kolom umum) | **Tinggi** (dapat mengarang nomor pasal & angka fiktif) | **Nihil pada Verdict** (Aturan deterministik, bukan generasi bebas) |
| **Privasi & Keamanan Data (PII / Kerahasiaan Harga)** | Aman (lingkup internal organisasi) | Tergantung server vendor (seringkali cloud luar negeri) | **Rentan Bocor** (data terkirim ke server publik) | **Aman & Lokal** (Mesin lokal 100% offline, PII sensor sebelum AI) |
| **Dukungan Dokumen Excel BoQ (.xlsx)** | Manual periksa rumus sel | Seringkali terpisah / add-on mahal | Tidak andal dalam membaca sheet multi-kolom | **Bawaan (Native openpyxl)** dengan deteksi over-budget vs Pagu |
| **Deteksi Jebakan Merek (Equivalency Exception)** | Rawan terlewat bila klausul tersembunyi | Kaku (flagging semua nama merk tanpa cek "atau setara") | Tidak konsisten | **Kontekstual** (Mengecualikan frasa "atau setara" / "equivalent") |
| **Simulasi Denda Keterlambatan Kontrak** | Hitungan kalkulator manual | Jarang tersedia untuk format klausul Indonesia | Rawan salah kalkulasi matematika | **Otomatis** (Simulasi multi-skenario & deteksi denda tanpa batas) |
| **Sanggahan Builder Terarah** | Mengetik surat dari template kosong (1-2 hari) | Tidak tersedia | Format generik tanpa kutipan verbatim terverifikasi | **Otomatis & Terverifikasi** (Menyertakan dasar hukum & sitasi exact) |
| **Dukungan Ekosistem Terbuka (IBM / MCP)** | Tidak ada | Proprietary / Tertutup | API Proprietary | **Terbuka (IBM watsonx & Bob MCP)** |

---

## 2. Analisis Keunggulan Spesifik BidSentry

### A. Arsitektur Hibrida Berbasis Aturan Deterministik
Sistem kepatuhan konvensional yang semata-mata mengandalkan LLM prompt seringkali menghasilkan halusinasi hukum: menyebutkan pasal fiktif, salah menafsirkan batas sanggah LKPP, atau mengklaim pelanggaran pada dokumen yang sebenarnya patuh. BidSentry menyelesaikan masalah ini dengan mendasarkan putusan hukum (GO / NO-GO) pada mesin aturan berbasis kode dan konfigurasi deklaratif (`config/rules.yaml`), sedangkan LLM hanya digunakan sebagai penasihat semantik sekunder yang terverifikasi substring persis.

### B. Pemisahan Hak Sanggah vs Kekurangan Berkas
Mayoritas sistem evaluasi dokumen gagal membedakan subjek kesalahan. BidSentry secara cerdas membedakan:
- **Pelanggaran Pokja/Panitia** (Penguncian merek eksklusif, jadwal lelang mepet, denda tanpa batas): Mengarahkan pada pembuatan draf **Surat Sanggahan Resmi**.
- **Kekurangan Berkas Penyedia Sendiri** (NPWP belum diunggah, garansi belum disertakan): Dikelompokkan ke catatan internal **"Perlu Dilengkapi"**, bukan untuk disanggahkan ke panitia lelang.

### C. Kedaulatan Data Pengadaan (Data Sovereignty)
Banyak kementerian dan BUMN memiliki regulasi ketat bahwa dokumen HPS (Harga Perkiraan Sendiri) dan penawaran teknis bersifat rahasia negara. BidSentry dapat dioperasikan secara penuh pada laptop auditor atau server on-premise tertutup tanpa membutuhkan koneksi internet sama sekali.

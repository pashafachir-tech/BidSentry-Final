# BidSentry Model & Decision System Card

## 1. Ikhtisar Sistem & Arsitektur Keputusan
BidSentry adalah sistem hibrida untuk audit kepatuhan dokumen pengadaan publik Indonesia. Sistem memisahkan secara tegas dua lapisan evaluasi:

```
[ Dokumen Pengadaan (KAK / Dokumen Pemilihan) ]
                       │
                       ▼
         [ Ekstraksi Teks & Normalisasi ]
                       │
                       ▼
    ┌────────────────────────────────────────┐
    │ LAPISAN 1: Mesin Deterministik Lokal   │
    │ (config/rules.yaml + engine.py)        │ ──► Menghasilkan Temuan Hukum,
    │ - Pola RegEx & Validasi Logika Ketat   │     Status Kepatuhan, Skor Risiko,
    │ - 100% Berjalan Lokal & Offline        │     dan Rekomendasi Verdict (GO/NO-GO)
    └────────────────────────────────────────┘
                       │ (Hanya bila persetujuan pengguna aktif)
                       ▼
    ┌────────────────────────────────────────┐
    │ LAPISAN 2: Penasihat Semantik (LLM)    │
    │ (IBM watsonx.ai / Langflow)            │ ──► Menyarankan Konteks Sekunder
    │ - Didahului Redaksi Data Pribadi (PII) │     (Ringkasan Kualifikasi, SLA)
    │ - Rekonstruksi Kutipan Asli (Recovery) │     TIDAK mengubah verdict hukum
    └────────────────────────────────────────┘
```

### Batasan Tegas (System Boundaries):
1. **Aturan Deterministik Mengikat**: Keputusan hukum (seperti diskriminasi spesifikasi merek, jadwal di bawah batas minimum LKPP, klausul denda tanpa batas, atau defisit anggaran BoQ vs Pagu) dievaluasi **hanya** oleh mesin aturan berbasis Perpres 12/2021 dan peraturan turunannya. Model bahasa (LLM) dilarang mengubah status hukum atau verdict secara sepihak.
2. **Karakter LLM Bersifat Penasihat (Advisory)**: LLM bertindak sebagai asisten pencari konteks. Setiap kutipan wajib diverifikasi sebagai *exact substring* dari dokumen sumber. Kandidat yang lolos aturan Python menjadi temuan; kandidat merek di luar pola aturan hanya tampil untuk dicek manusia dan tidak memengaruhi verdict. Teks yang dikirim dibatasi 48.000 karakter per audit.

---

## 2. Kebijakan Privasi & Redaksi Data Pribadi (PII Redaction)
Untuk melindungi kerahasiaan dokumen penawaran dan data pribadi sebelum transmisi ke provider model eksternal (watsonx / Langflow):

### Entitas yang Dimasking Secara Otomatis:
- **NIK (Nomor Induk Kependudukan)**: 16 digit, termasuk yang berspasi atau bertanda hubung, disensor menjadi `[NIK-REDACTED]`.
- **NPWP (Nomor Pokok Wajib Pajak)**: Format 15/16 digit disensor menjadi `[NPWP-REDACTED]`.
- **Nomor Telepon**: Nomor seluler dan telepon kantor disensor menjadi `[PHONE-REDACTED]`.
- **Alamat Surel (Email)**: Format email disensor menjadi `[EMAIL-REDACTED]`.
- **Nomor Rekening Bank**: Nomor berlabel rekening, dengan atau tanpa pemisah, disensor menjadi `[ACCOUNT-REDACTED]`.
- **Nama dan Alamat Berlabel**: Nama setelah label seperti `Direktur:` atau `a.n.` menjadi `[NAME-REDACTED]`, dan alamat setelah label `Alamat` menjadi `[ADDRESS-REDACTED]`. Nama dan alamat tanpa label belum tersensor.

Bila pola PII masih terdeteksi setelah penyensoran, panggilan AI dibatalkan. Teks sumber utuh disimpan di `audit_sources/` agar kutipan dapat diverifikasi, dihapus saat audit dihapus, dan paling lama 90 hari sesuai `AUDIT_RETENTION_DAYS`.

### Lokasi Pemrosesan & Transfer Lintas Negara:
ekstraksi AI bersifat opsional dan hanya berjalan setelah pengguna memberi persetujuan per audit. Teks yang sudah disensor PII-nya diproses di proyek IBM watsonx.ai region Tokyo (`jp-tok`), yaitu di luar Indonesia. Organisasi yang memakai BidSentry perlu memastikan hal ini sesuai kebijakan transfer data lintas negara (UU 27/2022 tentang Pelindungan Data Pribadi, Pasal 56). Tanpa persetujuan, seluruh analisis berjalan lokal tanpa mengirim data keluar.

### Pemulihan Kutipan Asli (Verbatim Quote Recovery):
Jika LLM mengembalikan kutipan yang mengandung placeholder redaksi (misal `[NIK-REDACTED]`), modul `bidsentry.lib.pii.recover_unmasked_quote` memetakan kembali placeholder ke potongan teks asli dokumen sumber pengguna secara aman di lingkungan lokal, sehingga audit trail tetap memiliki bukti tekstual utuh tanpa membocorkan data pribadi ke penyedia cloud AI.

---

## 3. Kebijakan Penetapan Verdict (Verdict Policy)
Sistem memisahkan secara ketat antara pelanggaran hukum terkonfirmasi vs status administratif yang masih memerlukan klarifikasi:

1. **`NO-GO` (Hanya untuk Cacat Fatal yang Pasti)**:
   - Diberikan **hanya** jika terdapat temuan kesenjangan pasti (`status == "GAP"`):
     * Penguncian merek atau spesifikasi diskriminatif tanpa klausul kesetaraan (Pasal 19 ayat (2) Perpres 16/2018 sebagaimana diubah terakhir dengan Perpres 46/2025), di luar pengecualian suku cadang, sistem yang sudah ada, dan katalog elektronik.
     * Masa sanggah di bawah 5 hari kalender setelah pengumuman pemenang (Lampiran Peraturan LKPP 12/2021).
     * Klausul denda yang menyatakan tanpa batas, atau tarif di atas 1‰ per hari tanpa batas akumulasi.
     * Total biaya BoQ melebihi Pagu Anggaran yang tersedia (defisit anggaran).
     * Mark-up tarif man-month konsultan di atas batas pedoman remunerasi nasional.
     * Dokumen legalitas penyedia yang terbukti telah kedaluwarsa sebelum batas akhir penawaran.
     * Terindikasi adanya benturan kepentingan personal/afiliasi yang dilarang.
   - Ketiadaan dokumen penawaran atau masa berlaku yang hampir habis **dilarang keras** memicu status `NO-GO`.
   - Ambang yang belum terverifikasi pada naskah regulasi (masa penawaran minimum) dan klausul denda 1‰ yang tidak menyebut batas **tidak boleh** memicu `NO-GO`; keduanya berstatus `REVIEW`.

2. **`BELUM CUKUP BUKTI` (Status Terpisah untuk Bukti Kosong & Dokumen Mendekati Kedaluwarsa)**:
   - **Bukti Kosong / Belum Diunggah**: Ketika mengevaluasi draf KAK PPK, slot dokumen penawaran penyedia (NPWP, NIB, SBU, Jaminan) berstatus `REVIEW` karena berkas penyedia memang belum diunggah. Status ini menandakan perlunya kelengkapan berkas, bukan vonis pembatalan paket.
   - **Cakupan Rendah**: Dokumen panjang yang hampir tidak ada klausulnya dikenali aturan (R5b) tidak boleh mendapat `GO`.
   - **Tanggal Acuan Kosong**: Bila batas penawaran tidak diisi dan tidak tertulis di dokumen, masa berlaku SBU berstatus `REVIEW`. Sistem tidak memakai tanggal hari ini, sehingga dokumen yang sama selalu menghasilkan verdict yang sama.
   - **Dokumen Mendekati Kedaluwarsa (`EXPIRING`)**: Dokumen legalitas yang masa berlakunya masih aktif namun kurang dari 30 hari sebelum batas penawaran diberi status `EXPIRING` dengan rekomendasi *BELUM CUKUP BUKTI* agar penyedia menyertakan bukti perpanjangan, bukan vonis diskualifikasi seketika.

3. **`GO`**:
   - Seluruh persyaratan administratif dan teknis yang terbaca telah diverifikasi pemenuhannya dari bukti yang disertakan, dan tidak ada cacat yang pasti.

4. **`TIDAK ADA SYARAT TERBACA`**:
   - Dokumen tidak memuat bab persyaratan kualifikasi, teknis, atau kontrak yang dapat diidentifikasi oleh aturan sistem (misal: berkas pindaian gambar tanpa teks OCR atau notulensi rapat umum).

---

## 4. Batasan Sistem (System Limitations)
1. **Bukan Nasihat Hukum (Not Legal Advice)**: BidSentry adalah alat bantu telaah administratif dan teknis. Hasil evaluasi tidak memiliki kekuatan hukum pembatalan lelang dan tidak menggantikan wewenang Pokja Pemilihan atau Pengadilan Tata Usaha Negara.
2. **Tingkat Risiko Bukan Vonis Fraud**: Tingkat risiko (Rendah / Sedang / Tinggi / Kritis) ditetapkan oleh tabel keputusan deterministik R0–R6 (termasuk R5b), bukan skor gabungan, dan merupakan alat triase untuk membantu auditor atau penyedia memprioritaskan telaah dokumen, bukan penetapan adanya tindak pidana korupsi.
3. **Ketergantungan Ekstraksi Teks**: Sistem bergantung pada keterbacaan teks digital. PDF hasil pindai (scan) tanpa lapisan OCR tidak dapat dianalisis secara akurat dan akan menampilkan status `TIDAK ADA SYARAT TERBACA`.

---

## 5. Analisis Potensi Kesalahan (Error & Failure Analysis)

| Karakteristik Dokumen | Potensi Masalah | Mitigasi BidSentry |
| :--- | :--- | :--- |
| **Pindaian Citra Murni (Scanned PDF)** | Teks tidak dapat diekstrak oleh parser PDF standar. | Sistem mendeteksi panjang teks nol dan memberikan notifikasi ramah pengguna untuk melakukan OCR terlebih dahulu. |
| **Tabel BoQ / Anggaran Kompleks** | Format multi-kolom dan sel terdistorsi dalam konversi PDF teks. | Didukung modul parser berkas Excel asli (`.xlsx`) via `openpyxl` yang membaca angka numerik dan struktur kolom secara presisi. |
| **Klausul Terpecah Lintas Baris** | Pemotongan kalimat oleh *line-break* pada PDF dua kolom. | Modul normalisasi merekonstruksi paragraf lintas baris (`_lines()` paragraph stitching) sambil tetap mempertahankan indeks baris asal. |
| **Penyebutan Merek yang Diperbolehkan** | Dokumen menyebutkan merek namun diikuti klausul kesetaraan ("atau setara"). | Pengecualian klausul kesetaraan otomatis mengenali frasa "atau setara", "setara", atau "equivalent", mencegah *false positive* pada aturan lock-in. |

---

## 6. Metrik Evaluasi & Pemantauan (Benchmark Evaluasi)
Angka resmi dihasilkan otomatis oleh `python scripts/run_benchmarks.py` ke [`BENCHMARK_REPORT.md`](BENCHMARK_REPORT.md) dan dijaga CI (gagal bila F1 gabungan < 0,90).

| Ringkasan (51 dokumen sintetis berlabel, micro-average, pencocokan per rule family) | Nilai |
| :--- | :--- |
| Precision | 96,3% (CI Wilson 95%: 82–99%) |
| Recall | 100% (CI Wilson 95%: 87–100%) |
| False positive / false negative | 1 / 0 |

Semua set disusun tim, pernah dilihat selama pengembangan, dan berisi dokumen pendek (median sekitar 270 karakter), sehingga angka ini adalah **uji regresi** pola klausul, bukan estimasi akurasi lapangan. Satu false positive (`budget_03`) adalah perbedaan label yang dicatat di laporan. Catatan historis per iterasi ada di [`BENCHMARK_RESULTS.md`](BENCHMARK_RESULTS.md).

---

## 7. Batasan yang Diketahui (Known Limitations)

1. **Belum Ada Data Lapangan Independen**:
   - Seluruh set benchmark bersifat sintetis dan dibuat tim. Akurasi pada dokumen tender nyata baru dapat diklaim setelah pilot dengan label independen (lihat [`PILOT_VALIDATION.md`](PILOT_VALIDATION.md)).
2. **Cakupan Aturan Berbasis Pola Teks (Pattern-Based)**:
   - Logika deteksi mengandalkan ekspresi reguler deklaratif dan pencocokan teks substring; sistem tidak melakukan pemahaman semantik mendalam pada dokumen yang menggunakan metafora atau parafrasa kompleks tanpa model bahasa.
3. **Keterbatasan Bahasa Dokumen**:
   - Sistem dioptimalkan untuk bahasa Indonesia dokumen pengadaan LPSE (istilah KAK, HPS, DIPA, BoQ). Dukungan bahasa Inggris saat ini baru mencakup istilah kunci jadwal ("bidding period", "working days") dan klausul ekuivalensi ("or equivalent").
4. **Deteksi Diskriminasi Regional Spesifik Pola**:
   - Deteksi pembatasan wilayah baru mencakup pola eksplisit domisili ("wajib berdomisili"), asosiasi ("anggota KADIN"), dan kepemilikan kantor cabang lokal yang tidak dikecualikan oleh lokasi pekerjaan sah.
5. **Keamanan Prompt Injection**:
   - Mesin aturan lokal 100% kebal terhadap prompt injection karena beroperasi murni secara deterministik tanpa LLM. Namun, jalur inferensi LLM eksternal opsional (watsonx / Langflow) hanya dilindungi oleh filter sanitasi PII dan verifikasi kutipan teks persis (*exact quote grounding*), bukan pembuktian formal adversarial defense.

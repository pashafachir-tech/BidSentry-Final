# Rencana validasi pilot BidSentry

Dokumen ini adalah protokol kerja, bukan hasil pilot. Tidak ada wawancara, pengukuran dampak, evaluasi akurasi, atau kesediaan membayar yang diklaim selesai sebelum bukti nyata dicatat.

## Tujuan dan pertanyaan

Pilot kecil harus menjawab tiga pertanyaan sebelum produk dipakai untuk keputusan pengadaan:

1. Apakah reviewer benar-benar mengalami masalah menemukan persyaratan, bukti, dan perubahan versi dokumen?
2. Apakah BidSentry membantu reviewer menavigasi dokumen lebih cepat tanpa menaikkan risiko temuan yang keliru atau terlewat?
3. Apakah alur lokal, privasi, dan biaya operasional dapat diterima oleh organisasi yang akan menggunakannya?

## Rancangan yang disarankan

- Libatkan 3–5 reviewer dari peran yang relevan (pengadaan, teknis, hukum, atau pemeriksa internal). Jumlah tersebut adalah target pilot, bukan sampel yang cukup untuk klaim umum.
- Gunakan 5–10 dokumen yang pengguna berhak proses. Mulai dengan dokumen sintetis atau yang sudah disamarkan; jangan unggah dokumen tender nyata tanpa persetujuan pemilik dan persetujuan keamanan organisasi.
- Catat tugas yang sama untuk alur biasa dan alur berbantuan BidSentry. Gunakan dokumen sebanding dan selang-seling urutan agar efek belajar tidak selalu menguntungkan salah satu alur.
- Sebelum melihat keluaran aplikasi, dua reviewer secara terpisah tandai klausul yang perlu ditinjau dan rujukan sumbernya. Selesaikan perbedaan melalui adjudikasi manusia dan simpan definisi label. Ini menjadi pembanding pilot, bukan “ground truth” universal.
- Jangan gabungkan label *perlu ditinjau* dengan keputusan kepatuhan. Keluaran produk saat ini adalah sinyal pencarian kata kunci dan triase; ia tidak membuktikan pemenuhan atau ketidakpatuhan.

## Ukuran yang dicatat

| Ukuran | Cara mencatat | Batas interpretasi |
|---|---|---|
| Waktu tugas review | Stopwatch dari tugas dimulai sampai reviewer menyelesaikan daftar pemeriksaan yang disepakati; catat per reviewer, dokumen, dan alur | Bandingkan pasangan yang setara; tampilkan jumlah sampel dan median. Jangan menyebut penghematan waktu tanpa baseline yang setara. |
| Keterlacakan sumber | Hitung temuan yang rujukan file/barisnya dapat ditemukan dan dikonfirmasi reviewer | Ini mengukur keterlacakan pada sampel, bukan ketepatan hukum atau kelengkapan dokumen. |
| Sinyal didukung / perlu info / tidak didukung | Gunakan label review BidSentry dan cocokkan dengan adjudikasi independen setelah pilot | Laporkan tabel hitungan lengkap dan sampel; jangan menyebut input reviewer sebagai akurasi model. |
| Sinyal terlewat | Bandingkan isu yang disepakati reviewer independen dengan sinyal yang muncul | Laporkan false negative pada dokumen pilot secara jelas. Mesin sekarang tidak menyimpulkan GAP hanya dari ketiadaan kata kunci. |
| Waktu engine lokal | Catat median runtime aturan lokal yang tampil di ringkasan dan jumlah sampel (maksimal 100 audit lokal terbaru) | Tidak termasuk ekstraksi file, Langflow, jaringan, atau waktu manusia; bukan klaim kecepatan seluruh proses. |
| Usability dan kegagalan unggah | Catat tugas selesai/tidak, format, error, dan pertanyaan pengguna tanpa menyimpan isi dokumen | Pisahkan PDF hasil scan yang memerlukan OCR dari PDF teks yang didukung. |
| Kesediaan membayar dan biaya | Wawancara terpisah: siapa pembeli, anggaran, proses pengadaan software, harga yang dianggap layak, serta biaya implementasi/dukungan | Sampai divalidasi, langganan workspace dan paket integrasi tetap hipotesis bisnis. |

Laporkan ukuran sampel, rentang atau median yang sesuai, kasus gagal, batas sistem, dan metode pencatatan bersama setiap angka. Jangan menghapus kasus yang tidak nyaman dari ringkasan.

## 2. Dekomposisi Waktu & Pengukuran Throughput Teknis

Sebagai acuan perbandingan baseline terukur dalam protokol pengujian:

### A. Dekomposisi Waktu Review: Manual vs Berbantuan BidSentry
- **Hipotesis Baseline Manual (4,5 jam / 270 menit, belum diukur; ini nilai bawaan kartu biaya di aplikasi)**:
  - Pembacaan teliti Kerangka Acuan Kerja (KAK) & Spesifikasi Teknis: 120 – 180 menit.
  - Verifikasi silang Bill of Quantities (BoQ) terhadap Pagu Anggaran/HPS: 30 – 60 menit.
  - Pengecekan riwayat adendum & konsistensi klausul: 30 – 45 menit.
  - Penyusunan draf Berita Acara Evaluasi (Pokja) atau Surat Sanggahan (Vendor): 60 – 120 menit.
- **Perkiraan Pipeline Mesin (dokumen sekitar 100 halaman, belum diukur di dokumen nyata)**:
  - Ekstraksi teks & tabel dari PDF multi-halaman (`DocumentExtractionService`): **1.2 – 3.5 detik**.
  - Evaluasi matriks kepatuhan 31 aturan deterministik (`bidsentry.evaluators.engine`): **< 0.5 detik**.
  - Pemeriksaan ketimpangan harga satuan BoQ & denda kontrak: **< 0.2 detik**.
  - Ekstraksi kutipan via IBM watsonx.ai (atau fallback lokal): **15 – 30 detik**.
  - Pembentukan draf Berita Acara / surat DOCX: **< 1 detik**.
  - *Catatan: angka ini hanya waktu mesin. Waktu verifikasi manusia belum diukur dan harus dicatat saat pilot.*

### B. Presisi Deteksi Ketimpangan Harga (Pricing Imbalance Precision)
- **Metodologi**: Modul `bidsentry.audits.pricing_imbalance` membandingkan tarif man-month dan harga satuan material terhadap indeks standar (seperti pedoman INKINDO atau Standar Satuan Harga / SSH).
- **Ambang Batas**:
  - Deviasi > 100% dari tarif standar memicu peringatan risiko mark-up sedang.
  - Deviasi > 200% (misal man-month Solution Architect Rp 150 jt vs standar Rp 45–60 jt) memicu flag fatal `FIN-UNBALANCED-PRICING` / `RISIKO TINGGI`.
  - Duplikasi pos lisensi dengan pemeliharaan tahun pertama dideteksi via pemeriksaan irisan klausul hak pakai (*double counting*).

### C. Transparansi Konsumsi Token & Biaya Komputasi (Token Cost Transparency)
- **Model Fondasi**: model chat via IBM watsonx.ai (default `mistralai/mistral-small-3-1-24b-instruct-2503`).
- **Efisiensi Pra-Inferensi**: Redaksi PII lokal membuang entitas sensitif sebelum payload dikirim, menghemat token context window.
- **Metrik Konsumsi**:
  - Teks yang dikirim dibatasi 48.000 karakter (sekitar 13.000 token masuk termasuk instruksi).
  - Token keluar diperkirakan sekitar 600.
  - Biaya AI: sekitar Rp 7 untuk dokumen pendek dan paling tinggi sekitar Rp 26 per audit, memakai harga Mistral Small 3.1 di watsonx dan kurs Rp 16.500.
  - Margin: belum dihitung; hosting dan dukungan juga belum dihitung.

## Privasi, keselamatan, dan tata kelola

- Dapatkan persetujuan untuk ikut pilot dan otorisasi pemrosesan setiap dokumen. Gunakan data sintetis atau disamarkan bila izin belum tersedia.
- Jelaskan bahwa teks diproses di server BidSentry untuk aturan. Teks sumber utuh disimpan terpisah di `audit_sources/` (tanpa sensor, agar kutipan dapat diverifikasi), dihapus saat audit dihapus dan paling lama 90 hari; audit log hanya memuat metadata dan kutipan temuan.
- Langflow bersifat opsional dan memerlukan persetujuan pada setiap audit. Jangan mengirim dokumen sensitif ke integrasi eksternal tanpa persetujuan serta pemeriksaan kebijakan organisasi.
- Batasi akses ke folder kerja, tetapkan masa simpan pilot, lalu hapus salinan dokumen sesuai persetujuan. Catat siapa yang bertanggung jawab atas penghapusan.
- Setiap temuan dan skor perlu keputusan reviewer. Jangan gunakan demo atau pilot ini sebagai keputusan kelayakan tender otomatis.

## Paket bukti untuk matriks penilaian

| Kriteria | Bukti produk yang dapat didemonstrasikan | Bukti nyata yang masih perlu dikumpulkan |
|---|---|---|
| Problem clarity & relevance (15%) | Alur drag-and-drop, temuan, sumber file/baris, dan tindak lanjut | Wawancara terarah, observasi alur saat ini, pernyataan masalah yang tervalidasi |
| Innovation, creativity, feasibility & monetization (20%) | Mesin aturan deterministik, rules engine, persetujuan integrasi, fallback, dan protokol pilot | Perbandingan terhadap alur kerja yang ada, biaya pilot, wawancara pembeli dan kesediaan membayar |
| User impact & benefits (15%) | Alur reviewer dan pencatatan disposisi yang benar-benar dimasukkan | Baseline dan hasil tugas berpasangan, keterlacakan sumber, kasus terlewat, feedback pengguna |
| Technical execution & prototype (20%) | Demo file yang didukung, hasil audit, pencarian/filter, ekspor, dan status koneksi | Catatan run end-to-end di mesin presentasi, format berhasil/gagal, runtime terukur, bukti integrasi live bila diklaim |
| Responsible AI (10%) | Skor triase tidak terkalibrasi, batas aturan, consent, pemrosesan lokal, dan log metadata | Persetujuan pilot, pemeriksaan privasi, adjudikasi, proses eskalasi dan penghapusan data |
| Pitching presentation & QnA (20%) | Stage runner demo dan jejak audit | Deck, naskah, pembagian peran bicara, latihan Q&A, dan kepatuhan waktu |

**Status saat ini:** protokol dan alur demonstrasi tersedia; hasil pilot, validasi masalah, dampak, kesediaan membayar, serta deck pitching belum tersedia dalam workspace ini.

## Gate sebelum demo/rilis

1. Jalankan demo dari awal pada perangkat presentasi dan siapkan TXT/DOCX/PDF teks yang memang diizinkan.
2. Tunjukkan satu bukti sumber dan satu contoh batas sistem; sebutkan bahwa PDF hasil scan memerlukan OCR.
3. Periksa status koneksi dari aplikasi. Tampilkan konektor sebagai opsional bila belum berhasil diuji end-to-end.
4. Pastikan tampilan runtime menyebut bahwa ukurannya hanya untuk rules engine lokal. Angka baru bermakna setelah audit nyata dijalankan; jumlah sampel harus ikut ditampilkan.
5. Simpan bukti pilot dan partisipasi secara terpisah dari demo sintetis. Jangan mengisi angka contoh seolah hasil nyata.

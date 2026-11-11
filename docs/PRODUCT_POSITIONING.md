# Posisi produk, AI Insights, dan monetisasi BidSentry

Dokumen ini menetapkan arah produk yang dapat diuji. Rekomendasi fitur, harga, dan manfaat di bawah adalah hipotesis sampai divalidasi bersama pengguna yang berwenang memproses dokumen.

## Janji produk

**BidSentry membantu tim pengadaan dan hukum menemukan bagian dokumen yang perlu diperiksa, menautkannya ke sumber, lalu menyiapkan langkah verifikasi berikutnya.** Produk ini adalah ruang kerja review berbantuan aturan dan AI; bukan sistem penentu kelulusan, penasihat hukum otomatis, atau pendeteksi fraud.

Nilai yang dijual adalah satu paket review yang lebih mudah ditelusuri: persyaratan, bukti, perubahan versi, pertanyaan, dan langkah berikutnya tersusun dalam satu alur. Jangan mengklaim penghematan “ratus kali” sebelum pengujian berpasangan menunjukkan hasilnya.

## Dua pekerjaan yang dibantu

| Peran | Pekerjaan yang ingin diselesaikan | Keluaran BidSentry | Batas keputusan |
|---|---|---|---|
| Reviewer pengadaan | Menautkan syarat paket ke dokumen bukti, memeriksa dokumen yang kurang/akan kedaluwarsa, dan memastikan adendum yang berlaku ikut dipakai | Matriks syarat-bukti, rujukan file/baris hasil ekstraksi, daftar pertanyaan dan dokumen yang perlu dikonfirmasi | Pencocokan teks tidak membuktikan kepatuhan atau kelayakan peserta |
| Reviewer hukum | Menemukan klausul kontrak dan perubahan adendum yang perlu ditelaah, lalu menyiapkan pertanyaan bagi penasihat/pihak berwenang | Ringkasan klausul, kutipan sumber, perubahan/ambiguitas yang perlu dikonfirmasi, draf pertanyaan | Bukan opini hukum final atau pengganti penasihat hukum |

Pengguna harian dapat berupa staf pengadaan, pemeriksa teknis, atau tim legal. Pembeli dapat berupa konsultan pengadaan, kantor hukum, atau organisasi yang memiliki tim review berulang. Untuk organisasi publik, proses keamanan, pengadaan software, dan kebutuhan instalasi privat dapat menjadi syarat pembelian tersendiri.

## Alur produk dan batas tiap komponen

1. Reviewer memilih fokus **Pengadaan** atau **Hukum**, kemudian memasukkan dokumen pemilihan, adendum, dan bukti melalui drag-and-drop atau teks.
2. Ekstraksi dan aturan lokal berjalan lebih dulu. Aturan deterministik mencari pola dan menampilkan sumber serta kutipan; hasilnya berstatus sinyal untuk diperiksa manusia.
3. Jika reviewer memberi persetujuan eksplisit dan koneksi tersedia, Langflow menerima teks setelah penyamaran beberapa pola angka yang dikenali aplikasi. Ini bukan jaminan semua data sensitif terhapus. Instruksi analisis mengikuti fokus peran; flow menyusun ringkasan lintas dokumen, perubahan yang tampak, pertanyaan, serta langkah berikutnya.
4. Hasil ditampilkan pada tab **AI Insights & langkah berikutnya**, terpisah dari **Matriks & bukti**. Insight AI dan prioritas aturan lokal diberi label berbeda. Ekspor hasil review berformat Excel; sheet `AI Insights` disertakan jika reviewer telah membuka tab AI Insights sebelum mengekspor.
5. Reviewer membuka sumber asli, mengubah atau menolak saran, mencatat disposisi, dan baru kemudian menyiapkan ekspor/tindak lanjut.

Langflow berfungsi sebagai lapisan orkestrasi dan analisis lintas dokumen, bukan sekadar pembaca file. Ekstraksi file tetap lokal. Langflow tidak mengubah skor aturan lokal. Isi dokumen diperlakukan sebagai data tidak tepercaya, bukan instruksi kepada model. AI diminta mengutip bukti yang benar-benar ada, mengakui informasi yang tidak ditemukan, dan tidak mengeluarkan verdict. Rujukan baris aplikasi saat ini berasal dari teks hasil ekstraksi, bukan nomor halaman asli; pilot harus menguji keterlacakan kutipan sebelum fitur dipakai untuk keputusan penting.

## Hipotesis monetisasi yang perlu diuji

Harga acuan BidSentry ada di satu tempat, yaitu [MONETIZATION_STRATEGY.md](MONETIZATION_STRATEGY.md), dan sama dengan tabel di README. Semua harga masih **hipotesis yang diuji lewat wawancara**, belum harga pasar tervalidasi:

| Paket | Sasaran | Harga uji |
|---|---|---:|
| Pay-Per-Audit (QRIS) | Kontraktor CV/UMKM | Rp5.000 per 10 audit (Rp500/dokumen) |
| Vendor Pro | Kontraktor aktif LPSE | Rp300.000/bulan |
| BUMD/BLUD Pilot | RSUD BLUD, BUMD, satuan pengawas | Rp800.000/bulan (Rp9,6 juta/tahun, cukup SPK) |

Fitur tim seperti kolaborasi dan deployment privat belum tersedia; jangan menjualnya sebagai fitur aktif sebelum dibangun. Sebagai pembanding kategori yang berdekatan (bukan kompetitor langsung atau bukti kesediaan membayar), Cicero mencantumkan Legal Pro Rp499.000/bulan dan Privy mencantumkan Enterprise tanda tangan elektronik Rp225.000/akun/bulan: [Cicero pricing](https://cicero.id/pricing), [Privy pricing](https://privy.id/id/digital-signature).

Sebelum menentukan harga tetap, wawancarai pengguna dan pembeli secara terpisah. Cari tahu frekuensi review, siapa pemilik anggaran, metode kerja saat ini, batas pemrosesan data, biaya support, dan apakah pembeli lebih memilih per-seat, per-workspace, atau per-paket. Catat penolakan dan alasan harga terasa tidak layak.

## Bukti manfaat yang layak dijual

Jalankan tugas sebanding dengan cara kerja biasa dan dengan BidSentry. Ukur waktu sampai checklist review selesai, proporsi temuan yang rujukannya dapat diverifikasi, jumlah koreksi reviewer, isu yang terlewat, pengulangan kerja, dan keberhasilan unggah. Laporkan median, ukuran sampel, variasi, serta kegagalan.

Nilai ekonominya dihitung setelah data pilot ada:

`nilai waktu = (median menit tanpa produk − median menit dengan produk) × jumlah paket per bulan × biaya tenaga kerja per jam ÷ 60`

Tambahkan biaya pengerjaan ulang yang benar-benar tercatat; jangan mengubah risiko potensial menjadi kerugian yang diklaim telah dihindari. Harga terasa layak bila pembeli melihat manfaat yang terukur dan dapat diaudit, bukan karena presentasi menyebut persentase penghematan tanpa baseline.

## Hubungan dengan matriks juri

- **Problem clarity:** demonstrasikan satu alur per peran dari dokumen masuk sampai pertanyaan/tindak lanjut.
- **Innovation, feasibility, monetization:** tampilkan sintesis lintas dokumen yang merujuk sumber, fallback lokal, kuota AI, dan hasil wawancara harga.
- **User impact:** tunjukkan pengukuran tugas berpasangan, bukan angka demonstrasi.
- **Technical execution:** tunjukkan ingest, versi/adendum, kutipan, output AI yang opt-in, serta ekspor.
- **Responsible AI:** tunjukkan consent, pemisahan skor aturan dan AI, pencatatan batas, dan konfirmasi manusia.

## Urutan build yang disarankan

1. Uji dua alur peran pada 3–5 reviewer dan dokumen yang pemrosesannya diizinkan.
2. Pastikan setiap saran Langflow dapat dicocokkan dengan sumber; catat temuan tanpa rujukan sebagai belum tervalidasi.
3. Perbaiki locator halaman untuk PDF/DOCX dan penanganan perbandingan versi adendum sebelum menjualnya sebagai fitur audit trail.
4. Uji harga workspace dan kuota insight melalui wawancara; jangan menambahkan checkout/payment sebelum pembeli, biaya model, dan jalur pengadaan diketahui.
5. Setelah ada hasil pilot, terbitkan satu halaman bukti: metode, waktu, sampel, sumber yang terverifikasi, kegagalan, dan batas interpretasi.


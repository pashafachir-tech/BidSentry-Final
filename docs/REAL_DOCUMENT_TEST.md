# Uji BidSentry pada Dokumen Tender Nyata

**Status: belum diperiksa orang luar tim.** Kolom "Pemeriksa" sengaja kosong. Jangan mengutip laporan ini sebagai angka akurasi lapangan sebelum kolom itu terisi.

- Tanggal uji: 9 November 2026
- Mesin: BidSentry v4.2, aturan lokal saja (AI tidak dipanggil)
- Masukan: PDF publik sebagai Dokumen Pemilihan, tanpa dokumen penawaran dan tanpa batas akhir penawaran

## 1. Hasil pada dokumen apa adanya

| Dokumen | Sumber | Halaman | Karakter | Waktu mesin | Verdict | Cakupan | GAP | REVIEW |
| :--- | :--- | ---: | ---: | ---: | :--- | :---: | ---: | ---: |
| Konstruksi Gedung FIB, Unsoed | [ppid.unsoed.ac.id](https://ppid.unsoed.ac.id/pbj/doc/fib2025/5.%20Dokumen%20Pemilihan%20FIB%202025.pdf) | 134 | 231.528 | 323 ms | BELUM CUKUP BUKTI | 7/20 | 0 | 6 |
| Dokumen Pemilihan PK Paket A, DJP | [pajak.go.id](https://pajak.go.id/sites/default/files/2025-07/e%26f.%20Dokumen%20Pemilihan%20PK%20Paket%20A.pdf) | 107 | 204.907 | 290 ms | BELUM CUKUP BUKTI | 7/20 | 0 | 6 |
| Konsultansi Layanan TI/DC, BKN | [bkn.go.id](https://www.bkn.go.id/wp-content/uploads/2025/10/DokumenSeleksiJakonLayananTIDC.pdf) | 67 | 98.497 | 163 ms | BELUM CUKUP BUKTI | 4/20 | 0 | 3 |
| LDP Repair List Kapal, Basarnas | [ppid.basarnas.go.id](https://ppid.basarnas.go.id/storage/files/34/2025/PBJ/REPAIR%20LIST%20KAPAL/II.b.6.%20LDP%20Penyusunan%20Repair%20List%20Kapal%20Tahap%20II%20Tahun%202025.pdf) | 4 | 3.218 | 20 ms | TIDAK ADA SYARAT TERBACA | 0/20 | 0 | 0 |

Pagu dan HPS yang benar terbaca pada dokumen Unsoed dan DJP, dan keduanya tidak melampaui pagu.

### Temuan untuk diperiksa

Kolom "Penilaian awal" adalah pembacaan tim pengembang, bukan penilaian independen.

| Dokumen | Temuan | Kutipan yang ditampilkan mesin | Penilaian awal | Pemeriksa (benar/salah) |
| :--- | :--- | :--- | :--- | :--- |
| Unsoed | ADM-NPWP | "b. NPWP;" | Relevan | |
| Unsoed | ADM-KSWP | "Mempunyai status valid keterangan Wajib Pajak..." | Relevan | |
| Unsoed | ADM-NIB | "Memiliki SBU dengan Kualifikasi Usaha kecil ... atau NIB KBLI 41016" | Relevan | |
| Unsoed | ADM-SBU | "b. Persyaratan kepemilikan Sertifikat Badan Usaha" | Relevan | |
| Unsoed | ADM-BOND | "b) Jaminan Penawaran (apabila disyaratkan);" | Relevan, nilainya tidak terbaca | |
| Unsoed | CON-PENALTY | "Denda Keterlambatan sebesar 1/1000 ..." | Relevan, batas akumulasi tidak tertulis | |
| DJP | ADM-NPWP | "b. NPWP;" | Relevan | |
| DJP | ADM-KSWP | "Mempunyai status valid keterangan Wajib Pajak..." | Relevan | |
| DJP | ADM-NIB | "Memiliki Nomor Induk Berusaha (NIB) dan Sertifikat Standar..." | Relevan | |
| DJP | ADM-SBU | "b. Persyaratan kepemilikan Sertifikat Badan Usaha" | Relevan | |
| DJP | ADM-BOND | "b) Jaminan Penawaran (apabila disyaratkan);" | Relevan, nilainya tidak terbaca | |
| DJP | CON-PENALTY | "Denda Keterlambatan sebesar 1/1000 ..." | Relevan, batas akumulasi tidak tertulis | |
| BKN | ADM-NPWP | "3. KTP dan NPWP" | Perlu dicek konteksnya | |
| BKN | ADM-BOND | "Jaminan Penawaran dikeluarkan dari penjamin yang sama..." | Relevan, nilainya tidak terbaca | |
| BKN | ADM-EXPERTS | "Unsur kualifikasi tenaga ahli..." | Perlu dicek konteksnya | |

## 2. Uji sisipan pelanggaran

Karena dokumen di atas tidak memuat pelanggaran, kalimat pelanggaran yang diketahui disisipkan ke teks asli tiga dokumen panjang, pada beberapa posisi. Untuk over-budget, nilai HPS asli dinaikkan.

| Set | Sebelum perbaikan | Sesudah perbaikan |
| :--- | :---: | :---: |
| Set awal: 17 jenis pelanggaran, 2 posisi, 3 dokumen | 81/102 | 102/102 |
| Set kedua: 18 kalimat berbeda, 3 posisi, 3 dokumen | belum ada | 162/162 |
| Temuan GAP tambahan di luar sisipan (set kedua) | belum ada | 0 |

**Batas uji ini:** kalimat sisipan ditulis tim dan banyak memakai kosakata yang dikenali aturan. Set kedua disusun sebelum perbaikan terakhir, tetapi tetap bukan uji buta. Angka ini menunjukkan mesin tidak lagi kehilangan pelanggaran di dalam dokumen panjang; ini bukan recall pada pelanggaran alami.

## 2a. Uji ulang dan dua KAK/spesifikasi baru

Keempat dokumen di atas diuji ulang lewat alur API penuh (unggah, audit, Berita Acara, surat klarifikasi). Hasilnya sama, semua kutipan temuan cocok persis dengan teks sumber, dan rantai audit log tetap valid.

| Dokumen | Sumber | Halaman | Waktu mesin | Verdict | Cakupan | GAP | REVIEW |
| :--- | :--- | ---: | ---: | :--- | :---: | ---: | ---: |
| KAK Server Data Center, Perum LKBN ANTARA | [ppid.antaranews.com](https://ppid.antaranews.com/assets/upload/file/regulasi/2-Tahap-Pemilihan/3-Spesifikasi-Teknis-Pengadaan-Server-Data-Center.pdf) | 4 | 9 ms | NO-GO, Tinggi | 4/20 | 2 | 2 |
| TOR Server SRM, PANDI (2022) | [api.pandi.id](https://api.pandi.id/public/files/2022/9/tor-no-4020-052-2022-tentang-pengadaan-server-sistem-registri-mandiri-srm-1663147873.pdf) | 8 | 13 ms | NO-GO, Tinggi | 2/20 | 1 | 1 |

Pembacaan awal tim atas kedua dokumen ini, setelah perbaikan aturan berdasarkan dokumen yang sama (belum diperiksa pihak independen). Karena aturan disesuaikan dari dokumen ini, baris yang tertangkap setelah perbaikan bukan bukti kemampuan pada dokumen baru.

| Dokumen | Isi dokumen | Hasil mesin | Penilaian awal | Pemeriksa (benar/salah) |
| :--- | :--- | :--- | :--- | :--- |
| ANTARA | "Minimal menyertakan 2x Intel Xeon Gold 24 Core", tanpa opsi setara | SPEC-LOCKIN-CPU (GAP) | Tertangkap, temuan alami pertama | |
| ANTARA | "support warranty minimal 3 tahun" | ADM-WARRANTY (REVIEW) | Benar, bukti penawaran tidak ada | |
| ANTARA | Mitra minimal "Titanium Partner" dan surat dukungan dari principal | SPEC-PRINCIPAL-REVIEW (REVIEW) | Tertangkap setelah perbaikan, perlu dinilai kewajarannya | |
| ANTARA | Kantor pusat atau perwakilan di Jakarta | SPEC-REGIONAL-LOCKIN (GAP) | Tertangkap setelah perbaikan, perlu dinilai apakah wajar | |
| PANDI | "Processor Intel Xeon Gold 5318N / 5318S" pada tabel spesifikasi | SPEC-LOCKIN-CPU (GAP) | Tertangkap setelah perbaikan | |
| PANDI | "Garansi / Service 3 Tahun" | ADM-WARRANTY (REVIEW) | Benar, kutipan kini hanya baris terkait | |

Perum dan PANDI tidak selalu tunduk pada Perpres pengadaan, sedangkan mesin belum membedakan jenis instansi. Rujukan Pasal 19 pada temuan ANTARA perlu dicek keberlakuannya.

## 3. Bug yang ditemukan dan sudah diperbaiki

1. Daftar isi, nomor halaman, paraf, dan baris formulir kosong terbaca sebagai syarat.
2. Aturan hanya membaca kemunculan pertama, sehingga pelanggaran di bagian lain dokumen terlewat.
3. Ambang bersyarat seperti "HPS di atas Rp50 miliar" terbaca sebagai nilai paket.
4. Garansi bank tertukar dengan garansi produk.
5. Baris "maksimal ..." yang jauh dari klausul denda dianggap batas denda.
6. "Dalam waktu N hari setelah ..." dianggap offset, bukan lama waktu.
7. Label tenaga ahli menyebut sertifikat yang tidak diminta dokumen.
8. Tabel spesifikasi menyatu menjadi satu kalimat, sehingga kata dari baris lain memengaruhi aturan.
9. Syarat tingkat kemitraan, surat dukungan principal, dan kantor pusat di lokasi tertentu belum dikenali.

## 4. Yang belum dapat disimpulkan

- **Deteksi pelanggaran alami baru diuji pada dua dokumen spesifikasi kecil,** dan aturannya sudah disesuaikan dari dua dokumen itu. Perlu dokumen baru untuk menguji kembali. HPS rinci dan jadwal SPSE belum diuji.
- **Deteksi tabel bersifat perkiraan.** Sebagian teks kolom sempit masih dianggap tabel; pada uji ulang ini verdict dokumen panjang tidak berubah.
- **Parafrase di luar pola aturan masih lolos**, misalnya "harus terdaftar di Kabupaten X", kecuali ekstraksi AI menandai mereknya.
- **Dokumen dua kolom** kadang tersusun tidak berurutan saat diekstrak. Beberapa PDF juga kehilangan spasi antarkata.
- **Pemeriksaan tim tidak setara telaah hukum.** Diperlukan pemeriksa yang paham pengadaan.

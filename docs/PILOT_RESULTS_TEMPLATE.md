# Templat Hasil Pengujian Pilot Pengguna (User Testing & Pilot Results)

> **Catatan Integritas Data (Aturan Keras Proyek)**:
> Seluruh baris metrik pengguna manusia pada dokumen ini berstatus **"BELUM DIKUMPULKAN"**. Tidak ada data wawancara, angka pilot, atau testimoni palsu yang dikarang. Tabel di bawah adalah instrumen pengumpulan data terstandarisasi yang siap digunakan saat program uji coba (pilot study) bersama mitra instansi/penyedia dilaksanakan.

---

## 1. Log Pengujian Pilot Mitra Pengguna (User Testing Log)

| ID Sesi | Persona / Profil Mitra | Jenis Dokumen Diuji | Temuan Terdeteksi | Waktu Selesai (Menit) | Skor Kepuasan (CSAT 1-5) | Status Validasi Lapangan |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `PILOT-001` | Pokja Pemilihan K/L | KAK Pengadaan TI | BELUM DIKUMPULKAN | BELUM DIKUMPULKAN | BELUM DIKUMPULKAN | BELUM DIKUMPULKAN |
| `PILOT-002` | Vendor Penyedia Swasta | Dokumen Pemilihan Konstruksi | BELUM DIKUMPULKAN | BELUM DIKUMPULKAN | BELUM DIKUMPULKAN | BELUM DIKUMPULKAN |
| `PILOT-003` | Auditor Internal (APIP) | Paket Konsultansi Manajemen | BELUM DIKUMPULKAN | BELUM DIKUMPULKAN | BELUM DIKUMPULKAN | BELUM DIKUMPULKAN |
| `PILOT-004` | Bid Manager System Integrator | KAK Cloud & Hardware | BELUM DIKUMPULKAN | BELUM DIKUMPULKAN | BELUM DIKUMPULKAN | BELUM DIKUMPULKAN |
| `PILOT-005` | Pokja Pemilihan Daerah | Dokumen Pengadaan Jasa Lainnya | BELUM DIKUMPULKAN | BELUM DIKUMPULKAN | BELUM DIKUMPULKAN | BELUM DIKUMPULKAN |

---

## 2. Metrik Perbandingan Waktu: Estimasi Throughput Teknis vs Manual

> **Pernyataan Penafian (Disclaimer)**:
> Kolom "BidSentry (Throughput Mesin)" di bawah merupakan pengukuran teknis waktu eksekusi kode backend pada dokumen sintetis benchmark (latensi parsing + evaluasi regex/logika aturan). Nilai ini **BUKAN** klaim penghematan biaya tenaga kerja manusia yang telah tervalidasi di lapangan, karena proses verifikasi akhir tetap membutuhkan pertimbangan manusia (Human-in-the-Loop).

| Tahapan Evaluasi | Estimasi Review Manual (Manusia) | BidSentry (Throughput Mesin) | Keterangan Metodologi |
| :--- | :--- | :--- | :--- |
| **Ekstraksi & Penelusuran KAK (100 Halaman)** | 120 – 180 Menit | **1.2 – 3.5 Detik** | Parser PDF Plumber + normalisasi teks |
| **Pengecekan Lock-in Merek & Spesifikasi** | 30 – 60 Menit | **< 0.1 Detik** | Pencocokan pola regex aturan `rules.yaml` |
| **Verifikasi Batas Minimum Jadwal LKPP** | 15 – 30 Menit | **< 0.1 Detik** | Perhitungan selisih tanggal kalender/kerja |
| **Pengecekan Over-Budget BoQ vs Pagu** | 30 – 60 Menit | **< 0.5 Detik** | Parser tabel `.xlsx` / ekstraksi angka HPS |
| **Penyusunan Draf Surat Sanggahan Resmi** | 60 – 120 Menit | **Instan (< 1 Detik)** | Sanggahan builder dengan sitasi Perpres 12/2021 |

---

## 3. Rencana Pengumpulan Data Pilot (Methodology Plan)
Saat fase uji coba lapangan resmi dimulai, data akan dikumpulkan melalui metodologi berikut:
1. **Perekaman Sesi Pengguna**: Mengukur waktu penyelesaian tugas (*time-to-task-completion*) auditor sebelum dan sesudah menggunakan BidSentry.
2. **Pengujian Buta (Blind Testing)**: Memberikan dokumen tender nyata beranomali kepada dua tim auditor (dengan dan tanpa bantuan BidSentry) untuk menghitung selisih temuan *missed red flags*.
3. **Survei Standar Usability (SUS)**: Mengukur skor *System Usability Scale* dengan target minimal 75/100 dari minimal 20 responden praktisi pengadaan.

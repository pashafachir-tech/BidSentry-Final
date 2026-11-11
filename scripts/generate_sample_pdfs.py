"""Generate rich multi-page PDF sample tenders with structured tables and metadata."""

from pathlib import Path
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    PageBreak,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

OUT_DIR = Path("data/sample_tenders/pdf_tenders")
OUT_DIR.mkdir(parents=True, exist_ok=True)

styles = getSampleStyleSheet()
title_style = ParagraphStyle(
    "TitleStyle",
    parent=styles["Heading1"],
    fontSize=14,
    leading=18,
    alignment=1,  # Center
    textColor=colors.HexColor("#1A2019"),
)
h2_style = ParagraphStyle(
    "H2Style",
    parent=styles["Heading2"],
    fontSize=11,
    leading=14,
    textColor=colors.HexColor("#2C3E2D"),
)
body_style = ParagraphStyle(
    "BodyStyle",
    parent=styles["Normal"],
    fontSize=9,
    leading=12,
    textColor=colors.HexColor("#333333"),
)


def generate_rab_pdf():
    pdf_path = OUT_DIR / "paket_konstruksi_rab_kompleks.pdf"
    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=letter,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=36,
    )
    story = []

    # Header
    story.append(Paragraph("PEMERINTAH DAERAH PROVINSI DAERAH KHUSUS", title_style))
    story.append(Paragraph("DINAS PEKERJAAN UMUM DAN PENATAAN RUANG", title_style))
    story.append(Spacer(1, 10))
    story.append(Paragraph("RINCIAN ANGGARAN BIAYA (RAB) / BILL OF QUANTITIES (BOQ)", title_style))
    story.append(Paragraph("Paket Pekerjaan: Rekonstruksi & Peningkatan Kapasitas Jalan Koridor Utama", body_style))
    story.append(Paragraph("Nomor Tender: TND-PUPR-2026-8801 | Pagu DIPA: Rp 12.500.000.000,-", body_style))
    story.append(Spacer(1, 15))

    # Table Page 1
    story.append(Paragraph("A. DIVISI 1 - UMUM & DRAINASE", h2_style))
    data_p1 = [
        ["No", "Uraian Pekerjaan", "Volume", "Satuan", "Harga Satuan (Rp)", "Total Harga (Rp)"],
        ["1.1", "Mobilisasi dan Demobilisasi Alat Berat", "1,00", "Ls", "150.000.000", "150.000.000"],
        ["1.2", "Penyelenggaraan SMKK / Keselamatan Konstruksi", "1,00", "Ls", "75.000.000", "75.000.000"],
        ["1.3", "Manajemen dan Rekayasa Lalu Lintas", "1,00", "Ls", "45.000.000", "45.000.000"],
        ["2.1", "Galian Saluran Drainase Tanah Biasa", "2.400,00", "M3", "48.000", "115.200.000"],
        ["2.2", "Pasangan Batu dengan Mortar (Saluran U)", "850,00", "M3", "820.000", "697.000.000"],
        ["2.3", "Gorong-gorong Pipa Beton Bertulang D60", "120,00", "M'", "750.000", "90.000.000"],
    ]
    t1 = Table(data_p1, colWidths=[30, 220, 55, 45, 95, 95])
    t1.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2A3427")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("ALIGN", (2, 1), (-1, -1), "RIGHT"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CCCCCC")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8F9F7")]),
    ]))
    story.append(t1)

    story.append(PageBreak())

    # Table Page 2
    story.append(Paragraph("B. DIVISI 2 & 3 - PEKERJAAN TANAH DAN PERKERASAN BERBUTIR", h2_style))
    data_p2 = [
        ["No", "Uraian Pekerjaan", "Volume", "Satuan", "Harga Satuan (Rp)", "Total Harga (Rp)"],
        ["3.1", "Galian Tanah Biasa Badan Jalan", "4.500,00", "M3", "42.000", "188.000.000"],
        ["3.2", "Timbunan Pilihan dari Sumber Galian", "3.200,00", "M3", "92.000", "294.400.000"],
        ["4.1", "Lapis Pondasi Agregat Semen Kelas A", "1.850,00", "M3", "375.000", "693.750.000"],
        ["4.2", "Lapis Pondasi Agregat Kelas B", "2.100,00", "M3", "315.000", "661.500.000"],
        ["5.1", "Lapis Resap Pengikat - Aspal Cair", "8.500,00", "Liter", "17.500", "148.750.000"],
        ["5.2", "Laston Lapis Aus (AC-WC) Tebal 4 cm", "1.350,00", "Ton", "1.420.000", "1.917.000.000"],
        ["5.3", "Laston Lapis Antara (AC-BC) Tebal 6 cm", "1.800,00", "Ton", "1.360.000", "2.448.000.000"],
        ["6.1", "Beton Struktur fc' 20 MPa K-250", "720,00", "M3", "1.280.000", "921.600.000"],
        ["6.2", "Baja Tulangan Sirip BjTS 420B", "48.000,00", "Kg", "16.200", "777.600.000"],
        ["SUBTOTAL", "Total Rincian Divisi 1 s.d. Divisi 3", "", "", "", "9.223.800.000"],
        ["PPN 11%", "Pajak Pertambahan Nilai (11%)", "", "", "", "1.014.618.000"],
        ["TOTAL", "Total Biaya Penawaran Fisik", "", "", "", "10.238.418.000"],
    ]
    t2 = Table(data_p2, colWidths=[30, 220, 55, 45, 95, 95])
    t2.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2A3427")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("ALIGN", (2, 1), (-1, -1), "RIGHT"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CCCCCC")),
        ("BACKGROUND", (0, -3), (-1, -1), colors.HexColor("#EAEFE8")),
        ("FONTNAME", (0, -3), (-1, -1), "Helvetica-Bold"),
    ]))
    story.append(t2)
    story.append(Spacer(1, 15))
    story.append(Paragraph("Ketentuan Pembayaran & Denda: Denda keterlambatan ditetapkan 1/1000 per hari dengan batas maksimum denda 5% dari nilai kontrak.", body_style))
    story.append(Paragraph("Jadwal Pengadaan: Pemasukan penawaran 8 hari kerja, masa sanggah 5 hari kalender.", body_style))

    doc.build(story)
    print(f"Generated RAB PDF: {pdf_path}")


def generate_kak_pdf():
    pdf_path = OUT_DIR / "paket_pengadaan_it_server_kak.pdf"
    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=letter,
        leftMargin=40,
        rightMargin=40,
        topMargin=40,
        bottomMargin=40,
    )
    story = []

    story.append(Paragraph("KERANGKA ACUAN KERJA (KAK)", title_style))
    story.append(Paragraph("PENGADAAN SERVER DAN INFRASTRUKTUR DATA CENTER", title_style))
    story.append(Spacer(1, 12))
    story.append(Paragraph("BAB I. LATAR BELAKANG DAN SUMBER DANA", h2_style))
    story.append(Paragraph(
        "Alokasi pagu anggaran yang disediakan dalam DIPA APBN Tahun Anggaran 2026 "
        "untuk pengadaan perangkat server data center adalah sebesar Rp 7.500.000.000,- (Tujuh Koma Lima Miliar Rupiah). "
        "Total rincian perhitungan kebutuhan teknis BoQ diestimasi sebesar Rp 7.200.000.000,-.",
        body_style,
    ))
    story.append(Spacer(1, 10))
    story.append(Paragraph("BAB II. PERSYARATAN KUALIFIKASI PENYEDIA", h2_style))
    story.append(Paragraph(
        "1. Memiliki Nomor Induk Berusaha (NIB) berbasis risiko yang masih berlaku sesuai bidang KBLI 62021.<br/>"
        "2. Memiliki NPWP perusahaan valid dengan status Konfirmasi Status Wajib Pajak (KSWP) Valid.<br/>"
        "3. Memiliki pengalaman pekerjaan serupa dalam kurun waktu 3 (tiga) tahun terakhir.<br/>"
        "4. Menyerahkan surat jaminan purna jual (garansi) minimal 12 bulan (1 tahun) dari distributor resmi.",
        body_style,
    ))
    story.append(Spacer(1, 10))
    story.append(Paragraph("BAB III. SPESIFIKASI TEKNIS PERANGKAT", h2_style))
    story.append(Paragraph(
        "Server wajib menggunakan prosesor Intel Xeon Platinum generasi Emerald Rapids, "
        "interkoneksi bus UPI 4.0, dan modul manajemen remote eksklusif Dell iDRAC 10 Enterprise. "
        "Penawaran merek lain tidak dapat diterima panitia pengadaan.",
        body_style,
    ))
    story.append(Spacer(1, 10))
    story.append(Paragraph("BAB IV. JADWAL PEMILIHAN DAN KETENTUAN KONTRAK", h2_style))
    story.append(Paragraph(
        "Masa pemasukan penawaran diberikan selama 3 (tiga) hari kerja sejak pengumuman lelang. "
        "Masa sanggah ditetapkan selama 2 (dua) hari kerja.<br/>"
        "Denda keterlambatan pelaksanaan pekerjaan adalah 1/1000 per hari dari nilai kontrak tanpa batas maksimal denda.",
        body_style,
    ))

    doc.build(story)
    print(f"Generated KAK PDF: {pdf_path}")


if __name__ == "__main__":
    generate_rab_pdf()
    generate_kak_pdf()

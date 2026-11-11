"""Canonical catalog of every finding code the deterministic engine can emit.

Each rule declares:

* ``family`` – the canonical concept used for benchmarking. Labels written with
  older or alternative IDs are mapped to a family through ``aliases``.
* ``party`` – whose document the finding is about. Only ``tender_document``
  gaps can be raised in a vendor objection letter.
* ``critical_on_gap`` – a confirmed gap on this rule alone puts the package in
  the *Kritis* risk tier.
* ``legal_basis`` – structured citations. Each carries a verification status
  that says exactly how far it was checked, so the UI and the generated letters
  never present an unchecked article number as settled law:

  - ``DIPERIKSA_NASKAH``  : article text read and matched (source recorded);
  - ``DIPERIKSA_SEKUNDER``: article number and substance confirmed only by
    secondary sources (training material, law-firm analysis, model contracts);
  - ``PERLU_VERIFIKASI_HUKUM``: not yet checked; reviewers must confirm.

  Verification log (2026-11-07): Pasal 19 ayat (2), Pasal 26 ayat (5) and
  Pasal 7 ayat (1) huruf e / ayat (2) were read in the Perpres 46/2025
  consolidated text; UU 1/2004 Pasal 3 ayat (3) was read in the statute text.
  Pasal 26 contains *no* "HPS must not exceed pagu" rule, so over-budget is
  anchored on UU 1/2004 Pasal 3 ayat (3) instead. Minimum schedule durations in
  Peraturan LKPP 12/2021 could not be confirmed and stay unverified.

  Verification log (2026-11-09): the Lampiran of Peraturan LKPP 12/2021
  (salinan JDIH BPKP) states that bidders who submitted an offer may object
  through SPSE to the winner determination within 5 calendar days of the
  announcement. No fixed minimum bid-preparation period was found there, so that
  number can only ask for review.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

VerificationStatus = Literal["DIPERIKSA_NASKAH", "DIPERIKSA_SEKUNDER", "PERLU_VERIFIKASI_HUKUM"]
_STATUS_ORDER = {"DIPERIKSA_NASKAH": 2, "DIPERIKSA_SEKUNDER": 1, "PERLU_VERIFIKASI_HUKUM": 0}

PERPRES_FULL = (
    "Peraturan Presiden Nomor 16 Tahun 2018 tentang Pengadaan Barang/Jasa Pemerintah sebagaimana telah "
    "beberapa kali diubah, terakhir dengan Peraturan Presiden Nomor 46 Tahun 2025"
)
CONSOLIDATED_SOURCE = "Naskah konsolidasi Perpres 46/2025 (jdih.lkpp.go.id; dibaca melalui mirror api-law.crpg.info, 7 Nov 2026)"


@dataclass(frozen=True)
class Citation:
    instrument: str
    article: str
    substance: str
    status: VerificationStatus
    source: str = ""

    @property
    def formal(self) -> str:
        """Official-letter style: 'Pasal 19 ayat (2) Peraturan Presiden Nomor ...'."""
        return f"{self.article} {self.instrument}".strip()

    def as_dict(self) -> dict[str, str]:
        return {"instrument": self.instrument, "article": self.article, "substance": self.substance, "status": self.status, "source": self.source, "formal": self.formal}


@dataclass(frozen=True)
class RuleSpec:
    code: str
    family: str
    title: str
    category: str
    party: Literal["tender_document", "bidder_evidence"]
    default_severity: Literal["CRITICAL", "HIGH", "MEDIUM", "LOW"] = "HIGH"
    critical_on_gap: bool = False
    legal_basis: tuple[Citation, ...] = field(default_factory=tuple)
    aliases: tuple[str, ...] = field(default_factory=tuple)

    @property
    def legal_reference(self) -> str:
        return "; ".join(f"{c.formal} — {c.substance}" for c in self.legal_basis)

    @property
    def legal_verification(self) -> VerificationStatus:
        """The weakest status among the citations: one unchecked article makes the whole basis unchecked."""
        if not self.legal_basis:
            return "PERLU_VERIFIKASI_HUKUM"
        return min((c.status for c in self.legal_basis), key=lambda status: _STATUS_ORDER[status])


# ----------------------------------------------------------------------- citations
BRAND = Citation(PERPRES_FULL, "Pasal 19 ayat (2)",
                 "penyebutan merek dalam spesifikasi teknis/KAK hanya dimungkinkan untuk komponen Barang/Jasa, suku cadang, bagian dari satu sistem yang sudah ada, atau Barang/Jasa dalam katalog elektronik",
                 "DIPERIKSA_NASKAH", CONSOLIDATED_SOURCE)
PENALTY_RATE = Citation("Peraturan Presiden Nomor 16 Tahun 2018 tentang Pengadaan Barang/Jasa Pemerintah", "Pasal 79 ayat (4)",
                        "denda keterlambatan sebesar 1‰ (satu permil) dari nilai kontrak atau nilai bagian kontrak untuk setiap hari keterlambatan",
                        "DIPERIKSA_SEKUNDER", "Materi pelatihan PBJ dan analisis hukum Pasal 78–79 (sumber sekunder); cocokkan dengan naskah konsolidasi")
PENALTY_CAP = Citation("Model Syarat-Syarat Umum Kontrak (SSUK) dokumen pemilihan LKPP", "ketentuan denda keterlambatan",
                       "denda keterlambatan tidak melampaui besarnya Jaminan Pelaksanaan",
                       "DIPERIKSA_SEKUNDER", "SSUK beberapa instansi yang mengikuti model LKPP (sumber sekunder)")
BUDGET = Citation("Undang-Undang Nomor 1 Tahun 2004 tentang Perbendaharaan Negara", "Pasal 3 ayat (3)",
                  "setiap pejabat dilarang melakukan tindakan yang berakibat pengeluaran atas beban APBN/APBD jika anggaran untuk membiayai pengeluaran tersebut tidak tersedia atau tidak cukup tersedia",
                  "DIPERIKSA_NASKAH", "Naskah UU 1/2004 (peraturan.bpk.go.id/Details/40446; dibaca melalui Wikisource, 7 Nov 2026)")
HPS_CEILING = Citation(PERPRES_FULL, "Pasal 26 ayat (5)",
                       "HPS digunakan antara lain sebagai dasar untuk menetapkan batas tertinggi penawaran yang sah dan menilai kewajaran harga",
                       "DIPERIKSA_NASKAH", CONSOLIDATED_SOURCE)
HPS_BASIS = Citation(PERPRES_FULL, "Pasal 26 ayat (1)",
                     "HPS dihitung secara keahlian dan menggunakan data yang dapat dipertanggungjawabkan",
                     "DIPERIKSA_NASKAH", CONSOLIDATED_SOURCE)
ETHICS_COI = Citation(PERPRES_FULL, "Pasal 7 ayat (1) huruf e jo. ayat (2)",
                      "semua pihak wajib menghindari dan mencegah pertentangan kepentingan yang berakibat persaingan usaha tidak sehat; ayat (2) merinci keadaan pertentangan kepentingan",
                      "DIPERIKSA_NASKAH", CONSOLIDATED_SOURCE)
ETHICS_COLLUSION = Citation(PERPRES_FULL, "Pasal 7 ayat (1) huruf c dan g",
                            "tidak saling mempengaruhi yang berakibat persaingan usaha tidak sehat; menghindari penyalahgunaan wewenang dan/atau kolusi",
                            "DIPERIKSA_NASKAH", CONSOLIDATED_SOURCE)
PRINCIPLES = Citation(PERPRES_FULL, "Pasal 6",
                      "prinsip pengadaan: efisien, efektif, transparan, terbuka, bersaing, adil, dan akuntabel",
                      "PERLU_VERIFIKASI_HUKUM")
SCHEDULE = Citation("Peraturan Lembaga Kebijakan Pengadaan Barang/Jasa Pemerintah Nomor 12 Tahun 2021 tentang Pedoman Pelaksanaan Pengadaan Barang/Jasa Pemerintah melalui Penyedia, sebagaimana diubah dengan Peraturan Lembaga Nomor 4 Tahun 2024",
                    "Lampiran, ketentuan Sanggah dan jadwal pemilihan",
                    "sanggah disampaikan dalam 5 hari kalender setelah pengumuman pemenang; angka minimum masa penawaran yang dipakai sistem berasal dari config/rules.yaml dan tidak ditemukan pada Lampiran tersebut",
                    "PERLU_VERIFIKASI_HUKUM", "Lampiran Peraturan LKPP 12/2021 (jdih.bpkp.go.id, dibaca 9 Nov 2026); perubahan Peraturan LKPP 4/2024 belum dicocokkan")
NPWP = Citation("Ketentuan teknis NPWP Direktorat Jenderal Pajak", "format nomor", "NPWP berformat 15 atau 16 digit", "PERLU_VERIFIKASI_HUKUM")
KSWP = Citation("Ketentuan Konfirmasi Status Wajib Pajak (KSWP) DJP", "status KSWP", "status wajib pajak dikonfirmasi valid", "PERLU_VERIFIKASI_HUKUM")
NIB = Citation("Peraturan Pemerintah Nomor 5 Tahun 2021 tentang Penyelenggaraan Perizinan Berusaha Berbasis Risiko", "ketentuan NIB", "NIB sebagai identitas pelaku usaha", "PERLU_VERIFIKASI_HUKUM")
SBU = Citation("Undang-Undang Nomor 2 Tahun 2017 tentang Jasa Konstruksi jo. Peraturan Pemerintah Nomor 14 Tahun 2021", "ketentuan SBU", "SBU berlaku pada saat pemasukan penawaran", "PERLU_VERIFIKASI_HUKUM")
BOND = Citation(PERPRES_FULL, "ketentuan jaminan penawaran", "nilai jaminan penawaran sesuai Dokumen Pemilihan", "PERLU_VERIFIKASI_HUKUM")
TENDER_DOC = Citation("Dokumen Pemilihan paket", "ketentuan terkait", "persyaratan sebagaimana tercantum dalam Dokumen Pemilihan dan adendumnya", "PERLU_VERIFIKASI_HUKUM")
BILLING = Citation("Pedoman standar remunerasi tenaga ahli (INKINDO) dan prinsip kewajaran harga", "batas tarif", "tarif tenaga ahli dinilai terhadap pedoman remunerasi", "PERLU_VERIFIKASI_HUKUM")
EFFICIENCY = Citation(PERPRES_FULL, "Pasal 7 ayat (1) huruf f", "menghindari dan mencegah pemborosan dan kebocoran keuangan negara", "DIPERIKSA_NASKAH", CONSOLIDATED_SOURCE)

_RULES: tuple[RuleSpec, ...] = (
    # --- Bidder evidence (administrasi penyedia) ---------------------------
    RuleSpec("ADM-NPWP", "ADM-NPWP", "Format NPWP", "Administrasi", "bidder_evidence", "MEDIUM", legal_basis=(NPWP,)),
    RuleSpec("ADM-KSWP", "ADM-KSWP", "Status KSWP/perpajakan", "Administrasi", "bidder_evidence", "MEDIUM", legal_basis=(KSWP,)),
    RuleSpec("ADM-NIB", "ADM-NIB", "Nomor Induk Berusaha (NIB)", "Administrasi", "bidder_evidence", "MEDIUM", legal_basis=(NIB,)),
    RuleSpec("ADM-SBU", "ADM-SBU", "Masa berlaku SBU", "Administrasi", "bidder_evidence", "HIGH", legal_basis=(SBU,)),
    RuleSpec("ADM-BOND", "ADM-BOND", "Nilai jaminan penawaran", "Administrasi", "bidder_evidence", "HIGH", legal_basis=(BOND,)),
    RuleSpec("ADM-WARRANTY", "ADM-WARRANTY", "Lama garansi/jaminan", "Administrasi", "bidder_evidence", "HIGH", legal_basis=(TENDER_DOC,)),
    RuleSpec("ADM-EXPERTS", "ADM-EXPERTS", "Kualifikasi & sertifikasi tenaga ahli", "Administrasi", "bidder_evidence", "MEDIUM", legal_basis=(TENDER_DOC,)),
    # --- Tender document red flags -----------------------------------------
    RuleSpec("ADD-CHANGE", "ADD-CHANGE", "Perubahan persyaratan adendum", "Adendum", "tender_document", "MEDIUM", legal_basis=(TENDER_DOC,)),
    RuleSpec("CON-PENALTY", "CON-PENALTY", "Klausul denda keterlambatan tanpa batas maksimum", "Kontrak", "tender_document", "HIGH",
             critical_on_gap=True, legal_basis=(PENALTY_RATE, PENALTY_CAP)),
    RuleSpec("CON-PENALTY-RATE", "CON-PENALTY-RATE", "Tarif denda harian di atas pembanding 1‰", "Kontrak", "tender_document", "MEDIUM", legal_basis=(PENALTY_RATE,)),
    RuleSpec("SPEC-LOCKIN-CPU", "SPEC-LOCKIN", "Spesifikasi mengunci merek/arsitektur prosesor", "Spesifikasi", "tender_document", legal_basis=(BRAND,), aliases=("SPEC-LOCKIN-PROC",)),
    RuleSpec("SPEC-LOCKIN-GPU", "SPEC-LOCKIN", "Spesifikasi mengunci akselerator/GPU tertentu", "Spesifikasi", "tender_document", legal_basis=(BRAND,)),
    RuleSpec("SPEC-LOCKIN-MGMT", "SPEC-LOCKIN", "Spesifikasi mengunci sistem manajemen/storage vendor", "Spesifikasi", "tender_document", legal_basis=(BRAND,)),
    RuleSpec("SPEC-LOCKIN-NETWORKING", "SPEC-LOCKIN", "Spesifikasi mengunci perangkat jaringan tertentu", "Spesifikasi", "tender_document", legal_basis=(BRAND,)),
    RuleSpec("SPEC-LOCKIN-SOFTWARE", "SPEC-LOCKIN", "Spesifikasi mengunci perangkat lunak/database tertentu", "Spesifikasi", "tender_document", legal_basis=(BRAND,)),
    RuleSpec("SPEC-BRAND-LOCKIN", "SPEC-LOCKIN", "Spesifikasi mengarah ke merek tertentu", "Spesifikasi", "tender_document", legal_basis=(BRAND,)),
    RuleSpec("SPEC-AI-LOCKIN", "SPEC-LOCKIN", "Penyebutan merek (diekstrak AI, divalidasi Python)", "Spesifikasi", "tender_document", legal_basis=(BRAND,)),
    RuleSpec("SPEC-BRAND-WATCH", "SPEC-BRAND-WATCH", "Merek disebut tanpa opsi setara (perlu ditelaah)", "Spesifikasi", "tender_document", "MEDIUM", legal_basis=(BRAND,)),
    RuleSpec("SPEC-BRAND-EXCEPTION", "SPEC-BRAND-EXCEPTION", "Penyebutan merek yang mungkin dikecualikan Pasal 19 ayat (2)", "Spesifikasi", "tender_document", "LOW", legal_basis=(BRAND,)),
    RuleSpec("SPEC-AI-BRAND-REVIEW", "SPEC-AI-BRAND-REVIEW", "Kandidat merek dari AI yang perlu dicek manusia", "Spesifikasi", "tender_document", "LOW", legal_basis=(BRAND,)),
    RuleSpec("PROC-TIMELINE-COMPRESSED", "PROC-TIMELINE", "Jadwal penawaran/masa sanggah dipersingkat", "Jadwal", "tender_document", legal_basis=(SCHEDULE,),
             aliases=("PROC-TIMELINE-PREP", "PROC-TIMELINE-SANGGAH", "PROC-TIMELINE-EXPEDITED")),
    RuleSpec("PROC-AI-TIMELINE", "PROC-TIMELINE", "Jadwal dipersingkat (diekstrak AI, divalidasi Python)", "Jadwal", "tender_document", legal_basis=(SCHEDULE,)),
    RuleSpec("PROC-UNREALISTIC-TIMELINE", "PROC-UNREALISTIC", "Durasi implementasi tidak realistis", "Jadwal", "tender_document",
             critical_on_gap=True, legal_basis=(ETHICS_COLLUSION, PRINCIPLES)),
    RuleSpec("GOV-CONFLICT-INTEREST", "GOV-COI", "Benturan kepentingan / afiliasi pejabat", "Integritas", "tender_document",
             critical_on_gap=True, legal_basis=(ETHICS_COI,)),
    RuleSpec("SPEC-REGIONAL-LOCKIN", "SPEC-REGIONAL", "Persyaratan domisili/asosiasi regional diskriminatif", "Kualifikasi", "tender_document",
             legal_basis=(PRINCIPLES,), aliases=("DISC-GEO-BRANCH", "DISC-GEO-DOMICILE")),
    RuleSpec("SPEC-PRINCIPAL-REVIEW", "SPEC-PRINCIPAL-REVIEW", "Syarat kemitraan atau dukungan principal", "Kualifikasi", "tender_document", "MEDIUM", legal_basis=(PRINCIPLES,)),
    RuleSpec("SPEC-INCUMBENT-LOCKIN", "SPEC-INCUMBENT", "Kriteria pengalaman mengarah ke inkumben", "Kualifikasi", "tender_document", legal_basis=(PRINCIPLES, BRAND)),
    RuleSpec("FIN-OVER-BUDGET", "FIN-OVER-BUDGET", "Total BoQ/HPS melebihi pagu anggaran", "Keuangan", "tender_document",
             critical_on_gap=True, legal_basis=(BUDGET, HPS_CEILING), aliases=("FIN-HPS-OVER-PAGU",)),
    RuleSpec("FIN-MARKUP-RATE", "FIN-BILLING-RATE", "Billing rate tenaga ahli di atas pedoman", "Keuangan", "tender_document",
             legal_basis=(BILLING, EFFICIENCY), aliases=("FIN-BILLING-RATE",)),
    RuleSpec("FIN-DOUBLE-LICENSE", "FIN-DOUBLE-COUNT", "Duplikasi pembiayaan lisensi & pemeliharaan", "Keuangan", "tender_document", legal_basis=(EFFICIENCY,)),
    RuleSpec("FIN-BOQ-ARITHMETIC", "FIN-BOQ-ARITHMETIC", "Selisih aritmetika rincian BoQ/HPS", "Keuangan", "tender_document", "MEDIUM",
             legal_basis=(HPS_BASIS, EFFICIENCY)),
)

CATALOG: dict[str, RuleSpec] = {rule.code: rule for rule in _RULES}
_ALIASES: dict[str, str] = {alias: rule.code for rule in _RULES for alias in rule.aliases}


def get_rule(code: str) -> RuleSpec:
    """Return the rule for a finding code; numbered addendum rows share ADD-CHANGE."""
    canonical = canonical_code(code)
    if canonical in CATALOG:
        return CATALOG[canonical]
    raise KeyError(f"Finding code {code!r} is not registered in the rule catalog.")


def canonical_code(code: str) -> str:
    code = str(code or "").strip().upper()
    if code.startswith("ADD-") and code[4:].isdigit():
        return "ADD-CHANGE"
    return _ALIASES.get(code, code)


def family_of(code: str) -> str:
    """Canonical concept for benchmarking; unknown codes keep their own name."""
    canonical = canonical_code(code)
    rule = CATALOG.get(canonical)
    return rule.family if rule else canonical


def all_rules() -> list[RuleSpec]:
    return list(_RULES)


__all__ = ["CATALOG", "Citation", "RuleSpec", "VerificationStatus", "all_rules", "canonical_code", "family_of", "get_rule"]

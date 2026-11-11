"""Extract text from user supplied procurement documents without storing files.

Hardening rules (each one has a chaos test in ``tests/test_chaos_inputs.py``):

* Empty, corrupted, password-protected or binary-disguised files are rejected
  with a user-facing Indonesian message, never a stack trace.
* Very large documents are *truncated*, not rejected: at most ``MAX_PDF_PAGES``
  pages and ``MAX_EXTRACTED_CHARACTERS`` characters are read, and the response
  carries ``truncated=True`` plus a warning the UI shows to the user.
* Office files (DOCX/XLSX) are ZIP containers; their declared uncompressed size
  is checked before parsing to stop decompression bombs.
* A scanned PDF without a text layer returns no text and a warning. It never
  injects placeholder text into the audit.
"""

from __future__ import annotations

import io
import re
import zipfile
import zlib
from pathlib import PurePath
from typing import Any
from xml.etree import ElementTree

from bidsentry.types.schemas import ValidationError

MAX_DOCUMENT_BYTES = 8 * 1024 * 1024
MAX_EXPANDED_FILE_BYTES = 8 * 1024 * 1024
MAX_ZIP_UNCOMPRESSED_BYTES = 64 * 1024 * 1024
MAX_EXTRACTED_CHARACTERS = 1_000_000
MAX_PDF_PAGES = 500
SCANNED_CHARS_PER_PAGE = 25
SUPPORTED_EXTENSIONS = {".txt", ".md", ".csv", ".json", ".docx", ".pdf", ".xlsx"}


def _reject(message: str, issue: str) -> ValidationError:
    return ValidationError(message, [{"field": "file", "issue": issue}])


class _Budget:
    """Collects text up to the character cap and records why reading stopped."""

    def __init__(self) -> None:
        self.parts: list[str] = []
        self.size = 0
        self.truncated = False

    def add(self, text: str) -> bool:
        if self.truncated:
            return False
        room = MAX_EXTRACTED_CHARACTERS - self.size
        if len(text) > room:
            self.parts.append(text[:room])
            self.size = MAX_EXTRACTED_CHARACTERS
            self.truncated = True
            return False
        self.parts.append(text)
        self.size += len(text)
        return True

    def text(self, separator: str = "\n") -> str:
        return separator.join(self.parts)


class DocumentExtractionService:
    def extract(self, filename: str, content: bytes) -> dict[str, Any]:
        safe_name = PurePath(str(filename or "")).name[:240]
        extension = PurePath(safe_name).suffix.casefold()
        if extension not in SUPPORTED_EXTENSIONS:
            allowed = ", ".join(sorted(SUPPORTED_EXTENSIONS))
            raise _reject(f"Format file belum didukung. Gunakan: {allowed}.", "unsupported_format")
        if not isinstance(content, (bytes, bytearray)) or not content:
            raise _reject("File kosong (0 byte). Unggah ulang dokumen yang berisi teks.", "empty_file")
        content = bytes(content)
        if len(content) > MAX_DOCUMENT_BYTES:
            raise _reject("Ukuran file maksimum 8 MB. Pecah dokumen menjadi beberapa bagian.", "file_too_large")

        warnings: list[str] = []
        truncated = False
        scanned_pdf = False
        pages: int | None = None
        excel_items_count: int | None = None
        try:
            if extension == ".docx":
                self._guard_zip(content, "DOCX")
                text, truncated = self._docx(content)
                extraction_mode = "docx_xml_parser"
            elif extension == ".xlsx":
                self._guard_zip(content, "Excel")
                from bidsentry.audits.excel_parser import parse_boq_excel
                excel = parse_boq_excel(content)
                text = excel["text"]
                excel_items_count = len(excel["items"])
                warnings.extend(excel.get("warnings", []))
                truncated = bool(excel.get("truncated"))
                extraction_mode = "excel_table_parser"
            elif extension == ".pdf":
                text, pages, extraction_mode, scanned_pdf, truncated, pdf_warnings = self._pdf_analyzed(content)
                warnings.extend(pdf_warnings)
            else:
                text, truncated = self._plain_text(content, extension)
                extraction_mode = "plain_text"
        except ValidationError:
            raise
        except Exception as exc:
            raise _reject("Isi file tidak dapat diekstrak. File mungkin rusak, terpotong saat diunduh, atau diproteksi.", "extraction_failed") from exc

        text = "\n".join(line.rstrip() for line in text.replace("\x00", "").splitlines()).strip()
        if not text and not scanned_pdf:
            raise _reject("Tidak ada teks yang dapat dibaca dari file ini. Pastikan file berisi teks digital, bukan gambar.", "no_extractable_text")
        if truncated:
            warnings.append(
                f"Dokumen sangat besar: hanya {MAX_EXTRACTED_CHARACTERS:,} karakter pertama".replace(",", ".")
                + (f" (maksimal {MAX_PDF_PAGES} halaman)" if extension == ".pdf" else "")
                + " yang diperiksa. Unggah bagian lain secara terpisah agar seluruh isi diaudit."
            )

        result: dict[str, Any] = {
            "filename": safe_name,
            "text": text,
            "characters": len(text),
            "extraction_mode": extraction_mode,
            "scanned_pdf": scanned_pdf,
            "truncated": truncated,
            "warnings": warnings,
        }
        if pages is not None:
            result["pages"] = pages
        if excel_items_count is not None:
            result["excel_items_count"] = excel_items_count
        return result

    # ------------------------------------------------------------- formats
    @staticmethod
    def _guard_zip(content: bytes, label: str) -> None:
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                total = sum(info.file_size for info in archive.infolist())
                if len(archive.infolist()) > 10_000 or total > MAX_ZIP_UNCOMPRESSED_BYTES:
                    raise _reject(f"Isi file {label} setelah dibuka melebihi batas aman. File ditolak untuk mencegah 'zip bomb'.", "expanded_file_too_large")
        except zipfile.BadZipFile as exc:
            raise _reject(f"File {label} rusak atau bukan file {label} yang valid.", "corrupted_file") from exc

    @staticmethod
    def _plain_text(content: bytes, extension: str) -> tuple[str, bool]:
        sample = content[:8192]
        if b"\x00" in sample or sum(1 for byte in sample if byte < 9 or 13 < byte < 32) > len(sample) * 0.05:
            raise _reject("File ini berisi data biner, bukan teks. Periksa ekstensi file atau ekspor ulang sebagai teks.", "binary_content")
        try:
            text = content.decode("utf-8-sig")
        except UnicodeDecodeError:
            try:
                text = content.decode("cp1252")
            except UnicodeDecodeError:
                text = content.decode("latin-1")
        if extension == ".json":
            import json
            try:
                text = json.dumps(json.loads(text), ensure_ascii=False, indent=2)
            except (json.JSONDecodeError, RecursionError):
                pass
        if len(text) > MAX_EXTRACTED_CHARACTERS:
            return text[:MAX_EXTRACTED_CHARACTERS], True
        return text, False

    @staticmethod
    def _docx(content: bytes) -> tuple[str, bool]:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            try:
                info = archive.getinfo("word/document.xml")
            except KeyError as exc:
                raise _reject("File DOCX tidak memiliki isi dokumen (word/document.xml). File mungkin rusak.", "corrupted_file") from exc
            if info.file_size > MAX_EXPANDED_FILE_BYTES:
                raise _reject("Isi dokumen DOCX setelah dibuka melebihi batas aman 8 MB.", "expanded_file_too_large")
            with archive.open(info) as stream:
                document = stream.read(MAX_EXPANDED_FILE_BYTES + 1)
            if len(document) > MAX_EXPANDED_FILE_BYTES:
                raise _reject("Isi dokumen DOCX setelah dibuka melebihi batas aman 8 MB.", "expanded_file_too_large")
        if b"<!DOCTYPE" in document.upper() or b"<!ENTITY" in document.upper():
            raise _reject("Deklarasi XML khusus tidak diizinkan pada DOCX.", "unsafe_xml_declaration")
        root = ElementTree.fromstring(document)
        ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
        budget = _Budget()
        for paragraph in root.iter(f"{ns}p"):
            parts: list[str] = []
            for node in paragraph.iter():
                if node.tag == f"{ns}t" and node.text:
                    parts.append(node.text)
                elif node.tag == f"{ns}tab":
                    parts.append("\t")
                elif node.tag in {f"{ns}br", f"{ns}cr"}:
                    parts.append("\n")
            value = "".join(parts).strip()
            if value and not budget.add(value + "\n"):
                break
        return budget.text(""), budget.truncated

    @staticmethod
    def _pdf_analyzed(content: bytes) -> tuple[str, int, str, bool, bool, list[str]]:
        """Read at most MAX_PDF_PAGES pages / MAX_EXTRACTED_CHARACTERS characters."""
        warnings: list[str] = []
        page_count = 0
        budget = _Budget()
        pages_truncated = False

        try:
            import pymupdf
            with pymupdf.open(stream=content, filetype="pdf") as doc:
                if doc.needs_pass or doc.is_encrypted:
                    raise _reject("PDF dilindungi kata sandi atau terenkripsi. Buka proteksinya lalu unggah ulang.", "encrypted_pdf")
                page_count = len(doc)
                for index, page in enumerate(doc):
                    if index >= MAX_PDF_PAGES:
                        pages_truncated = True
                        break
                    if not budget.add((page.get_text() or "") + "\n"):
                        break
        except ValidationError:
            raise
        except Exception:
            budget = _Budget()

        if not budget.size:
            try:
                from pypdf import PdfReader
                reader = PdfReader(io.BytesIO(content), strict=False)
                if reader.is_encrypted:
                    raise _reject("PDF dilindungi kata sandi atau terenkripsi. Buka proteksinya lalu unggah ulang.", "encrypted_pdf")
                page_count = page_count or len(reader.pages)
                for index, page in enumerate(reader.pages):
                    if index >= MAX_PDF_PAGES:
                        pages_truncated = True
                        break
                    if not budget.add((page.extract_text() or "") + "\n"):
                        break
            except ValidationError:
                raise
            except Exception:
                budget = _Budget()

        if not budget.size and not page_count:
            # No parser could open the file at all: not a usable PDF.
            fallback = DocumentExtractionService._pdf_basic(content)
            if not fallback.strip():
                raise _reject("File PDF rusak atau tidak valid sehingga tidak dapat dibuka.", "corrupted_file")
            budget.add(fallback)
            warnings.append("PDF tidak dapat dibuka parser standar; teks dibaca dengan pembaca cadangan dan mungkin tidak lengkap.")

        text = budget.text().strip()
        page_count = max(page_count, 1)
        if pages_truncated:
            warnings.append(f"PDF memiliki {page_count} halaman; hanya {MAX_PDF_PAGES} halaman pertama yang diperiksa.")
        if len(text) / page_count < SCANNED_CHARS_PER_PAGE:
            warnings.append(
                "Dokumen terdeteksi sebagai pindaian (hampir tanpa lapisan teks). OCR belum tersedia pada versi ini; "
                "unggah PDF digital atau salin teks dokumen agar dapat diaudit. Audit tanpa teks akan berstatus Tidak Dapat Dinilai."
            )
            return text, page_count, "scanned_no_text_layer", True, budget.truncated or pages_truncated, warnings
        return text, page_count, "digital_pdf_text", False, budget.truncated or pages_truncated, warnings

    @staticmethod
    def _pdf_basic(content: bytes) -> str:
        """Best-effort extraction for uncomplicated PDFs when parsers are absent."""
        source = content.decode("latin-1", errors="ignore")
        streams: list[str] = []
        expanded_bytes = 0
        for match in re.finditer(r"stream\r?\n(.*?)\r?\nendstream", source, flags=re.DOTALL):
            raw = match.group(1).encode("latin-1", errors="ignore")
            decoded = raw
            for window in (zlib.MAX_WBITS, -zlib.MAX_WBITS):
                try:
                    inflater = zlib.decompressobj(window)
                    candidate = inflater.decompress(raw, MAX_EXPANDED_FILE_BYTES - expanded_bytes + 1)
                    if len(candidate) > MAX_EXPANDED_FILE_BYTES - expanded_bytes or inflater.unconsumed_tail:
                        raise _reject("PDF memuat data terkompresi yang melebihi batas aman 8 MB.", "expanded_file_too_large")
                    if inflater.eof:
                        decoded = candidate
                        break
                except zlib.error:
                    continue
            expanded_bytes += len(decoded)
            if expanded_bytes > MAX_EXPANDED_FILE_BYTES:
                raise _reject("PDF memuat data terkompresi yang melebihi batas aman 8 MB.", "expanded_file_too_large")
            streams.append(decoded.decode("latin-1", errors="ignore"))
            if len(streams) > 200:
                break
        text_source = "\n".join(streams)
        found: list[str] = []
        token = re.compile(r"\(((?:\\.|[^\\)])*)\)\s*Tj|\[([^\]]*?)\]\s*TJ")
        for item in token.finditer(text_source):
            value = item.group(1) if item.group(1) is not None else item.group(2)
            pieces = re.findall(r"\(((?:\\.|[^\\)])*)\)|<([0-9A-Fa-f]+)>", value)
            decoded_pieces: list[str] = []
            for literal, hexadecimal in pieces:
                if hexadecimal:
                    try:
                        decoded_pieces.append(bytes.fromhex(hexadecimal).decode("utf-16-be" if len(hexadecimal) % 4 == 0 else "latin-1", errors="ignore"))
                    except ValueError:
                        continue
                else:
                    literal = re.sub(r"\\([\\()])", r"\1", literal)
                    literal = re.sub(r"\\([0-7]{1,3})", lambda m: chr(int(m.group(1), 8)), literal)
                    decoded_pieces.append(literal.replace(r"\n", "\n").replace(r"\r", "\r").replace(r"\t", "\t"))
            if decoded_pieces:
                found.append("".join(decoded_pieces))
        return "\n".join(found)


__all__ = ["DocumentExtractionService", "MAX_DOCUMENT_BYTES", "MAX_EXTRACTED_CHARACTERS", "MAX_PDF_PAGES"]

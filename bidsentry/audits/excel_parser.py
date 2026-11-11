"""Deterministic, defensive Excel (.xlsx) parser for Bill of Quantities (BoQ) / HPS.

* Streams sheets in read-only mode and stops after ``MAX_ROWS`` rows (warning).
* Scans every sheet for a header row (uraian/pekerjaan + volume/harga/jumlah);
  falls back to a plain cell dump when no BoQ header exists anywhere.
* Uses cached values only (``data_only``): formulas are never evaluated, so
  circular references and hostile formulas such as ``=cmd|'/c calc'!A1`` or
  ``=SYSTEM()`` are inert. Any text cell that *looks* like a formula is reported
  as text and flagged in the warnings.
* Amounts written as text ("Rp 1.250.000,-", "1,25 miliar") are normalised;
  NaN/inf and negative quantities are ignored rather than poisoning totals.
* Emits text lines in the same ``Uraian | vol satuan | Rp harga | Rp jumlah``
  shape the BoQ arithmetic audit and Excel export read back.
"""

from __future__ import annotations

import io
import math
from typing import Any

import openpyxl

from bidsentry.audits.currency import parse_amount

MAX_ROWS = 5_000
MAX_COLUMNS = 40
FORMULA_PREFIXES = ("=", "+", "-", "@")
_DESC = ("uraian", "deskripsi", "pekerjaan", "item", "nama barang", "description")
_VOL = ("vol", "qty", "kuantitas", "jumlah barang", "banyaknya")
_UNIT = ("satuan", "unit", "sat.")
_PRICE = ("harga satuan", "unit price", "tarif", "harga/sat")
_TOTAL = ("total", "jumlah harga", "jumlah biaya", "subtotal", "jumlah (rp)", "jumlah")
_HPS = ("hps satuan", "harga satuan hps", "oe")


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        number = float(value)
    else:
        text = str(value).strip()
        if not text:
            return None
        amount = parse_amount(text if any(ch.isalpha() for ch in text) else "Rp " + text)
        if amount is None:
            try:
                amount = float(text.replace(" ", "").replace(",", "."))
            except ValueError:
                return None
        number = amount
    return number if math.isfinite(number) and number >= 0 else None


def _find(header: list[str], keys: tuple[str, ...], used: set[int]) -> int | None:
    for index, cell in enumerate(header):
        if index not in used and cell and any(key in cell for key in keys):
            used.add(index)
            return index
    return None


def _header_map(row: tuple[Any, ...]) -> dict[str, int] | None:
    header = [str(cell).strip().casefold() if cell is not None else "" for cell in row[:MAX_COLUMNS]]
    if not any(any(key in cell for key in _DESC) for cell in header):
        return None
    if not any(any(key in cell for key in _VOL + _PRICE + _TOTAL) for cell in header):
        return None
    used: set[int] = set()
    mapping: dict[str, int] = {}
    # Order matters: the more specific labels claim their column first.
    for name, keys in (("hps", _HPS), ("price", _PRICE), ("desc", _DESC), ("vol", _VOL), ("unit", _UNIT), ("total", _TOTAL)):
        index = _find(header, keys, used)
        if index is not None:
            mapping[name] = index
    for index, cell in enumerate(header):
        if index not in used and cell in {"no", "no.", "nomor", "kode"}:
            mapping["no"] = index
            break
    return mapping if "desc" in mapping else None


def _cell(row: tuple[Any, ...], index: int | None) -> Any:
    return row[index] if index is not None and index < len(row) else None


def parse_boq_excel(file_bytes: bytes) -> dict[str, Any]:
    """Parse a BoQ/HPS workbook into items, a total and audit-ready text."""
    workbook = openpyxl.load_workbook(filename=io.BytesIO(file_bytes), read_only=True, data_only=True)
    warnings: list[str] = []
    items: list[dict[str, Any]] = []
    fallback_lines: list[str] = []
    rows_seen = 0
    truncated = False
    formula_like = 0
    try:
        for sheet in workbook.worksheets:
            mapping: dict[str, int] | None = None
            for row in sheet.iter_rows(values_only=True, max_col=MAX_COLUMNS):
                rows_seen += 1
                if rows_seen > MAX_ROWS:
                    truncated = True
                    break
                if not any(cell not in (None, "") for cell in row):
                    continue
                if mapping is None:
                    mapping = _header_map(row)
                    if mapping is None:
                        cells = [str(cell).strip() for cell in row if cell not in (None, "")]
                        fallback_lines.append(f"[{sheet.title}] " + " | ".join(cells))
                    continue
                description = str(_cell(row, mapping.get("desc")) or "").strip()
                if not description or description.casefold().startswith(("total", "jumlah", "grand total", "ppn", "sub total")):
                    continue
                if description.startswith(FORMULA_PREFIXES):
                    formula_like += 1
                raw_volume = _cell(row, mapping.get("vol"))
                volume = _number(raw_volume)
                price = _number(_cell(row, mapping.get("price")))
                total = _number(_cell(row, mapping.get("total")))
                volume_missing = raw_volume in (None, "")
                if total is None and price is not None and (volume is not None or volume_missing):
                    # An empty volume means "1 lot"; a volume that is present but invalid is never guessed.
                    total = price * (volume if volume is not None else 1.0)
                items.append({
                    "sheet": sheet.title,
                    "no": str(_cell(row, mapping.get("no")) or len(items) + 1),
                    "description": description[:1000],
                    "volume": volume,
                    "unit": str(_cell(row, mapping.get("unit")) or "unit").strip()[:80] or "unit",
                    "unit_price": price,
                    "total": total or 0.0,
                    "hps_unit_price": _number(_cell(row, mapping.get("hps"))),
                })
            if truncated:
                break
    finally:
        workbook.close()

    if truncated:
        warnings.append(f"Workbook berisi lebih dari {MAX_ROWS:,} baris; baris setelahnya tidak dibaca.".replace(",", "."))
    if formula_like:
        warnings.append(f"{formula_like} uraian diawali karakter formula (=, +, -, @); diperlakukan sebagai teks biasa dan tidak pernah dieksekusi.")
    if not items:
        warnings.append("Tidak ditemukan tabel BoQ dengan kolom uraian dan harga/jumlah; isi sel dibaca sebagai teks biasa.")

    def money(value: float | None) -> str:
        return "Rp " + f"{value:,.0f}".replace(",", ".") if value is not None else "-"

    lines = ["=== HASIL PEMBACAAN BILL OF QUANTITIES (BoQ / HPS) ==="]
    for item in items:
        volume = item["volume"]
        volume_text = (f"{volume:g}" if volume is not None else "1").replace(".", ",")
        hps = f" | {money(item['hps_unit_price'])}" if item["hps_unit_price"] is not None else ""
        lines.append(f"{item['description']} | {volume_text} {item['unit']} | {money(item['unit_price'] if item['unit_price'] is not None else item['total'])} | {money(item['total'])}{hps}")
    total = sum(item["total"] for item in items)
    if items:
        lines.append(f"\nTOTAL BIAYA BoQ: {money(total)}")
    else:
        lines.extend(fallback_lines[:MAX_ROWS])
    return {"items": items, "total_idr": total, "text": "\n".join(lines), "warnings": warnings, "truncated": truncated}


__all__ = ["parse_boq_excel"]

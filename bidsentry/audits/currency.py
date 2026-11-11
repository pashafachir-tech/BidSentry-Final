"""Robust Indonesian Rupiah amount normaliser for prose, tables and BoQ text.

Recognised forms (all return the same float):

    Rp 3.400.000.000,-      Rp3.400.000.000,00     IDR 3,400,000,000.00
    3.400.000.000           Rp 3,4 miliar          Rp 3.4 M      3,4 milyar
    3400 juta               Rp 3.400 jt            3400000000

Single-letter magnitudes (M/B/T/K) are only accepted right after a currency
prefix, so "100 m" (metres) or "5 T" (tonnes) in a specification are never
read as money. Bare numbers without currency or magnitude need at least five
digits, so years ("2026") and durations ("6 hari") are ignored.
"""

from __future__ import annotations

import re

_MAGNITUDE = {
    "triliun": 1e12, "t": 1e12,
    "miliar": 1e9, "milyar": 1e9, "m": 1e9, "b": 1e9, "bn": 1e9,
    "juta": 1e6, "jt": 1e6,
    "ribu": 1e3, "rb": 1e3, "k": 1e3,
}
_WORD_UNITS = {"triliun", "miliar", "milyar", "juta", "jt", "ribu", "rb", "bn"}

AMOUNT_PATTERN = re.compile(
    r"(?P<cur>\bRp\.?|\bIDR)?\s*"
    r"(?P<num>\d{1,3}(?:[.,\s]\d{3})+(?:[.,]\d{1,2})?|\d+(?:[.,]\d+)?)"
    r"(?:\s*(?P<unit>triliun|miliar|milyar|juta|ribu|jt|rb|bn|[TtMmBbKk])\b)?",
    re.I,
)


def _plain_number(raw: str) -> float | None:
    """Parse a grouped number, inferring which of '.' / ',' is the decimal mark."""
    text = raw.replace(" ", "")
    dots, commas = text.count("."), text.count(",")
    if dots and commas:
        decimal = "," if text.rfind(",") > text.rfind(".") else "."
        thousands = "." if decimal == "," else ","
        text = text.replace(thousands, "").replace(decimal, ".")
    elif dots > 1 or commas > 1:
        text = text.replace(".", "").replace(",", "")
    elif dots == 1 or commas == 1:
        sep = "." if dots else ","
        head, tail = text.split(sep)
        # "3.400" / "3,400" are thousands groups; "3,4" / "3.45" are decimals.
        text = head + tail if len(tail) == 3 else head + "." + tail
    try:
        return float(text)
    except ValueError:
        return None


def _decimal_number(raw: str) -> float | None:
    """Number followed by a magnitude word: '3,4' or '3.4' are decimals, '3.400' is grouped."""
    text = raw.replace(" ", "")
    if re.fullmatch(r"\d{1,3}(?:[.,]\d{3})+", text):
        return _plain_number(text)
    try:
        return float(text.replace(",", "."))
    except ValueError:
        return None


def iter_amounts(text: str):
    """Yield ``(value_idr, match)`` for every money-like amount in ``text``."""
    for match in AMOUNT_PATTERN.finditer(text or ""):
        currency = bool(match.group("cur"))
        unit = (match.group("unit") or "").casefold()
        raw = match.group("num")
        if unit and (unit in _WORD_UNITS or currency):
            value = _decimal_number(raw)
            if value is not None:
                yield value * _MAGNITUDE[unit], match
            continue
        if not currency and len(re.sub(r"\D", "", raw)) < 5:
            continue
        value = _plain_number(raw)
        if value is not None and (currency or value >= 10_000):
            yield value, match


def parse_amount(text: str) -> float | None:
    """First Rupiah amount in ``text`` or ``None``."""
    for value, _ in iter_amounts(text):
        return value
    return None


__all__ = ["AMOUNT_PATTERN", "iter_amounts", "parse_amount"]

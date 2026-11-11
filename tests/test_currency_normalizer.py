"""Rupiah normaliser: many spellings, no false money reads."""

from __future__ import annotations

import pytest

from bidsentry.audits.currency import parse_amount

THREE_POINT_FOUR_BILLION = 3_400_000_000


@pytest.mark.parametrize("text", [
    "Rp 3.400.000.000,-",
    "Rp3.400.000.000,00",
    "IDR 3,400,000,000.00",
    "sebesar 3.400.000.000 rupiah",
    "Rp 3,4 miliar",
    "Rp 3.4 M",
    "3,4 milyar",
    "3400 juta",
    "Rp 3.400 jt",
    "3400000000",
])
def test_equivalent_spellings(text: str) -> None:
    assert parse_amount(text) == pytest.approx(THREE_POINT_FOUR_BILLION)


@pytest.mark.parametrize("text", [
    "Tahun anggaran 2026",
    "Masa sanggah 5 hari kerja",
    "Kabel sepanjang 100 m",
    "Kapasitas 5 T per hari",
    "Volume 12 unit",
])
def test_non_money_is_ignored(text: str) -> None:
    assert parse_amount(text) is None


def test_small_currency_amounts_and_thousand_units() -> None:
    assert parse_amount("Rp 850 rb") == pytest.approx(850_000)
    assert parse_amount("Rp 1,25 triliun") == pytest.approx(1_250_000_000_000)
    assert parse_amount("Rp 95.000.000") == pytest.approx(95_000_000)

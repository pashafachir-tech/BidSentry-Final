"""Contract-delay penalty parser and transparent what-if arithmetic."""

from __future__ import annotations

import re
from typing import Any


_RATE = re.compile(r"(?P<n>\d+(?:[.,]\d+)?)\s*/\s*(?P<d>\d{3,})|(?P<per_mille>\d+(?:[.,]\d+)?)\s*(?:‰|permil|per\s*mille)|(?P<pct>\d+(?:[.,]\d+)?)\s*%", re.I)

_WORD_NUM_MAP: dict[str, float] = {
    "nol": 0.0, "zero": 0.0,
    "satu": 1.0, "one": 1.0,
    "dua": 2.0, "two": 2.0,
    "tiga": 3.0, "three": 3.0,
    "empat": 4.0, "four": 4.0,
    "lima": 5.0, "five": 5.0,
    "enam": 6.0, "six": 6.0,
    "tujuh": 7.0, "seven": 7.0,
    "delapan": 8.0, "eight": 8.0,
    "sembilan": 9.0, "nine": 9.0,
    "sepuluh": 10.0, "ten": 10.0,
    "sebelas": 11.0, "eleven": 11.0,
    "dua belas": 12.0, "twelve": 12.0,
    "tiga belas": 13.0, "thirteen": 13.0,
    "empat belas": 14.0, "fourteen": 14.0,
    "lima belas": 15.0, "fifteen": 15.0,
    "enam belas": 16.0, "sixteen": 16.0,
    "tujuh belas": 17.0, "seventeen": 17.0,
    "delapan belas": 18.0, "eighteen": 18.0,
    "sembilan belas": 19.0, "nineteen": 19.0,
    "dua puluh": 20.0, "twenty": 20.0,
    "dua puluh lima": 25.0, "twenty five": 25.0,
}

_EXPLICIT_UNCAPPED = re.compile(
    r"\b(?:tanpa\s+batas|tidak\s+terbatas|without\s+limit|no\s+maximum|uncapped)\b",
    re.I,
)

_CAP_PREFIX = (
    r"(?:batas\s+(?:maksimal|maksimum|paling\s+banyak|paling\s+tinggi|sebesar-besarnya|setinggi-tingginya)|"
    r"maksimal|maksimum|paling\s+banyak|paling\s+tinggi|sebesar-besarnya|setinggi-tingginya|"
    r"tidak\s+lebih\s+dari|tidak\s+melebihi|dibatasi\s+sebesar|"
    r"capped\s+at|up\s+to(?:\s+a\s+maximum\s+of)?|not\s+exceeding|limit(?:ed)?\s+to|maximum\s+of)"
)

_DIGIT_CAP = re.compile(
    _CAP_PREFIX + r"\D{0,60}(\d+(?:[.,]\d+)?)\s*(?:%|persen\b|percent\b)",
    re.I,
)

_WORDS_REGEX = r"(" + "|".join(sorted([re.escape(k) for k in _WORD_NUM_MAP.keys()], key=len, reverse=True)) + r")"
_WORD_CAP = re.compile(
    _CAP_PREFIX + r"(?:[^a-zA-Z0-9\n]*\b[a-zA-Z]+\b){0,6}\s*" + _WORDS_REGEX + r"(?:\s+(?:koma|titik|point)\s+([a-z0-9]+))?\s*(?:%|persen\b|percent\b)",
    re.I,
)

_CAP = _DIGIT_CAP

# The model SSUK caps delay fines at the performance bond, stated without a percentage.
_BOND_CAP = re.compile(
    r"(?:tidak\s+(?:boleh\s+)?(?:melampaui|melebihi)|paling\s+(?:tinggi|banyak)|maksimal|maksimum|setinggi-tingginya|sebesar-besarnya|mencapai|dibatasi|not\s+exceeding|capped\s+at)\b.{0,60}?\bjaminan\s+pelaksanaan\b",
    re.I,
)


def _parse_cap(clause: str) -> float | None:
    if not clause:
        return None
    if _EXPLICIT_UNCAPPED.search(clause):
        return None

    m_digit = _DIGIT_CAP.search(clause)
    if m_digit:
        try:
            return _decimal(m_digit.group(1)) / 100.0
        except ValueError:
            pass

    m_word = _WORD_CAP.search(clause)
    if m_word:
        base_word = m_word.group(1).lower().strip()
        val = _WORD_NUM_MAP.get(base_word)
        if val is not None:
            dec_word = m_word.group(2)
            if dec_word:
                dec_word = dec_word.lower().strip()
                dec_val = _WORD_NUM_MAP.get(dec_word)
                if dec_val is None and dec_word.isdigit():
                    dec_val = float(dec_word)
                if dec_val is not None:
                    val = val + (dec_val / 10.0 if dec_val < 10 else dec_val / 100.0)
            return val / 100.0

    return None


def _decimal(value: str) -> float:
    return float(value.replace(",", "."))


def _parse_rate(text: str) -> float | None:
    match = _RATE.search(text)
    if not match:
        return None
    if match.group("n"):
        denominator = float(match.group("d"))
        return _decimal(match.group("n")) / denominator if denominator else None
    if match.group("per_mille"):
        return _decimal(match.group("per_mille")) / 1000
    return _decimal(match.group("pct")) / 100


def calculate_penalty_scenarios(
    contract_value_idr: float,
    clause_text: str,
    *,
    delay_days: tuple[int, ...] = (10, 30, 50),
    statutory_daily_rate: float = 0.001,
    illustrative_cap_percentage: float = 0.05,
) -> dict[str, Any]:
    """Compute contract and comparison scenarios without making a legal finding.

    Perpres 16/2018 as amended through Perpres 46/2025 specifies a 1‰ daily
    delay fine in the cited provision. A 5% cap is exposed only as an
    illustrative assumption and must not be presented as the statutory cap.
    """
    if isinstance(contract_value_idr, bool) or contract_value_idr < 0:
        raise ValueError("contract_value_idr must be a non-negative number")
    if not 0 < statutory_daily_rate < 1 or not 0 < illustrative_cap_percentage <= 1:
        raise ValueError("Penalty rate and cap must be within valid percentage bounds")
    lines = [line.strip() for line in clause_text.splitlines() if line.strip()]
    penalty_lines: list[str] = []
    last_penalty_index = -10
    for index, line in enumerate(lines):
        if re.search(r"denda|sanksi\s+keterlambatan|liquidated\s+damages|delay\s+penalty", line, re.I):
            penalty_lines.append(line)
            last_penalty_index = index
        elif index - last_penalty_index <= 2 and (
            re.match(r"^(?:batas|maksimal|maksimum|paling\s+banyak|tidak\s+lebih|total\s+akumulasi|capped|up\s+to|not\s+exceeding)", line, re.I)
            or _BOND_CAP.search(line)
        ):
            penalty_lines.append(line)
    full_clause = " ".join(penalty_lines)
    clause = full_clause[:1200]
    # Judge the harshest daily rate in the document, wherever it appears.
    daily_rates = [rate for line in penalty_lines if re.search(r"hari|\bday|‰|permil|/\s*1000", line, re.I) and (rate := _parse_rate(line)) is not None]
    contract_rate = max(daily_rates) if daily_rates else _parse_rate(full_clause) if full_clause else None
    clause_cap = _parse_cap(full_clause) if full_clause else None
    explicitly_uncapped = bool(_EXPLICIT_UNCAPPED.search(full_clause))
    capped_by_bond = bool(full_clause and clause_cap is None and not explicitly_uncapped and _BOND_CAP.search(full_clause))
    no_stated_cap = bool(penalty_lines and clause_cap is None and not capped_by_bond)
    # Silence about a cap at the regulated rate is a question for the reviewer; only an
    # explicit "no limit", or an above-regulation rate with no limit, is a confirmed gap.
    uncapped = no_stated_cap and (explicitly_uncapped or (contract_rate is not None and contract_rate > statutory_daily_rate))
    scenarios: list[dict[str, Any]] = []
    for days in delay_days:
        if isinstance(days, bool) or days < 0:
            raise ValueError("delay_days must contain non-negative integers")
        contractual_raw = contract_value_idr * (contract_rate or statutory_daily_rate) * days
        effective_cap = clause_cap if clause_cap is not None else illustrative_cap_percentage if capped_by_bond else None
        contractual_value = min(contractual_raw, contract_value_idr * effective_cap) if effective_cap is not None else contractual_raw
        statutory_comparison_raw = contract_value_idr * statutory_daily_rate * days
        illustrative_cap = contract_value_idr * illustrative_cap_percentage
        scenarios.append({
            "delay_days": days,
            "contract_clause_amount_idr": round(contractual_value, 2),
            "contract_clause_amount_uncapped_idr": round(contractual_raw, 2),
            "contract_clause_vs_illustrative_cap_excess_idr": round(max(0, contractual_value - illustrative_cap), 2),
            "1_per_mille_daily_comparison_idr": round(statutory_comparison_raw, 2),
            "illustrative_5_percent_cap_amount_idr": round(min(statutory_comparison_raw, illustrative_cap), 2),
            "illustrative_cap_excess_idr": round(max(0, contractual_value - illustrative_cap), 2),
            "statutory_comparison_cap_excess_idr": round(max(0, statutory_comparison_raw - illustrative_cap), 2),
        })
    alerts: list[str] = []
    if uncapped:
        alerts.append("CRITICAL_POISON_PILL")
    elif no_stated_cap:
        alerts.append("PENALTY_CAP_NOT_STATED")
    if contract_rate is not None and contract_rate > statutory_daily_rate:
        alerts.append("CONTRACT_RATE_ABOVE_1_PER_MILLE_COMPARISON")
    if not penalty_lines:
        alerts.append("PENALTY_CLAUSE_NOT_FOUND")
    return {
        "status": "calculated" if contract_value_idr > 0 else "contract_value_required",
        "contract_value_idr": round(contract_value_idr, 2),
        "clause_quote": clause or None,
        "contract_daily_rate": contract_rate,
        "contract_cap_percentage": clause_cap,
        "contract_cap_basis": "persen_klausul" if clause_cap is not None else "jaminan_pelaksanaan" if capped_by_bond else None,
        "uncapped_clause_detected": uncapped,
        "alerts": alerts,
        "scenarios": scenarios,
        "assumptions": {
            "daily_comparison_rate": statutory_daily_rate,
            "daily_rate_source": "Perpres 16/2018 Pasal 79 ayat (4): 1‰ per hari dari nilai kontrak atau bagian kontrak (dikonfirmasi sumber sekunder; cocokkan dengan naskah konsolidasi)",
            "cap_source": "Model SSUK LKPP: denda keterlambatan tidak melampaui besarnya Jaminan Pelaksanaan (sumber sekunder)",
            "illustrative_cap_percentage": illustrative_cap_percentage,
            "cap_note": "Ilustrasi 5% mengasumsikan Jaminan Pelaksanaan sebesar 5% nilai kontrak; batas sebenarnya adalah besaran Jaminan Pelaksanaan pada kontrak paket.",
        },
        "review_note": "Aritmetika ini bukan nasihat hukum. Cocokkan basis pengenaan (nilai kontrak atau bagian kontrak), klausul final, dan aturan yang berlaku pada tanggal paket.",
    }

"""Compare tender requirements before and after an addendum."""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any


_SPLIT = re.compile(r"\n+|(?<=[.!?;])\s+(?=[A-Z0-9])")
_SPACE = re.compile(r"\s+")


def _items(text: str) -> list[str]:
    values: list[str] = []
    for raw in _SPLIT.split(text.replace("\r", "\n")):
        value = _SPACE.sub(" ", raw).strip(" \t-*•–—")
        if len(value) >= 8:
            values.append(value)
    return values


def _key(text: str) -> str:
    return _SPACE.sub(" ", re.sub(r"[^\w%.,:/-]", " ", text.casefold())).strip()


def diff_addendum(original_text: str, addendum_text: str, *, threshold: float = 0.48) -> dict[str, Any]:
    """Return requirement-level changes, preserving exact source wording.

    This is a text comparison aid. It does not decide which document legally
    controls; publication dates, hierarchy clauses and procurement rules still
    require reviewer confirmation.
    """
    original = _items(original_text)
    added = _items(addendum_text)
    remaining = set(range(len(added)))
    changes: list[dict[str, Any]] = []
    for index, requirement in enumerate(original, start=1):
        key = _key(requirement)
        exact = next((candidate for candidate in sorted(remaining) if _key(added[candidate]) == key), None)
        if exact is not None:
            remaining.remove(exact)
            changes.append({"item_id": f"REQ-{index:03d}", "original_requirement": requirement, "adendum_requirement": added[exact], "change_status": "UNCHANGED", "similarity": 1.0})
            continue
        best = max(remaining, key=lambda candidate: SequenceMatcher(None, key, _key(added[candidate])).ratio(), default=None)
        similarity = SequenceMatcher(None, key, _key(added[best])).ratio() if best is not None else 0.0
        if best is not None and similarity >= threshold:
            remaining.remove(best)
            changes.append({"item_id": f"REQ-{index:03d}", "original_requirement": requirement, "adendum_requirement": added[best], "change_status": "MODIFIED", "similarity": round(similarity, 4)})
        else:
            changes.append({"item_id": f"REQ-{index:03d}", "original_requirement": requirement, "adendum_requirement": None, "change_status": "REVOKED", "similarity": round(similarity, 4)})
    for index in sorted(remaining):
        changes.append({"item_id": f"ADD-{index + 1:03d}", "original_requirement": None, "adendum_requirement": added[index], "change_status": "ADDED", "similarity": 0.0})
    obsolete = [
        {"item_id": row["item_id"], "criterion": row["original_requirement"], "reason": "Persyaratan asli tidak ditemukan dalam teks adendum." if row["change_status"] == "REVOKED" else "Redaksi persyaratan berubah; periksa versi yang berlaku."}
        for row in changes if row["change_status"] in {"REVOKED", "MODIFIED"}
    ]
    return {"status": "compared", "comparison_method": "normalized line and sentence similarity", "changes": changes, "obsolete_criteria": obsolete, "counts": {status: sum(row["change_status"] == status for row in changes) for status in ("UNCHANGED", "MODIFIED", "REVOKED", "ADDED")}, "review_note": "Kemiripan teks tidak menetapkan urutan atau kekuatan hukum dokumen."}

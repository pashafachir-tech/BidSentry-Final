#!/usr/bin/env python3
"""Audit benchmark test labels against engine rule catalog.

Identifies valid vs phantom rule IDs in expected_findings and forbidden_findings,
and analyzes their impact on benchmark metrics (especially Trap Evasion Rate).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))



def get_engine_rule_ids() -> set[str]:
    """Every finding code the engine can emit, plus the label aliases the catalog maps."""
    from bidsentry.evaluators.rule_catalog import all_rules

    ids: set[str] = set()
    for rule in all_rules():
        ids.add(rule.code)
        ids.update(rule.aliases)
    return ids

def audit_directory(dir_path: Path, engine_ids: set[str]) -> list[dict[str, Any]]:
    rows = []
    for f in sorted(dir_path.glob("*.json")):
        data = json.loads(f.read_text(encoding="utf-8"))
        doc_id = data.get("id", f.stem)
        is_trap = data.get("is_trap", False)
        exp_findings = data.get("expected_findings", {})
        forb_findings = data.get("forbidden_findings", [])

        exp_keys = set(exp_findings.keys())
        forb_keys = set(forb_findings)
        doc_label_ids = exp_keys | forb_keys

        valid_in_doc = doc_label_ids & engine_ids
        phantom_in_doc = doc_label_ids - engine_ids

        rows.append({
            "file": f.name,
            "doc_id": doc_id,
            "is_trap": is_trap,
            "expected_findings": sorted(exp_keys),
            "forbidden_findings": sorted(forb_keys),
            "valid_ids": sorted(valid_in_doc),
            "phantom_ids": sorted(phantom_in_doc),
            "has_phantom": bool(phantom_in_doc),
        })
    return rows


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    engine_ids = get_engine_rule_ids()

    blind_rows = audit_directory(ROOT / "data" / "test_blind", engine_ids)
    budget_rows = audit_directory(ROOT / "data" / "test_narrative_budget", engine_ids)
    all_rows = blind_rows + budget_rows

    all_expected: set[str] = set()
    all_forbidden: set[str] = set()
    for r in all_rows:
        all_expected.update(r["expected_findings"])
        all_forbidden.update(r["forbidden_findings"])

    all_label_ids = all_expected | all_forbidden
    valid_ids = all_label_ids & engine_ids
    phantom_ids = all_label_ids - engine_ids

    print("=" * 70)
    print("BID SENTRY - AUDIT INTEGRITAS LABEL PENGUJIAN (BENCHMARK SUITE v1)")
    print("=" * 70)
    print(f"Total Rule ID di Kamus Engine     : {len(engine_ids)}")
    print(f"Total Unique ID di Label Benchmark : {len(all_label_ids)}")
    print(f"  - Valid ID (Terdaftar di Engine) : {len(valid_ids)} ({len(valid_ids)/len(all_label_ids)*100:.1f}%)")
    print(f"  - Phantom ID (Tidak Ada di Engine): {len(phantom_ids)} ({len(phantom_ids)/len(all_label_ids)*100:.1f}%)")
    print("-" * 70)

    print("\n[DAFTAR ID VALID (DAPAT DIPRODUKSI ENGINE)]:")
    for vid in sorted(valid_ids):
        print(f"  [VALID]   {vid}")

    print("\n[DAFTAR PHANTOM ID (TIDAK PERNAH ADA DI ENGINE)]:")
    alias_hint = {
        "SPEC-LOCKIN-PROC": "Setara dengan SPEC-LOCKIN-CPU di engine",
        "PROC-TIMELINE-PREP": "Setara dengan PROC-TIMELINE-COMPRESSED di engine",
        "PROC-TIMELINE-SANGGAH": "Setara dengan PROC-TIMELINE-COMPRESSED di engine",
        "FIN-HPS-OVER-PAGU": "Setara dengan FIN-OVER-BUDGET di engine",
        "FIN-BILLING-RATE": "Setara dengan FIN-MARKUP-RATE di engine",
        "GOV-CONFLICT-INTEREST": "Tidak ada modul deteksi benturan kepentingan",
    }
    for pid in sorted(phantom_ids):
        hint = alias_hint.get(pid, "Tidak dikenal")
        print(f"  [PHANTOM] {pid:<25} -> {hint}")

    print("\n" + "=" * 70)
    print("RINCIAN AUDIT PER-DOKUMEN DENGAN PHANTOM ID")
    print("=" * 70)
    for r in all_rows:
        if r["has_phantom"]:
            trap_tag = " [TRAP]" if r["is_trap"] else ""
            print(f"Dokumen: {r['doc_id']}{trap_tag}")
            print(f"  File     : {r['file']}")
            print(f"  Expected : {r['expected_findings']}")
            print(f"  Forbidden: {r['forbidden_findings']}")
            print(f"  Phantom  : {r['phantom_ids']}")
            print()

    print("=" * 70)
    print("IMPLIKASI METODOLOGIS TERHADAP SKOR EVALUASI")
    print("=" * 70)
    print("1. Trap Evasion Semu (Trivial Pass):")
    print("   Pada dokumen jebakan seperti blind_05 dan blind_10, forbidden_findings")
    print("   seluruhnya berisi phantom ID (misal SPEC-LOCKIN-PROC, GOV-CONFLICT-INTEREST).")
    print("   Karena engine tidak memiliki ID tersebut, forbidden findings TIDAK PERNAH")
    print("   mungkin terpicu. Hal ini menyebabkan Trap Evasion Rate lolos secara semu (100%),")
    print("   bukan karena engine cerdas menolak jebakan, melainkan karena label salah sasaran.")
    print("2. Reduksi Buatan pada Macro Precision & Recall:")
    print("   Pada dokumen non-trap (blind_02, 03, 06, 09), penggunaan ID hantu pada")
    print("   expected_findings menyebabkan engine yang mendeteksi pelanggaran secara tepat")
    print("   (misal SPEC-LOCKIN-CPU) tetap diganjar 1 FN dan 1 FP.")
    print("3. Kesimpulan:")
    print("   Label benchmark v1 memerlukan set pengujian tandingan yang jujur (Traps v2)")
    print("   dengan ID aturan yang valid dan kontrol positif yang ketat.")
    print("=" * 70)


if __name__ == "__main__":
    main()

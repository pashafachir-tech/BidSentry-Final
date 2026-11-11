#!/usr/bin/env python3
"""One-command stage reset: clean audit history and seed the two demo packages.

    python scripts/seed_demo.py              # back up history, seed Paket A (Pokja) and Paket B (Vendor)
    python scripts/seed_demo.py --keep-history

The previous audit log is MOVED to backups/demo-reset-<timestamp>/ (never
deleted), so engine metrics on the dashboard start fresh. The packages are run
through the real evaluation pipeline, so every number shown on stage is a real
engine result for the synthetic demo documents.

After seeding, open http://127.0.0.1:8000 and use the demo hotkeys:
    [1] Pokja + Paket A   [2] Vendor + Paket B   [Esc] close
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bidsentry.app import create_application  # noqa: E402
from bidsentry.config import Settings  # noqa: E402
from bidsentry.services.demo_service import reset_and_seed  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--keep-history", action="store_true", help="Do not move the existing audit log to backups/.")
    args = parser.parse_args()

    settings = Settings.from_environment()
    application = create_application(settings)
    report = reset_and_seed(application, keep_history=args.keep_history)

    if report["backup"]:
        print(f"Riwayat audit lama dipindahkan ke: {report['backup']}")
    else:
        print("Tidak ada riwayat audit lama; workspace sudah bersih." if not args.keep_history else "Riwayat audit dipertahankan.")
    for item in report["seeded"]:
        print(f"[{item['key']}] {item['role']:<6} {item['package_name']}")
        print(f"      {item['verdict']} · Risiko {item['risk_label']} ({item['rule']}) · temuan: {', '.join(item['findings'])} · {item['engine_ms']} ms")
    print("\nSiap tampil. Buka http://127.0.0.1:8000 lalu tekan [1] untuk Pokja atau [2] untuk Vendor.")
    return 0 if len(report["seeded"]) == 2 else 1


if __name__ == "__main__":
    raise SystemExit(main())

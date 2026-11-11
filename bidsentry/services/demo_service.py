"""Stage-demo packages (synthetic) and one-command workspace reset.

The two packages in ``data/demo`` are synthetic and labelled as such in their
package names, so a demo audit can never be mistaken for a real tender.
``reset_and_seed`` *moves* the previous audit history to a timestamped backup
folder instead of deleting it.
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

DEMO_DIR_NAME = "demo"


def demo_dir(workspace_root: Path) -> Path:
    return workspace_root / "data" / DEMO_DIR_NAME


def load_packages(workspace_root: Path) -> list[dict[str, Any]]:
    packages: list[dict[str, Any]] = []
    for path in sorted(demo_dir(workspace_root).glob("paket_*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(data, dict) and isinstance(data.get("request"), dict) and data.get("role") in {"pokja", "vendor"}:
            packages.append({key: data.get(key) for key in ("key", "role", "title", "story", "synthetic", "request")})
    return packages


def _history_paths(audit_log_path: Path) -> list[Path]:
    return [
        audit_log_path,
        audit_log_path.parent / "audit_sources",
        audit_log_path.with_name(f"{audit_log_path.stem}_comprehensive_chain.jsonl"),
    ]


def backup_history(audit_log_path: Path) -> Path | None:
    """Move existing audit history into ``backups/demo-reset-<timestamp>``; return that folder."""
    existing = [path for path in _history_paths(audit_log_path) if path.exists()]
    if not existing:
        return None
    target = audit_log_path.parent / "backups" / f"demo-reset-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    target.mkdir(parents=True, exist_ok=True)
    for path in existing:
        shutil.move(str(path), str(target / path.name))
    return target


def reset_and_seed(application: Any, *, keep_history: bool = False) -> dict[str, Any]:
    """Back up the audit log, then run each demo package through the real audit pipeline."""
    backup = None if keep_history else backup_history(application.settings.audit_log_path)
    seeded = []
    for package in load_packages(application.settings.workspace_root):
        payload = {**package["request"], "allow_external_processing": False}  # a stage reset never sends text to an AI provider
        result = application.audit.create(payload, role=package["role"])
        seeded.append({
            "key": package["key"], "role": package["role"], "audit_id": result["audit_id"],
            "package_name": result["package_name"], "verdict": result["verdict"], "risk_label": result["risk"]["label"],
            "rule": result["risk"]["rule_applied"], "findings": [f["id"] for f in result["findings"] if f["status"] != "TERPENUHI"],
            "engine_ms": result["performance"]["engine_duration_ms"],
        })
    return {"backup": str(backup) if backup else None, "seeded": seeded}


__all__ = ["backup_history", "load_packages", "reset_and_seed"]

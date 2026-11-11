#!/usr/bin/env python3
"""Synchronize test count across README and documentation based on actual test suite collection."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def get_actual_test_count() -> int:
    """Query pytest for collected test item count."""
    cmd = [str(ROOT / ".venv" / "Scripts" / "python.exe"), "-m", "pytest", "--collect-only", "-q"]
    output = subprocess.check_output(cmd, cwd=str(ROOT), text=True)
    # Output ends with e.g. "87 tests collected in 0.12s" or "87 items"
    m = re.search(r"(\d+)\s+(?:tests?|items?)\s+collected", output)
    if m:
        return int(m.group(1))
    raise RuntimeError(f"Could not parse test count from pytest output: {output}")


def update_docs(test_count: int) -> None:
    readme_path = ROOT / "README.md"
    if readme_path.exists():
        content = readme_path.read_text(encoding="utf-8")
        # Update badge
        content = re.sub(
            r"tests-\d+%20passed-brightgreen\.svg",
            f"tests-{test_count}%20passed-brightgreen.svg",
            content,
        )
        content = re.sub(
            r"## 🧪 Rangkaian Pengujian Mandiri \(\d+ Test Cases\)",
            f"## 🧪 Rangkaian Pengujian Mandiri ({test_count} Test Cases)",
            content,
        )
        content = re.sub(
            r"\((\d+) passed tests(?:, 0 warnings)?\)",
            f"({test_count} passed tests, 0 warnings)",
            content,
        )
        readme_path.write_text(content, encoding="utf-8")
        print(f"Updated {readme_path.name} to {test_count} tests.")

    changelog_path = ROOT / "docs" / "CHANGELOG.md"
    if changelog_path.exists():
        content = changelog_path.read_text(encoding="utf-8")
        content = re.sub(r"\b\d+\s+unit tests\b", f"{test_count} unit tests", content)
        changelog_path.write_text(content, encoding="utf-8")
        print(f"Updated {changelog_path.name} to {test_count} tests.")


if __name__ == "__main__":
    count = get_actual_test_count()
    print(f"Actual collected test count: {count}")
    update_docs(count)

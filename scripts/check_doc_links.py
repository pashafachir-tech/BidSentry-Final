#!/usr/bin/env python3
"""Scanner for verifying that all local markdown links in README.md and docs/*.md exist and use relative paths."""

from __future__ import annotations

import re
import sys
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

LINK_PATTERN = re.compile(r'!?\[([^\]]*)\]\(([^)]+)\)')


def get_markdown_files() -> list[Path]:
    files = [ROOT / "README.md"]
    docs_dir = ROOT / "docs"
    if docs_dir.exists():
        files.extend(sorted(docs_dir.glob("*.md")))
    return [f for f in files if f.exists()]


def check_markdown_links() -> tuple[list[str], int]:
    """Scan README.md and docs/*.md for invalid local links or file:/// absolute paths.
    
    Returns (errors, total_links_checked).
    """
    errors: list[str] = []
    total_checked = 0

    for doc in get_markdown_files():
        content = doc.read_text(encoding="utf-8")
        rel_doc = doc.relative_to(ROOT)

        for match in LINK_PATTERN.finditer(content):
            label, raw_target = match.group(1), match.group(2).strip()
            total_checked += 1

            # 1. Absolute Windows / file protocol link forbidden
            if raw_target.lower().startswith("file:///"):
                errors.append(f"[{rel_doc}] Absolute file:// link forbidden: {raw_target} (label: '{label}')")
                continue

            # 2. Skip external links and internal-page anchors
            if raw_target.startswith(("http://", "https://", "mailto:", "ftp://", "#")):
                continue

            # 3. Strip query parameters and anchors
            clean_target = raw_target.split("#")[0].split("?")[0].strip()
            if not clean_target:
                continue

            # URL unquote (%20 -> space, etc.)
            clean_target = urllib.parse.unquote(clean_target)

            # 4. Resolve relative to the markdown file's directory
            resolved_target = (doc.parent / clean_target).resolve()

            if not resolved_target.exists():
                errors.append(
                    f"[{rel_doc}] Target does not exist: '{raw_target}' "
                    f"resolved to '{resolved_target}' (label: '{label}')"
                )

    return errors, total_checked


def main() -> int:
    errors, total = check_markdown_links()
    if errors:
        print(f"FAILED: Found {len(errors)} broken link(s) across {total} links checked:\n", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        return 1

    print(f"PASSED: All {total} markdown links in README.md and docs/*.md are valid and relative.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

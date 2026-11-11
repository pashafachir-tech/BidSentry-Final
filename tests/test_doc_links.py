"""Test to ensure all markdown documentation links are valid, relative, and non-broken."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.check_doc_links import check_markdown_links


def test_markdown_documentation_links():
    """Verify that all markdown links in README.md and docs/*.md exist and use relative paths."""
    errors, total_checked = check_markdown_links()
    assert not errors, f"Found {len(errors)} broken documentation links:\n" + "\n".join(f" - {e}" for e in errors)
    assert total_checked > 0, "Expected at least one documentation link to be checked"

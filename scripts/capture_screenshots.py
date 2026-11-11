#!/usr/bin/env python3
"""End-to-end UI walkthrough that also refreshes docs/screenshots/.

Starts a throwaway local server (temporary audit log, demo packages are local-only,
nothing is sent to an AI provider), then drives Chromium through the stage demo:

    login screen -> Pokja command center -> Demo A (Pokja) -> audit trail -> Demo B (Vendor)

Every step asserts what the jury will see, so this doubles as the browser smoke test.

    python scripts/capture_screenshots.py            # needs: pip install playwright && playwright install chromium
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "screenshots"


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _wait_until_up(url: str, timeout: float = 30.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2):
                return
        except OSError:
            time.sleep(0.3)
    raise RuntimeError(f"Server did not start at {url}")


def main() -> int:
    from playwright.sync_api import expect, sync_playwright

    OUT.mkdir(parents=True, exist_ok=True)
    port = _free_port()
    base = f"http://127.0.0.1:{port}"
    with tempfile.TemporaryDirectory() as tmp:
        env = {
            **os.environ,
            "HOST": "127.0.0.1", "PORT": str(port), "AUDIT_LOG_PATH": str(Path(tmp) / "audit.jsonl"),
            "BIDSENTRY_ACCESS_TOKEN": "", "BIDSENTRY_POKJA_PIN": "", "BIDSENTRY_VENDOR_PIN": "",
            "BIDSENTRY_SESSION_SECRET": "screenshot-run", "LANGFLOW_ENABLED": "false",
        }
        server = subprocess.Popen([sys.executable, "server.py", "--port", str(port)], cwd=ROOT, env=env,
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            _wait_until_up(base + "/api/health")
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True)
                page = browser.new_context(viewport={"width": 1440, "height": 900}, device_scale_factor=1).new_page()

                page.goto(base, wait_until="networkidle")
                expect(page.locator("form.login-role")).to_have_count(2)
                page.screenshot(path=str(OUT / "01_login_peran.png"))

                page.locator('form.login-role[data-login-role="pokja"] button[type="submit"]').click()
                expect(page.locator(".role-chip")).to_contain_text("Pokja")
                page.wait_for_timeout(1300)  # role transition animation
                page.screenshot(path=str(OUT / "02_command_center_pokja.png"))

                # Toasts are fixed overlays; keep them out of the documentation images.
                page.add_style_tag(content="#toast, .toast { display: none !important; }")
                page.keyboard.press("1")  # Demo A: over-budget + uncapped penalty
                expect(page.locator("#risk-review")).to_be_visible(timeout=20000)
                expect(page.locator(".review-table tbody tr").first).to_be_visible()
                page.wait_for_timeout(600)
                page.locator("#risk-review").screenshot(path=str(OUT / "03_hasil_pokja_demo_a.png"))

                page.locator('[data-action="review-tab"][data-tab="proof"]').first.click()
                page.wait_for_timeout(400)
                page.locator("#risk-review").screenshot(path=str(OUT / "04_jejak_audit_ai_python.png"))

                page.keyboard.press("2")  # Demo B: brand lock-in + BoQ arithmetic mismatch
                expect(page.locator(".role-chip")).to_contain_text("Vendor", timeout=20000)
                expect(page.locator("#risk-review")).to_be_visible(timeout=20000)
                page.wait_for_timeout(1300)
                page.locator("#risk-review").screenshot(path=str(OUT / "05_hasil_vendor_demo_b.png"))
                browser.close()
        finally:
            server.terminate()
            try:
                server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server.kill()
    for name in sorted(path.name for path in OUT.glob("0*.png")):
        print("saved", OUT / name)
    return 0


if __name__ == "__main__":
    sys.exit(main())

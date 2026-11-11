#!/usr/bin/env python3
"""Check the local BidSentry API and report optional integration modes."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request


def main() -> int:
    host = os.environ.get("HOST", "127.0.0.1")
    port = os.environ.get("PORT", os.environ.get("BRIDGE_PORT", "8000"))
    url = f"http://{host}:{port}/api/health"
    try:
        with urllib.request.urlopen(url, timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        print(f"BidSentry API unavailable at {url}: {exc}", file=sys.stderr)
        return 1
    data = payload.get("data", {})
    if data.get("status") != "ok":
        print("BidSentry responded, but its health payload is not valid.", file=sys.stderr)
        return 1
    integrations = data.get("integrations", {})
    print(f"BidSentry API: ready ({url})")
    for name in ("langflow", "composio", "ibm_bob"):
        service = integrations.get(name, {})
        mode = service.get("mode", "status unavailable")
        configured = service.get("configured", service.get("mcp_config_present", False))
        print(f"{name}: {mode} ({'configured' if configured else 'not configured'})")
    print("Optional services do not block local audits.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

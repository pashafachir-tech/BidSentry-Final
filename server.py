#!/usr/bin/env python3
"""BidSentry local application entry point.

The HTTP transport, routes, controllers, and business services live in the
``bidsentry`` package. This file is intentionally kept as a small CLI wrapper
for compatibility with ``python server.py`` and the existing launcher.
"""

from __future__ import annotations

import argparse
from dataclasses import replace

from bidsentry.config import Settings
from bidsentry.asgi import create_asgi_app, _is_loopback_host


def run(port: int | None = None, langflow_url: str | None = None) -> None:
    import uvicorn

    settings = Settings.from_environment()
    if port is not None:
        settings = replace(settings, port=port)
    if langflow_url is not None:
        settings = replace(settings, langflow_url=langflow_url.rstrip("/"))
    if not settings.access_token and not _is_loopback_host(settings.host):
        raise SystemExit(
            f"FATAL: Server menolak start pada HOST '{settings.host}' tanpa BIDSENTRY_ACCESS_TOKEN. "
            "Konfigurasikan token akses atau gunakan host loopback (127.0.0.1)."
        )
    uvicorn.run(create_asgi_app(settings), host=settings.host, port=settings.port, access_log=False)


def main() -> None:
    settings = Settings.from_environment()
    parser = argparse.ArgumentParser(description="Start the BidSentry local review workspace.")
    parser.add_argument("--port", "-p", type=int, default=settings.port, help="HTTP port")
    parser.add_argument("--langflow", "-l", default=settings.langflow_url, help="Langflow base URL")
    args = parser.parse_args()
    run(port=args.port, langflow_url=args.langflow)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""ROME Daemon — pure WebSocket, no middlemen.

Replaces Uvicorn/Starlette/ASGI with raw websockets.serve().
HTTP routes (/health, /dashboard) served via process_request hook.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import mimetypes
import signal
import sys
import time
from pathlib import Path

_PARENT = str(Path(__file__).resolve().parent.parent)
if _PARENT not in sys.path:
    sys.path.insert(0, _PARENT)

import dictator.core as core
core.IS_DAEMON = True

from websockets.asyncio.server import serve
from websockets.http11 import Response
from websockets.datastructures import Headers as WSHeaders

from dictator.core import task_registry, DAEMON_START_TIME
from dictator.ws_server import rome_ws_handler

_CFG_PATH = Path(__file__).with_name("config.json")
_DASHBOARD_DIR = Path(__file__).parent / "dashboard"
_VERSION = "4.0"

logger = logging.getLogger("rome.daemon")


def load_config() -> dict:
    if not _CFG_PATH.exists():
        return {}
    try:
        return json.loads(_CFG_PATH.read_text())
    except Exception:
        return {}


# ── HTTP via process_request ──────────────────────────────────────────

_MIME_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css",
    ".js": "application/javascript",
    ".json": "application/json",
    ".png": "image/png",
    ".svg": "image/svg+xml",
    ".ico": "image/x-icon",
}


def _http_response(status: int, body: bytes, content_type: str = "application/json") -> Response:
    headers = WSHeaders([
        ("Content-Type", content_type),
        ("Content-Length", str(len(body))),
        ("Cache-Control", "no-store"),
    ])
    return Response(status, "OK" if status == 200 else "Not Found", headers, body)


async def process_request(connection, request):
    """Intercept HTTP requests before WS upgrade. Serve /health and /dashboard."""
    from urllib.parse import urlparse
    parsed = urlparse(request.path)
    path = parsed.path

    # Health endpoint
    if path == "/health":
        tasks = task_registry.get_all()
        active = sum(1 for t in tasks.values() if t.get("status") in {"registered", "running"})
        body = json.dumps({
            "ok": True,
            "version": _VERSION,
            "uptime_s": round(time.monotonic() - DAEMON_START_TIME, 3),
            "active_tasks": active,
            "total_tasks": len(tasks),
        }).encode()
        return _http_response(200, body)

    # Dashboard static files
    if path in ("/dashboard", "/dashboard/"):
        index = _DASHBOARD_DIR / "index.html"
        if index.exists():
            return _http_response(200, index.read_bytes(), "text/html; charset=utf-8")

    if path.startswith("/dashboard/"):
        rel = path[len("/dashboard/"):]
        file_path = (_DASHBOARD_DIR / rel).resolve()
        # Security: ensure path stays within dashboard dir
        if str(file_path).startswith(str(_DASHBOARD_DIR)) and file_path.is_file():
            ext = file_path.suffix
            ctype = _MIME_TYPES.get(ext, "application/octet-stream")
            return _http_response(200, file_path.read_bytes(), ctype)
        return _http_response(404, b"Not Found", "text/plain")

    # Everything else: proceed with WebSocket upgrade (return None)
    if path != "/ws":
        return _http_response(404, b"Not Found", "text/plain")


# ── Main ──────────────────────────────────────────────────────────────

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    cfg = load_config()
    parser = argparse.ArgumentParser(description="ROME daemon (WS-native)")
    parser.add_argument("--host", default=str(cfg.get("daemon_host", "127.0.0.1")))
    parser.add_argument("--port", type=int, default=int(cfg.get("daemon_port", 8741)))
    return parser.parse_args(argv)


async def run(host: str, port: int) -> None:
    # Sweep orphaned tasks from previous run
    swept = task_registry.sweep_orphans()
    if swept:
        logger.warning("Swept %d orphaned task(s) to failed on startup", swept)

    stop = asyncio.get_running_loop().create_future()

    def _signal_handler():
        if not stop.done():
            stop.set_result(None)

    for sig in (signal.SIGINT, signal.SIGTERM):
        asyncio.get_running_loop().add_signal_handler(sig, _signal_handler)

    async with serve(
        rome_ws_handler,
        host,
        port,
        process_request=process_request,
        logger=logger,
        open_timeout=30,
    ) as server:
        logger.info("ROME daemon v%s listening on ws://%s:%d/ws", _VERSION, host, port)
        await stop

    logger.info("ROME daemon shut down.")


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stderr,
    )
    args = parse_args(argv)
    asyncio.run(run(args.host, args.port))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

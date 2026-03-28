#!/usr/bin/env python3
"""Unified ASGI entrypoint for ROME."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

_PARENT = str(Path(__file__).resolve().parent.parent)
if _PARENT not in sys.path:
    sys.path.insert(0, _PARENT)

import dictator.core as core
core.IS_DAEMON = True

import uvicorn
from contextlib import asynccontextmanager
from starlette.applications import Starlette
from starlette.responses import FileResponse
from starlette.routing import Mount, Route, WebSocketRoute

from dictator.core import task_registry
from dictator.orchestrator import create_mcp_server
from dictator.ws_server import rome_ws_endpoint

_CFG_PATH = Path(__file__).with_name("config.json")
_VERSION = "2.5"


def load_config() -> dict:
    if not _CFG_PATH.exists():
        return {}
    try:
        return json.loads(_CFG_PATH.read_text())
    except Exception:
        return {}


async def dashboard_index(request) -> FileResponse:
    del request
    p = Path(__file__).parent / "dashboard" / "index.html"
    return FileResponse(str(p), media_type="text/html; charset=utf-8",
                        headers={"Cache-Control": "no-store"})


async def health_endpoint(request):
    """Lightweight HTTP health check — no WS needed."""
    import time
    from starlette.responses import JSONResponse
    from dictator.core import DAEMON_START_TIME
    tasks = task_registry.get_all()
    active = sum(1 for t in tasks.values() if t.get("status") in {"registered", "running"})
    return JSONResponse({
        "ok": True,
        "version": _VERSION,
        "uptime_s": round(time.monotonic() - DAEMON_START_TIME, 3),
        "active_tasks": active,
        "total_tasks": len(tasks),
    })


@asynccontextmanager
async def lifespan(app):
    swept = task_registry.sweep_orphans()
    if swept:
        import logging
        logging.getLogger("rome.daemon").warning("Swept %d orphaned task(s) to failed on startup", swept)
    yield


def create_app() -> Starlette:
    # Use the orchestrator to create the ROME MCP server instance
    mcp = create_mcp_server("ROME")

    from starlette.staticfiles import StaticFiles
    dashboard_dir = Path(__file__).parent / "dashboard"
    return Starlette(
        lifespan=lifespan,
        debug=False,
        routes=[
            Mount("/mcp", app=mcp.sse_app()),
            WebSocketRoute("/ws", endpoint=rome_ws_endpoint),
            Route("/health", endpoint=health_endpoint),
            Route("/dashboard", endpoint=dashboard_index),
            Route("/dashboard/", endpoint=dashboard_index),
            Mount("/dashboard", app=StaticFiles(directory=str(dashboard_dir), html=True)),
        ],
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    cfg = load_config()
    parser = argparse.ArgumentParser(description="ROME unified daemon")
    parser.add_argument("--host", default=str(cfg.get("daemon_host", "127.0.0.1")))
    parser.add_argument("--port", type=int, default=int(cfg.get("daemon_port", 8741)))
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    import socket
    cfg = uvicorn.Config(create_app(), host=args.host, port=args.port, reload=True, reload_dirs=[str(Path(__file__).parent.parent)])
    cfg.socket_options = [(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)]
    server = uvicorn.Server(cfg)
    server.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

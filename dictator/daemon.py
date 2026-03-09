#!/usr/bin/env python3
"""Unified ASGI entrypoint for ROME."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

# Enable ROME daemon features in ws_server and other modules
os.environ["ROME_DAEMON"] = "1"

import uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import FileResponse, HTMLResponse, JSONResponse
from starlette.routing import Mount, Route, WebSocketRoute

# When invoked as `python3 dictator/daemon.py`, ensure the parent dir
# (rome-core/) is on sys.path so `from dictator.xxx` imports work.
_PARENT = str(Path(__file__).resolve().parent.parent)
if _PARENT not in sys.path:
    sys.path.insert(0, _PARENT)

from dictator.core import mcp, task_registry, event_bus
from dictator.ws_server import rome_ws_endpoint

_CFG_PATH = Path(__file__).with_name("config.json")
_START_TIME = time.monotonic()
_VERSION = "2.4"


def load_config() -> dict[str, Any]:
    if not _CFG_PATH.exists():
        return {}
    try:
        return json.loads(_CFG_PATH.read_text())
    except Exception:
        return {}


def import_tool_modules() -> None:
    # Each module registers its @mcp.tool() decorators on import.
    import dictator.tools_fs  # noqa: F401
    import dictator.tools_git  # noqa: F401
    import dictator.tools_drupal  # noqa: F401
    import dictator.tools_legion  # noqa: F401
    import dictator.tools_skyrim  # noqa: F401
    import dictator.tools_desktop  # noqa: F401
    import dictator.tools_media  # noqa: F401
    import dictator.tools_gc  # noqa: F401
    import dictator.tools_stats  # noqa: F401
    import dictator.tools_prefect  # noqa: F401
    import dictator.tools_docs  # noqa: F401


def _task_counts() -> tuple[int, int]:
    tasks = task_registry.get_all()
    active = sum(1 for task in tasks.values() if task.get("status") in {"registered", "running"})
    return active, len(tasks)


async def status_endpoint(request) -> JSONResponse:
    del request
    active_tasks, total_tasks = _task_counts()
    return JSONResponse(
        {
            "ok": True,
            "version": _VERSION,
            "uptime_s": round(time.monotonic() - _START_TIME, 3),
            "active_tasks": active_tasks,
            "total_tasks": total_tasks,
        }
    )



async def clear_finished(request) -> JSONResponse:
    del request
    n = task_registry.clear_finished()
    return JSONResponse({"ok": True, "cleared": n})


async def event_relay(request: Request) -> JSONResponse:
    """Receive events from stdio MCP via HTTP POST."""
    from dictator.events import emit_dispatch_start, emit_complete, emit_error, emit_progress
    b = await request.json()
    t, tid, p = b.get("type",""), b.get("task_id",""), b.get("payload",{})
    if t == "dispatch_start":
        task_registry.register(tid, p.get("capability","?"))
        await emit_dispatch_start(event_bus, tid, p.get("capability","?"))
    elif t == "complete":
        task_registry.complete(tid, p.get("status","SUCCESS"), p.get("report_path"))
        await emit_complete(event_bus, tid, p.get("status"), p.get("report_path"), p.get("usage"))
    elif t == "progress":
        task_registry.update_progress(tid, p.get("percent",0), p.get("message",""))
        await emit_progress(event_bus, tid, p.get("percent",0), p.get("message",""))
    elif t == "error":
        await emit_error(event_bus, tid, p.get("message",""))
    return JSONResponse({"ok": True})

async def dashboard_placeholder(request) -> HTMLResponse:
    del request
    return HTMLResponse(
        """
        <!doctype html>
        <html lang="en">
          <head>
            <meta charset="utf-8">
            <title>ROME Dashboard</title>
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <style>
              body {
                background: #111827;
                color: #f9fafb;
                font-family: monospace;
                margin: 0;
                min-height: 100vh;
                display: grid;
                place-items: center;
              }
              main {
                max-width: 40rem;
                padding: 2rem;
                text-align: center;
              }
              h1 {
                margin: 0 0 1rem;
              }
              p {
                color: #d1d5db;
                line-height: 1.5;
              }
            </style>
          </head>
          <body>
            <main>
              <h1>ROME Dashboard</h1>
              <p>Dashboard UI is reserved for Phase 4. Use <code>/api/status</code>, <code>/mcp</code>, or <code>/ws</code> for now.</p>
            </main>
          </body>
        </html>
        """
    )


async def dashboard_index(request) -> FileResponse:
    del request
    dashboard_path = Path(__file__).parent / "dashboard" / "index.html"
    return FileResponse(
        str(dashboard_path),
        media_type="text/html; charset=utf-8",
        headers={"Cache-Control": "no-store"},
    )


def create_app() -> Starlette:
    import_tool_modules()

    async def _startup() -> None:
        from dictator.tools_gc import auto_gc

        auto_gc()

    from starlette.staticfiles import StaticFiles
    dashboard_dir = Path(__file__).parent / "dashboard"
    return Starlette(
        debug=False,
        on_startup=[_startup],
        routes=[
            Mount("/mcp", app=mcp.sse_app()),
            WebSocketRoute("/ws", endpoint=rome_ws_endpoint),
            Route("/api/status", endpoint=status_endpoint),
            Route("/api/event", endpoint=event_relay, methods=["POST"]),
            Route("/api/clear", endpoint=clear_finished, methods=["POST"]),
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
    import os
    os.environ["ROME_DAEMON"] = "1"
    args = parse_args(argv)
    uvicorn.run(create_app(), host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


# Create app lazily only when needed (via uvicorn in main())
# Don't create at module level to ensure ROME_DAEMON is set

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
from starlette.responses import FileResponse
from starlette.routing import Mount, Route, WebSocketRoute

# When invoked as `python3 dictator/daemon.py`, ensure the parent dir
# (rome-core/) is on sys.path so `from dictator.xxx` imports work.
_PARENT = str(Path(__file__).resolve().parent.parent)
if _PARENT not in sys.path:
    sys.path.insert(0, _PARENT)

from dictator.core import mcp
from dictator.ws_server import rome_ws_endpoint

_CFG_PATH = Path(__file__).with_name("config.json")
_VERSION = "2.5"


def load_config() -> dict[str, Any]:
    if not _CFG_PATH.exists():
        return {}
    try:
        return json.loads(_CFG_PATH.read_text())
    except Exception:
        return {}


def import_tool_modules() -> None:
    import dictator.tools_fs       # noqa: F401
    import dictator.tools_git      # noqa: F401
    import dictator.tools_drupal   # noqa: F401
    import dictator.tools_legion   # noqa: F401
    import dictator.tools_skyrim   # noqa: F401
    import dictator.tools_desktop  # noqa: F401
    import dictator.tools_media    # noqa: F401
    import dictator.tools_gc       # noqa: F401
    import dictator.tools_stats    # noqa: F401
    import dictator.tools_prefect  # noqa: F401
    import dictator.tools_docs     # noqa: F401


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

    from starlette.staticfiles import StaticFiles
    dashboard_dir = Path(__file__).parent / "dashboard"
    return Starlette(
        debug=False,
        routes=[
            Mount("/mcp", app=mcp.sse_app()),
            WebSocketRoute("/ws", endpoint=rome_ws_endpoint),
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
    os.environ["ROME_DAEMON"] = "1"
    args = parse_args(argv)
    uvicorn.run(create_app(), host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

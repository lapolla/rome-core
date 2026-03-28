#!/usr/bin/env python3
"""
MCP Server "asshole" — modular Python dictator.
Thin entry point: uses the orchestrator to load tools.
"""

import sys
import os
from pathlib import Path

# When invoked as `python3 dictator/cli.py`, ensure the parent dir
# (rome-core/) is on sys.path so `from dictator.xxx` imports work.
_parent = str(Path(__file__).resolve().parent.parent)
if _parent not in sys.path:
    sys.path.insert(0, _parent)

# The orchestrator handles dynamic tool discovery and registration
from dictator.orchestrator import create_mcp_server

# profile = os.environ.get("ROME_PROFILE")
# sys.stderr.write(f"ROME: Active profile: {'full' if profile is None else profile}\n")
mcp = create_mcp_server("asshole", profile=os.environ.get("ROME_PROFILE"))

if __name__ == "__main__":
    # Startup GC: clean old legion dirs before serving
    # from dictator.tools_gc import auto_gc
    # try:
    #     auto_gc()
    # except Exception:
    #     pass
    mcp.run(transport="stdio")

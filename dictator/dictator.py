#!/usr/bin/env python3
"""
MCP Server "asshole" — modular Python dictator.
Thin entry point: uses the orchestrator to load tools.
"""

import sys
import os
from pathlib import Path

# When invoked as `python3 dictator/dictator.py`, ensure the parent dir
# (rome-core/) is on sys.path so `from dictator.xxx` imports work.
_parent = str(Path(__file__).resolve().parent.parent)
if _parent not in sys.path:
    sys.path.insert(0, _parent)

# The orchestrator handles dynamic tool discovery and registration
from dictator.orchestrator import create_mcp_server

# Initialize the MCP instance by discovering all tools_*.py in the package
profile = os.environ.get("ROME_PROFILE")
print(f"ROME: Active profile: {'full' if profile is None else profile}", file=sys.stderr)
mcp = create_mcp_server("asshole", profile=profile)

if __name__ == "__main__":
    # Startup GC: clean old legion dirs before serving
    from dictator.tools_gc import auto_gc
    try:
        auto_gc()
    except Exception:
        pass
    mcp.run(transport="stdio")

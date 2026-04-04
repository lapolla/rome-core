#!/usr/bin/env python3
"""
ROME Native Entry Point — modular Python dictator.
MCP IS DEAD. EXCLUSIVELY use the native ROME registry.
"""

import sys
import os
from pathlib import Path

_parent = str(Path(__file__).resolve().parent.parent)
if _parent not in sys.path:
    sys.path.insert(0, _parent)

from dictator.orchestrator import create_registry

# The registry handles dynamic tool discovery and native registration
# for consumption by the WebSocket daemon or direct CLI execution.
registry = create_registry("ROME", profile=os.environ.get("ROME_PROFILE"))

if __name__ == "__main__":
    # If invoked directly, list registered tools to prove the mesh is active.
    print(f"ROME Native Mesh: {len(registry.tools)} tools loaded.")
    for tool_name in sorted(registry.tools.keys()):
        print(f" - {tool_name}")

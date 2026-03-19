"""
ROME MCP Orchestrator — dynamic tool discovery and registration.
This module provides the logic to load modular toolsets into a FastMCP instance.
"""

import importlib
import pkgutil
import json
import sys
from pathlib import Path
from mcp.server.fastmcp import FastMCP
from dictator import core


def get_capabilities():
    """Read capabilities from config.json."""
    cfg_path = Path(__file__).parent / "config.json"
    if cfg_path.exists():
        try:
            cfg = json.loads(cfg_path.read_text())
            return cfg.get("capabilities", [])
        except Exception as e:
            print(f"Error reading config.json: {e}", file=sys.stderr)
    return []


def register_all_tools(mcp: FastMCP, filter_capabilities: bool = False, profile: str | None = None):
    """
    Dynamically discover and register all 'tools_*.py' modules.
    If profile is provided, only load modules listed in that profile (None = all).
    If filter_capabilities is True, only load tools mentioned in config.json.
    Profile takes precedence over filter_capabilities.
    """
    capabilities = get_capabilities()
    package_path = str(Path(__file__).parent)

    # Resolve profile to allowed module list (None = no filtering)
    allowed_modules = None
    excludes = set() # Initialize an empty set for excluded tools
    if profile:
        from dictator.profiles import get_profile, get_tool_excludes
        allowed_modules = get_profile(profile)  # None for "full", list for others
        if allowed_modules is not None:
            print(f"[ROME] Profile '{profile}': loading {allowed_modules}", file=sys.stderr)
        else:
            print(f"[ROME] Profile '{profile}': loading all modules", file=sys.stderr)
        excludes = get_tool_excludes(profile)

    for loader, module_name, is_pkg in pkgutil.iter_modules([package_path]):
        if module_name.startswith("tools_"):
            cap_name = module_name[6:]

            # Profile filtering (takes precedence)
            if allowed_modules is not None:
                if cap_name not in allowed_modules:
                    continue
            # Legacy config.json filtering
            elif filter_capabilities and capabilities and cap_name not in capabilities:
                continue

            try:
                module = importlib.import_module(f"dictator.{module_name}")
                if hasattr(module, "register"):
                    module.register(mcp)
                    # Remove excluded tools
                    for tool_name in list(mcp._tool_manager._tools.keys()):
                        if tool_name in excludes:
                            print(f"[ROME] Profile '{profile}': excluding tool '{tool_name}'", file=sys.stderr)
                            del mcp._tool_manager._tools[tool_name]
            except Exception as e:
                print(f"Failed to load toolset {module_name}: {e}", file=sys.stderr)


def create_mcp_server(name: str = "ROME", filter_capabilities: bool = False, profile: str | None = None) -> FastMCP:
    """Create a FastMCP instance and register discovered tools."""
    mcp = FastMCP(name)
    register_all_tools(mcp, filter_capabilities=filter_capabilities, profile=profile)
    return mcp

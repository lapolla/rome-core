"""
ROME MCP Orchestrator — dynamic tool discovery and registration.
This module provides the logic to load modular toolsets into a FastMCP instance.
"""

import importlib
import pkgutil
import json
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
        except Exception:
            pass
    return []

def register_all_tools(mcp: FastMCP, filter_capabilities: bool = False):
    """
    Dynamically discover and register all 'tools_*.py' modules.
    If filter_capabilities is True, only load tools mentioned in config.json.
    """
    capabilities = get_capabilities()
    package_path = str(Path(__file__).parent)
    
    # Iterate over all modules in the current package (dictator)
    for loader, module_name, is_pkg in pkgutil.iter_modules([package_path]):
        if module_name.startswith("tools_"):
            # If filtering is enabled, check if the toolset is in the allowed list
            # e.g. "tools_fs" -> capability "fs"
            cap_name = module_name[6:] 
            if filter_capabilities and capabilities and cap_name not in capabilities:
                continue
                
            try:
                # Import the module
                module = importlib.import_module(f"dictator.{module_name}")
                
                # Check for the standardized 'register' function
                if hasattr(module, "register"):
                    module.register(mcp)
                else:
                    # Fallback or legacy support: some might register on import
                    # but we prefer the explicit 'register(mcp)' call now.
                    pass
            except Exception as e:
                print(f"Failed to load toolset {module_name}: {e}")

def create_mcp_server(name: str = "ROME", filter_capabilities: bool = False) -> FastMCP:
    """Create a FastMCP instance and register discovered tools."""
    mcp = FastMCP(name)
    register_all_tools(mcp, filter_capabilities=filter_capabilities)
    return mcp

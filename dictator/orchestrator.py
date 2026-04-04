"""
ROME Orchestrator — dynamic tool discovery and native registration.
MCP IS DEAD. EXCLUSIVELY use the native ROME registry.
"""

import importlib
import pkgutil
import json
import sys
from pathlib import Path
from dictator import core

class RomeRegistry:
    """Native replacement for FastMCP instrumentarium."""
    def __init__(self, name: str = "ROME"):
        self.name = name
        self.tools = {}

    def tool(self, name: str | None = None):
        """Decorator to register a native ROME tool."""
        def decorator(func):
            tool_name = name or func.__name__
            self.tools[tool_name] = func
            return func
        return decorator

    def register_all(self, filter_capabilities: bool = False, profile: str | None = None):
        """Discover and load tools_*.py modules into this registry."""
        capabilities = self._get_capabilities()
        package_path = str(Path(__file__).parent)

        allowed_modules = None
        excludes = set()
        if profile:
            from dictator.profiles import get_profile, get_tool_excludes
            allowed_modules = get_profile(profile)
            excludes = get_tool_excludes(profile)

        for loader, module_name, is_pkg in pkgutil.iter_modules([package_path]):
            if module_name.startswith("tools_"):
                cap_name = module_name[6:]
                if allowed_modules is not None and cap_name not in allowed_modules:
                    continue
                elif filter_capabilities and capabilities and cap_name not in capabilities:
                    continue

                try:
                    module = importlib.import_module(f"dictator.{module_name}")
                    if hasattr(module, "register"):
                        module.register(self)
                        # Purge excludes
                        for tool_name in list(self.tools.keys()):
                            if tool_name in excludes:
                                del self.tools[tool_name]
                except Exception as e:
                    print(f"Failed to load ROME toolset {module_name}: {e}", file=sys.stderr)

    def _get_capabilities(self):
        cfg_path = Path(__file__).parent / "config.json"
        if cfg_path.exists():
            try:
                cfg = json.loads(cfg_path.read_text())
                return cfg.get("capabilities", [])
            except Exception: pass
        return []

def create_registry(name: str = "ROME", profile: str | None = None) -> RomeRegistry:
    """Create a native ROME registry and register discovered tools."""
    registry = RomeRegistry(name)
    registry.register_all(profile=profile)
    return registry

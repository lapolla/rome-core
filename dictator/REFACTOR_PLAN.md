# MCP Refactor Plan: Modular Tool Architecture

## Goal
Transition the ROME MCP (Dictator) from a monolithic import structure to a dynamic, plugin-based architecture. This will improve maintainability, allow for easier extension by third parties, and enable conditional tool loading.

## 1. Dynamic Tool Discovery
Replace the hardcoded imports in `dictator.py` with an automated discovery mechanism.
- **Implementation:** Use `pkgutil` or `importlib` to iterate over the `dictator/` directory and import all modules starting with `tools_`.
- **Benefit:** Adding a new toolset only requires creating a new `tools_*.py` file; no changes to the entry point are needed.

## 2. Capability-Based Organization
Group tools into "Capabilities" or "Domains" that can be toggled via `config.json`.
- **Implementation:** Add a `capabilities` section to `config.json`. Only load tool modules that are enabled in the configuration.
- **Benefit:** Reduces the tool surface area for specific deployments and prevents loading unnecessary dependencies (e.g., Skyrim tools on a web-only server).

## 3. Standardized Response Format
Enforce a consistent response structure across all tools.
- **Implementation:** Create a `DictatorResponse` helper class or decorator that standardizes JSON output for success/error states, truncation, and metadata.
- **Benefit:** Predictable parsing for workers (Legions) and other MCP clients.

## 4. Async/Sync Boundary Cleanup
Ensure all blocking operations in tool implementations are properly wrapped in `asyncio.to_thread` or use async-native libraries where possible.
- **Implementation:** Audit `tools_*.py` for synchronous filesystem or network calls and refactor them to be non-blocking.
- **Benefit:** Improved server responsiveness under high load.

## 5. Metadata & Documentation
Leverage `FastMCP`'s ability to provide rich metadata.
- **Implementation:** Enhance tool docstrings with structured information (e.g., required permissions, expected execution time).
- **Benefit:** Better auto-generated documentation and improved AI agent understanding of tool capabilities.

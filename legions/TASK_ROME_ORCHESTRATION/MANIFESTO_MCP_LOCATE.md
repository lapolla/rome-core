# Manifesto: MCP Locator
**Role:** Imperial Scout (ROME Legionary)
**Objective:** Locate the configuration or source code definition files for the 'my-local-server' MCP.

## 1. Search Strategy
Execute shell commands to search common system and user directories for files related to MCP server definitions. Prioritize files that suggest configuration, tool definitions, or server implementations.

## 2. Keywords to Search For
*   `mcp_server`
*   `tool_definitions`
*   `config.json`
*   `server.py`
*   `server.js`
*   `server.ts`
*   `plugins/` (directories that might contain tool definitions)

## 3. Directories to Prioritize
*   `/etc/` (system-wide configurations)
*   `/usr/local/lib/` (common installation path for libraries/scripts)
*   `~/.config/` (user-specific configurations)
*   `~/.local/lib/` (user-specific libraries/scripts)
*   `/opt/` (optional software packages)
*   `/var/lib/` (data for MCPs)

## 4. Output Requirements
Report the absolute paths of all relevant files or directories found. The output should be clear and list potential candidates for the MCP server's definition.

---
**"To command, one must first locate the heart of the machine."**

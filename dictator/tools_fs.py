"""Filesystem tools: shell_exec, fs_read, fs_write, read_anywhere, write_anywhere, list_directory."""

import json
from pathlib import Path

from dictator.core import mcp, run_cmd, ROOT_DIR


@mcp.tool()
async def shell_exec(command: str) -> str:
    """Execute a shell command (cwd = /var/www/ftk_lms)."""
    from dictator.rome_log import log_event
    log_event("shell_exec", message=command[:200])
    r = await run_cmd(command, cwd=ROOT_DIR)
    return json.dumps(r, indent=2)


@mcp.tool()
async def fs_read(path: str) -> str:
    """Read a file relative to /var/www/ftk_lms."""
    full = (ROOT_DIR / path).resolve()
    if not full.is_relative_to(ROOT_DIR):
        return json.dumps({"ok": False, "message": "Path escapes root directory"})
    return full.read_text(encoding="utf-8")


@mcp.tool()
async def fs_write(path: str, content: str) -> str:
    """Write a file relative to /var/www/ftk_lms."""
    full = (ROOT_DIR / path).resolve()
    if not full.is_relative_to(ROOT_DIR):
        return json.dumps({"ok": False, "message": "Path escapes root directory"})
    full.write_text(content, encoding="utf-8")
    return f"Wrote {len(content)} bytes to {full}"


@mcp.tool()
async def read_anywhere(path: str) -> str:
    """Read a file by absolute path."""
    return Path(path).resolve().read_text(encoding="utf-8")


@mcp.tool()
async def write_anywhere(path: str, content: str) -> str:
    """Write a file by absolute path."""
    p = Path(path).resolve()
    p.write_text(content, encoding="utf-8")
    return json.dumps({"ok": True, "message": f"Wrote {len(content)} bytes to {p}"})


@mcp.tool()
async def list_directory(dir_path: str, recursive: bool = False) -> str:
    """List directory contents, optionally recursive."""
    abs_path = Path(dir_path).resolve()
    entries = []

    def walk(current: Path):
        for item in sorted(current.iterdir()):
            kind = "directory" if item.is_dir() else "file"
            entries.append({"name": item.name, "path": str(item), "type": kind})
            if recursive and item.is_dir():
                try:
                    walk(item)
                except PermissionError:
                    pass

    try:
        walk(abs_path)
        return json.dumps({"ok": True, "dir_path": dir_path, "entries": entries}, indent=2)
    except Exception as e:
        return json.dumps({"ok": False, "message": str(e)})

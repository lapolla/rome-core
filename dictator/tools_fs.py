"""Filesystem tools: shell_exec, fs_read, fs_write, read_anywhere, write_anywhere, list_directory."""

import json
from pathlib import Path

from dictator.core import run_cmd, ROOT_DIR


def register(mcp):
    """Register FS tools with the given FastMCP instance."""

    @mcp.tool()
    async def shell_exec(command: str) -> str:
        """Execute a shell command (cwd = /var/www/ftk_lms)."""
        from dictator.core import run_cmd_stream
        from dictator.rome_log import log_event
        log_event(tool="shell_exec", message=command[:200])
        r = await run_cmd_stream(command, cwd=ROOT_DIR)
        out = r.get("stdout", "").strip()
        
        if r.get("truncated"):
            out += "\n\n[ROME: Output truncated for context safety. Use 'read_anywhere' on the report for full logs.]"

        if not r.get("ok", False):
            err = r.get("stderr", r.get("message", ""))
            exit_code = r.get("exit_code", "?")
            return f"ERR({exit_code}): {err}" if err else f"ERR({exit_code})"
        return out if out else "OK"

    @mcp.tool()
    async def fs_read(path: str, start_line: int = 1, end_line: int | None = None) -> str:
        """Read a file relative to /var/www/ftk_lms (1-indexed, inclusive)."""
        full = (ROOT_DIR / path).resolve()
        if not full.is_relative_to(ROOT_DIR):
            return json.dumps({"ok": False, "message": "Path escapes root directory"})
        
        try:
            lines = full.read_text(encoding="utf-8").splitlines()
            total = len(lines)
            start = max(0, start_line - 1)
            end = end_line if end_line is not None else total
            content = "\n".join(lines[start:end])
            
            # Metadata header for the agent (cheap context)
            header = f"[ROME: lines {start+1}-{min(end, total)} of {total}]\n"
            return header + content
        except Exception as e:
            return f"ERR: {e}"

    @mcp.tool()
    async def read_anywhere(path: str, start_line: int = 1, end_line: int | None = None) -> str:
        """Read a file by absolute path (1-indexed, inclusive)."""
        p = Path(path).resolve()
        try:
            lines = p.read_text(encoding="utf-8").splitlines()
            total = len(lines)
            start = max(0, start_line - 1)
            end = end_line if end_line is not None else total
            content = "\n".join(lines[start:end])
            header = f"[ROME: lines {start+1}-{min(end, total)} of {total}]\n"
            return header + content
        except Exception as e:
            return f"ERR: {e}"

    @mcp.tool()
    async def list_directory(dir_path: str, recursive: bool = False, max_depth: int = 2, ignore_git: bool = True, limit: int = 100) -> str:
        """List directory contents with depth control, gitignore awareness, and a results limit."""
        abs_path = Path(dir_path).resolve()
        entries = []

        # Simple ignore list (cheap version of gitignore awareness)
        IGNORE_PATTERNS = {".git", "__pycache__", "node_modules", ".pytest_cache", ".venv", "venv", "target", "build"}

        def walk(current: Path, depth: int):
            if depth > max_depth or len(entries) >= limit:
                return
            
            try:
                for item in sorted(current.iterdir()):
                    if len(entries) >= limit:
                        break
                        
                    if ignore_git and item.name in IGNORE_PATTERNS:
                        continue
                        
                    kind = "directory" if item.is_dir() else "file"
                    rel = item.relative_to(abs_path)
                    entries.append({"name": item.name, "path": str(rel), "type": kind, "depth": depth})
                    
                    if recursive and item.is_dir():
                        walk(item, depth + 1)
            except PermissionError:
                pass

        try:
            walk(abs_path, 0)
            result = {"ok": True, "dir_path": dir_path, "count": len(entries), "entries": entries}
            if len(entries) >= limit:
                result["truncated"] = True
                result["note"] = f"Limited to {limit} entries for context safety."
            return json.dumps(result, indent=2)
        except Exception as e:
            return json.dumps({"ok": False, "message": str(e)})

"""Filesystem tools: fs_read, fs_write, read_anywhere, write_anywhere, list_directory."""

import asyncio
import json
import sys
from pathlib import Path

from dictator.core import run_cmd, ROOT_DIR


def _debug(msg: str):
    print(f"[TOOLS_FS] {msg}", file=sys.stderr, flush=True)


async def _gemini_summarize(content: str, instruction: str, timeout: int = 15) -> str | None:
    """Quick Gemini Flash summarization. Returns summary or None on failure."""
    GEMINI_CLI = "/home/paul-kane/projects/gemini-cli/bundle/gemini.js"
    prompt = f"{instruction}\n\n```\n{content[:8000]}\n```"
    try:
        proc = await asyncio.create_subprocess_exec(
            GEMINI_CLI, "-p", prompt,
            "--sandbox", "false",
            "-m", "gemini-3.1-pro",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        _debug(f"gemini_summarize: rc={proc.returncode}, stdout_len={len(stdout)}, stderr={stderr.decode()[:200]}")
        if proc.returncode == 0 and stdout:
            return stdout.decode().strip()
    except asyncio.TimeoutError:
        _debug("gemini_summarize: TIMEOUT")
    except Exception as e:
        _debug(f"gemini_summarize: {type(e).__name__}: {e}")
    return None


def _is_compact_mode() -> bool:
    """Check if running in a compact profile (gemini, core)."""
    import os
    profile = os.environ.get("ROME_PROFILE", "")
    return profile in ("gemini", "core")


def register(mcp):
    """Register FS tools with the given FastMCP instance."""

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
    async def fs_write(path: str, content: str) -> str:
        """Write content to a file relative to /var/www/ftk_lms."""
        full = (ROOT_DIR / path).resolve()
        if not full.is_relative_to(ROOT_DIR):
            return json.dumps({"ok": False, "message": "Path escapes root directory"})
        
        try:
            full.parent.mkdir(parents=True, exist_ok=True)
            full.write_text(content, encoding="utf-8")
            return "OK: Wrote to " + str(full)
        except Exception as e:
            return f"ERR: {e}"

    @mcp.tool()
    async def read_anywhere(path: str, start_line: int = 1, end_line: int | None = None) -> str:
        """Read a file by absolute path (1-indexed, inclusive).
        start_line=0 returns structural overview (functions, classes, imports) without full content."""
        p = Path(path).resolve()
        try:
            text = p.read_text(encoding="utf-8")
            lines = text.splitlines(keepends=True)
            total = len(lines)

            # Overview mode: structural summary without full content
            if start_line == 0:
                import re
                ext = p.suffix.lower()
                outline = [f"[ROME: overview of {p.name} — {total} lines]"]

                if ext in (".py", ".pyx"):
                    for i, line in enumerate(lines, 1):
                        stripped = line.strip()
                        if stripped.startswith(("def ", "async def ", "class ")):
                            outline.append(f"  {i}: {stripped.split('(')[0].split(':')[0]}")
                        elif stripped.startswith(("import ", "from ")):
                            outline.append(f"  {i}: {stripped}")
                elif ext in (".cpp", ".h", ".hpp", ".c"):
                    for i, line in enumerate(lines, 1):
                        stripped = line.strip()
                        if re.match(r"^(class |struct |namespace |void |bool |int |auto |static |inline |template)", stripped):
                            outline.append(f"  {i}: {stripped[:80]}")
                        elif stripped.startswith("#include"):
                            outline.append(f"  {i}: {stripped}")
                elif ext in (".js", ".ts", ".mjs", ".tsx"):
                    for i, line in enumerate(lines, 1):
                        stripped = line.strip()
                        if re.match(r"^(export |function |class |const |async function|import )", stripped):
                            outline.append(f"  {i}: {stripped[:80]}")
                elif ext in (".json", ".yaml", ".yml", ".toml"):
                    if total <= 50:
                        outline.append("".join(lines))
                    else:
                        outline.append("".join(lines[:30]))
                        outline.append(f"  ... ({total - 40} lines omitted) ...")
                        outline.append("".join(lines[-10:]))
                else:
                    if total <= 40:
                        outline.append("".join(lines))
                    else:
                        outline.append("".join(lines[:20]))
                        outline.append(f"  ... ({total - 30} lines omitted) ...")
                        outline.append("".join(lines[-10:]))

                return "\n".join(outline)

            s = max(1, start_line) - 1
            e = min(total, end_line) if end_line else total
            selected = lines[s:e]
            num_selected = e - s

            # Smart summarize: large reads get Gemini digest
            # Compact mode (gemini profile): >50 lines. Normal: >100 lines full-file only.
            compact = _is_compact_mode()
            summarize_threshold = 50 if compact else 100
            should_summarize = (compact and num_selected > summarize_threshold) or (not compact and start_line == 1 and end_line is None and num_selected > summarize_threshold)
            if should_summarize:
                _debug(f"read_anywhere: triggering summarize for {p.name} ({num_selected} lines)")
                summary = await _gemini_summarize(
                    "".join(selected),
                    f"Summarize this {p.suffix} file ({total} lines) in 5-10 bullet points. "
                    "List key functions/classes/structures with line numbers. "
                    "Flag anything unusual. Be extremely concise — no preamble."
                )
                if summary:
                    return f"[ROME: AI summary of {p.name} — {total} lines]\n{summary}"
                _debug("read_anywhere: summarize returned None, falling back to raw")

            header = f"[ROME: lines {s+1}-{e} of {total}]\n"
            return header + "".join(selected)
        except Exception as e:
            return f"ERR: {e}"

    @mcp.tool()
    async def write_anywhere(path: str, content: str) -> str:
        """Write content to a file by absolute path."""
        p = Path(path).resolve()
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
            return "OK: Wrote to " + str(p)
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

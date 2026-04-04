"""Sovereign Filesystem tools: fs_read, fs_write, read_anywhere, write_anywhere, list_directory."""

import asyncio
import json
import os
from pathlib import Path

from dictator.core import ROME_ROOT, DictatorResponse, dictator_tool

# For tests
ROOT_DIR = ROME_ROOT


def register(registry):
    """Register FS tools with the given native ROME registry instance."""

    @registry.tool()
    @dictator_tool
    async def fs_read(path: str) -> str:
        """Read a file relative to ROOT_DIR."""
        root = Path(ROOT_DIR).resolve()
        p = (root / path).resolve()
        if not str(p).startswith(str(root)):
            return DictatorResponse.fail(error=f"Path {path} escapes ROOT_DIR")
        
        if not await asyncio.to_thread(p.exists):
            return DictatorResponse.fail(error=f"File not found: {p}")
        
        def _read():
            with open(p, "r", encoding="utf-8") as f:
                return f.read()
        
        content = await asyncio.to_thread(_read)
        line_count = len(content.splitlines())
        # We still return the prefixed string for LLM compatibility, but wrapped in DictatorResponse
        return DictatorResponse.success(
            message=f"Read {len(content)} bytes",
            data=f"[ROME: lines 1-{line_count} of {p}]\n{content}"
        )

    @registry.tool()
    @dictator_tool
    async def fs_write(path: str, content: str) -> str:
        """Write a file relative to ROOT_DIR."""
        root = Path(ROOT_DIR).resolve()
        p = (root / path).resolve()
        if not str(p).startswith(str(root)):
            return DictatorResponse.fail(error=f"Path {path} escapes ROOT_DIR")
        
        def _write():
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
            return len(content)
        
        written = await asyncio.to_thread(_write)
        return DictatorResponse.success(message=f"Wrote {written} bytes to {p}", written=written)

    @registry.tool()
    @dictator_tool
    async def read_anywhere(path: str, start_line: int = 1, end_line: int | None = None) -> str:
        """Read any file on the system (absolute path)."""
        p = Path(path).expanduser().resolve()
        if not await asyncio.to_thread(p.exists):
            return DictatorResponse.fail(error=f"File not found: {p}")
        
        def _read():
            with open(p, "r", encoding="utf-8") as f:
                return f.readlines()
        
        all_lines = await asyncio.to_thread(_read)
        if end_line is None:
            selected = all_lines[start_line-1:]
        else:
            selected = all_lines[start_line-1:end_line]
        
        content = "".join(selected)
        actual_end = start_line + len(selected) - 1
        return DictatorResponse.success(
            data=f"[ROME: lines {start_line}-{actual_end} of {p}]\n{content}",
            total_lines=len(all_lines)
        )

    @registry.tool()
    @dictator_tool
    async def write_anywhere(path: str, content: str) -> str:
        """Write content to any absolute path (overwrites)."""
        p = Path(path).expanduser().resolve()
        
        def _write():
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
            return len(content)
            
        written = await asyncio.to_thread(_write)
        return DictatorResponse.success(message=f"Successfully wrote {written} bytes to {p}", written=written)

    @registry.tool()
    @dictator_tool
    async def list_directory(dir_path: str) -> str:
        """List contents of any directory."""
        p = Path(dir_path).expanduser().resolve()
        if not await asyncio.to_thread(p.is_dir):
            return DictatorResponse.fail(error=f"Directory not found: {p}")
        
        def _list():
            entries = []
            for item in sorted(p.iterdir()):
                entries.append({
                    "name": item.name,
                    "type": "directory" if item.is_dir() else "file",
                    "size": item.stat().st_size if not item.is_dir() else None
                })
            return entries
            
        entries = await asyncio.to_thread(_list)
        return DictatorResponse.success(data=entries, path=str(p))

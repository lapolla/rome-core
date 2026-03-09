#!/usr/bin/env python3
"""
MCP Server "asshole" — modular Python dictator.
Thin entry point: imports core + all tool modules, then runs.
"""

import sys
from pathlib import Path

# When invoked as `python3 dictator/dictator.py`, ensure the parent dir
# (rome-core/) is on sys.path so `from dictator.xxx` imports work.
_parent = str(Path(__file__).resolve().parent.parent)
if _parent not in sys.path:
    sys.path.insert(0, _parent)

# Core creates the FastMCP instance and shared utilities
from dictator.core import mcp  # noqa: F401

# Each module registers its @mcp.tool() decorators on import
import dictator.tools_fs        # noqa: F401  — shell_exec, fs_read/write, read/write_anywhere, list_directory
import dictator.tools_git       # noqa: F401  — git_status, git_diff, git_commit, git_push
import dictator.tools_drupal    # noqa: F401  — rsync_ftk_modules, drush_run, drupal_fj_run
import dictator.tools_legion    # noqa: F401  — execute_legion, execute_campaign
import dictator.tools_skyrim    # noqa: F401  — skyrim_*, compile_papyrus
import dictator.tools_desktop   # noqa: F401  — desktop_*
import dictator.tools_media     # noqa: F401  — music_*, http_fetch, fetch_mo2_mod
import dictator.tools_gc        # noqa: F401  — gc_legions, legion_stats
import dictator.tools_stats     # noqa: F401  — rome_tail
import dictator.tools_prefect   # noqa: F401  — execute_prefect
import dictator.tools_docs      # noqa: F401  — update_project_docs

if __name__ == "__main__":
    # Startup GC: clean old legion dirs before serving
    from dictator.tools_gc import auto_gc
    auto_gc()
    mcp.run(transport="stdio")

"""Git tools: status, diff, commit, push — all operate on GIT_ROOT."""

import json
import shlex

from dictator.core import mcp, run_cmd, GIT_ROOT


@mcp.tool()
async def git_status() -> str:
    """Show git status (branch + short) for the Drupal11 repo."""
    r = await run_cmd("git status --short --branch", cwd=GIT_ROOT)
    return json.dumps(r, indent=2)


@mcp.tool()
async def git_diff(path: str = "") -> str:
    """Show git diff (optionally for a specific path) in Drupal11 repo."""
    cmd = f"git diff -- {path}" if path else "git diff"
    r = await run_cmd(cmd, cwd=GIT_ROOT)
    r["command"] = cmd
    return json.dumps(r, indent=2)


@mcp.tool()
async def git_commit(message: str, files: list[str] | None = None) -> str:
    """Commit staged or specific files with a commit message."""
    if files:
        add_cmd = "git add " + " ".join(shlex.quote(f) for f in files)
    else:
        add_cmd = "git add -A"

    r = await run_cmd(add_cmd, cwd=GIT_ROOT)
    if not r.get("ok"):
        return json.dumps(r, indent=2)

    commit_cmd = f"git commit -m {shlex.quote(message)}"
    r = await run_cmd(commit_cmd, cwd=GIT_ROOT)
    return json.dumps(r, indent=2)


@mcp.tool()
async def git_push(branch: str = "master") -> str:
    """Push current branch to origin."""
    r = await run_cmd(f"git push origin {shlex.quote(branch)}", cwd=GIT_ROOT)
    return json.dumps(r, indent=2)

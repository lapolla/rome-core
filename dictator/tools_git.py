"""Git tools: status, diff, commit, push — now accept an optional repo_path."""

import json
import shlex
from pathlib import Path

from dictator.core import run_cmd, GIT_ROOT


def register(registry):
    """Register Git tools with the given native ROME registry instance."""

    @registry.tool()
    async def git_status(repo_path: str = "") -> str:
        """Show git status (branch + short) for a repo."""
        cwd = Path(repo_path) if repo_path else GIT_ROOT
        r = await run_cmd("git status --short --branch", cwd=cwd)
        return r.get("stdout", "") if r.get("ok") else f"ERR: {r.get('stderr', '')}"

    @registry.tool()
    async def git_diff(path: str = "", repo_path: str = "") -> str:
        """Show git diff (optionally for a specific path) in a repo."""
        cwd = Path(repo_path) if repo_path else GIT_ROOT
        cmd = f"git diff -- {path}" if path else "git diff"
        r = await run_cmd(cmd, cwd=cwd)
        return r.get("stdout", "") if r.get("ok") else f"ERR: {r.get('stderr', '')}"

    @registry.tool()
    async def git_commit(message: str, files: list[str] | None = None, repo_path: str = "") -> str:
        """Commit staged or specific files with a commit message in a repo."""
        cwd = Path(repo_path) if repo_path else GIT_ROOT
        if files:
            add_cmd = "git add " + " ".join(shlex.quote(f) for f in files)
        else:
            add_cmd = "git add -A"

        r = await run_cmd(add_cmd, cwd=cwd)
        if not r.get("ok"):
            return f"ERR(add): {r.get('stderr', '')}"
        commit_cmd = f"git commit -m {shlex.quote(message)}"
        r = await run_cmd(commit_cmd, cwd=cwd)
        return r.get("stdout", "OK") if r.get("ok") else f"ERR: {r.get('stderr', '')}"

    @registry.tool()
    async def git_push(branch: str = "master", repo_path: str = "") -> str:
        """Push current branch to origin for a repo."""
        cwd = Path(repo_path) if repo_path else GIT_ROOT
        r = await run_cmd(f"git push origin {shlex.quote(branch)}", cwd=cwd)
        return "OK" if r.get("ok") else f"ERR: {r.get('stderr', '')}"

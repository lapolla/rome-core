#!/usr/bin/env python3
"""
MCP Server "asshole" — Python port of server.mjs + dictator tools.
19 tools total. Runs on stdio via `python3 asshole.py`.
"""

import asyncio
import json
import os
import shlex
import subprocess
from pathlib import Path
from typing import Optional

from mcp.server.fastmcp import FastMCP

# ── Paths ──────────────────────────────────────────────────────────────
ROOT_DIR = Path("/var/www/ftk_lms")
GIT_ROOT = Path("/home/paul-kane/projects/Drupal11")
ROME_ROOT = Path(os.environ.get("ROME_ROOT", "/home/paul-kane/projects/rome-core"))
ARSENAL_PATH = ROME_ROOT / "arsenal" / "core_arsenal.json"
SKYRIM_STATE_FILE = Path(
    "/media/paul-kane/SteamGames/steamapps/compatdata/489830/pfx/drive_c/tmp/skyrim_state.json"
)
MO2_DOWNLOADS = Path.home() / "Games" / "MO2" / "downloads"

# ── Server ─────────────────────────────────────────────────────────────
mcp = FastMCP("asshole")

MAX_BUF = 10 * 1024 * 1024  # 10 MB default output cap


async def run_cmd(
    cmd: str,
    cwd: str | Path = ROOT_DIR,
    env: dict | None = None,
    max_output: int = MAX_BUF,
) -> dict:
    """Run a shell command and return {ok, stdout, stderr} or error info."""
    try:
        proc = await asyncio.create_subprocess_shell(
            cmd,
            cwd=str(cwd),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        stdout_b, stderr_b = await proc.communicate()
        stdout = stdout_b.decode(errors="replace")[:max_output]
        stderr = stderr_b.decode(errors="replace")[:max_output]
        if proc.returncode == 0:
            return {"ok": True, "stdout": stdout, "stderr": stderr}
        return {
            "ok": False,
            "exit_code": proc.returncode,
            "stdout": stdout,
            "stderr": stderr,
        }
    except Exception as e:
        return {"ok": False, "message": str(e)}


# ═══════════════════════════════════════════════════════════════════════
#  1. rsync_ftk_modules
# ═══════════════════════════════════════════════════════════════════════
@mcp.tool()
async def rsync_ftk_modules(include_themes: bool = False) -> str:
    """Rsync custom Drupal modules (and optionally themes) from dev to /var/www."""
    result: dict = {"ok": True, "modules": None, "themes": None}

    module_cmd = "rsync -av --delete /home/paul-kane/projects/Drupal11/modules/custom/ /var/www/ftk_lms/web/modules/custom/"
    r = await run_cmd(module_cmd, cwd="/")
    result["modules"] = {"command": module_cmd, **r}

    if include_themes:
        theme_cmd = "rsync -av --delete /home/paul-kane/projects/Drupal11/themes/custom/ /var/www/ftk_lms/web/themes/custom/"
        r = await run_cmd(theme_cmd, cwd="/")
        result["themes"] = {"command": theme_cmd, **r}

    if not result["modules"].get("ok", True):
        result["ok"] = False
    return json.dumps(result, indent=2)


# ═══════════════════════════════════════════════════════════════════════
#  2. http_fetch
# ═══════════════════════════════════════════════════════════════════════
@mcp.tool()
async def http_fetch(url: str, dest_path: str, extract: bool = False) -> str:
    """Download a file from URL to dest_path. Optionally extract archive."""
    abs_path = Path(dest_path).resolve()
    abs_path.parent.mkdir(parents=True, exist_ok=True)

    dl_cmd = f"wget -O {shlex.quote(str(abs_path))} {shlex.quote(url)}"
    dl = await run_cmd(dl_cmd, cwd=str(abs_path.parent))

    extract_info = None
    if extract and dl.get("ok"):
        ext_cmd = None
        s = str(abs_path).lower()
        if s.endswith(".zip"):
            ext_cmd = f"unzip -o {shlex.quote(str(abs_path))}"
        elif s.endswith((".7z", ".7zip")):
            ext_cmd = f"7z x -y {shlex.quote(str(abs_path))}"
        elif s.endswith((".tar", ".tar.gz", ".tgz")):
            ext_cmd = f"tar xf {shlex.quote(str(abs_path))}"
        if ext_cmd:
            extract_info = await run_cmd(ext_cmd, cwd=str(abs_path.parent), max_output=50 * 1024 * 1024)
            extract_info["command"] = ext_cmd

    return json.dumps(
        {"ok": dl.get("ok", False), "url": url, "dest": str(abs_path), "download": dl, "extract": extract_info},
        indent=2,
    )


# ═══════════════════════════════════════════════════════════════════════
#  3. fetch_mo2_mod
# ═══════════════════════════════════════════════════════════════════════
@mcp.tool()
async def fetch_mo2_mod(url: str, filename: str = "") -> str:
    """Download a mod to ~/Games/MO2/downloads."""
    MO2_DOWNLOADS.mkdir(parents=True, exist_ok=True)

    if not filename:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        last = parsed.path.split("/")[-1]
        filename = last if last else f"mod_{int(__import__('time').time())}.bin"

    dest = MO2_DOWNLOADS / filename
    dl_cmd = f"wget -O {shlex.quote(str(dest))} {shlex.quote(url)}"
    dl = await run_cmd(dl_cmd, cwd=str(MO2_DOWNLOADS))
    return json.dumps({"ok": dl.get("ok", False), "url": url, "dest": str(dest), "download": dl}, indent=2)


# ═══════════════════════════════════════════════════════════════════════
#  4. shell_exec
# ═══════════════════════════════════════════════════════════════════════
@mcp.tool()
async def shell_exec(command: str) -> str:
    """Execute a shell command (cwd = /var/www/ftk_lms)."""
    r = await run_cmd(command, cwd=ROOT_DIR)
    return json.dumps(r, indent=2)


# ═══════════════════════════════════════════════════════════════════════
#  5. fs_read
# ═══════════════════════════════════════════════════════════════════════
@mcp.tool()
async def fs_read(path: str) -> str:
    """Read a file relative to /var/www/ftk_lms."""
    full = ROOT_DIR / path
    return full.read_text(encoding="utf-8")


# ═══════════════════════════════════════════════════════════════════════
#  6. fs_write
# ═══════════════════════════════════════════════════════════════════════
@mcp.tool()
async def fs_write(path: str, content: str) -> str:
    """Write a file relative to /var/www/ftk_lms."""
    full = ROOT_DIR / path
    full.write_text(content, encoding="utf-8")
    return f"Wrote {len(content)} bytes to {full}"


# ═══════════════════════════════════════════════════════════════════════
#  7. git_status
# ═══════════════════════════════════════════════════════════════════════
@mcp.tool()
async def git_status() -> str:
    """Show git status (branch + short) for the Drupal11 repo."""
    r = await run_cmd("git status --short --branch", cwd=GIT_ROOT)
    return json.dumps(r, indent=2)


# ═══════════════════════════════════════════════════════════════════════
#  8. git_diff
# ═══════════════════════════════════════════════════════════════════════
@mcp.tool()
async def git_diff(path: str = "") -> str:
    """Show git diff (optionally for a specific path) in Drupal11 repo."""
    cmd = f"git diff -- {path}" if path else "git diff"
    r = await run_cmd(cmd, cwd=GIT_ROOT)
    r["command"] = cmd
    return json.dumps(r, indent=2)


# ═══════════════════════════════════════════════════════════════════════
#  9. git_commit
# ═══════════════════════════════════════════════════════════════════════
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


# ═══════════════════════════════════════════════════════════════════════
# 10. git_push
# ═══════════════════════════════════════════════════════════════════════
@mcp.tool()
async def git_push(branch: str = "master") -> str:
    """Push current branch to origin."""
    r = await run_cmd(f"git push origin {shlex.quote(branch)}", cwd=GIT_ROOT)
    return json.dumps(r, indent=2)


# ═══════════════════════════════════════════════════════════════════════
# 11. drush_run
# ═══════════════════════════════════════════════════════════════════════
@mcp.tool()
async def drush_run(args: str) -> str:
    """Run a Drush command (e.g. 'status', 'cr', 'updb -y')."""
    cmd = f"composer exec drush {args}"
    r = await run_cmd(cmd, cwd=ROOT_DIR)
    r["command"] = cmd
    return json.dumps(r, indent=2)


# ═══════════════════════════════════════════════════════════════════════
# 12. drupal_fj_run
# ═══════════════════════════════════════════════════════════════════════
@mcp.tool()
async def drupal_fj_run(
    base_url: str = "",
    db_dsn: str = "",
    output_dir: str = "",
    browser: str = "firefox",
    headless: bool = True,
    webdriver_url: str = "http://127.0.0.1:4444",
    start_driver: bool = True,
    driver_host: str = "127.0.0.1",
    driver_port: int = 4444,
    driver_log: str = "/tmp/geckodriver.log",
    testsuite: str = "",
    test_path: str = "",
    extra_args: str = "",
) -> str:
    """Run Drupal FunctionalJavascript tests (Mink + WebDriver)."""
    result: dict = {
        "ok": True,
        "started_driver": False,
        "driver_pid": None,
        "driver_check": None,
        "command": None,
        "stdout": None,
        "stderr": None,
        "exit_code": 0,
    }

    base_url = base_url or os.environ.get("SIMPLETEST_BASE_URL", "")
    db_dsn = db_dsn or os.environ.get("SIMPLETEST_DB", "")
    output_dir = output_dir or os.environ.get("BROWSERTEST_OUTPUT_DIRECTORY", "/tmp/browser_output")
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    # Check driver status
    check_url = f"http://{driver_host}:{driver_port}/status"
    chk = await run_cmd(f"curl -s {check_url} | head -c 400", cwd=ROOT_DIR)
    if chk.get("ok") and chk.get("stdout", "").strip():
        result["driver_check"] = chk["stdout"]
    else:
        result["driver_check"] = None

    # Start driver if needed
    if not result["driver_check"] and start_driver:
        if browser == "firefox":
            start_cmd = f"nohup geckodriver --host {driver_host} --port {driver_port} > {shlex.quote(driver_log)} 2>&1 & echo $!"
        else:
            start_cmd = f'nohup chromedriver --port={driver_port} --url-base=/wd/hub --allowed-ips="" > {shlex.quote(driver_log)} 2>&1 & echo $!'

        dr = await run_cmd(start_cmd, cwd=ROOT_DIR)
        if dr.get("ok"):
            result["started_driver"] = True
            try:
                result["driver_pid"] = int(dr["stdout"].strip())
            except ValueError:
                pass

    # Build Mink driver args
    if browser == "firefox":
        fx_args = '["-headless"]' if headless else "[]"
        driver_args = f'["firefox", {{"browserName":"firefox","moz:firefoxOptions":{{"args":{fx_args}}}}}, "{webdriver_url}"]'
    else:
        ch_args = '["--headless=new","--disable-gpu","--no-sandbox","--disable-dev-shm-usage"]' if headless else "[]"
        driver_args = f'["chrome", {{"browserName":"chrome","goog:chromeOptions":{{"args":{ch_args}}}}}, "{webdriver_url}"]'

    env = {**os.environ}
    env["MINK_DRIVER_ARGS_WEBDRIVER"] = driver_args
    if base_url:
        env["SIMPLETEST_BASE_URL"] = base_url
    if db_dsn:
        env["SIMPLETEST_DB"] = db_dsn
    env["BROWSERTEST_OUTPUT_DIRECTORY"] = output_dir

    if not env.get("SIMPLETEST_BASE_URL"):
        return json.dumps({"ok": False, "message": "Missing SIMPLETEST_BASE_URL"}, indent=2)
    if not env.get("SIMPLETEST_DB"):
        return json.dumps({"ok": False, "message": "Missing SIMPLETEST_DB"}, indent=2)

    cmd = "./vendor/bin/phpunit -c web/core"
    if testsuite:
        cmd += f" --testsuite {testsuite}"
    if test_path:
        cmd += f" {test_path}"
    if extra_args:
        cmd += f" {extra_args}"
    result["command"] = cmd

    r = await run_cmd(cmd, cwd=ROOT_DIR, env=env, max_output=50 * 1024 * 1024)
    result["stdout"] = r.get("stdout", "")
    result["stderr"] = r.get("stderr", "")
    result["exit_code"] = r.get("exit_code", 0 if r.get("ok") else 1)
    if not r.get("ok"):
        result["ok"] = False

    return json.dumps(result, indent=2)


# ═══════════════════════════════════════════════════════════════════════
# 13. read_anywhere
# ═══════════════════════════════════════════════════════════════════════
@mcp.tool()
async def read_anywhere(path: str) -> str:
    """Read a file by absolute path."""
    return Path(path).resolve().read_text(encoding="utf-8")


# ═══════════════════════════════════════════════════════════════════════
# 14. write_anywhere
# ═══════════════════════════════════════════════════════════════════════
@mcp.tool()
async def write_anywhere(path: str, content: str) -> str:
    """Write a file by absolute path."""
    p = Path(path).resolve()
    p.write_text(content, encoding="utf-8")
    return json.dumps({"ok": True, "message": f"Wrote {len(content)} bytes to {p}"})


# ═══════════════════════════════════════════════════════════════════════
# 15. execute_legion  (from dictator)
# ═══════════════════════════════════════════════════════════════════════
@mcp.tool()
async def execute_legion(
    task_id: str,
    capability: str,
    args: list[str],
    input_files: list[str] | None = None,
) -> str:
    """Execute a ROME legion worker for a given capability."""
    import shutil
    import time

    if input_files is None:
        input_files = []

    if not ARSENAL_PATH.exists():
        return json.dumps({"ok": False, "message": "Arsenal file not found"})

    arsenal = json.loads(ARSENAL_PATH.read_text())
    cap = arsenal.get("capabilities", {}).get(capability)
    if not cap:
        return f'ERROR: Capability "{capability}" not found.'

    task_dir = ROME_ROOT / "legions" / task_id
    task_dir.mkdir(parents=True, exist_ok=True)

    for f in input_files:
        src = (ROME_ROOT / f).resolve()
        dest = task_dir / f
        if src.exists():
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(src), str(dest))

    cap_args = " ".join(cap.get("args", []))
    quoted_args = " ".join(shlex.quote(a) for a in args)
    command = f"{cap['exec']} {task_id} {time.time()} {cap_args} {quoted_args}"

    env = {**os.environ, "ROME_TASK_DIR": str(task_dir)}
    r = await run_cmd(command, cwd=task_dir, env=env)
    if r.get("ok"):
        return r.get("stdout", "")
    return f"Legion Execution Failed: {r.get('message', r.get('stderr', ''))}"


# ═══════════════════════════════════════════════════════════════════════
# 16. list_directory  (from dictator)
# ═══════════════════════════════════════════════════════════════════════
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


# ═══════════════════════════════════════════════════════════════════════
# 18. skyrim_read_state  (from dictator)
# ═══════════════════════════════════════════════════════════════════════
@mcp.tool()
async def skyrim_read_state(path: str = "") -> str:
    """Read Skyrim state JSON (optionally a dot-path like 'player.health')."""
    try:
        state = json.loads(SKYRIM_STATE_FILE.read_text())
        if path:
            value = state
            for key in path.split("."):
                value = value[key]
            return json.dumps({"ok": True, "path": path, "value": value}, indent=2)
        return json.dumps({"ok": True, **state}, indent=2)
    except Exception as e:
        return json.dumps({"ok": False, "message": str(e)})


# ═══════════════════════════════════════════════════════════════════════
# 19. skyrim_console  (from dictator)
# ═══════════════════════════════════════════════════════════════════════
@mcp.tool()
async def skyrim_console(commands: list[str]) -> str:
    """Send console commands to Skyrim via xdotool."""
    try:
        # Focus Skyrim window
        r = await run_cmd('xdotool search --name "Skyrim Special Edition"', cwd="/tmp")
        if r.get("ok"):
            for wid in r["stdout"].strip().split("\n"):
                wid = wid.strip()
                if not wid:
                    continue
                name_r = await run_cmd(f"xdotool getwindowname {wid}", cwd="/tmp")
                name = name_r.get("stdout", "")
                if "Mod Organizer" not in name:
                    await run_cmd(f"xdotool windowactivate --sync {wid} windowfocus --sync {wid}", cwd="/tmp")
                    break

        # Open console
        await run_cmd("xdotool key grave", cwd="/tmp")
        for cmd in commands:
            await run_cmd(f"xdotool type --delay 12 -- {shlex.quote(cmd)}", cwd="/tmp")
            await run_cmd("xdotool key Return", cwd="/tmp")
        # Close console
        await run_cmd("xdotool key grave", cwd="/tmp")

        return json.dumps({"ok": True, "commands": commands})
    except Exception as e:
        return json.dumps({"ok": False, "message": str(e)})


# ═══════════════════════════════════════════════════════════════════════
#  Main
# ═══════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    mcp.run(transport="stdio")

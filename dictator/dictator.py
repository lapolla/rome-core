#!/usr/bin/env python3
"""
MCP Server "asshole" — Python port of server.mjs + dictator tools.
34 tools total. Runs on stdio via `python3 asshole.py`.
"""

import asyncio
import json
import os
import shlex
import subprocess
import time as _time
from pathlib import Path
from typing import Optional

from mcp.server.fastmcp import FastMCP
from dictator.rome_log import log_event

# ── Config ─────────────────────────────────────────────────────────────
_CFG_PATH = Path(__file__).parent / "config.json"
_cfg = {}
if _CFG_PATH.exists():
    try:
        _cfg = json.loads(_CFG_PATH.read_text())
    except Exception:
        pass

# ── Paths (config with hardcoded fallbacks) ────────────────────────────
ROOT_DIR = Path(_cfg.get("root_dir", "/var/www/ftk_lms"))
GIT_ROOT = Path(_cfg.get("git_root", "/home/paul-kane/projects/Drupal11"))
ROME_ROOT = Path(os.environ.get("ROME_ROOT", _cfg.get("rome_root", "/home/paul-kane/projects/rome-core")))
ARSENAL_PATH = ROME_ROOT / "arsenal" / "core_arsenal.json"
SKYRIM_STATE_FILE = Path(
    _cfg.get("skyrim_state_file",
             "/media/paul-kane/SteamGames/steamapps/compatdata/489830/pfx/drive_c/tmp/skyrim_state.json")
)
_mo2_raw = _cfg.get("mo2_downloads", "~/Games/MO2/downloads")
MO2_DOWNLOADS = Path(_mo2_raw).expanduser()

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
    t0 = _time.monotonic()
    try:
        proc = await asyncio.create_subprocess_shell(
            cmd,
            cwd=str(cwd),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        stdout_b, stderr_b = await proc.communicate()
        elapsed = _time.monotonic() - t0

        truncated = len(stdout_b) > max_output or len(stderr_b) > max_output
        stdout = stdout_b.decode(errors="replace")[:max_output]
        stderr = stderr_b.decode(errors="replace")[:max_output]
        if truncated:
            stdout += "\n[ROME: output truncated at 10MB]"
            log_event("run_cmd", status="truncated", duration_s=elapsed, message=cmd[:200])

        result: dict
        if proc.returncode == 0:
            result = {"ok": True, "stdout": stdout, "stderr": stderr}
        else:
            result = {
                "ok": False,
                "exit_code": proc.returncode,
                "stdout": stdout,
                "stderr": stderr,
            }
        if truncated:
            result["truncated"] = True

        log_event("run_cmd", status="ok" if result["ok"] else "error", duration_s=elapsed, message=cmd[:200])
        return result
    except Exception as e:
        elapsed = _time.monotonic() - t0
        log_event("run_cmd", status="exception", duration_s=elapsed, message=str(e)[:200])
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
    log_event("shell_exec", message=command[:200])
    r = await run_cmd(command, cwd=ROOT_DIR)
    return json.dumps(r, indent=2)


# ═══════════════════════════════════════════════════════════════════════
#  5. fs_read
# ═══════════════════════════════════════════════════════════════════════
@mcp.tool()
async def fs_read(path: str) -> str:
    """Read a file relative to /var/www/ftk_lms."""
    full = (ROOT_DIR / path).resolve()
    if not full.is_relative_to(ROOT_DIR):
        return json.dumps({"ok": False, "message": "Path escapes root directory"})
    return full.read_text(encoding="utf-8")


# ═══════════════════════════════════════════════════════════════════════
#  6. fs_write
# ═══════════════════════════════════════════════════════════════════════
@mcp.tool()
async def fs_write(path: str, content: str) -> str:
    """Write a file relative to /var/www/ftk_lms."""
    full = (ROOT_DIR / path).resolve()
    if not full.is_relative_to(ROOT_DIR):
        return json.dumps({"ok": False, "message": "Path escapes root directory"})
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

    t0 = _time.monotonic()

    # Normalize capability to uppercase
    capability = capability.upper()

    if input_files is None:
        input_files = []

    if not ARSENAL_PATH.exists():
        return json.dumps({"ok": False, "message": "Arsenal file not found"})

    arsenal = json.loads(ARSENAL_PATH.read_text())
    cap = arsenal.get("capabilities", {}).get(capability)
    if not cap:
        return f'ERROR: Capability "{capability}" not found.'

    timeout_s = cap.get("timeout", 300)

    task_dir = ROME_ROOT / "legions" / task_id
    task_dir.mkdir(parents=True, exist_ok=True)

    for f in input_files:
        f_path = Path(f)
        if f_path.is_absolute():
            src = f_path.resolve()
            dest = task_dir / f_path.name
        else:
            src = (ROME_ROOT / f_path).resolve()
            dest = task_dir / f_path

        if src.exists():
            if src.resolve() == dest.resolve():
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(src), str(dest))

    cap_args = " ".join(cap.get("args", []))
    quoted_args = " ".join(shlex.quote(a) for a in args)
    command = f"{cap['exec']} {task_id} {_time.time()} {cap_args} {quoted_args}"

    log_event("execute_legion", task_id=task_id, message=f"cap={capability} timeout={timeout_s}s")

    env = {**os.environ, "ROME_TASK_DIR": str(task_dir)}
    try:
        r = await asyncio.wait_for(run_cmd(command, cwd=task_dir, env=env), timeout=timeout_s)
    except asyncio.TimeoutError:
        elapsed = _time.monotonic() - t0
        log_event("execute_legion", task_id=task_id, status="timeout", duration_s=elapsed,
                  message=f"Timed out after {timeout_s}s")
        return json.dumps({"ok": False, "message": f"Legion timed out after {timeout_s}s"})

    elapsed = _time.monotonic() - t0
    ok = r.get("ok", False)
    log_event("execute_legion", task_id=task_id, status="ok" if ok else "error", duration_s=elapsed)

    if ok:
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
# 17. music_play  (from dictator)
# ═══════════════════════════════════════════════════════════════════════
@mcp.tool()
async def music_play(query: str, fade_ms: int = 500) -> str:
    """Play music via yt-dlp + mpv. Accepts a URL or search query."""
    try:
        is_url = query.startswith("http")
        ytdl_query = query if is_url else f"ytsearch:{query}"

        r = await run_cmd(
            f"yt-dlp --no-download --print webpage_url {shlex.quote(ytdl_query)}", cwd="/tmp"
        )
        if not r.get("ok"):
            return json.dumps({"ok": False, "message": r.get("stderr", "yt-dlp failed")})

        url = r["stdout"].strip()
        proc = subprocess.Popen(
            ["mpv", url, "--no-video", "--volume=100"],
            start_new_session=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return json.dumps({"ok": True, "url": url, "pid": proc.pid})
    except Exception as e:
        return json.dumps({"ok": False, "message": str(e)})


# ═══════════════════════════════════════════════════════════════════════
# 18. skyrim_read_state  (from dictator)
# ═══════════════════════════════════════════════════════════════════════
@mcp.tool()
async def skyrim_read_state(path: str = "") -> str:
    """Read Skyrim state JSON (optionally a dot-path like 'player.health')."""
    try:
        if not SKYRIM_STATE_FILE.exists():
            return json.dumps({"ok": False, "message": "Skyrim state file not found"})
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
# 20. music_stop
# ═══════════════════════════════════════════════════════════════════════
@mcp.tool()
async def music_stop() -> str:
    """Stop all running mpv instances."""
    r = await run_cmd("pkill mpv", cwd="/tmp")
    return json.dumps(r)


# ═══════════════════════════════════════════════════════════════════════
# 21. music_status
# ═══════════════════════════════════════════════════════════════════════
@mcp.tool()
async def music_status() -> str:
    """Check if mpv is currently playing."""
    r = await run_cmd("pgrep -l mpv", cwd="/tmp")
    is_playing = r.get("ok", False) and "mpv" in r.get("stdout", "")
    return json.dumps({"ok": True, "playing": is_playing, "output": r.get("stdout", "").strip()})


# ═══════════════════════════════════════════════════════════════════════
# 22. skyrim_face_actor
# ═══════════════════════════════════════════════════════════════════════
@mcp.tool()
async def skyrim_face_actor(actor_id: str = "player") -> str:
    """Make the specified actor face the camera."""
    cmd = [f"prid {actor_id}", "lookat player"]
    return await skyrim_console(cmd)


# ═══════════════════════════════════════════════════════════════════════
# 23. skyrim_follow_actor
# ═══════════════════════════════════════════════════════════════════════
@mcp.tool()
async def skyrim_follow_actor(actor_id: str, target_id: str = "player") -> str:
    """Make an actor follow a target."""
    cmd = [f"prid {actor_id}", f"setav variable01 1", f"evp"]
    # Note: Following logic usually requires a mod or specific AI package commands
    return await skyrim_console(cmd)


# ═══════════════════════════════════════════════════════════════════════
# 24. desktop_screenshot
# ═══════════════════════════════════════════════════════════════════════
@mcp.tool()
async def desktop_screenshot(window_id: str = "") -> str:
    """Capture a screenshot. Returns path to the saved image."""
    import time
    path = f"/tmp/screenshot_{int(time.time())}.png"
    cmd = f"scrot {shlex.quote(path)}"
    if window_id:
        cmd = f"scrot -u {shlex.quote(path)} --window {shlex.quote(window_id)}"
    
    r = await run_cmd(cmd, cwd="/tmp")
    if r.get("ok"):
        return json.dumps({"ok": True, "path": path})
    return json.dumps(r)


# ═══════════════════════════════════════════════════════════════════════
# 25. desktop_click
# ═══════════════════════════════════════════════════════════════════════
@mcp.tool()
async def desktop_click(x: int, y: int, button: int = 1, clicks: int = 1, window_id: str = "") -> str:
    """Click at screen coordinates."""
    if window_id:
        await run_cmd(f"xdotool windowactivate --sync {shlex.quote(window_id)}", cwd="/tmp")
    
    cmd = f"xdotool mousemove {x} {y} click --repeat {clicks} {button}"
    r = await run_cmd(cmd, cwd="/tmp")
    return json.dumps(r)


# ═══════════════════════════════════════════════════════════════════════
# 26. desktop_type_text
# ═══════════════════════════════════════════════════════════════════════
@mcp.tool()
async def desktop_type_text(text: str, delay_ms: int = 12) -> str:
    """Type text via xdotool."""
    cmd = f"xdotool type --delay {delay_ms} -- {shlex.quote(text)}"
    r = await run_cmd(cmd, cwd="/tmp")
    return json.dumps(r)


# ═══════════════════════════════════════════════════════════════════════
# 27. desktop_press_key
# ═══════════════════════════════════════════════════════════════════════
@mcp.tool()
async def desktop_press_key(key: str) -> str:
    """Press a key combo (e.g. 'Return', 'alt+F4')."""
    cmd = f"xdotool key --clearmodifiers {shlex.quote(key)}"
    r = await run_cmd(cmd, cwd="/tmp")
    return json.dumps(r)


# ═══════════════════════════════════════════════════════════════════════
# 28. desktop_find_window
# ═══════════════════════════════════════════════════════════════════════
@mcp.tool()
async def desktop_find_window(name: str = "", class_name: str = "") -> str:
    """Find window IDs by title or class."""
    if name:
        cmd = f"xdotool search --name {shlex.quote(name)}"
    elif class_name:
        cmd = f"xdotool search --class {shlex.quote(class_name)}"
    else:
        return json.dumps({"ok": False, "message": "Must provide name or class_name"})
    
    r = await run_cmd(cmd, cwd="/tmp")
    ids = r.get("stdout", "").strip().split("\n") if r.get("ok") else []
    return json.dumps({"ok": r.get("ok"), "ids": [i for i in ids if i]})


# ═══════════════════════════════════════════════════════════════════════
# 29. desktop_focus_window
# ═══════════════════════════════════════════════════════════════════════
@mcp.tool()
async def desktop_focus_window(window_id: str) -> str:
    """Activate and focus a window."""
    r = await run_cmd(f"xdotool windowactivate --sync {shlex.quote(window_id)} windowfocus --sync {shlex.quote(window_id)}", cwd="/tmp")
    return json.dumps(r)


# ═══════════════════════════════════════════════════════════════════════
# 30. desktop_get_mouse_location
# ═══════════════════════════════════════════════════════════════════════
@mcp.tool()
async def desktop_get_mouse_location() -> str:
    """Get current mouse X, Y coordinates."""
    r = await run_cmd("xdotool getmouselocation --shell", cwd="/tmp")
    # Output is like X=100\nY=200\nSCREEN=0\nWINDOW=12345
    return json.dumps({"ok": r.get("ok"), "data": r.get("stdout", "").strip()})


# ═══════════════════════════════════════════════════════════════════════
# 31. desktop_notify
# ═══════════════════════════════════════════════════════════════════════
@mcp.tool()
async def desktop_notify(message: str, title: str = "ROME", urgency: str = "normal", expire_ms: int = 5000) -> str:
    """Show a desktop notification using notify-send."""
    cmd = f"notify-send -t {expire_ms} -u {shlex.quote(urgency)} {shlex.quote(title)} {shlex.quote(message)}"
    r = await run_cmd(cmd, cwd="/tmp")
    return json.dumps(r)


# ═══════════════════════════════════════════════════════════════════════
# 32. execute_campaign
# ═══════════════════════════════════════════════════════════════════════
@mcp.tool()
async def execute_campaign(
    campaign_id: str,
    tasks: list[dict],
) -> str:
    """
    Execute multiple ROME tasks in parallel.
    Each task dict: { 'id': str, 'capability': str, 'args': list[str], 'input_files': list[str] }
    """
    t0 = _time.monotonic()
    log_event("execute_campaign", task_id=campaign_id, message=f"{len(tasks)} tasks")

    async def run_task(t):
        return await execute_legion(
            task_id=f"{campaign_id}_{t['id']}",
            capability=t['capability'],
            args=t['args'],
            input_files=t.get('input_files', [])
        )

    results = await asyncio.gather(*(run_task(t) for t in tasks))

    elapsed = _time.monotonic() - t0
    log_event("execute_campaign", task_id=campaign_id, status="ok", duration_s=elapsed,
              message=f"Completed {len(tasks)} tasks")

    report = {
        "campaign_id": campaign_id,
        "results": {t['id']: r for t, r in zip(tasks, results)}
    }
    return json.dumps(report, indent=2)


# ═══════════════════════════════════════════════════════════════════════
# 33. skyrim_pivot
# ═══════════════════════════════════════════════════════════════════════
@mcp.tool()
async def skyrim_pivot(degrees: float) -> str:
    """Turn the player in place by a relative degree using dynamic mouse calibration (~300px per 90deg)."""
    # 1. Get current heading
    state_r = await skyrim_read_state()
    state = json.loads(state_r)
    if not state.get("ok"):
        return state_r
    
    # 2. Focus and Calibrate (Simulated logic from FIXME.md)
    # base px_per_degree = 300 / 90 = 3.33
    px_to_move = int(degrees * 3.33)
    
    # 3. Execute mouse movement
    await run_cmd(f"xdotool mousemove_relative -- {px_to_move} 0", cwd="/tmp")
    
    return json.dumps({"ok": True, "degrees": degrees, "px_moved": px_to_move})


# ═══════════════════════════════════════════════════════════════════════
# 34. skyrim_compound_move
# ═══════════════════════════════════════════════════════════════════════
@mcp.tool()
async def skyrim_compound_move(look_dx: int = 0, direction: str = "") -> str:
    """Execute a turn or a move command. Passing look_dx without a direction turns in place."""
    if look_dx != 0:
        await run_cmd(f"xdotool mousemove_relative -- {look_dx} 0", cwd="/tmp")
    
    if direction:
        # Use standard movement keys (WASD)
        key_map = {"forward": "w", "back": "s", "left": "a", "right": "d"}
        key = key_map.get(direction.lower())
        if key:
            await run_cmd(f"xdotool keydown {key} sleep 0.5 keyup {key}", cwd="/tmp")
            
    return json.dumps({"ok": True, "look_dx": look_dx, "direction": direction})


# ═══════════════════════════════════════════════════════════════════════
# 35. compile_papyrus
# ═══════════════════════════════════════════════════════════════════════
@mcp.tool()
async def compile_papyrus(mod_name: str, scripts: list[str] | None = None) -> str:
    """
    Compile Papyrus scripts using compile_papyrus.sh.
    mod_name: The folder name under MO2/mods/.
    scripts: Optional list of .psc basenames (without extension). If omitted, all scripts in the mod are compiled.
    """
    script_path = Path("/media/paul-kane/SteamGames/Games/mods/compile_papyrus.sh")
    if not script_path.exists():
        return json.dumps({"ok": False, "message": f"Compiler script not found at {script_path}"})

    cmd = f"bash {shlex.quote(str(script_path))} {shlex.quote(mod_name)}"
    if scripts:
        cmd += " " + " ".join(shlex.quote(s) for s in scripts)

    # Use the directory containing the script as CWD
    r = await run_cmd(cmd, cwd=script_path.parent)
    r["command"] = cmd
    return json.dumps(r, indent=2)


# ═══════════════════════════════════════════════════════════════════════
#  Main
# ═══════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    mcp.run(transport="stdio")

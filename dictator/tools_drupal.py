"""Drupal tools: rsync_ftk_modules, drush_run, drupal_fj_run."""

import json
import os
import shlex
from pathlib import Path

from dictator.core import (
    mcp, run_cmd, ROOT_DIR,
    DRUPAL_MODULES_SRC, DRUPAL_MODULES_DEST,
    DRUPAL_THEMES_SRC, DRUPAL_THEMES_DEST,
)


@mcp.tool()
async def rsync_ftk_modules(include_themes: bool = False) -> str:
    """Rsync custom Drupal modules (and optionally themes) from dev to /var/www."""
    result: dict = {"ok": True, "modules": None, "themes": None}

    module_cmd = f"rsync -av --delete {DRUPAL_MODULES_SRC} {DRUPAL_MODULES_DEST}"
    r = await run_cmd(module_cmd, cwd="/")
    result["modules"] = {"command": module_cmd, **r}

    if include_themes:
        theme_cmd = f"rsync -av --delete {DRUPAL_THEMES_SRC} {DRUPAL_THEMES_DEST}"
        r = await run_cmd(theme_cmd, cwd="/")
        result["themes"] = {"command": theme_cmd, **r}

    if not result["modules"].get("ok", True):
        result["ok"] = False
    return json.dumps(result, indent=2)


@mcp.tool()
async def drush_run(args: str) -> str:
    """Run a Drush command (e.g. 'status', 'cr', 'updb -y')."""
    cmd = f"composer exec drush {args}"
    r = await run_cmd(cmd, cwd=ROOT_DIR)
    r["command"] = cmd
    return json.dumps(r, indent=2)


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

    check_url = f"http://{driver_host}:{driver_port}/status"
    chk = await run_cmd(f"curl -s {check_url} | head -c 400", cwd=ROOT_DIR)
    if chk.get("ok") and chk.get("stdout", "").strip():
        result["driver_check"] = chk["stdout"]
    else:
        result["driver_check"] = None

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

    if browser == "firefox":
        fx_args = '[\"-headless\"]' if headless else "[]"
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

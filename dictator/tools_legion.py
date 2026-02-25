"""Legion tools: execute_legion, execute_campaign."""

import asyncio
import json
import os
import shlex
import shutil
import time as _time
from pathlib import Path

from dictator.core import mcp, run_cmd, run_cmd_stream, ROME_ROOT, ARSENAL_PATH
from dictator.rome_log import log_event


@mcp.tool()
async def execute_legion(
    task_id: str,
    capability: str,
    args: list[str],
    input_files: list[str] | None = None,
) -> str:
    """Execute a ROME legion worker for a given capability."""
    t0 = _time.monotonic()
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
        # Use run_cmd_stream to forward progress bars to terminal in real-time
        r = await asyncio.wait_for(run_cmd_stream(command, cwd=task_dir, env=env), timeout=timeout_s)
    except asyncio.TimeoutError:
        elapsed = _time.monotonic() - t0
        log_event("execute_legion", task_id=task_id, status="timeout", duration_s=elapsed,
                  message=f"Timed out after {timeout_s}s")
        return json.dumps({"ok": False, "message": f"Legion timed out after {timeout_s}s"})

    elapsed = _time.monotonic() - t0
    ok = r.get("ok", False)

    usage = None
    progress = []
    manifest_path = task_dir / "manifest.json"
    try:
        if manifest_path.exists():
            manifest = json.loads(manifest_path.read_text())
            usage = manifest.get("usage")
            progress = manifest.get("progress", [])
    except Exception:
        pass

    log_event("execute_legion", task_id=task_id, status="ok" if ok else "error",
              duration_s=elapsed, usage=usage)

    result = {
        "ok": ok,
        "task_id": task_id,
        "capability": capability,
        "elapsed_s": round(elapsed, 2),
        "progress": progress,
        "usage": usage,
    }
    if ok:
        result["output"] = r.get("stdout", "")
    else:
        result["error"] = r.get("message", r.get("stderr", ""))

    return json.dumps(result, indent=2)


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

    total_usage = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "cost_usd": 0.0}
    has_usage = False
    for t in tasks:
        manifest_path = ROME_ROOT / "legions" / f"{campaign_id}_{t['id']}" / "manifest.json"
        try:
            if manifest_path.exists():
                m = json.loads(manifest_path.read_text())
                u = m.get("usage")
                if u:
                    has_usage = True
                    total_usage["input_tokens"] += u.get("input_tokens", 0)
                    total_usage["output_tokens"] += u.get("output_tokens", 0)
                    total_usage["total_tokens"] += u.get("total_tokens", 0)
                    if u.get("cost_usd") is not None:
                        total_usage["cost_usd"] += u["cost_usd"]
        except Exception:
            pass

    elapsed = _time.monotonic() - t0
    log_event("execute_campaign", task_id=campaign_id, status="ok", duration_s=elapsed,
              message=f"Completed {len(tasks)} tasks",
              usage=total_usage if has_usage else None)

    report = {
        "campaign_id": campaign_id,
        "total_usage": total_usage if has_usage else None,
        "results": {t['id']: r for t, r in zip(tasks, results)}
    }
    return json.dumps(report, indent=2)

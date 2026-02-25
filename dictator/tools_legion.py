"""Legion tools: execute_legion, execute_campaign, rome_dispatch."""

import asyncio
import hashlib
import json
import os
import shlex
import shutil
import time as _time
from pathlib import Path

from dictator.core import mcp, run_cmd, run_cmd_stream, ROME_ROOT, ARSENAL_PATH
from dictator.rome_log import log_event

FALLBACK_CHAIN = {"GEMINI": "CODEX"}
BUSY_PATTERNS = ["service temporarily unavailable", "overloaded", "rate_limit",
                 "rate limit", "quota", "503", "429", "capacity"]

CACHE_DIR = ROME_ROOT / "legions" / ".cache"
CACHE_TTL = 3600  # 1 hour


def _is_busy(r: dict) -> bool:
    if r.get("ok"):
        return False
    text = (r.get("stdout", "") + r.get("stderr", "")).lower()
    return any(p in text for p in BUSY_PATTERNS)


def _cache_key(capability: str, args: list) -> str:
    return hashlib.sha256(f"{capability}:{':'.join(args)}".encode()).hexdigest()[:16]


@mcp.tool()
async def execute_legion(
    task_id: str,
    capability: str,
    args: list[str],
    input_files: list[str] | None = None,
    no_cache: bool = False,
    prompt_file: str = "",
) -> str:
    """Execute a ROME legion worker for a given capability."""
    t0 = _time.monotonic()
    capability = capability.upper()

    if input_files is None:
        input_files = []

    if not ARSENAL_PATH.exists():
        return json.dumps({"ok": False, "message": "Arsenal file not found"}, indent=2)

    arsenal = json.loads(ARSENAL_PATH.read_text())
    cap = arsenal.get("capabilities", {}).get(capability)
    if not cap:
        return json.dumps({"ok": False, "message": f'Capability "{capability}" not found.'}, indent=2)

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

    # File-based dispatch (Phase 17)
    if prompt_file:
        pf = Path(prompt_file)
        if pf.exists():
            file_content = pf.read_text()
            # Write to task dir for the worker to find
            (task_dir / "task.md").write_text(file_content)
            args = ["Read and execute the task in task.md in your current working directory. Output results with [ROME_STATUS: SUCCESS] or [ROME_STATUS: FAILED]."]

    # Prompt Patches (Phase 10) — inject coding rules into the prompt
    patches_path = Path(__file__).parent / "legion_patches.json"
    if patches_path.exists():
        try:
            patches = json.loads(patches_path.read_text()).get(capability, [])
            if patches and args:
                patch_block = "\n".join(f"- {p}" for p in patches)
                args = list(args)  # don't mutate original
                args[0] = f"## Coding Rules\n{patch_block}\n\n{args[0]}"
        except Exception:
            pass

    cap_args = " ".join(cap.get("args", []))
    quoted_args = " ".join(shlex.quote(a) for a in args)
    command = f"{cap['exec']} {task_id} {_time.time()} {cap_args} {quoted_args}"

    # Result Caching (Phase 12)
    cache_file = CACHE_DIR / f"{_cache_key(capability, args)}.json"
    if not no_cache and cache_file.exists():
        try:
            cached = json.loads(cache_file.read_text())
            if _time.time() - cached.get('timestamp', 0) < CACHE_TTL:
                log_event(tool="execute_legion", message="cache hit", task_id=task_id)
                return cached["result"]
        except Exception:
            pass

    log_event(tool="execute_legion", task_id=task_id, message=f"cap={capability} timeout={timeout_s}s")

    env = {**os.environ, "ROME_TASK_DIR": str(task_dir)}
    fallback_used = None
    try:
        # Use run_cmd_stream to forward progress bars to terminal in real-time
        r = await asyncio.wait_for(run_cmd_stream(command, cwd=task_dir, env=env), timeout=timeout_s)

        # Failover Chain (Phase 7)
        if not r.get('ok') and _is_busy(r) and FALLBACK_CHAIN.get(capability):
            fallback_cap_name = FALLBACK_CHAIN.get(capability)
            fallback_cap = arsenal.get("capabilities", {}).get(fallback_cap_name)
            if fallback_cap:
                log_event(tool="execute_legion", task_id=task_id,
                          message=f"Busy. Falling back {capability} -> {fallback_cap_name}")
                fallback_used = fallback_cap_name
                f_cap_args = " ".join(fallback_cap.get("args", []))
                f_command = f"{fallback_cap['exec']} {task_id} {_time.time()} {f_cap_args} {quoted_args}"
                fb_timeout = fallback_cap.get("timeout", 120)
                r = await asyncio.wait_for(run_cmd_stream(f_command, cwd=task_dir, env=env), timeout=fb_timeout)
    except asyncio.TimeoutError:
        elapsed = _time.monotonic() - t0
        log_event(tool="execute_legion", task_id=task_id, status="timeout", duration_s=elapsed,
                  message=f"Timed out after {timeout_s}s")
        return json.dumps({"ok": False, "message": f"Legion timed out after {timeout_s}s"}, indent=2)

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

    log_event(tool="execute_legion", task_id=task_id, status="ok" if ok else "error",
              duration_s=elapsed, usage=usage)

    result = {
        "ok": ok,
        "task_id": task_id,
        "capability": capability,
        "fallback_used": fallback_used,
        "elapsed_s": round(elapsed, 2),
        "progress": progress,
        "usage": usage,
    }
    if ok:
        result["output"] = r.get("stdout", "")
    else:
        result["error"] = r.get("message", r.get("stderr", ""))

    # Auto summary (Phase 19)
    status_icon = "OK" if ok else "FAIL"
    fb = f" (fallback: {fallback_used})" if fallback_used else ""
    cost = ""
    if usage and isinstance(usage, dict):
        if usage.get("cost_usd"):
            cost = f" ${usage['cost_usd']:.4f}"
        elif usage.get("total_tokens"):
            cost = f" {usage['total_tokens']}tok"
    model = usage.get("model", "") if usage and isinstance(usage, dict) else ""
    result["summary"] = f"[{status_icon}] {task_id} | {capability}{fb} | {model} | {round(elapsed, 1)}s{cost}"

    result_json = json.dumps(result, indent=2)

    # Cache the result if ok
    if result.get('ok') and not no_cache:
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            cache_file.write_text(json.dumps({"timestamp": _time.time(), "result": result_json}))
        except Exception:
            pass

    return result_json


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
    log_event(tool="execute_campaign", task_id=campaign_id, message=f"{len(tasks)} tasks")

    async def run_task(t):
        return await execute_legion(
            task_id=f"{campaign_id}_{t['id']}",
            capability=t['capability'],
            args=t['args'],
            input_files=t.get('input_files', [])
        )

    # Campaign Error Isolation (Phase 8)
    results = await asyncio.gather(*(run_task(t) for t in tasks), return_exceptions=True)

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
    log_event(tool="execute_campaign", task_id=campaign_id, status="ok", duration_s=elapsed,
              message=f"Completed {len(tasks)} tasks",
              usage=total_usage if has_usage else None)

    task_results = {}
    for t, result in zip(tasks, results):
        tid = f"{campaign_id}_{t['id']}"
        if isinstance(result, Exception):
            task_results[t['id']] = json.dumps({"ok": False, "error": str(result), "task_id": tid}, indent=2)
        else:
            task_results[t['id']] = result

    report = {
        "campaign_id": campaign_id,
        "total_usage": total_usage if has_usage else None,
        "results": task_results
    }
    # Campaign summary (Phase 19)
    ok_count = sum(1 for r in results if not isinstance(r, Exception) and '"ok": true' in str(r).lower())
    tok = total_usage.get("total_tokens", 0) if has_usage else 0
    report["summary"] = f"[CAMPAIGN] {campaign_id} | {ok_count}/{len(tasks)} ok | {round(elapsed, 1)}s | {tok}tok"

    return json.dumps(report, indent=2)


@mcp.tool()
async def rome_dispatch(task_id: str, capability: str, prompt: str, input_files: list[str] | None = None) -> str:
    """Quick dispatch: writes prompt to file, then executes legion. Keeps approval dialog clean."""
    task_dir = ROME_ROOT / "legions" / task_id
    task_dir.mkdir(parents=True, exist_ok=True)
    (task_dir / "task.md").write_text(prompt)
    return await execute_legion(
        task_id=task_id,
        capability=capability,
        args=["Read and execute the task in task.md in your current working directory. Output results with [ROME_STATUS: SUCCESS] or [ROME_STATUS: FAILED]."],
        input_files=input_files,
    )

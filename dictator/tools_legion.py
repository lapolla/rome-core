"""Legion tools: execute_legion, execute_campaign, rome_dispatch."""

from collections.abc import Callable
import asyncio
import hashlib
import json
import os
import re
import shlex
import shutil
import sys
import threading
import time as _time
from pathlib import Path

from dictator.core import mcp, run_cmd, run_cmd_stream, ROME_ROOT, ARSENAL_PATH
from dictator.rome_log import log_event

FALLBACK_CHAIN = {"GEMINI": "CODEX", "CODEX": "OPENCODE"}
BUSY_PATTERNS = ["service temporarily unavailable", "overloaded", "rate_limit",
                 "rate limit", "quota", "503", "429", "capacity"]

CACHE_DIR = ROME_ROOT / "legions" / ".cache"
CACHE_TTL = 3600  # 1 hour
MAX_OUTPUT_CHARS = 2000


class OrchestratorUI:
    def __init__(self, task_ids):
        self.task_ids = task_ids
        self.stats = {
            tid: {"percent": 0, "msg": "Standing by", "elapsed": 0.0, "status": "PENDING"}
            for tid in task_ids
        }
        self.lock = threading.Lock()
        for _ in task_ids:
            sys.stderr.write("\n")
        sys.stderr.flush()

    def update(self, task_id, line):
        m = re.search(r"(\d+)%\s+.\s+\[([\d.]+)s\]\s+(.*)", line)
        if m:
            with self.lock:
                self.stats[task_id].update({
                    "percent": int(m.group(1)),
                    "elapsed": float(m.group(2)),
                    "msg": m.group(3).strip(),
                })
        elif "MISSION COMPLETE" in line.upper() or "SUCCESS" in line.upper():
            with self.lock:
                self.stats[task_id]["status"] = "SUCCESS"
                self.stats[task_id]["percent"] = 100
        elif "FAILED" in line.upper() or "ERR:" in line.upper():
            with self.lock:
                self.stats[task_id]["status"] = "FAILED"

    def redraw(self):
        with self.lock:
            sys.stderr.write(f"\033[{len(self.task_ids)}A")
            for tid in self.task_ids:
                s = self.stats[tid]
                filled = int(25 * s["percent"] / 100)
                if s["status"] == "SUCCESS":
                    color = "\033[92m"
                elif s["status"] == "FAILED":
                    color = "\033[91m"
                else:
                    color = "\033[0m"
                bar = "█" * filled + "░" * (25 - filled)
                status_tag = f"[{s['status']:7}]" if s["status"] != "PENDING" else f"{s['percent']:3}%"
                # Show only last 12 chars of TID for cleaner dashboard
                display_id = tid.split("_")[-1] if "_" in tid else tid
                line = (
                    f"\033[K[ROME:{display_id:12}] {color}{bar} {status_tag}"
                    f" [{s['elapsed']:5.1f}s]\033[0m >> {s['msg'][:30]}"
                )
                sys.stderr.write(line + "\n")
            sys.stderr.flush()

    def finalize(self, summary):
        sys.stderr.write(f"\n\033[1;36m=== CAESAR'S CONSOLIDATED INTELLIGENCE ===\033[0m\n")
        sys.stderr.write(f"{summary}\n\n")
        sys.stderr.flush()


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
    result = await _execute_legion_impl(task_id, capability, args, input_files, no_cache, prompt_file)
    payload = json.dumps(result, indent=2)
    est_tokens = len(payload) // 4
    log_event(tool='token_guard', message='mcp_outbound', task_id=task_id, usage={'estimated_output_tokens': est_tokens})
    return payload


async def _execute_legion_impl(
    task_id: str,
    capability: str,
    args: list[str],
    input_files: list[str] | None = None,
    no_cache: bool = False,
    prompt_file: str = "",
    on_progress: Callable | None = None,
) -> dict:
    """Core legion logic. Returns a result dict (not JSON string)."""
    t0 = _time.monotonic()
    capability = capability.upper()

    if input_files is None:
        input_files = []

    if not ARSENAL_PATH.exists():
        return {"ok": False, "message": "Arsenal file not found"}

    arsenal = json.loads(ARSENAL_PATH.read_text())
    cap = arsenal.get("capabilities", {}).get(capability)
    if not cap:
        return {"ok": False, "message": f'Capability "{capability}" not found.'}

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
            (task_dir / "task.md").write_text(file_content)
            args = ["Read and execute the task in task.md in your current working directory. Output results with [ROME_STATUS: SUCCESS] or [ROME_STATUS: FAILED]."]

    # Prompt Patches (Phase 10)
    patches_path = Path(__file__).parent / "legion_patches.json"
    if patches_path.exists():
        try:
            patches = json.loads(patches_path.read_text()).get(capability, [])
            if patches and args:
                patch_block = "\n".join(f"- {p}" for p in patches)
                args = list(args)
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
                return json.loads(cached["result"])
        except Exception:
            pass

    log_event(tool="execute_legion", task_id=task_id, message=f"cap={capability} timeout={timeout_s}s")

    env = {**os.environ, "ROME_TASK_DIR": str(task_dir)}
    fallback_used = None
    try:
        r = await asyncio.wait_for(run_cmd_stream(command, cwd=task_dir, env=env, on_stderr=on_progress), timeout=timeout_s)

        # Failover Chain (Phase 7) — walks GEMINI→CODEX→OPENCODE
        current_cap = capability
        while not r.get('ok') and _is_busy(r) and FALLBACK_CHAIN.get(current_cap):
            next_cap_name = FALLBACK_CHAIN[current_cap]
            next_cap = arsenal.get("capabilities", {}).get(next_cap_name)
            if not next_cap:
                break
            log_event(tool="execute_legion", task_id=task_id,
                      message=f"Busy. Falling back {current_cap} -> {next_cap_name}")
            fallback_used = next_cap_name
            f_cap_args = " ".join(next_cap.get("args", []))
            f_command = f"{next_cap['exec']} {task_id} {_time.time()} {f_cap_args} {quoted_args}"
            fb_timeout = next_cap.get("timeout", 120)
            r = await asyncio.wait_for(run_cmd_stream(f_command, cwd=task_dir, env=env, on_stderr=on_progress), timeout=fb_timeout)
            current_cap = next_cap_name
    except asyncio.TimeoutError:
        elapsed = _time.monotonic() - t0
        log_event(tool="execute_legion", task_id=task_id, status="timeout", duration_s=elapsed,
                  message=f"Timed out after {timeout_s}s")
        return {"ok": False, "message": f"Legion timed out after {timeout_s}s"}

    # CODEX Sandbox Sync (Phase 21)
    if (capability == "CODEX" or fallback_used == "CODEX") and r.get("ok"):
        tmp_dir = Path("/tmp") / f"rome_{task_id}"
        if tmp_dir.exists():
            for f in tmp_dir.rglob("*"):
                if f.is_file():
                    target = task_dir / f.relative_to(tmp_dir)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(str(f), str(target))
        for f in input_files:
            f_path = Path(f)
            src = f_path.resolve() if f_path.is_absolute() else (ROME_ROOT / f_path).resolve()
            dest = task_dir / (f_path.name if f_path.is_absolute() else f_path)
            if dest.exists() and dest.is_file():
                src.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(str(dest), str(src))

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
            # Trim progress to reduce MCP response bloat
            if len(progress) > 6:
                progress = progress[:3] + [f'... [{len(progress) - 6} lines trimmed] ...'] + progress[-3:]
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

    if result.get('output') and len(result['output']) > MAX_OUTPUT_CHARS:
        original_len = len(result['output'])
        report_path = task_dir / f'report_{task_id}.txt'
        if not report_path.exists():
            report_path.write_text(result['output'])
        result['output'] = result['output'][:200] + f'\n...[TRUNCATED — full output: {report_path}]'
        result['truncated'] = True
        result['report_path'] = str(report_path)
        log_event(tool='token_guard', message='output truncated', task_id=task_id, truncated_chars=original_len)

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

    # Cache the result if ok
    if result.get('ok') and not no_cache:
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            cache_file.write_text(json.dumps({"timestamp": _time.time(), "result": json.dumps(result, indent=2)}))
        except Exception:
            pass

    return result


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

    # --- Centurion Dashboard V2: Real-time Orchestrator UI ---
    task_ids = [f"{campaign_id}_{t['id']}" for t in tasks]
    ui = OrchestratorUI(task_ids)

    async def run_task(t):
        tid = f"{campaign_id}_{t['id']}"

        def on_progress(line):
            ui.update(tid, line)
            ui.redraw()

        return await _execute_legion_impl(
            task_id=tid,
            capability=t['capability'],
            args=t['args'],
            input_files=t.get('input_files', []),
            on_progress=on_progress
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
    ok_count = 0
    artifact_paths = []
    for t, result in zip(tasks, results):
        tid = f"{campaign_id}_{t['id']}"
        if isinstance(result, Exception):
            task_results[t['id']] = json.dumps({"ok": False, "error": str(result), "task_id": tid}, indent=2)
        else:
            task_results[t['id']] = json.dumps(result, indent=2) if isinstance(result, dict) else result
            try:
                r = result if isinstance(result, dict) else json.loads(result)
                if r.get("ok"):
                    ok_count += 1
                # Collect artifact paths from manifest
                manifest_path = ROME_ROOT / "legions" / tid / "manifest.json"
                if manifest_path.exists():
                    m = json.loads(manifest_path.read_text())
                    for a in m.get("artifacts", []):
                        artifact_paths.append(a.get("path", ""))
            except Exception:
                pass

    # Finalize UI
    tok = total_usage.get("total_tokens", 0) if has_usage else 0
    cost = total_usage.get("cost_usd", 0.0) if has_usage else 0.0
    cost_str = f" ${cost:.4f}" if cost else ""
    summary = f"Campaign: {campaign_id} | {ok_count}/{len(tasks)} succeeded | {round(elapsed, 1)}s | {tok}tok{cost_str}"
    if artifact_paths:
        summary += f"\nArtifacts: {', '.join(artifact_paths[:5])}"
    
    ui.finalize(summary)

    report = {
        "campaign_id": campaign_id,
        "ok": True,
        "total_usage": total_usage if has_usage else None,
        "results": task_results,
        "summary": f"{ok_count}/{len(tasks)} ok | {round(elapsed, 1)}s | {tok}tok{cost_str}",
    }

    payload = json.dumps(report, indent=2)
    est_tokens = len(payload) // 4
    log_event(tool='token_guard', message='mcp_outbound', task_id=campaign_id, usage={'estimated_output_tokens': est_tokens})
    return payload


@mcp.tool()
async def rome_dispatch(task_id: str, capability: str, prompt: str, input_files: list[str] | None = None, no_cache: bool = False) -> str:
    """Quick dispatch: writes prompt to file, then executes legion. Keeps approval dialog clean."""
    task_dir = ROME_ROOT / "legions" / task_id
    task_dir.mkdir(parents=True, exist_ok=True)
    (task_dir / "task.md").write_text(prompt)
    result = await _execute_legion_impl(
        task_id=task_id,
        capability=capability,
        args=["Read and execute the task in task.md in your current working directory. Output results with [ROME_STATUS: SUCCESS] or [ROME_STATUS: FAILED]."],
        input_files=input_files,
        no_cache=no_cache,
    )
    payload = json.dumps(result, indent=2)
    est_tokens = len(payload) // 4
    log_event(tool='token_guard', message='mcp_outbound', task_id=task_id, usage={'estimated_output_tokens': est_tokens})
    return payload


@mcp.tool()
async def clear_cache() -> str:
    """Clear the legion result cache."""
    count = 0
    if CACHE_DIR.exists():
        for f in CACHE_DIR.glob('*.json'):
            f.unlink()
            count += 1
    log_event(tool='clear_cache', message=f'Cleared {count} cached entries')
    return f'Cleared {count} cached entries from {CACHE_DIR}'


@mcp.tool()
async def recommend_capability(task_description: str) -> str:
    """Recommend the best Legion capability based on task heuristics."""
    import re
    desc = task_description.lower()
    word_count = len(desc.split())

    kw_gemini = ["review", "analyze", "security", "architect", "complex", "audit", "refactor", "design"]
    kw_centurion = ["multi-step", "complex", "review and fix", "analyze and edit", "refactor across"]
    kw_codex = ["fix", "implement", "update", "write", "add", "small", "patch", "rename"]
    kw_shell = ["grep", "build", "test", "find", "run", "execute", "shell", "bash", "compile", "move", "copy", "delete"]

    files_match = re.search(r'(\d+)\s+files?', desc)
    lines_match = re.search(r'(\d+)\s+lines?', desc)
    file_count = int(files_match.group(1)) if files_match else 0
    line_count = int(lines_match.group(1)) if lines_match else 0

    sg = sum(1 for k in kw_gemini if k in desc)
    scen = sum(1 for k in kw_centurion if k in desc)
    sc = sum(1 for k in kw_codex if k in desc)
    ss = sum(1 for k in kw_shell if k in desc)

    if file_count > 10 or line_count > 1000:
        sg += 3

    if ss > sg and ss > scen and ss > sc:
        rec, reason = "SAFE_SHELL", "Task dominated by execution/search/build operations."
    elif sg >= scen and sg >= sc and word_count <= 50:
        rec, reason = "GEMINI", "High reasoning or large context requirements detected."
    elif scen >= sc or word_count > 50:
        rec, reason = "CENTURION", "Multi-step complex task requiring orchestrator oversight."
    else:
        rec, reason = "CODEX", "Focused implementation or small fix with moderate context."

    return json.dumps({
        "recommendation": rec,
        "reasoning": reason,
        "scores": {"gemini": sg, "centurion": scen, "codex": sc, "shell": ss},
    }, indent=2)


@mcp.tool()
async def launch_centurion(campaign_id: str, tasks: list[dict]) -> str:
    """Launch a campaign with the Centurion CLI dashboard (fire-and-forget, renders in terminal)."""
    import subprocess
    import tempfile

    campaign = {"campaign_id": campaign_id, "tasks": tasks}
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", prefix=f"centurion_{campaign_id}_",
                                       dir=str(ROME_ROOT / "legions"), delete=False)
    json.dump(campaign, tmp)
    tmp.close()

    centurion_path = str(ROME_ROOT / "legions" / "centurion.py")
    # Open the user's terminal directly so dashboard renders there, not in MCP pipes
    tty = open("/dev/tty", "w")
    subprocess.Popen(
        ["python3", centurion_path, tmp.name],
        stdout=tty, stderr=tty, stdin=subprocess.DEVNULL,
        start_new_session=True,
    )

    return f"Centurion launched: {campaign_id} with {len(tasks)} tasks. Watch your terminal."

#!/usr/bin/env python3
import json
import os
import re
import sys
import time
import asyncio
import threading
import shutil
from datetime import datetime

# --- CONFIGURATION & PATHS ---
# Centurion V2: Standalone parallel orchestrator for ROME.
ROME_ROOT = os.environ.get("ROME_ROOT", "/home/paul-kane/projects/rome-core")
ARSENAL_PATH = os.path.join(ROME_ROOT, "arsenal", "core_arsenal.json")

def log_event(tool, message, task_id=None, **kwargs):
    """Structured logger following ROME keyword-only requirements."""
    try:
        sys.path.insert(0, ROME_ROOT)
        from dictator.rome_log import log_event as _log_event
        _log_event(tool=tool, message=message, task_id=task_id, **kwargs)
    except Exception:
        pass

# --- DASHBOARD UI ---
class OrchestratorUI:
    def __init__(self, task_ids):
        self.task_ids = task_ids
        # Pad all task labels to the same width
        display_ids = [tid.split("_")[-1] if "_" in tid else tid for tid in task_ids]
        self.max_id_len = max(len(d) for d in display_ids) if display_ids else 12
        self.stats = {
            tid: {"percent": 0, "msg": "Standing by", "elapsed": 0.0, "status": "PENDING"}
            for tid in task_ids
        }
        self.lock = threading.Lock()
        self.is_tty = sys.stderr.isatty()
        self._last_simple_print = 0
        if self.is_tty:
            for _ in task_ids:
                sys.stderr.write("\n")
            sys.stderr.flush()

    def update(self, task_id, line):
        # Handle structured progress: "75% x [12.3s] Thinking..."
        m = re.search(r"(\d+)%\s+.\s+\[([\d.]+)s\]\s+(.*)", line)
        if m:
            with self.lock:
                self.stats[task_id].update({
                    "percent": int(m.group(1)),
                    "elapsed": float(m.group(2)),
                    "msg": m.group(3).strip(),
                })
        elif "MISSION COMPLETE" in line.upper() or "SUCCESS" in line.upper() or line.startswith("OK:"):
            with self.lock:
                self.stats[task_id]["status"] = "SUCCESS"
                self.stats[task_id]["percent"] = 100
        elif "FAILED" in line.upper() or "ERR:" in line.upper():
            with self.lock:
                self.stats[task_id]["status"] = "FAILED"

    def redraw(self):
        with self.lock:
            if not self.is_tty:
                now = time.time()
                if now - self._last_simple_print < 2.0:
                    return
                self._last_simple_print = now
                for tid in self.task_ids:
                    s = self.stats[tid]
                    reported = s["percent"]
                    time_pct = min(90, int(s["elapsed"] / 60.0 * 90)) if s["status"] == "PENDING" else reported
                    ep = max(reported, time_pct)
                    if s["status"] == "SUCCESS": ep = 100
                    display_id = tid.split("_")[-1] if "_" in tid else tid
                    tag = f"[{s['status']:7}]" if s["status"] != "PENDING" else f"{ep:3}%"
                    print(f"[ROME:{display_id:{self.max_id_len}}] {tag} [{s['elapsed']:5.1f}s] {s['msg'][:40]}", flush=True)
                return
            # TTY mode: overwrite lines in place
            sys.stderr.write(f"\033[{len(self.task_ids)}A")
            for tid in self.task_ids:
                s = self.stats[tid]
                # Time-based minimum: ramp to 90% over 60s when reported % is low
                reported = s["percent"]
                time_pct = min(90, int(s["elapsed"] / 60.0 * 90)) if s["status"] == "PENDING" else reported
                effective_pct = max(reported, time_pct)
                if s["status"] == "SUCCESS":
                    effective_pct = 100
                filled = int(25 * effective_pct / 100)
                if s["status"] == "SUCCESS":
                    color = "\033[92m"
                elif s["status"] == "FAILED":
                    color = "\033[91m"
                else:
                    color = "\033[0m"
                bar = "\u2588" * filled + "\u2591" * (25 - filled)
                status_tag = f"[{s['status']:7}]" if s["status"] != "PENDING" else f"{effective_pct:3}%"
                display_id = tid.split("_")[-1] if "_" in tid else tid
                line = (
                    f"\033[K[ROME:{display_id:{self.max_id_len}}] {color}{bar} {status_tag}"
                    f" [{s['elapsed']:5.1f}s]\033[0m >> {s['msg'][:30]}"
                )
                sys.stderr.write(line + "\n")
            sys.stderr.flush()

    def finalize(self, summary):
        sys.stderr.write(f"\n\033[1;36m=== CAESAR'S CONSOLIDATED INTELLIGENCE ===\033[0m\n")
        sys.stderr.write(f"{summary}\n\n")
        sys.stderr.flush()

# --- PARALLEL EXECUTION ENGINE ---
async def run_task(task, arsenal, ui, global_start, results):
    """Executes a single legion_wrapper task as an async subprocess."""
    tid = task["id"]
    capability = task["capability"]
    args = task.get("args", [])
    
    cap_data = arsenal.get("capabilities", {}).get(capability.upper())
    if not cap_data:
        ui.update(tid, f"ERR: Unknown capability: {capability}")
        results[tid] = {"status": "FAILED", "error": f"Unknown capability: {capability}"}
        return

    # Prepare command for legion_wrapper.py
    exec_path = cap_data.get("exec", os.path.join(ROME_ROOT, "legions", "legion_wrapper.py"))
    wrapper_args = [tid, str(global_start)] + cap_data.get("args", []) + args
    
    # Task-specific directory setup
    task_dir = os.path.join(ROME_ROOT, "legions", tid)
    if os.path.exists(task_dir):
        shutil.rmtree(task_dir)
    os.makedirs(task_dir, exist_ok=True)
    
    env = {**os.environ, "PYTHONUNBUFFERED": "1", "ROME_TASK_DIR": task_dir}
    
    process = await asyncio.create_subprocess_exec(
        exec_path, *wrapper_args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=task_dir,
        env=env
    )

    async def drain_pipe(pipe):
        """Consume pipe to avoid deadlock."""
        while True:
            chunk = await pipe.read(1024)
            if not chunk:
                break

    async def poll_progress(task_dir, tid):
        """Poll progress.log for structured updates."""
        log_path = os.path.join(task_dir, "progress.log")
        # Wait for log file to appear
        while not os.path.exists(log_path):
            if process.returncode is not None:
                return
            await asyncio.sleep(0.1)
        
        with open(log_path, "r") as f:
            last_pos = 0
            while True:
                f.seek(last_pos)
                lines = f.readlines()
                last_pos = f.tell()
                for line in lines:
                    ui.update(tid, line.strip())
                
                if process.returncode is not None:
                    # One final sweep after process finishes
                    remaining = f.readlines()
                    for line in remaining:
                        ui.update(tid, line.strip())
                    break
                await asyncio.sleep(0.1)

    # Consume both pipes and poll progress concurrently
    await asyncio.gather(
        drain_pipe(process.stdout),
        drain_pipe(process.stderr),
        poll_progress(task_dir, tid),
        process.wait()
    )

    # Read the ROME v2 manifest.json to extract usage and status
    manifest_path = os.path.join(task_dir, "manifest.json")
    manifest = {}
    if os.path.exists(manifest_path):
        try:
            with open(manifest_path) as f:
                manifest = json.load(f)
        except Exception:
            pass

    status = manifest.get("status", "SUCCESS" if process.returncode == 0 else "FAILED")
    results[tid] = {
        "status": status,
        "manifest": manifest,
        "exit_code": process.returncode,
        "sandbox": task_dir
    }

async def main_async(campaign):
    """Main parallel loop using asyncio for orchestration."""
    tasks = campaign.get("tasks", [])
    if not tasks:
        print("Empty campaign.")
        sys.exit(0)

    # Brief pause so Claude Code finishes rendering before we draw on /dev/tty
    await asyncio.sleep(0.5)

    # Load arsenal using standard protocol: arsenal.get('capabilities', {}).items()
    with open(ARSENAL_PATH) as f:
        arsenal = json.load(f)

    task_ids = [t["id"] for t in tasks]
    ui = OrchestratorUI(task_ids)
    global_start = time.time()
    results = {}

    # Background UI refresh task
    async def ui_loop():
        while any(tid not in results for tid in task_ids):
            ui.redraw()
            await asyncio.sleep(0.2)
        ui.redraw()

    # Launch all tasks in parallel
    task_coros = [run_task(t, arsenal, ui, global_start, results) for t in tasks]
    
    await asyncio.gather(ui_loop(), *task_coros)

    elapsed = time.time() - global_start
    
    # Aggregate summary stats
    success_count = sum(1 for r in results.values() if r["status"] == "SUCCESS")
    fail_count = len(tasks) - success_count
    
    total_in = 0
    total_out = 0
    for r in results.values():
        usage = r.get("manifest", {}).get("usage")
        if usage:
            total_in += usage.get("input_tokens", 0)
            total_out += usage.get("output_tokens", 0)

    summary = (
        f"Campaign: {campaign.get('campaign_id', 'N/A')}\n"
        f"Status:   {'SUCCESS' if fail_count == 0 else 'PARTIAL FAILURE'}\n"
        f"Tasks:    {success_count} succeeded, {fail_count} failed\n"
        f"Elapsed:  {elapsed:.2f}s\n"
        f"Usage:    {total_in} in / {total_out} out tokens"
    )
    ui.finalize(summary)
    
    report = {
        "campaign_id": campaign.get("campaign_id"),
        "success": success_count,
        "failed": fail_count,
        "elapsed_s": round(elapsed, 2),
        "usage": {"input_tokens": total_in, "output_tokens": total_out},
        "tasks": {tid: {"status": r["status"], "exit_code": r["exit_code"]} for tid, r in results.items()}
    }
    
    # Write report to file instead of dumping JSON to terminal
    campaign_id = campaign.get("campaign_id", "unknown")
    report_path = os.path.join(ROME_ROOT, "legions", f"{campaign_id}_report.json")
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)

    print(f"Report: {report_path}")
    
    # Final exit code based on complete success
    if fail_count > 0:
        sys.exit(1)

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 centurion.py <campaign.json | inline_json>")
        sys.exit(1)

    # Unified input parser: file or inline JSON
    arg = sys.argv[1]
    try:
        if arg.startswith("{"):
            campaign = json.loads(arg)
        else:
            with open(arg) as f:
                campaign = json.load(f)
    except Exception as e:
        print(f"Error parsing campaign: {e}")
        sys.exit(1)

    asyncio.run(main_async(campaign))

if __name__ == "__main__":
    main()

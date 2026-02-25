#!/usr/bin/env python3
"""
ROME Centurion — Unified DAG-aware parallel orchestrator.

Usage:
    centurion.py <campaign.json>
    centurion.py -              # read campaign from stdin

Campaign JSON format:
{
  "tasks": {
    "TASK_ID": {
      "capability": "GEMINI",
      "args": ["prompt or command"],
      "depends_on": [],
      "input_files": []
    }
  }
}
"""

import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from queue import Empty, Queue


class OrchestratorUI:
    def __init__(self, names):
        self.names = names
        self.stats = {
            n: {"percent": 0, "msg": "Standing by", "elapsed": 0.0, "status": "PENDING"}
            for n in names
        }
        self.lock = threading.Lock()
        for _ in names:
            sys.stderr.write("\n")
        sys.stderr.flush()

    def update(self, name, line):
        m = re.search(r"(\d+)%\s+.\s+\[([\d.]+)s\]\s+(.*)", line)
        if m:
            with self.lock:
                self.stats[name].update({
                    "percent": int(m.group(1)),
                    "elapsed": float(m.group(2)),
                    "msg": m.group(3).strip(),
                })
            self._redraw()

    def set_final(self, name, status):
        with self.lock:
            self.stats[name]["status"] = status
            self.stats[name]["percent"] = 100 if status != "BLOCKED" else 0
        self._redraw()

    def _redraw(self):
        with self.lock:
            sys.stderr.write(f"\033[{len(self.names)}A")
            for name in self.names:
                s = self.stats[name]
                filled = int(25 * s["percent"] / 100)
                if s["status"] == "SUCCESS":
                    color = "\033[92m"
                elif s["status"] == "FAILED":
                    color = "\033[91m"
                elif s["status"] == "BLOCKED":
                    color = "\033[93m"
                else:
                    color = "\033[0m"
                bar = "█" * filled + "░" * (25 - filled)
                if s["status"] in ("PENDING",):
                    status_tag = f"{s['percent']:3}%"
                else:
                    status_tag = f"[{s['status']}]"
                line = (
                    f"\033[K[ROME:{name:15}] {color}{bar} {status_tag}"
                    f" [{s['elapsed']:5.1f}s]\033[0m >> {s['msg'][:30]}"
                )
                sys.stderr.write(line + "\n")
            sys.stderr.flush()


def run_legion(tid, capability, args, input_files, ui_queue, arsenal, global_start, results):
    task_dir = os.environ.get("ROME_ROOT", os.path.expanduser("~/projects/rome-core"))
    sandbox = os.path.join(task_dir, "legions", tid)
    if os.path.exists(sandbox):
        shutil.rmtree(sandbox)
    os.makedirs(sandbox)

    cap_data = arsenal["capabilities"].get(capability.upper())
    if not cap_data:
        results[tid] = {"status": "FAILED", "error": f"Unknown capability: {capability}"}
        ui_queue.put(("final", tid, "FAILED"))
        return

    wrapper = os.path.join(task_dir, "legions", "legion_wrapper.py")
    full_cmd = [wrapper, tid, str(global_start)] + cap_data.get("args", []) + args

    # Copy input files
    for f in (input_files or []):
        src = os.path.abspath(f)
        if os.path.exists(src):
            dest = os.path.join(sandbox, os.path.basename(f))
            shutil.copy2(src, dest)

    env = {**os.environ, "PYTHONUNBUFFERED": "1", "ROME_TASK_DIR": sandbox}
    process = subprocess.Popen(
        full_cmd, cwd=sandbox,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, bufsize=1, env=env,
    )

    for line in process.stderr:
        ui_queue.put(("update", tid, line))

    process.wait()

    # Load manifest
    manifest_path = os.path.join(sandbox, "manifest.json")
    manifest = {}
    if os.path.exists(manifest_path):
        try:
            with open(manifest_path) as f:
                manifest = json.load(f)
        except Exception:
            pass

    status = manifest.get("status", "SUCCESS" if process.returncode == 0 else "FAILED")
    results[tid] = {"status": status, "manifest": manifest, "sandbox": sandbox}
    ui_queue.put(("final", tid, status))


def run_campaign(campaign):
    tasks = campaign.get("tasks", {})
    if not tasks:
        print("No tasks in campaign.", file=sys.stderr)
        return {}

    arsenal_path = os.path.join(
        os.environ.get("ROME_ROOT", os.path.expanduser("~/projects/rome-core")),
        "arsenal", "core_arsenal.json",
    )
    with open(arsenal_path) as f:
        arsenal = json.load(f)

    ui = OrchestratorUI(list(tasks.keys()))
    ui_queue = Queue()
    global_start = time.time()
    results = {}

    running = set()
    completed = set()
    failed = set()

    print(f"--- ROME CENTURION: {len(tasks)} tasks ---", file=sys.stderr)

    while len(completed) + len(failed) < len(tasks):
        # Spawn eligible tasks
        for tid, spec in tasks.items():
            if tid in running or tid in completed or tid in failed:
                continue
            deps = spec.get("depends_on", [])
            if all(d in completed for d in deps):
                running.add(tid)
                threading.Thread(
                    target=run_legion,
                    args=(tid, spec["capability"], spec.get("args", []),
                          spec.get("input_files", []), ui_queue, arsenal,
                          global_start, results),
                    daemon=True,
                ).start()
            elif any(d in failed for d in deps):
                failed.add(tid)
                ui.set_final(tid, "BLOCKED")
                results[tid] = {"status": "BLOCKED", "blocked_by": [d for d in deps if d in failed]}

        # Process events
        try:
            msg_type, tid, data = ui_queue.get(timeout=0.2)
            if msg_type == "update":
                ui.update(tid, data)
            elif msg_type == "final":
                ui.set_final(tid, data)
                running.discard(tid)
                if data == "SUCCESS":
                    completed.add(tid)
                else:
                    failed.add(tid)
        except Empty:
            pass

    elapsed = time.time() - global_start

    # Aggregate usage
    total_usage = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "cost_usd": 0.0}
    has_usage = False
    for res in results.values():
        u = res.get("manifest", {}).get("usage")
        if u:
            has_usage = True
            total_usage["input_tokens"] += u.get("input_tokens", 0)
            total_usage["output_tokens"] += u.get("output_tokens", 0)
            total_usage["total_tokens"] += u.get("total_tokens", 0)
            if u.get("cost_usd") is not None:
                total_usage["cost_usd"] += u["cost_usd"]

    report = {
        "elapsed_s": round(elapsed, 2),
        "total": len(tasks),
        "success": len(completed),
        "failed": len(failed),
        "usage": total_usage if has_usage else None,
        "tasks": {tid: {"status": r["status"]} for tid, r in results.items()},
    }

    print(f"\n\033[1;36m=== CENTURION REPORT: {len(completed)}/{len(tasks)} OK"
          f" in {elapsed:.1f}s ===\033[0m", file=sys.stderr)
    for tid, r in results.items():
        color = "\033[92m" if r["status"] == "SUCCESS" else "\033[91m"
        print(f"  {color}[{r['status']:7}]\033[0m {tid}", file=sys.stderr)

    return report


def main():
    if len(sys.argv) < 2:
        print(__doc__, file=sys.stderr)
        sys.exit(1)

    source = sys.argv[1]
    if source == "-":
        campaign = json.load(sys.stdin)
    else:
        with open(source) as f:
            campaign = json.load(f)

    report = run_campaign(campaign)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()

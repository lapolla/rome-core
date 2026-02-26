#!/usr/bin/env python3
import json
import os
import subprocess
import time
import sys
import re

# Constants
ROME_ROOT = os.environ.get("ROME_ROOT", "/home/paul-kane/projects/rome-core")
ARSENAL_PATH = os.path.join(ROME_ROOT, "arsenal", "core_arsenal.json")
TASK_DIR = os.environ.get("ROME_TASK_DIR", ".")

# Best-effort import of Rome log
try:
    sys.path.insert(0, os.path.join(ROME_ROOT, "dictator"))
    from rome_log import log_event
except Exception:
    def log_event(**_kw): pass

def run_cmd(cmd, task_id="unknown", cwd=None, timeout=300):
    """Wrapper for subprocess.run following coding rules."""
    log_event(tool="run_cmd", message=f"Executing: {' '.join(cmd[:10])}", task_id=task_id)
    try:
        env = {**os.environ, "PYTHONUNBUFFERED": "1"}
        if cwd:
            env["ROME_TASK_DIR"] = cwd
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=cwd, env=env)
        return {"ok": proc.returncode == 0, "stdout": proc.stdout, "stderr": proc.stderr, "exit_code": proc.returncode}
    except Exception as e:
        return {"ok": False, "error": str(e), "exit_code": 1}

class CenturionUI:
    def __init__(self, task_id, global_start):
        self.task_id = task_id
        self.global_start = global_start
        self.hb_chars = ["|", "/", "-", "\\"]
        self.hb_idx = 0
        self.progress_path = os.path.join(TASK_DIR, "progress.log")

    def log(self, percent, msg):
        elapsed = time.time() - self.global_start
        hb = self.hb_chars[self.hb_idx % 4]
        self.hb_idx += 1
        line = f"{percent}% {hb} [{elapsed:.1f}s] {msg}"
        sys.stderr.write(line + "\n")
        sys.stderr.flush()
        try:
            with open(self.progress_path, "a") as f:
                f.write(line + "\n")
        except: pass

def extract_json(text):
    if not text: return None
    stripped = text.strip()
    # Step 1: Unwrap agent JSON envelopes
    # Gemini: {"response": "...", "stats": {...}}
    # Claude: {"result": "...", "usage": {...}}
    try:
        envelope = json.loads(stripped[stripped.find("{"):])
        if "response" in envelope and "stats" in envelope:
            stripped = envelope["response"]  # unwrap Gemini
        elif "result" in envelope and "usage" in envelope:
            stripped = envelope["result"]  # unwrap Claude
    except: pass
    # Step 2: Strip markdown code fences
    stripped = re.sub(r"```json\s*", "", stripped)
    stripped = re.sub(r"```\s*", "", stripped)
    # Step 3: Try direct parse
    try:
        parsed = json.loads(stripped.strip())
        if isinstance(parsed, dict) and "subtasks" in parsed:
            return parsed
    except: pass
    # Step 4: Find first { ... } block with brace matching
    depth = 0
    start = None
    for i, c in enumerate(stripped):
        if c == '{':
            if depth == 0: start = i
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0 and start is not None:
                try:
                    parsed = json.loads(stripped[start:i+1])
                    if isinstance(parsed, dict) and "subtasks" in parsed:
                        return parsed
                except: pass
                start = None
    return None

def main():
    if len(sys.argv) < 5: sys.exit(1)
    task_id, global_start = sys.argv[1], float(sys.argv[2])
    planner_args = sys.argv[3:-1]
    user_prompt = sys.argv[-1]
    
    ui = CenturionUI(task_id, global_start)
    ui.log(5, "Phase 1: Planning...")
    
    plan_prompt = f"""You are a ROME Centurion planner. Decompose this task into sub-tasks.
OUTPUT ONLY valid JSON:
{{"subtasks": [{{"id": "s1", "capability": "CODEX|OPENCODE|SAFE_SHELL", "description": "what", "args": ["full prompt for worker"]}}], "reasoning": "why"}}
TASK: {user_prompt}"""
    
    # Execute planner
    r = run_cmd(planner_args + [plan_prompt], task_id)
    plan = extract_json(r.get("stdout", ""))
    
    if not plan or "subtasks" not in plan:
        ui.log(10, "Plan failed or invalid JSON, falling back to GEMINI...")
        plan = {"subtasks": [{"id": "fallback", "capability": "GEMINI", "description": "Fallback", "args": [user_prompt]}]}

    # Load Arsenal
    try:
        with open(ARSENAL_PATH) as f:
            arsenal = json.load(f)
        caps = arsenal.get("capabilities", {})
    except:
        caps = {}

    subtask_results = []
    total_usage = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "cost_usd": 0.0}
    
    ui.log(20, f"Phase 2: Executing {len(plan['subtasks'])} subtasks...")
    
    legions_dir = os.path.join(ROME_ROOT, "legions")
    for i, sub in enumerate(plan["subtasks"]):
        cap_name = sub.get("capability")
        sub_id = f"{task_id}_{sub.get('id')}"
        ui.log(int(20 + (i/len(plan['subtasks']))*70), f"Running {sub_id} ({cap_name})...")

        if cap_name not in caps:
            subtask_results.append({"id": sub_id, "ok": False, "error": f"Capability {cap_name} not found"})
            continue

        cap = caps[cap_name]
        # Each subtask gets its own directory
        sub_dir = os.path.join(legions_dir, sub_id)
        os.makedirs(sub_dir, exist_ok=True)

        # Command: legion_wrapper.py TASK_ID START_TIME ARGS...
        cmd = [cap["exec"], sub_id, str(time.time())] + cap.get("args", []) + sub.get("args", [])
        timeout = cap.get("timeout", 120)

        sr = run_cmd(cmd, sub_id, cwd=sub_dir, timeout=timeout)

        # Load subtask manifest from its own directory
        sub_manifest = {}
        sub_manifest_path = os.path.join(sub_dir, "manifest.json")
        if os.path.exists(sub_manifest_path):
            try:
                with open(sub_manifest_path) as f:
                    sub_manifest = json.load(f)
                usage = sub_manifest.get("usage")
                if usage:
                    for k in ["input_tokens", "output_tokens", "total_tokens"]:
                        total_usage[k] += usage.get(k, 0)
                    total_usage["cost_usd"] += usage.get("cost_usd") or 0.0
            except: pass

        subtask_results.append({
            "id": sub_id,
            "ok": sr.get("ok", False),
            "exit_code": sr.get("exit_code", 1),
            "manifest": sub_manifest
        })

    ui.log(95, "Phase 3: Synthesizing...")
    report_path = os.path.join(TASK_DIR, f"report_{task_id}.txt")
    try:
        with open(report_path, "w") as f:
            f.write(f"CENTURION TASK REPORT: {task_id}\n")
            f.write(f"Original Task: {user_prompt}\n\n")
            for res in subtask_results:
                status = "OK" if res.get("ok") else "FAIL"
                f.write(f"--- Subtask {res['id']} [{status}] ---\n")
                sub_report = os.path.join(legions_dir, res['id'], f"report_{res['id']}.txt")
                if os.path.exists(sub_report):
                    with open(sub_report) as rf:
                        f.write(rf.read()[:2000] + "\n")
                else:
                    f.write("No report found.\n")
                f.write("\n")
    except: pass

    manifest = {
        "ok": all(r.get("ok") for r in subtask_results),
        "task_id": task_id,
        "elapsed_s": time.time() - global_start,
        "usage": total_usage,
        "subtask_results": subtask_results
    }
    
    try:
        with open(os.path.join(TASK_DIR, "manifest.json"), "w") as f:
            json.dump(manifest, f, indent=2)
    except: pass

    status = "SUCCESS" if manifest["ok"] else "FAILED"
    print(f"[ROME_STATUS: {status}]")
    print(f"{'OK' if manifest['ok'] else 'ERR'}:{task_id}")
    
    log_event(tool="centurion_wrapper", task_id=task_id, status=status.lower(), message="Task completed")

if __name__ == "__main__": main()

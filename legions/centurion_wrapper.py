#!/usr/bin/env python3
import json
import os
import subprocess
import time
import sys
import re
from dashboard import Dashboard

# Constants
ROME_ROOT = os.environ.get("ROME_ROOT", "/home/paul-kane/projects/rome-core")
ARSENAL_PATH = os.path.join(ROME_ROOT, "arsenal", "core_arsenal.json")
TASK_DIR = os.environ.get("ROME_TASK_DIR", ".")

FALLBACK_CHAIN = {
    "GEMINI":     ["GEMINI", "GEMINI", "CODEX"],
    "SAFE_SHELL": ["SAFE_SHELL", "SAFE_SHELL"],
    "CODEX":      ["CODEX", "GEMINI"],
}
MAX_RETRIES = 3

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

def extract_json(text):
    if not text: return None
    stripped = text.strip()
    try:
        envelope = json.loads(stripped[stripped.find("{"):])
        if "response" in envelope and "stats" in envelope:
            stripped = envelope["response"]
        elif "result" in envelope and "usage" in envelope:
            stripped = envelope["result"]
    except: pass
    stripped = re.sub(r"```json\s*", "", stripped)
    stripped = re.sub(r"```\s*", "", stripped)
    try:
        parsed = json.loads(stripped.strip())
        if isinstance(parsed, dict) and "subtasks" in parsed:
            return parsed
    except: pass
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
    if len(sys.argv) < 3:
        print("Usage: centurion_wrapper.py <planner_cli_args> <prompt>", file=sys.stderr)
        sys.exit(1)
    planner_args = sys.argv[1:-1]
    user_prompt = sys.argv[-1]
    task_id = os.environ.get("ROME_TASK_ID", f"centurion_{int(time.time())}")
    global_start = time.time()

    print(f"Phase 1: Planning for {task_id}...", file=sys.stderr)
    
    plan_prompt = f"""You are a ROME Centurion planner. Decompose this task into sub-tasks.
OUTPUT ONLY valid JSON:
{{"subtasks": [{{"id": "s1", "capability": "CODEX|OPENCODE|SAFE_SHELL", "description": "what", "args": ["full prompt for worker"]}}], "reasoning": "why"}}
TASK: {user_prompt}"""
    
    r = run_cmd(planner_args + [plan_prompt], task_id)
    plan = extract_json(r.get("stdout", ""))
    
    if not plan or "subtasks" not in plan:
        print("Plan failed or invalid JSON, falling back to GEMINI...", file=sys.stderr)
        plan = {"subtasks": [{"id": "fallback", "capability": "GEMINI", "description": "Fallback", "args": [user_prompt]}]}

    # Load Arsenal
    try:
        with open(ARSENAL_PATH) as f:
            arsenal = json.load(f)
        caps = arsenal.get("capabilities", {})
    except:
        caps = {}

    subtask_ids = [f"{task_id}_{sub.get('id')}" for sub in plan["subtasks"]]
    dashboard = Dashboard(subtask_ids, task_id)
    
    subtask_results = []
    total_usage = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "cost_usd": 0.0}
    
    legions_dir = os.path.join(ROME_ROOT, "legions")
    for i, sub in enumerate(plan["subtasks"]):
        original_cap = sub.get("capability")
        sub_id = subtask_ids[i]
        
        attempt = 0
        success = False
        last_sr = None
        last_manifest = {}
        
        while attempt < MAX_RETRIES:
            cap_name = original_cap
            if original_cap in FALLBACK_CHAIN:
                chain = FALLBACK_CHAIN[original_cap]
                if attempt < len(chain):
                    cap_name = chain[attempt]
                else:
                    cap_name = chain[-1]
            
            status = "RUNNING" if attempt == 0 else f"RETRY {attempt}/{MAX_RETRIES-1}"
            dashboard.update(sub_id, status, time.time() - global_start, f"Using {cap_name}...")

            if cap_name not in caps:
                last_sr = {"ok": False, "error": f"Capability {cap_name} not found", "exit_code": 1}
                attempt += 1
                continue

            cap = caps[cap_name]
            sub_dir = os.path.join(legions_dir, sub_id)
            os.makedirs(sub_dir, exist_ok=True)

            cmd = [cap["exec"], sub_id, str(time.time())] + cap.get("args", []) + sub.get("args", [])
            timeout = cap.get("timeout", 120)

            sr = run_cmd(cmd, sub_id, cwd=sub_dir, timeout=timeout)
            last_sr = sr

            sub_manifest = {}
            sub_manifest_path = os.path.join(sub_dir, "manifest.json")
            if os.path.exists(sub_manifest_path):
                try:
                    with open(sub_manifest_path) as f:
                        sub_manifest = json.load(f)
                    last_manifest = sub_manifest
                    usage = sub_manifest.get("usage")
                    if usage:
                        for k in ["input_tokens", "output_tokens", "total_tokens"]:
                            total_usage[k] += usage.get(k, 0)
                        total_usage["cost_usd"] += usage.get("cost_usd") or 0.0
                except: pass

            if sr.get("ok"):
                success = True
                dashboard.update(sub_id, "SUCCESS", time.time() - global_start, sub.get("description", "Complete"))
                break
            else:
                attempt += 1
                if attempt < MAX_RETRIES:
                    dashboard.update(sub_id, "RETRYING", time.time() - global_start, f"Attempt {attempt} failed")
                else:
                    dashboard.update(sub_id, "FAILED", time.time() - global_start, "Max retries reached")

        subtask_results.append({
            "id": sub_id,
            "ok": success,
            "exit_code": last_sr.get("exit_code", 1) if last_sr else 1,
            "manifest": last_manifest
        })

    # Prepare results for dashboard.finish
    finish_results = {}
    for res in subtask_results:
        summary = "Success" if res["ok"] else "Failed"
        if res.get("manifest") and res["manifest"].get("reason"):
             summary = res["manifest"]["reason"]
        
        finish_results[res["id"]] = {
            "status": "SUCCESS" if res["ok"] else "FAILED",
            "summary": summary
        }
    
    dashboard.finish(finish_results)

    # Synthesis
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

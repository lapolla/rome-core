#!/usr/bin/env python3
import subprocess, sys, time, threading, os, json, shutil, re
from queue import Queue, Empty

# --- ROME AUGUSTUS: THE IMPERIAL REFINEMENT (V2.3 - MONTY PYTHON VERIFICATION) ---
# Protocol: Verify pure Python architecture.

MAX_TASK_TIME = 45.0 

class AugustusUI:
    def __init__(self, names):
        self.names = names
        self.stats = {n: {"percent": 0, "msg": "Standing by", "elapsed": 0.0, "status": "PENDING"} for n in names}
        for _ in names: sys.stderr.write("\n")
        sys.stderr.flush()

    def update(self, name, line):
        m = re.search(r"(\d+)%\s+.\s+\[([\d.]+)s\]\s+(.*)", line)
        if m:
            self.stats[name].update({"percent": int(m.group(1)), "elapsed": float(m.group(2)), "msg": m.group(3).strip()})
        self._redraw()

    def set_final(self, name, status):
        self.stats[name]["status"] = status
        self.stats[name]["percent"] = 100
        self._redraw()

    def _redraw(self):
        sys.stderr.write(f"\033[{len(self.names)}A")
        for name in self.names:
            s = self.stats[name]
            filled = int(25 * s["percent"] / 100)
            color = "\033[92m" if s["status"] == "SUCCESS" else "\033[91m" if s["status"] == "FAILED" else "\033[0m"
            bar = "█" * filled + "░" * (25 - filled)
            status_tag = f"[{s['status']}]" if s["status"] != "PENDING" else f"{s['percent']:3}%"
            line = f"\033[K[MONTY:{name:15}] {color}{bar} {status_tag} [{s['elapsed']:5.1f}s]\033[0m >> {s['msg'][:30]}"
            sys.stderr.write(line + "\n")
        sys.stderr.flush()

def run_legion(tid, capability, cmd, ui_queue, arsenal, global_start, results):
    sandbox = f"/home/paul-kane/tmp/augustus_slave_{tid}"
    if os.path.exists(sandbox): shutil.rmtree(sandbox)
    os.makedirs(sandbox)
    cap_data = arsenal["capabilities"][capability]
    wrapper = os.path.expanduser("~/projects/rome-core/legions/legion_wrapper.py")
    full_prompt = " ".join(cmd)
    full_cmd = [wrapper, tid, str(global_start)] + cap_data["args"] + [full_prompt]
    process = subprocess.Popen(full_cmd, cwd=sandbox, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1, env={**os.environ, "PYTHONUNBUFFERED": "1"})
    for line in process.stderr: ui_queue.put(("update", tid, line))
    process.wait()
    intel_file = os.path.join(sandbox, f"report_{tid}.txt")
    intel_txt = ""
    if os.path.exists(intel_file):
        with open(intel_file, "r") as f: intel_txt = f.read()
    status = "SUCCESS" if process.returncode == 0 else "FAILED"
    results[tid] = {"status": status, "intel": intel_txt, "elapsed": time.time() - global_start}
    ui_queue.put(("final", tid, status))

def main():
    print("--- ROME SUPREME COMMAND: OPERATION MONTY PYTHON (V2.3) ---", file=sys.stderr)
    with open(os.path.expanduser("~/projects/rome-core/arsenal/core_arsenal.json"), "r") as f: arsenal = json.load(f)

    manifesto_verify = os.path.expanduser("~/projects/rome-core/legions/TASK_ROME_ORCHESTRATION/MANIFESTO_MONTY_VERIFY.md")
    
    tasks = {
        "MONTY_VERIFY": ("SAFE_SHELL", ["gemini mcp list && gemini --help"]),
        "GH_PUSH": ("SAFE_SHELL", ["git add . && git commit -m \"AUGUSTUS: ROME Protocol Restored - Pythonic Dictator Active\" && git push origin master"])
    }

    results, ui_queue, global_start = {}, Queue(), time.time()
    ui = AugustusUI(list(tasks.keys()))
    for tid, (cap, cmd) in tasks.items():
        threading.Thread(target=run_legion, args=(tid, cap, cmd, ui_queue, arsenal, global_start, results), daemon=True).start()

    active_tasks = len(tasks)
    while active_tasks > 0:
        try:
            msg_type, tid, data = ui_queue.get(timeout=0.1)
            if msg_type == "update": ui.update(tid, data)
            elif msg_type == "final": ui.set_final(tid, data); active_tasks -= 1
        except Empty: pass

    print("\n\033[1;36m=== MONTY PYTHON: VERIFICATION REPORT ===\033[0m")
    if "MONTY_VERIFY" in results:
        print(results["MONTY_VERIFY"]["intel"])

    print("\033[1;32mThe Pythonic era is established.\033[0m")

if __name__ == "__main__": main()

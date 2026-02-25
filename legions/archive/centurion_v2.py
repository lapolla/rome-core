#!/usr/bin/env python3
import subprocess, sys, time, threading, os, re, json, shutil
from queue import Queue, Empty

# --- ROME CENTURION V2.0: DAG-AWARE ORCHESTRATOR ---

class OrchestratorUI:
    def __init__(self, names):
        self.names = names
        self.stats = {n: {"percent": 0, "msg": "Standing by", "elapsed": 0.0, "status": "PENDING"} for n in names}
        for _ in names: sys.stderr.write("\n")
        sys.stderr.flush()

    def update(self, name, line):
        m = re.search(r"(\d+)%\s+.\s+\[([\d.]+)s\]\s+(.*)", line)
        if m:
            self.stats[name].update({
                "percent": int(m.group(1)),
                "elapsed": float(m.group(2)),
                "msg": m.group(3).strip()
            })
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
            color = "\033[92m" if s["status"] == "SUCCESS" else "\033[91m" if s["status"] == "FAILED" else "\033[93m" if s["status"] == "BLOCKED" else "\033[0m"
            bar = "█" * filled + "░" * (25 - filled)
            status_tag = f"[{s['status']}]" if s["status"] != "PENDING" else f"{s['percent']:3}%"
            line = f"\033[K[ROME:{name:15}] {color}{bar} {status_tag} [{s['elapsed']:5.1f}s]\033[0m >> {s['msg'][:30]}"
            sys.stderr.write(line + "\n")
        sys.stderr.flush()

def run_legion(tid, capability, cmd, ui_queue, arsenal, global_start, results):
    sandbox = f"/tmp/rome_slave_{tid}"
    if os.path.exists(sandbox): shutil.rmtree(sandbox)
    os.makedirs(sandbox)
    
    cap_data = arsenal["capabilities"][capability]
    wrapper = os.path.expanduser("~/projects/rome-core/legions/legion_wrapper.py")
    
    full_cmd = [wrapper, tid, str(global_start)] + cap_data["args"] + cmd
    
    process = subprocess.Popen(full_cmd, cwd=sandbox, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1, env={**os.environ, "PYTHONUNBUFFERED": "1"})
    
    for line in process.stderr:
        ui_queue.put(("update", tid, line))
    
    process.wait()
    
    # ROME V2.0: Load structured manifest
    manifest_path = os.path.join(sandbox, "manifest.json")
    manifest = {}
    if os.path.exists(manifest_path):
        with open(manifest_path, "r") as f:
            manifest = json.load(f)
            
    status = manifest.get("status", "SUCCESS" if process.returncode == 0 else "FAILED")
    results[tid] = {"status": status, "manifest": manifest}
    ui_queue.put(("final", tid, status))

def main():
    print("--- ROME SUPREME COMMAND: CENTURION V2.0 (DAG) ---", file=sys.stderr)
    
    with open(os.path.expanduser("~/projects/rome-core/arsenal/core_arsenal.json"), "r") as f:
        arsenal = json.load(f)

    # V2.0 Campaign Structure: ID -> (CAP, PROMPT, DEPENDS_ON)
    campaign = {
        "ARCH_BLUEPRINT": ("GEMINI", ["Design the V2 Manifest structure for the Suture engine. Code only."], []),
        "DISP_CORE":      ("GEMINI", ["Implement ROME::CommandDispatcher core singleton. Code only."], ["ARCH_BLUEPRINT"]),
        "DISP_QUEUE":     ("GEMINI", ["Implement ROME::CommandQueue thread-safe logic. Code only."], ["DISP_CORE"]),
        "JSON_PROC":      ("GEMINI", ["Implement nlohmann::json adapter for ROME. Code only."], ["ARCH_BLUEPRINT"]),
        "SUTURE_V2":      ("GEMINI", ["Implement the Suture V2 logic using manifest artifacts. Code only."], ["DISP_QUEUE", "JSON_PROC"])
    }

    results = {}
    ui = OrchestratorUI(list(campaign.keys()))
    ui_queue = Queue()
    global_start = time.time()
    
    running = set()
    completed = set()
    failed = set()

    while len(completed) + len(failed) < len(campaign):
        # 1. Spawn eligible tasks
        for tid, (cap, cmd, deps) in campaign.items():
            if tid not in running and tid not in completed and tid not in failed:
                # Check if all dependencies are met
                if all(d in completed for d in deps):
                    running.add(tid)
                    threading.Thread(target=run_legion, args=(tid, cap, cmd, ui_queue, arsenal, global_start, results), daemon=True).start()
                elif any(d in failed for d in deps):
                    failed.add(tid)
                    ui.set_final(tid, "BLOCKED")

        # 2. Process UI updates
        try:
            msg_type, tid, data = ui_queue.get(timeout=0.1)
            if msg_type == "update":
                ui.update(tid, data)
            elif msg_type == "final":
                ui.set_final(tid, data)
                running.remove(tid)
                if data == "SUCCESS": completed.add(tid)
                else: failed.add(tid)
        except Empty:
            pass

    print("\n\033[1;36m=== CAMPAIGN V2.0 CONSOLIDATED MANIFEST ===\033[0m")
    for tid, res in results.items():
        print(f"[{tid:15}] STATUS: {res['status']}")
        if "manifest" in res:
            for art in res["manifest"].get("artifacts", []):
                print(f"  -> ARTIFACT: {art['path']}")

if __name__ == "__main__": main()

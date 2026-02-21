#!/usr/bin/env python3
import subprocess, sys, time, threading, os, re, json, shutil
from queue import Queue, Empty

# --- ROME CENTURION: 12 LABORS OF CAESAR (V11) ---

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
            color = "\033[92m" if s["status"] == "SUCCESS" else "\033[91m" if s["status"] == "FAILED" else "\033[0m"
            bar = "█" * filled + "░" * (25 - filled)
            status_tag = f"[{s['status']}]" if s["status"] != "PENDING" else f"{s['percent']:3}%"
            # Surgical padding for IDs to keep bars aligned
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
    
    # REPORTING UP: No hidden dots this time
    intel_file = os.path.join(sandbox, f"report_{tid}.txt")
    intel_txt = ""
    if os.path.exists(intel_file):
        with open(intel_file, "r") as f:
            intel_txt = f.read()
            
    status = "SUCCESS" if process.returncode == 0 else "FAILED"
    results[tid] = {"status": status, "intel": intel_txt}
    ui_queue.put(("final", tid, status))

def main():
    print("--- ROME SUPREME COMMAND: 12 LABORS OF CAESAR ---", file=sys.stderr)
    
    with open(os.path.expanduser("~/projects/rome-core/arsenal/core_arsenal.json"), "r") as f:
        arsenal = json.load(f)

    # 12 Slaves: Atomic Division of C++, Python, and Logic
    tasks = {
        "LABOR_HDR_DEF":   ("GEMINI", ["C++ Header Guards and Namespaces for CommandDispatcher. Code only."]),
        "LABOR_HDR_STRC":  ("GEMINI", ["C++ 'Command' struct with enum types. Code only."]),
        "LABOR_HDR_CLS":   ("GEMINI", ["C++ 'CommandDispatcher' class private members (deque, mutex). Code only."]),
        "LABOR_IMPL_SNG":  ("GEMINI", ["C++ CommandDispatcher::Get() Singleton implementation. Code only."]),
        "LABOR_IMPL_PSH":  ("GEMINI", ["C++ thread-safe Push() logic for the command queue. Code only."]),
        "LABOR_IMPL_POP":  ("GEMINI", ["C++ thread-safe Pop() logic for the command queue. Code only."]),
        "LABOR_IMPL_FILE": ("GEMINI", ["C++ nlohmann::json file reader for 'skyrim_commands.json'. Code only."]),
        "LABOR_IMPL_PROC": ("GEMINI", ["C++ loop calling Dispatcher::Process() from std::jthread. Code only."]),
        "LABOR_IMPL_EX_R": ("GEMINI", ["C++ Execute('raw') using RE::Console::ExecuteCommand. Code only."]),
        "LABOR_IMPL_EX_K": ("GEMINI", ["C++ Execute('kill') using RE::Actor::KillImmediate. Code only."]),
        "LABOR_PY_ASSN":   ("OPENCODE", ["Write Python script to monitor state and kill hostiles. Code only."]),
        "LABOR_PY_ORCL":   ("CODEX", ["Write Python script to boost speed mult on audio peaks. Code only."])
    }

    results = {}
    ui = OrchestratorUI(list(tasks.keys()))
    ui_queue = Queue()
    global_start = time.time()
    
    for tid, (cap, cmd) in tasks.items():
        threading.Thread(target=run_legion, args=(tid, cap, cmd, ui_queue, arsenal, global_start, results), daemon=True).start()

    active_tasks = len(tasks)
    while active_tasks > 0:
        try:
            msg_type, tid, data = ui_queue.get(timeout=0.1)
            if msg_type == "update": ui.update(tid, data)
            elif msg_type == "final": ui.set_final(tid, data); active_tasks -= 1
        except Empty: pass

    # THE MASTER SUTURE (REPORTING UP)
    print("\n\033[1;36m=== CAESAR'S CONSOLIDATED INTELLIGENCE ===\033[0m")
    consolidated_path = "/home/paul-kane/tmp/caesar_final_code.cpp"
    with open(consolidated_path, "w") as f:
        for tid in sorted(tasks.keys()): # Sorted order for clean code assembly
            if tid in results and results[tid]["status"] == "SUCCESS":
                f.write(f"\n// --- LABORED BY {tid} ---\n")
                f.write(results[tid]["intel"])
                f.write("\n")
    
    print(f"Code assembled from 12 slaves: {consolidated_path}")
    print("\033[1;32mThe World is ready for the Final Suture.\033[0m")

if __name__ == "__main__": main()

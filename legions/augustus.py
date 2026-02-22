#!/usr/bin/env python3
import subprocess, sys, time, threading, os, json, shutil, re
from queue import Queue, Empty

# --- ROME AUGUSTUS: THE IMPERIAL REFINEMENT (V1.6 - FOCUSED EXTRACTION) ---
# Protocol: Optimized prompts to reduce LLM context load for faster and more accurate extraction.

MAX_TASK_TIME = 45.0 

class AugustusUI:
    def __init__(self, names):
        self.names = names
        self.stats = {n: {"percent": 0, "msg": "Standing by", "elapsed": 0.0, "status": "PENDING", "bloated": False} for n in names}
        for _ in names: sys.stderr.write("\n")
        sys.stderr.flush()

    def update(self, name, line):
        m = re.search(r"(\d+)%\s+.\s+\[([\d.]+)s\]\s+(.*)", line)
        if m:
            elapsed = float(m.group(2))
            self.stats[name].update({
                "percent": int(m.group(1)),
                "elapsed": elapsed,
                "msg": m.group(3).strip()
            })
            if elapsed > MAX_TASK_TIME and not self.stats[name]["bloated"]:
                self.stats[name]["bloated"] = True
                self.stats[name]["msg"] = "!!! BLOATED: DIVISION REQUIRED !!!"
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
            color = "\033[93m" if s["bloated"] else "\033[92m" if s["status"] == "SUCCESS" else "\033[91m" if s["status"] == "FAILED" else "\033[0m"
            bar = "█" * filled + "░" * (25 - filled)
            status_tag = f"[{s['status']}]" if s["status"] != "PENDING" else f"{s['percent']:3}%"
            line = f"\033[K[AUGUSTUS:{name:15}] {color}{bar} {status_tag} [{s['elapsed']:5.1f}s]\033[0m >> {s['msg'][:30]}"
            sys.stderr.write(line + "\n")
        sys.stderr.flush()

def run_legion(tid, capability, cmd, ui_queue, arsenal, global_start, results):
    sandbox = f"/home/paul-kane/tmp/augustus_slave_{tid}"
    if os.path.exists(sandbox): shutil.rmtree(sandbox)
    os.makedirs(sandbox)
    
    cap_data = arsenal["capabilities"][capability]
    wrapper = os.path.expanduser("~/projects/rome-core/legions/legion_wrapper.py")
    
    # FIX: JOIN ALL COMMAND PARTS INTO A SINGLE STRING FOR -p
    full_prompt = " ".join(cmd)
    full_cmd = [wrapper, tid, str(global_start)] + cap_data["args"] + [full_prompt]
    
    process = subprocess.Popen(full_cmd, cwd=sandbox, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1, env={**os.environ, "PYTHONUNBUFFERED": "1"})
    
    for line in process.stderr:
        ui_queue.put(("update", tid, line))
    
    process.wait()
    
    intel_file = os.path.join(sandbox, f"report_{tid}.txt")
    intel_txt = ""
    if os.path.exists(intel_file):
        with open(intel_file, "r") as f:
            intel_txt = f.read()
            
    status = "SUCCESS" if process.returncode == 0 else "FAILED"
    results[tid] = {"status": status, "intel": intel_txt, "elapsed": time.time() - global_start}
    ui_queue.put(("final", tid, status))

def main():
    print("--- ROME SUPREME COMMAND: OPERATION AUGUSTUS (V1.6) ---", file=sys.stderr)
    
    with open(os.path.expanduser("~/projects/rome-core/arsenal/core_arsenal.json"), "r") as f:
        arsenal = json.load(f)

    # 16 Slaves: Hyper-Parallel Extraction
    # Prompts now explicitly state to extract *from* the monolith, reducing LLM context load.
    monolith_path = "/home/paul-kane/tmp/caesar_final_code.cpp"
    manifesto_architect_path = os.path.expanduser("~/projects/rome-core/legions/TASK_ROME_ORCHESTRATION/MANIFESTO_ARCHITECT.md")
    manifesto_forge_path = os.path.expanduser("~/projects/rome-core/legions/TASK_ROME_ORCHESTRATION/MANIFESTO_FORGE.md")
    
    tasks = {
        # DISPATCHER HEADERS
        "TASK_DISP_H":     ("GEMINI", [f"From {monolith_path}, extract CommandDispatcher.h Header Guards and Classes, following {manifesto_architect_path}."]),
        # DISPATCHER IMPLEMENTATION (TRIPLE SPLIT)
        "TASK_DISP_SNG":   ("GEMINI", [f"From {monolith_path}, extract CommandDispatcher Singleton and Singleton access logic, following {manifesto_architect_path}."]),
        "TASK_DISP_PUSH":  ("GEMINI", [f"From {monolith_path}, extract CommandDispatcher thread-safe Push() implementation, following {manifesto_architect_path}."]),
        "TASK_DISP_POP":   ("GEMINI", [f"From {monolith_path}, extract CommandDispatcher thread-safe Pop() implementation, following {manifesto_architect_path}."]),
        "TASK_DISP_PROC":  ("GEMINI", [f"From {monolith_path}, extract CommandDispatcher Main Process Loop and thread management, following {manifesto_architect_path}."]),
        # HOOKS
        "TASK_HOOKS_H":    ("GEMINI", [f"From {monolith_path}, extract CommandHooks.h Headers, following {manifesto_architect_path}."]),
        "TASK_HOOKS_CON":  ("GEMINI", [f"From {monolith_path}, extract CommandHooks ExecuteRaw (RE::Console) implementation, following {manifesto_architect_path}."]),
        "TASK_HOOKS_ACT":  ("GEMINI", [f"From {monolith_path}, extract CommandHooks ExecuteKill (RE::Actor) implementation, following {manifesto_architect_path}."]),
        # JSON
        "TASK_JSON_H":     ("GEMINI", [f"From {monolith_path}, extract JsonProcessor.h Headers, following {manifesto_architect_path}."]),
        "TASK_JSON_CPP":   ("GEMINI", [f"From {monolith_path}, extract JsonProcessor.cpp nlohmann::json parsing implementation, following {manifesto_architect_path}."]),
        # FORGE (QUINTUPLE SPLIT)
        "TASK_FORGE_HDR":  ("GEMINI", [f"From {manifesto_forge_path}, generate CMake Header and Versioning (3.20+)."]),
        "TASK_FORGE_OPTS": ("GEMINI", [f"From {manifesto_forge_path}, generate CMake Options, C++20 Flags, and RTTI settings."]),
        "TASK_FORGE_DEPS": ("GEMINI", [f"From {manifesto_forge_path}, generate CMake Dependency Lookup (CommonLibSSE-NG, nlohmann_json)."]),
        "TASK_FORGE_TRGT": ("GEMINI", [f"From {manifesto_forge_path}, generate CMake add_library and Sources (src/*.cpp)."]),
        "TASK_FORGE_POST": ("GEMINI", [f"From {manifesto_forge_path}, generate CMake Post-build and DLL output configuration."]),
        # DOCS
        "TASK_README":     ("GEMINI", ["Generate a beautiful, technical README.md for ROME Core based on PROJECT_ROME.md and AUGUSTUS.md."])
    }

    results = {}
    ui = AugustusUI(list(tasks.keys()))
    ui_queue = Queue()
    global_start = time.time()
    
    for tid, (cap, cmd) in tasks.items():
        # The prompt is already built with explicit file references.
        # No need to add extra context here.
        threading.Thread(target=run_legion, args=(tid, cap, cmd, ui_queue, arsenal, global_start, results), daemon=True).start()

    active_tasks = len(tasks)
    while active_tasks > 0:
        try:
            msg_type, tid, data = ui_queue.get(timeout=0.1)
            if msg_type == "update": ui.update(tid, data)
            elif msg_type == "final": ui.set_final(tid, data); active_tasks -= 1
        except Empty: pass

    print("\n\033[1;36m=== AUGUSTUS: REFINEMENT COMPLETE ===\033[0m")

    # SUTURE SQUAD
    def extract_code(tid):
        if tid not in results or results[tid]["status"] != "SUCCESS": return f"// FAILED: {tid}"
        content = results[tid]["intel"]
        code_match = re.search(r"```(?:cpp|c\+\+|cmake|markdown|md)?\s*(.*?)\s*```", content, re.DOTALL | re.IGNORECASE)
        return code_match.group(1) if code_match else content.strip()

    # Deploy Dispatcher
    with open("src/CommandDispatcher.h", "w") as f: f.write(extract_code("TASK_DISP_H"))
    with open("src/CommandDispatcher.cpp", "w") as f:
        f.write("#include \"CommandDispatcher.h\"\n")
        f.write(extract_code("TASK_DISP_SNG") + "\n\n")
        f.write(extract_code("TASK_DISP_PUSH") + "\n\n")
        f.write(extract_code("TASK_DISP_POP") + "\n\n")
        f.write(extract_code("TASK_DISP_PROC"))
    
    # Deploy others
    with open("src/CommandHooks.h", "w") as f: f.write(extract_code("TASK_HOOKS_H"))
    with open("src/CommandHooks.cpp", "w") as f:
        f.write("#include \"CommandHooks.h\"\n")
        f.write(extract_code("TASK_HOOKS_CON") + "\n\n")
        f.write(extract_code("TASK_HOOKS_ACT"))
        
    with open("src/JsonProcessor.h", "w") as f: f.write(extract_code("TASK_JSON_H"))
    with open("src/JsonProcessor.cpp", "w") as f: f.write(extract_code("TASK_JSON_CPP"))
    with open("README.md", "w") as f: f.write(extract_code("TASK_README"))

    # Deploy CMake
    cmake_order = ["TASK_FORGE_HDR", "TASK_FORGE_OPTS", "TASK_FORGE_DEPS", "TASK_FORGE_TRGT", "TASK_FORGE_POST"]
    with open("CMakeLists.txt", "w") as f:
        f.write("# ROME AUTO-GENERATED CMAKE\n\n")
        f.write("\n\n".join([extract_code(tid) for tid in cmake_order]))

    # PERSISTENT LOGGING
    with open("AUGUSTUS_LOGS.md", "a") as log:
        log.write(f"\n## MISSION LOG: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        for tid, res in results.items():
            status_color = "✅" if res["status"] == "SUCCESS" else "❌"
            log.write(f"* {status_color} **{tid}**: {res['status']} in {res['elapsed']:.1f}s\n")

    print("\033[1;32mThe Empire is refined. Logs updated in AUGUSTUS_LOGS.md.\033[0m")

if __name__ == "__main__": main()

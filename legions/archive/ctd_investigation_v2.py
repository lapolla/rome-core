#!/usr/bin/env python3
import subprocess, sys, time, threading, os, json, shutil
from queue import Queue, Empty

# --- ROME CAMPAIGN: MADNESS_CTD_INVESTIGATION (V2.0) ---

def run_legion(tid, capability, cmd, ui_queue, arsenal, global_start, results, input_files=[]):
    sandbox = f"/tmp/rome_madness_ctd_{tid}"
    if os.path.exists(sandbox): shutil.rmtree(sandbox)
    os.makedirs(sandbox)
    
    cap_data = arsenal["capabilities"][capability]
    wrapper = os.path.expanduser("~/projects/rome-core/legions/legion_wrapper.py")
    
    # ROME Protocol v2.0 input files handling
    for f in input_files:
        src = f
        dest = os.path.join(sandbox, os.path.basename(f))
        shutil.copy2(src, dest)
    
    # Use the full path for the command string
    full_cmd = [wrapper, tid, str(global_start)] + cap_data["args"] + [cmd]
    
    process = subprocess.Popen(full_cmd, cwd=sandbox, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1, env={**os.environ, "PYTHONUNBUFFERED": "1"})
    
    for line in process.stderr: pass 
    process.wait()
    
    manifest_path = os.path.join(sandbox, "manifest.json")
    manifest = {}
    if os.path.exists(manifest_path):
        with open(manifest_path, "r") as f: manifest = json.load(f)
            
    status = manifest.get("status", "SUCCESS" if process.returncode == 0 else "FAILED")
    report_path = os.path.join(sandbox, f"report_{tid}.txt")
    intel = ""
    if os.path.exists(report_path):
        with open(report_path, "r") as f: intel = f.read()
    
    results[tid] = {"status": status, "intel": intel}

def main():
    with open(os.path.expanduser("~/projects/rome-core/arsenal/core_arsenal.json"), "r") as f: arsenal = json.load(f)

    # V2.0 Tasks
    tasks = {
        "opencode_search": ("OPENCODE", "Audit 'Plugin.cpp' and 'slmBridge.psc'. Identify all instances where 'StopCombat()' is called on an actor without a preceding 'Is3DLoaded()' check on THAT SPECIFIC actor in the SAME scope. Pay special attention to 'BridgeDefeatStart' in the Papyrus script."),
        "codex_review":    ("GEMINI", "Deep audit of 'State::TryDefeat' and 'State::DefeatComplete' in 'Plugin.cpp'. Look for race conditions when multiple defeats are active. A second defeat starts for victim B while defeat A is ongoing. Both defeats might pacify the SAME hostiles. Does 'DefeatComplete(A)' potentially call 'StopCombat' on a hostile that is still required for defeat B's scene? Is 'Is3DLoaded()' sufficient to prevent CTD if the actor is not in the current cell?")
    }

    # Input Files
    plugin_src = "/home/paul-kane/projects/sexlab-madness-plugin/src/Plugin.cpp"
    bridge_src = "/home/paul-kane/projects/sexlab-madness-plugin/mod/Scripts/Source/slmBridge.psc"

    results = {}
    global_start = time.time()
    
    threads = []
    for tid, (cap, cmd) in tasks.items():
        t = threading.Thread(target=run_legion, args=(tid, cap, cmd, None, arsenal, global_start, results, [plugin_src, bridge_src]))
        threads.append(t)
        t.start()

    for t in threads: t.join()

    print("\n\033[1;36m=== ROME INVESTIGATION INTELLIGENCE ===\033[0m")
    for tid in ["opencode_search", "codex_review"]:
        print(f"\n--- {tid.upper()} ---")
        if tid in results: print(results[tid]["intel"])
        else: print("NO DATA.")

if __name__ == "__main__": main()

#!/usr/bin/env python3
import json
import os
import subprocess
import time
import sys
import re
import fcntl

# Import centralized logger (best-effort — works even if dictator package isn't on path)
try:
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from dictator.rome_log import log_event as _log_event
except Exception:
    def _log_event(**_kw): pass

MAX_ARTIFACT_SIZE = 5 * 1024 * 1024  # 5 MB cap

# --- ROME LEGIONARY V2.0: STRUCTURED SIGNAL ENGINE ---

class LegionaryUI:
    def __init__(self, task_id, global_start):
        self.task_id = task_id
        self.bar_width = 30
        self.global_start = global_start
        self.percent = 0
        self.hb_chars = ["+", "x", "*", ".", "o"]
        self.hb_idx = 0
        
    def log(self, percent, msg):
        self.percent = percent
        elapsed = time.time() - self.global_start
        hb = self.hb_chars[self.hb_idx % len(self.hb_chars)]
        self.hb_idx += 1
        status = f"{self.percent}% {hb} [{elapsed:.1f}s] {msg[:40]}"
        sys.stderr.write(status + "\n")
        sys.stderr.flush()

    def handle_bytes(self, b):
        try:
            text = b.decode("utf-8", errors="ignore").lower()
            if "thinking" in text: self.log(20, "Reasoning...")
            elif "analyzing" in text: self.log(50, "Analyzing...")
            elif "generating" in text: self.log(80, "Generating...")
            elif self.percent < 95: self.log(min(95, self.percent + 1), "Working...")
        except: pass

def parse_rome_signals(text):
    """Extract artifacts and metadata from ROME v2.0 signal tags."""
    signals = {
        "primary_artifact": None,
        "metadata": {},
        "status_override": None
    }

    if not text:
        return signals

    # Extract primary artifact: [ROME_START] ... [ROME_END]
    try:
        artifact_match = re.search(r"\[ROME_START\](.*?)\[ROME_END\]", text, re.DOTALL)
        if artifact_match:
            artifact = artifact_match.group(1).strip()
            if len(artifact) > MAX_ARTIFACT_SIZE:
                artifact = artifact[:MAX_ARTIFACT_SIZE]
                signals["metadata"]["truncated"] = "true"
            signals["primary_artifact"] = artifact
    except Exception:
        pass

    # Extract metadata: [ROME_META: key=value]
    try:
        meta_matches = re.findall(r"\[ROME_META:\s*(\w+)\s*=\s*(.*?)\]", text)
        for key, val in meta_matches:
            signals["metadata"][key] = val.strip()
    except Exception:
        pass

    # Extract status: [ROME_STATUS: SUCCESS|FAILED|RETRY]
    try:
        status_match = re.search(r"\[ROME_STATUS:\s*(SUCCESS|FAILED|RETRY)\]", text, re.IGNORECASE)
        if status_match:
            signals["status_override"] = status_match.group(1).upper()
    except Exception:
        pass

    return signals

def main():
    if len(sys.argv) < 4: sys.exit(1)
    task_id, global_start, command = sys.argv[1], float(sys.argv[2]), sys.argv[3:]
    
    _log_event(tool="legion_wrapper", task_id=task_id, message=f"Starting: {' '.join(command)}"[:200])

    ui = LegionaryUI(task_id, global_start)
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        bufsize=0,
        env={**os.environ, "PYTHONUNBUFFERED": "1"}
    )
    
    fd = process.stdout.fileno()
    fl = fcntl.fcntl(fd, fcntl.F_GETFL)
    fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)
    
    ui.log(0, "Engaged (V2.0).")
    
    full_output = []
    while True:
        try:
            chunk = os.read(fd, 4096)
            if chunk:
                ui.handle_bytes(chunk)
                full_output.append(chunk)
            elif process.poll() is not None:
                break
        except OSError:
            if process.poll() is not None: break
            time.sleep(0.2)
            ui.log(ui.percent, "Awaiting thought...")
            continue

    ui.log(100, "Mission complete.")
    
    final_text = b"".join(full_output).decode("utf-8", errors="ignore")
    signals = parse_rome_signals(final_text)
    
    # Artifact extraction
    artifact_path = f"report_{task_id}.txt"
    with open(artifact_path, "w") as f:
        # If model provided [ROME_START] tags, use that content. 
        # Otherwise, fall back to full output (v1.1 behavior)
        if signals["primary_artifact"]:
            f.write(signals["primary_artifact"])
        else:
            f.write(final_text)
    
    # Determine final status
    exit_code = process.returncode
    status = "SUCCESS" if exit_code == 0 else "FAILED"
    if signals["status_override"]:
        status = signals["status_override"]
    
    # Generate ROME v2.0 Manifest
    manifest = {
        "rome_v": "2.0",
        "task_id": task_id,
        "status": status,
        "metadata": signals["metadata"],
        "artifacts": [
            {
                "path": os.path.abspath(artifact_path),
                "type": "extracted" if signals["primary_artifact"] else "raw"
            }
        ],
        "runtime": {
            "elapsed_s": time.time() - global_start,
            "exit_code": exit_code
        }
    }
    
    with open(f"manifest.json", "w") as f:
        json.dump(manifest, f, indent=2)
        
    # Backward compatibility for v1.1 orchestrators
    with open(f"meta_{task_id}.json", "w") as f:
        json.dump({
            "rome_v": "1.1-compat",
            "task_id": task_id,
            "result": {
                "status": status,
                "exit_code": exit_code,
                "path": os.path.abspath(artifact_path)
            }
        }, f)
        
    _log_event(tool="legion_wrapper", task_id=task_id, status=status.lower(),
               duration_s=time.time() - global_start,
               message=f"exit_code={exit_code}")

    print(f"OK:{task_id}" if status == "SUCCESS" else f"ERR:{task_id}")

if __name__ == "__main__": main()

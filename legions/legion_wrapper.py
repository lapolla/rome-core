#!/usr/bin/env python3
import json
import os
import subprocess
import time
import sys
import re
import fcntl

# --- ROME LEGIONARY V11: SYNC-CLOCK ENGINE (CLEAN FILENAMES) ---

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
        # FORMAT: PERCENT% HB [ELAPSEDs] MESSAGE
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

def main():
    if len(sys.argv) < 4: sys.exit(1)
    task_id, global_start, command = sys.argv[1], float(sys.argv[2]), sys.argv[3:]
    
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
    
    ui.log(0, "Engaged.")
    
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
    # NO DOT in filename to avoid hidden file "cat" fails
    with open(f"report_{task_id}.txt", "w") as f: f.write(final_text)
    
    result = {
        "rome_v": "1.1",
        "task_id": task_id,
        "result": {
            "status": "SUCCESS" if process.returncode == 0 else "FAILED",
            "exit_code": process.returncode,
            "path": os.path.abspath(f"report_{task_id}.txt")
        }
    }
    with open(f"meta_{task_id}.json", "w") as f: json.dump(result, f)
    print(f"OK:{task_id}" if process.returncode == 0 else f"ERR:{task_id}")

if __name__ == "__main__": main()

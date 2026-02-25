#!/usr/bin/env python3
import subprocess, sys, time, threading, os

class OrchestratorUI:
    def __init__(self, names):
        self.stats = {n: {"msg": "Waiting..."} for n in names}
        self.lock = threading.Lock()
        for _ in names: sys.stderr.write("\n")
        sys.stderr.flush()

    def update(self, name, line):
        with self.lock:
            self.stats[name]["msg"] = line.strip()[-50:]
            self._redraw()

    def _redraw(self):
        sys.stderr.write(f"\033[{len(self.stats)}A")
        for name, s in self.stats.items():
            sys.stderr.write(f"\033[K[TEST:{name:8}] >> {s['msg']}\n")
        sys.stderr.flush()

def run_test_slave(tid, ui):
    # Simple shell loop that prints to stderr
    cmd = ["bash", "-c", f"for i in 1 2 3 4 5; do echo \"Status check $i for {tid}\" >&2; sleep 1; done"]
    wrapper = os.path.expanduser("~/projects/rome-core/legions/legion_wrapper.py")
    process = subprocess.Popen([wrapper, tid] + cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)
    for line in process.stderr:
        ui.update(tid, line)
    process.wait()

def main():
    names = ["SLAVE_1", "SLAVE_2", "SLAVE_3", "SLAVE_4", "SLAVE_5"]
    ui = OrchestratorUI(names)
    threads = [threading.Thread(target=run_test_slave, args=(n, ui)) for n in names]
    for t in threads: t.start()
    for t in threads: t.join()
    print("\nDiagnostic Complete.")

if __name__ == "__main__": main()

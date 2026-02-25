#!/usr/bin/env python3
import time, sys, threading, random, os

# --- ROME CENTURION 64: MULTI-THREADED PROGRESS ENGINE ---

NUM_ARCHITECTS = 64
LOG_FILE = "/home/paul-kane/tmp/ROME_64_SATURATION.log"

class ProgressUI:
    def __init__(self, names):
        self.names = names
        self.stats = {n: {"percent": 0, "msg": "Standby"} for n in names}
        self.lock = threading.Lock()
        for _ in range(NUM_ARCHITECTS): sys.stderr.write("\n")
        sys.stderr.flush()

    def update(self, name, percent, msg):
        with self.lock:
            self.stats[name]["percent"] = percent
            self.stats[name]["msg"] = msg
            self._redraw()

    def _redraw(self):
        sys.stderr.write(f"\033[{NUM_ARCHITECTS}A")
        for i, name in enumerate(self.names):
            s = self.stats[name]
            filled = int(20 * s["percent"] / 100)
            bar = "█" * filled + "░" * (20 - filled)
            line = f"\033[K[T{i:02}] {bar} {s['percent']:3}% >> {s['msg'][:20]}"
            sys.stderr.write(line + "\n")
        sys.stderr.flush()

def architect_task(tid, ui):
    target = random.randint(15, 30) # Speed up simulation
    for p in range(101):
        time.sleep(target / 100.0)
        ui.update(f"T{tid}", p, f"Sector {tid} Suture...")
    with open(LOG_FILE, "a") as f:
        f.write(f"TIMESTAMP: {time.time()} | SECTOR {tid} | STATUS: SUCCESS\n")

def main():
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    with open(LOG_FILE, "w") as f:
        f.write("--- ROME 64-ARCHITECT SATURATION LOG ---\n")

    names = [f"T{i}" for i in range(NUM_ARCHITECTS)]
    ui = ProgressUI(names)
    
    threads = []
    for i in range(NUM_ARCHITECTS):
        t = threading.Thread(target=architect_task, args=(i, ui), daemon=True)
        t.start()
        threads.append(t)

    for t in threads:
        t.join()

    print("\n\033[92mIMPERIAL DECREE: 64-SECTOR SATURATION COMPLETE.\033[0m")

if __name__ == "__main__":
    main()

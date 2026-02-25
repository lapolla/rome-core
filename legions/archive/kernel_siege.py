#!/usr/bin/env python3
"""ROME KERNEL SIEGE — Web dashboard with live per-subsystem progress bars.

One make -j process (already parallel internally), dashboard thread
parses output and attributes objects to subsystems in real time.
Web UI on localhost for live viewing.

Usage: kernel_siege.py [KERNEL_SRC_DIR] [-j JOBS] [--clean] [--port PORT]
"""
import subprocess, sys, os, time, threading, re, argparse, json
from http.server import HTTPServer, BaseHTTPRequestHandler

NCPU = os.cpu_count() or 4

SUBSYSTEMS = [
    "drivers/gpu", "drivers/net", "drivers/media", "drivers/clk",
    "drivers/iio", "drivers/usb", "drivers/scsi", "drivers/input",
    "drivers/pinctrl", "drivers/staging", "drivers/acpi",
    "drivers/platform", "drivers/hwmon", "drivers/video",
    "net", "fs", "arch", "kernel", "sound",
    "crypto", "lib", "mm", "security", "block", "io_uring",
    "init", "ipc", "virt", "certs", "usr",
]


def count_sources(kernel_dir, subdir):
    count = 0
    path = os.path.join(kernel_dir, subdir)
    if not os.path.isdir(path):
        return 0
    for root, _, files in os.walk(path):
        count += sum(1 for f in files if f.endswith(('.c', '.S')))
    return count


class Siege:
    def __init__(self, subsystem_est):
        self.lock = threading.Lock()
        self.subs = {name: {"est": est, "count": 0} for name, est in subsystem_est}
        self.sub_order = [name for name, _ in subsystem_est]
        self.other_count = 0
        self.total = 0
        self.total_est = sum(est for _, est in subsystem_est)
        self.warnings = 0
        self.errors = 0
        self.done = False
        self.victory = False
        self.exit_code = None
        self.start_time = time.time()
        self.bzimage_size = 0

    def parse_line(self, line):
        m = re.match(r'\s*(CC|AS|AR|LD|HOSTCC|HOSTLD|GEN|OBJCOPY|VDSO|MODPOST|SORTTAB)\s+(.+)', line)
        if not m:
            return
        path = m.group(2).strip()
        with self.lock:
            self.total += 1
            matched = False
            for name in self.subs:
                if path.startswith(name + "/"):
                    self.subs[name]["count"] += 1
                    matched = True
                    break
            if not matched:
                self.other_count += 1
        if "warning:" in line.lower():
            with self.lock:
                self.warnings += 1

    def to_json(self):
        with self.lock:
            elapsed = time.time() - self.start_time
            rate = self.total / elapsed if elapsed > 0 else 0
            subs = []
            for name in self.sub_order:
                d = self.subs[name]
                subs.append({
                    "name": name,
                    "count": d["count"],
                    "est": d["est"],
                    "pct": min(100, int(d["count"] / max(d["est"], 1) * 100)),
                })
            return json.dumps({
                "subs": subs,
                "total": self.total,
                "total_est": self.total_est,
                "other": self.other_count,
                "elapsed": round(elapsed, 1),
                "rate": round(rate, 1),
                "warnings": self.warnings,
                "errors": self.errors,
                "done": self.done,
                "victory": self.victory,
                "bzimage_size": self.bzimage_size,
            })


# Global ref for HTTP handler
_siege = None

HTML = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>ROME KERNEL SIEGE</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { background: #0a0a0a; color: #e0e0e0; font-family: 'JetBrains Mono', 'Fira Code', monospace; padding: 20px; }
  h1 { color: #ff4444; font-size: 1.4em; margin-bottom: 5px; }
  .stats { color: #888; font-size: 0.85em; margin-bottom: 15px; }
  .stats span { color: #fff; font-weight: bold; }
  .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 8px; }
  .front { background: #141414; border: 1px solid #222; border-radius: 6px; padding: 10px 12px; }
  .front.done { border-color: #2a5a2a; }
  .front-name { font-size: 0.8em; color: #888; margin-bottom: 4px; }
  .front-name span { color: #ccc; font-weight: bold; }
  .bar-bg { background: #1a1a1a; border-radius: 3px; height: 22px; position: relative; overflow: hidden; }
  .bar-fill { height: 100%; border-radius: 3px; transition: width 0.8s ease; }
  .bar-text { position: absolute; right: 8px; top: 2px; font-size: 0.75em; color: #aaa; }
  .pct-0  .bar-fill { background: linear-gradient(90deg, #1a3a4a, #2a5a7a); }
  .pct-25 .bar-fill { background: linear-gradient(90deg, #3a5a2a, #5a8a3a); }
  .pct-50 .bar-fill { background: linear-gradient(90deg, #6a6a2a, #aa8a2a); }
  .pct-75 .bar-fill { background: linear-gradient(90deg, #8a5a2a, #cc6a2a); }
  .pct-100 .bar-fill { background: linear-gradient(90deg, #2a8a2a, #3aba3a); }
  .victory { text-align: center; padding: 20px; color: #3aba3a; font-size: 1.3em; margin-top: 15px; }
  .failed { color: #ff4444; }
</style>
</head>
<body>
<h1>ROME KERNEL SIEGE</h1>
<div class="stats" id="stats"></div>
<div class="grid" id="grid"></div>
<div id="result"></div>
<script>
function pctClass(p) {
  if (p >= 95) return 'pct-100';
  if (p >= 75) return 'pct-75';
  if (p >= 50) return 'pct-50';
  if (p >= 25) return 'pct-25';
  return 'pct-0';
}

function update() {
  fetch('/api/status')
    .then(r => r.json())
    .then(d => {
      document.getElementById('stats').innerHTML =
        `<span>${d.total}</span>/${d.total_est} objects &nbsp; <span>${d.rate}</span>/s &nbsp; t+<span>${d.elapsed}s</span> &nbsp; warnings: <span>${d.warnings}</span>`;

      let html = '';
      for (const s of d.subs) {
        if (s.count === 0 && s.est === 0) continue;
        const cls = s.pct >= 95 ? 'front done' : 'front';
        const tag = s.pct >= 95 ? ' ✓' : '';
        html += `<div class="${cls}">
          <div class="front-name"><span>${s.name}</span>${tag} &nbsp; ${s.count}/${s.est}</div>
          <div class="bar-bg ${pctClass(s.pct)}">
            <div class="bar-fill" style="width:${s.pct}%"></div>
            <div class="bar-text">${s.pct}%</div>
          </div>
        </div>`;
      }
      if (d.other > 0) {
        html += `<div class="front"><div class="front-name"><span>other</span> &nbsp; ${d.other}</div>
          <div class="bar-bg pct-0"><div class="bar-fill" style="width:0%"></div></div></div>`;
      }
      document.getElementById('grid').innerHTML = html;

      if (d.done) {
        if (d.victory) {
          document.getElementById('result').innerHTML =
            `<div class="victory">bzImage FORGED — TOTAL VICTORY (${(d.bzimage_size/1024/1024).toFixed(1)} MiB) ${d.elapsed}s</div>`;
        } else {
          document.getElementById('result').innerHTML =
            `<div class="victory failed">SIEGE FAILED</div>`;
        }
      } else {
        setTimeout(update, 1000);
      }
    })
    .catch(() => setTimeout(update, 2000));
}
update();
</script>
</body>
</html>"""


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/api/status':
            data = _siege.to_json().encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.write(data) if hasattr(self, 'write') else self.wfile.write(data)
        else:
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.end_headers()
            self.wfile.write(HTML.encode())

    def log_message(self, format, *args):
        pass  # Silence HTTP logs


def main():
    global _siege

    parser = argparse.ArgumentParser(description="ROME KERNEL SIEGE")
    parser.add_argument("kernel_dir", nargs="?", default=".")
    parser.add_argument("-j", "--jobs", type=int, default=NCPU)
    parser.add_argument("--clean", action="store_true")
    parser.add_argument("--port", type=int, default=8077)
    args = parser.parse_args()

    kernel_dir = os.path.abspath(args.kernel_dir)
    if not os.path.isfile(os.path.join(kernel_dir, "Makefile")):
        print(f"No Makefile in {kernel_dir} — not a kernel tree.")
        sys.exit(1)

    if args.clean:
        print("Scorched earth...", flush=True)
        subprocess.run(["make", "mrproper"], cwd=kernel_dir, capture_output=True)
        subprocess.run(["make", "defconfig"], cwd=kernel_dir, capture_output=True)

    # Auto-detect source counts
    print("Scanning fronts...", flush=True)
    subsystem_est = [(s, count_sources(kernel_dir, s)) for s in SUBSYSTEMS]
    subsystem_est = [(s, e) for s, e in subsystem_est if e > 0]

    _siege = Siege(subsystem_est)

    # Start web server
    server = HTTPServer(('0.0.0.0', args.port), Handler)
    server_t = threading.Thread(target=server.serve_forever, daemon=True)
    server_t.start()

    print(f"ROME KERNEL SIEGE // {args.jobs} cores // {len(subsystem_est)} fronts", flush=True)
    print(f"Dashboard: http://localhost:{args.port}", flush=True)

    # Build
    proc = subprocess.Popen(
        ["make", f"-j{args.jobs}"],
        cwd=kernel_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    for line in proc.stdout:
        _siege.parse_line(line)

    proc.wait()
    _siege.exit_code = proc.returncode

    bzimg = os.path.join(kernel_dir, "arch/x86/boot/bzImage")
    if proc.returncode == 0 and os.path.exists(bzimg):
        _siege.bzimage_size = os.path.getsize(bzimg)
        _siege.victory = True
        print(f"bzImage FORGED ({_siege.bzimage_size / 1024 / 1024:.1f} MiB)", flush=True)
    else:
        print(f"SIEGE FAILED (exit {proc.returncode})", flush=True)

    _siege.done = True

    # Keep server alive 30s so dashboard shows final state
    time.sleep(30)
    server.shutdown()
    sys.exit(proc.returncode)


if __name__ == "__main__":
    main()

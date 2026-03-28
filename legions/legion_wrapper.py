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
        self.progress_lines = []
        # Write progress to file in task_dir for real-time tailing
        task_dir = os.environ.get("ROME_TASK_DIR", ".")
        self._progress_path = os.path.join(task_dir, "progress.log")
        try:
            self._progress_f = open(self._progress_path, "w")
        except Exception:
            self._progress_f = None
        silent_raw = str(os.environ.get("ROME_SILENT", "")).strip().lower()
        self._silent = silent_raw in {"1", "true", "yes"}

    def log(self, percent, msg):
        self.percent = percent
        elapsed = time.time() - self.global_start
        # Centurion-style visual on stderr
        filled = int(self.bar_width * self.percent / 100)
        bar = "█" * filled + "░" * (self.bar_width - filled)
        display_id = self.task_id.split("_")[-1] if "_" in self.task_id else self.task_id
        vis = (
            f"\r\033[K[ROME:{display_id:<14}] {bar}"
            f"  {self.percent:3}% [{elapsed:5.1f}s] >> {msg[:30]}"
        )
        if not self._silent:
            sys.stderr.write(vis)
            sys.stderr.flush()
        # File log for dictator/centurion to read back
        hb = self.hb_chars[self.hb_idx % len(self.hb_chars)]
        self.hb_idx += 1
        line = f"{self.percent}% {hb} [{elapsed:.1f}s] {msg[:40]}"
        self.progress_lines.append(line)
        if self._progress_f:
            try:
                self._progress_f.write(line + "\n")
                self._progress_f.flush()
            except Exception:
                pass

    def finalize(self, status):
        elapsed = time.time() - self.global_start
        color = "\033[92m" if status == "SUCCESS" else "\033[91m"
        bar = "\u2588" * self.bar_width
        display_id = self.task_id.split("_")[-1] if "_" in self.task_id else self.task_id
        vis = (
            f"\r\033[K[ROME:{display_id:<14}] {color}{bar}"
            f"  [{status:7}] [{elapsed:5.1f}s]\033[0m >> Mission complete."
        )
        if not self._silent:
            sys.stderr.write(vis + "\n")
            sys.stderr.flush()

    def close(self):
        if self._progress_f:
            try:
                self._progress_f.close()
            except Exception:
                pass

    def handle_bytes(self, b):
        try:
            text = b.decode("utf-8", errors="ignore")
            text_lower = text.lower()
            # Detect MCP tool calls in agent output (Gemini/Claude JSON streams)
            if '"toolcall"' in text_lower or '"tool_use"' in text_lower or '"function_call"' in text_lower:
                match = re.search(r'"name"\s*:\s*"(\w+)"', text)
                if match:
                    self.log(min(90, self.percent + 5), f"Calling {match.group(1)}...")
                    return
            # Detect explicit progress patterns: "Step 3/5", "50%", "[3/5]"
            step_match = re.search(r'(?:step\s+)?(\d+)\s*/\s*(\d+)', text_lower)
            if step_match:
                cur, total = int(step_match.group(1)), int(step_match.group(2))
                if total > 0:
                    self.log(min(95, int(cur / total * 95)), f"Step {cur}/{total}")
                    return
            pct_match = re.search(r'(\d{1,3})%', text)
            if pct_match:
                pct = int(pct_match.group(1))
                if 0 < pct <= 100:
                    self.log(min(95, pct), f"Progress {pct}%")
                    return
            # Keyword-based phase detection (ordered by typical workflow)
            KEYWORDS = [
                ("error",     self.percent, "Error detected"),
                ("exception", self.percent, "Exception detected"),
                ("traceback", self.percent, "Traceback detected"),
                ("reading",   25, "Reading files..."),
                ("searching", 30, "Searching..."),
                ("thinking",  20, "Reasoning..."),
                ("planning",  25, "Planning..."),
                ("analyzing", 50, "Analyzing..."),
                ("compiling", 60, "Compiling..."),
                ("building",  60, "Building..."),
                ("testing",   70, "Running tests..."),
                ("installing",65, "Installing..."),
                ("downloading",40,"Downloading..."),
                ("writing",   75, "Writing..."),
                ("editing",   75, "Editing..."),
                ("creating",  70, "Creating..."),
                ("generating",80, "Generating..."),
                ("formatting",85, "Formatting..."),
                ("complete",  95, "Wrapping up..."),
                ("success",   95, "Success"),
                ("done",      95, "Done"),
            ]
            for kw, target_pct, msg in KEYWORDS:
                if kw in text_lower:
                    self.log(max(self.percent, min(95, target_pct)), msg)
                    return
            # Default: slow crawl
            if self.percent < 95:
                self.log(min(95, self.percent + 1), "Working...")
        except:
            pass

# Model pricing tables (USD per 1M tokens)
# Source: platform.claude.com/docs/en/docs/about-claude/pricing + ai.google.dev/gemini-api/docs/pricing
# Updated: March 2026

_CLAUDE_PRICING = {
    # model substring → (input_per_1m, output_per_1m)
    "claude-opus-4-6":    (5.00,  25.00),
    "claude-opus-4-5":    (5.00,  25.00),
    "claude-sonnet-4-6":  (3.00,  15.00),
    "claude-sonnet-4-5":  (3.00,  15.00),
    "claude-sonnet-4":    (3.00,  15.00),
    "claude-haiku-4-5":   (1.00,   5.00),
    "claude-haiku-3-5":   (0.80,   4.00),
    "claude-haiku-3":     (0.25,   1.25),
    "claude-opus-3":      (15.00, 75.00),
}

def _calc_claude_cost(model: str, input_tokens: int, output_tokens: int) -> float | None:
    model_lower = model.lower().replace(".", "-")
    for key, (inp_rate, out_rate) in _CLAUDE_PRICING.items():
        if key in model_lower:
            return round(
                (input_tokens / 1_000_000) * inp_rate +
                (output_tokens / 1_000_000) * out_rate,
                6,
            )
    return None

# Gemini model pricing (USD per 1M tokens)
_GEMINI_PRICING = {
    # (input_per_1m, output_per_1m) USD — lower tier (<=200k tokens)
    # Source: ai.google.dev/gemini-api/docs/pricing, March 2026
    "gemini-3.1-pro": (2.00, 12.00),
    "gemini-3-pro": (2.00, 12.00),
    "gemini-3-flash": (0.50, 3.00),
    "gemini-2.5-pro": (1.25, 10.00),
    "gemini-2.5-flash-lite": (0.10, 0.40),
    "gemini-2.5-flash": (0.30, 2.50),
    "gemini-2.0-flash-lite": (0.075, 0.30),
    "gemini-2.0-flash": (0.10, 0.40),
    "gemini-1.5-pro": (1.25, 5.00),
    "gemini-1.5-flash": (0.075, 0.30),
}

def _calc_gemini_cost(model, input_tokens, output_tokens):
    model_lower = model.lower()
    for key, (inp_rate, out_rate) in _GEMINI_PRICING.items():
        if key in model_lower:
            return round(
                (input_tokens / 1_000_000) * inp_rate +
                (output_tokens / 1_000_000) * out_rate,
                6,
            )
    return None

def parse_usage(text):
    """Dual-mode: try to extract usage stats from JSON output (Claude/Gemini).
    Returns (response_text, usage_dict) or (original_text, None) if not JSON."""
    if not text:
        return text, None

    # Strip any non-JSON preamble (Gemini emits stderr lines before JSON)
    stripped = text.strip()
    # Find first '{' to start of JSON
    idx = stripped.find("{")
    if idx < 0:
        return text, None

    try:
        data = json.loads(stripped[idx:])
    except (json.JSONDecodeError, ValueError):
        return text, None

    usage = None

    # Claude shape: {"result": "...", "usage": {...}, "total_cost_usd": ...}
    if "result" in data and "usage" in data:
        u = data["usage"]
        model = "unknown"
        if "modelUsage" in data and isinstance(data["modelUsage"], dict):
            model = next(iter(data["modelUsage"]), "unknown")
        usage = {
            "model": model,
            "input_tokens": u.get("input_tokens", 0) + u.get("cache_read_input_tokens", 0),
            "output_tokens": u.get("output_tokens", 0),
            "total_tokens": u.get("input_tokens", 0) + u.get("cache_read_input_tokens", 0)
                            + u.get("cache_creation_input_tokens", 0) + u.get("output_tokens", 0),
            "cost_usd": data.get("total_cost_usd"),
        }
        return data.get("result", ""), usage

    # Gemini shape: {"response": "...", "stats": {"models": {...}}}
    if "response" in data and "stats" in data:
        models = data.get("stats", {}).get("models", {})
        total_in = 0
        total_out = 0
        total_all = 0
        model_name = "unknown"
        for name, info in models.items():
            model_name = name  # last model wins (usually the main one)
            tokens = info.get("tokens", {})
            total_in += tokens.get("input", 0)
            total_out += tokens.get("candidates", 0)
            total_all += tokens.get("total", 0)
        usage = {
            "model": model_name,
            "input_tokens": total_in,
            "output_tokens": total_out,
            "total_tokens": total_all,
            "cost_usd": _calc_gemini_cost(model_name, total_in, total_out),
        }
        return data.get("response", ""), usage

    return text, None


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

    # Capture initial task.md state to detect Gemini overwriting/appending to it
    task_md_path = "task.md"
    initial_task_content = ""
    if os.path.exists(task_md_path):
        try:
            with open(task_md_path, "r") as f:
                initial_task_content = f.read()
        except: pass

    ui = LegionaryUI(task_id, global_start)
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        bufsize=0,
        start_new_session=True,
        env={
            **os.environ,
            "PYTHONUNBUFFERED": "1",
            "ROME_TASK_ID": task_id,
            "ROME_TASK_TOKEN": os.environ.get("ROME_TASK_TOKEN", "")
        }
    )
    
    fd = process.stdout.fileno()
    fl = fcntl.fcntl(fd, fcntl.F_GETFL)
    fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)
    
    ui.log(0, "Engaged (3.0.0).")
    
    full_output = []
    _idle_ticks = 0
    while True:
        try:
            chunk = os.read(fd, 4096)
            if chunk:
                ui.handle_bytes(chunk)
                full_output.append(chunk)
                _idle_ticks = 0
            elif process.poll() is not None:
                break
        except OSError:
            if process.poll() is not None: break
            time.sleep(0.5)
            _idle_ticks += 1
            if _idle_ticks % 10 == 1:  # log once every ~5s, not every 0.5s
                ui.log(ui.percent, "Awaiting thought...")
            continue

    status = "SUCCESS" if process.returncode == 0 else "FAILED"
    ui.finalize(status)
    ui.close()

    raw_text = b"".join(full_output).decode("utf-8", errors="ignore")

    # Dual-mode: extract usage from JSON output if available, else use raw text
    final_text, usage = parse_usage(raw_text)
    signals = parse_rome_signals(final_text)

    # Artifact extraction
    artifact_path = f"report_{task_id}.txt"
    with open(artifact_path, "w") as f:
        if signals["primary_artifact"]:
            f.write(signals["primary_artifact"])
        else:
            f.write(final_text)

    # Validation Step: check for empty/broken reports
    def is_empty_content(content):
        if not content: return True
        cleaned = content.replace("`", "").strip()
        if len(cleaned) == 0: return True
        # Bare ROME exit signal with no real content counts as empty
        if re.fullmatch(r'(OK|ERR):[a-zA-Z0-9_\-]+', cleaned): return True
        return False

    try:
        with open(artifact_path, "r") as f:
            report_content = f.read()
    except:
        report_content = ""

    if is_empty_content(report_content):
        # Check for bug signature: output is just the OK signal
        if final_text.strip() == f"OK:{task_id}":
            signals["metadata"]["bug_signature"] = "true"

        # Try to recover from task.md
        if os.path.exists(task_md_path):
            try:
                with open(task_md_path, "r") as f:
                    current_task_content = f.read()
                
                recovered_content = None
                # Case 1: Appended to task.md
                if len(current_task_content) > len(initial_task_content):
                    recovered_content = current_task_content[len(initial_task_content):].strip()
                
                # Case 2: Overwrote task.md or contains tags
                if is_empty_content(recovered_content):
                    task_signals = parse_rome_signals(current_task_content)
                    if task_signals["primary_artifact"]:
                        recovered_content = task_signals["primary_artifact"]
                    elif len(current_task_content) > 100: # Heuristic fallback
                         # Only if it's substantially different from initial
                         if current_task_content.strip() != initial_task_content.strip():
                             recovered_content = current_task_content.strip()
                
                if not is_empty_content(recovered_content):
                    with open(artifact_path, "w") as f:
                        f.write(recovered_content)
                    signals["metadata"]["recovered_from_task_md"] = "true"
                    report_content = recovered_content
            except Exception as e:
                _log_event(tool="legion_wrapper", task_id=task_id, message=f"Recovery failed: {e}")

    # Determine final status
    exit_code = process.returncode
    status = "SUCCESS" if exit_code == 0 else "FAILED"
    if signals["status_override"]:
        status = signals["status_override"]

    # Final check for empty report
    if is_empty_content(report_content) and status == "SUCCESS":
        status = "FAILED"
        signals["metadata"]["failure_reason"] = "empty_report"

    capability_name = command[0] # Extract capability name

    if status == "FAILED":
        try:
            from dictator.ws_client import send_event
            send_event('capability_status', '', {'capability': capability_name, 'available': False, 'reason': f'exit_code={exit_code}'})
        except Exception:
            pass

    # Generate ROME v2.0 Manifest
    manifest = {
        "rome_v": "2.0",
        "task_id": task_id,
        "status": status,
        "metadata": signals["metadata"],
        "usage": usage,
        "progress": ui.progress_lines,
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
               message=f"exit_code={exit_code}", usage=usage)

    print(f"OK:{task_id}" if status == "SUCCESS" else f"ERR:{task_id}")

if __name__ == "__main__": main()

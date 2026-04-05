#!/usr/bin/env python3
"""
ROME LEGIONARY V4.0: PERSISTENT WORKER ENGINE
Supports both legacy 'one-off' mode and persistent 'worker' mode over WebSocket.
"""
import asyncio
import json
import os
import subprocess
import time
import sys
import re
import fcntl
import argparse
import uuid
import platform
import logging

# Import centralized logger
try:
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from dictator.rome_log import log_event as _log_event
except Exception:
    def _log_event(**_kw): pass

MAX_ARTIFACT_SIZE = 5 * 1024 * 1024  # 5 MB cap

# --- UI & PROGRESS ---

class LegionaryUI:
    def __init__(self, task_id, global_start, ws_sender=None, task_dir=None):
        self.task_id = task_id
        self.bar_width = 30
        self.global_start = global_start
        self.percent = 0
        self.hb_chars = ["+", "x", "*", ".", "o"]
        self.hb_idx = 0
        self.progress_lines = []
        self.ws_sender = ws_sender

        # Write progress to file in task_dir for real-time tailing
        if task_dir is None:
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
            
        hb = self.hb_chars[self.hb_idx % len(self.hb_chars)]
        self.hb_idx += 1
        line = f"{self.percent}% {hb} [{elapsed:.1f}s] {msg[:40]}"
        self.progress_lines.append(line)
        
        if self._progress_f:
            try:
                self._progress_f.write(line + "\n")
                self._progress_f.flush()
            except Exception: pass
            
        # V4: Stream progress back via WS if available
        if self.ws_sender:
            asyncio.create_task(self.ws_sender({"type": "progress", "task_id": self.task_id, "payload": {"percent": self.percent, "message": msg}}))

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
            except Exception: pass

    def handle_bytes(self, b):
        try:
            text = b.decode("utf-8", errors="ignore")
            text_lower = text.lower()
            if '"toolcall"' in text_lower or '"tool_use"' in text_lower or '"function_call"' in text_lower:
                match = re.search(r'"name"\s*:\s*"(\w+)"', text)
                if match:
                    self.log(min(90, self.percent + 5), f"Calling {match.group(1)}...")
                    return
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
            KEYWORDS = [
                ("reading",   25, "Reading files..."),
                ("searching", 30, "Searching..."),
                ("thinking",  20, "Reasoning..."),
                ("planning",  25, "Planning..."),
                ("analyzing", 50, "Analyzing..."),
                ("compiling", 60, "Compiling..."),
                ("building",  60, "Building..."),
                ("testing",   70, "Running tests..."),
                ("writing",   75, "Writing..."),
                ("editing",   75, "Editing..."),
                ("creating",  70, "Creating..."),
                ("generating",80, "Generating..."),
                ("formatting",85, "Formatting..."),
            ]
            for kw, target_pct, msg in KEYWORDS:
                if kw in text_lower:
                    self.log(max(self.percent, min(95, target_pct)), msg)
                    return
            if self.percent < 95:
                self.log(min(95, self.percent + 1), "Working...")
        except: pass

# --- PRICING ---

_GEMINI_PRICING = {
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
            return round((input_tokens / 1_000_000) * inp_rate + (output_tokens / 1_000_000) * out_rate, 6)
    return None

# --- PARSING ---

def parse_usage(text):
    if not text: return text, None
    stripped = text.strip()
    idx = stripped.find("{")
    if idx < 0: return text, None
    try:
        data = json.loads(stripped[idx:])
    except (json.JSONDecodeError, ValueError): return text, None

    # Claude shape
    if "result" in data and "usage" in data:
        u = data["usage"]
        model = "unknown"
        if "modelUsage" in data and isinstance(data["modelUsage"], dict):
            model = next(iter(data["modelUsage"]), "unknown")
        usage = {
            "model": model,
            "input_tokens": u.get("input_tokens", 0) + u.get("cache_read_input_tokens", 0),
            "output_tokens": u.get("output_tokens", 0),
            "total_tokens": u.get("input_tokens", 0) + u.get("cache_read_input_tokens", 0) + u.get("cache_creation_input_tokens", 0) + u.get("output_tokens", 0),
            "cost_usd": data.get("total_cost_usd"),
        }
        return data.get("result", ""), usage

    # Gemini shape
    if "response" in data and "stats" in data:
        models = data.get("stats", {}).get("models", {})
        total_in, total_out, total_all, model_name = 0, 0, 0, "unknown"
        for name, info in models.items():
            model_name = name
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
    signals = {"primary_artifact": None, "metadata": {}, "status_override": None}
    if not text: return signals
    try:
        artifact_match = re.search(r"\[ROME_START\](.*?)\[ROME_END\]", text, re.DOTALL)
        if artifact_match:
            artifact = artifact_match.group(1).strip()
            if len(artifact) > MAX_ARTIFACT_SIZE:
                artifact = artifact[:MAX_ARTIFACT_SIZE]
                signals["metadata"]["truncated"] = "true"
            signals["primary_artifact"] = artifact
    except: pass
    try:
        meta_matches = re.findall(r"\[ROME_META:\s*(\w+)\s*=\s*(.*?)\]", text)
        for key, val in meta_matches: signals["metadata"][key] = val.strip()
    except: pass
    try:
        status_match = re.search(r"\[ROME_STATUS:\s*(SUCCESS|FAILED|RETRY)\]", text, re.IGNORECASE)
        if status_match: signals["status_override"] = status_match.group(1).upper()
    except: pass
    return signals

def is_empty_content(content):
    if not content: return True
    cleaned = content.replace("`", "").strip()
    if len(cleaned) == 0: return True
    if re.fullmatch(r'(OK|ERR):[a-zA-Z0-9_\-]+', cleaned): return True
    return False

# --- TASK EXECUTION CORE ---

async def execute_task(task_id, capability_name, cmd_args, ui_sender=None):
    """Asynchronous core of task execution."""
    t0 = time.time()
    task_dir = os.path.join(os.getcwd(), "legions", task_id)
    os.makedirs(task_dir, exist_ok=True)
    
    # Capture task.md for recovery
    task_md_path = os.path.join(task_dir, "task.md")
    initial_task_content = ""
    if os.path.exists(task_md_path):
        try:
            with open(task_md_path, "r") as f: initial_task_content = f.read()
        except: pass

    ui = LegionaryUI(task_id, t0, ws_sender=ui_sender, task_dir=task_dir)
    ui.log(0, "Engaged (4.0.0).")
    
    process = await asyncio.create_subprocess_exec(
        *cmd_args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        start_new_session=True,
        cwd=task_dir,
        env={
            **os.environ,
            "PYTHONUNBUFFERED": "1",
            "ROME_TASK_ID": task_id,
            "ROME_TASK_DIR": task_dir,
            "ROME_TASK_TOKEN": os.environ.get("ROME_TASK_TOKEN", "")
        }
    )
    
    full_output = []
    async for line in process.stdout:
        ui.handle_bytes(line)
        full_output.append(line)
        
    exit_code = await process.wait()
    status = "SUCCESS" if exit_code == 0 else "FAILED"
    ui.finalize(status)
    ui.close()

    raw_text = b"".join(full_output).decode("utf-8", errors="ignore")
    final_text, usage = parse_usage(raw_text)
    signals = parse_rome_signals(final_text)

    artifact_path = os.path.join(task_dir, f"report_{task_id}.txt")
    report_content = signals["primary_artifact"] or final_text
    
    # Recovery logic
    if is_empty_content(report_content) and os.path.exists(task_md_path):
         try:
            with open(task_md_path, "r") as f: current_task_content = f.read()
            recovered = None
            if len(current_task_content) > len(initial_task_content):
                recovered = current_task_content[len(initial_task_content):].strip()
            if is_empty_content(recovered):
                task_signals = parse_rome_signals(current_task_content)
                recovered = task_signals["primary_artifact"] or (current_task_content.strip() if len(current_task_content)>100 else None)
            if recovered:
                report_content = recovered
                signals["metadata"]["recovered_from_task_md"] = "true"
         except: pass

    with open(artifact_path, "w") as f: f.write(report_content)
    
    if signals["status_override"]: status = signals["status_override"]
    if is_empty_content(report_content) and status == "SUCCESS":
        status = "FAILED"
        signals["metadata"]["failure_reason"] = "empty_report"

    progress_log_path = os.path.join(task_dir, "progress.log")
    manifest = {
        "rome_v": "4.0", "task_id": task_id, "status": status, "metadata": signals["metadata"],
        "usage": usage,
        "progress": {
            "count": len(ui.progress_lines),
            "final": ui.progress_lines[-1] if ui.progress_lines else None,
            "log_path": progress_log_path,
        },
        "runtime": {"elapsed_s": time.time() - t0, "exit_code": exit_code},
        "artifacts": [{"path": artifact_path, "type": "extracted" if signals["primary_artifact"] else "raw"}]
    }
    with open(os.path.join(task_dir, "manifest.json"), "w") as f: json.dump(manifest, f, indent=2)

    _log_event(tool="legion_wrapper", task_id=task_id, status=status.lower(), duration_s=time.time() - t0, usage=usage)
    return manifest

# --- WORKER LOOP ---

async def _start_peer_server(capabilities, capability_cmd_base):
    """Start a local A2A peer WS server on a random port. Returns (server, port)."""
    import websockets
    import socket

    async def peer_handler(websocket):
        try:
            async for raw in websocket:
                try:
                    msg = json.loads(raw)
                    if msg.get("type") != "command":
                        continue
                    command = msg.get("command", "")
                    payload = msg.get("payload", {})
                    request_id = msg.get("request_id", "")
                    if command == "dispatch":
                        task_id = payload.get("task_id", "")
                        prompt = payload.get("prompt", "")
                        cap = payload.get("capability", capabilities[0] if capabilities else "")
                        await websocket.send(json.dumps({
                            "type": "response", "request_id": request_id,
                            "ok": True, "payload": {"task_id": task_id, "accepted": True}
                        }))
                        cmd = list(capability_cmd_base)
                        if prompt:
                            cmd.append(prompt)
                        async def run_and_report():
                            async def noop_sender(ev): pass
                            manifest = await execute_task(task_id, cap, cmd, ui_sender=noop_sender)
                            report_content = ""
                            try:
                                with open(manifest["artifacts"][0]["path"]) as fp:
                                    report_content = fp.read()
                            except Exception:
                                pass
                            await websocket.send(json.dumps({
                                "type": "event",
                                "event": {
                                    "type": "complete", "task_id": task_id,
                                    "payload": {
                                        "status": manifest["status"],
                                        "usage": manifest["usage"],
                                        "report": report_content
                                    }
                                }
                            }))
                        asyncio.create_task(run_and_report())
                    elif command == "ping":
                        await websocket.send(json.dumps({"type": "response", "request_id": request_id, "ok": True}))
                except Exception as e:
                    print(f"ROME A2A: peer handler error: {e}")
        except Exception:
            pass

    # Bind on random available port
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    server = await websockets.serve(peer_handler, "127.0.0.1", port)
    print(f"ROME A2A: Peer server listening on ws://127.0.0.1:{port}")
    return server, port


async def run_worker(ws_url, capabilities, capability_cmd_base, token=None):
    """Persistent worker loop."""
    import websockets
    print(f"ROME V4: Connecting as persistent worker to {ws_url}")
    headers = {"Authorization": f"Bearer {token}"} if token else {}

    # Start A2A peer server
    peer_server, peer_port = await _start_peer_server(capabilities, capability_cmd_base)
    peer_url = f"ws://127.0.0.1:{peer_port}"

    backoff = 1.0
    while True:
        try:
            async with websockets.connect(ws_url, additional_headers=headers) as ws:
                backoff = 1.0
                print("ROME V4: Registered. Awaiting tasks...")
                await ws.send(json.dumps({
                    "type": "agent_hello",
                    "capabilities": capabilities,
                    "version": "4.0.0",
                    "platform": platform.platform(),
                    "peer_url": peer_url
                }))
                
                while True:
                    raw = await ws.recv()
                    msg = json.loads(raw)
                    print(f"ROME V4: Received message type={msg.get('type')}")
                    if msg.get("type") == "command" and msg.get("command") == "dispatch":
                        payload = msg.get("payload", {})
                        task_id = payload.get("task_id")
                        cap = payload.get("capability")
                        prompt = payload.get("prompt")
                        
                        # In worker mode, we use the pre-configured CLI args for the capability
                        # but we append the prompt if it's a 'p' style CLI.
                        # For simplicity in this Demo: we assume the capability is passed in sys.argv
                        # and we use those args, replacing the prompt if needed.
                        
                        # Find where the actual command starts (after --mode, --capabilities etc)
                        # We use unknown from main_async or just skip known flags
                        # For now, let's just use the 'unknown' args passed from main
                        cmd = list(capability_cmd_base)
                        if prompt: cmd.append(prompt)
                        
                        async def ui_sender(ev):
                            await ws.send(json.dumps({"type": "event", "event": ev}))
                            
                        # Run task as background coroutine to keep WS responsive
                        async def task_runner():
                            manifest = await execute_task(task_id, cap, cmd, ui_sender=ui_sender)
                            # Load report content for inline inclusion in v4
                            report_content = ""
                            try:
                                with open(manifest["artifacts"][0]["path"], "r") as f:
                                    report_content = f.read()
                            except: pass
                            
                            await ws.send(json.dumps({
                                "type": "event",
                                "event": {
                                    "type": "complete",
                                    "task_id": task_id,
                                    "payload": {
                                        "status": manifest["status"],
                                        "usage": manifest["usage"],
                                        "report_path": manifest["artifacts"][0]["path"],
                                        "report": report_content
                                    }
                                }
                            }))
                        
                        asyncio.create_task(task_runner())
                        # Ack the dispatch
                        await ws.send(json.dumps({"type": "response", "request_id": msg.get("request_id"), "ok": True}))
        except Exception as e:
            print(f"ROME V4: Worker error: {e}. Reconnecting in {backoff:.1f}s...")
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 30)

# --- CLI ENTRY ---

async def main_async():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["once", "worker"], default="once")
    parser.add_argument("--task-id")
    parser.add_argument("--start-time", type=float)
    parser.add_argument("--ws-url", default="ws://127.0.0.1:8741/ws")
    parser.add_argument("--ws-token")
    parser.add_argument("--capabilities", nargs="+")
    args, unknown = parser.parse_known_args()

    if args.mode == "worker":
        if not args.capabilities:
            print("Worker mode requires --capabilities")
            sys.exit(1)
        token = args.ws_token or os.environ.get("ROME_WEBSOCKET_TOKEN")
        # Strip argparse separator "--" from unknown args before using as cmd base
        capability_cmd = [a for a in unknown if a != "--"]
        await run_worker(args.ws_url, args.capabilities, capability_cmd, token=token)
    else:
        # Legacy once-off mode
        # Usage: legion_wrapper.py <task_id> <start_time> <cmd...>
        if len(sys.argv) < 4: sys.exit(1)
        task_id = sys.argv[1]
        start_time = float(sys.argv[2])
        cmd = sys.argv[3:]
        manifest = await execute_task(task_id, "LEGACY", cmd)
        print("OK" if manifest["status"] == "SUCCESS" else "ERR")

if __name__ == "__main__":
    asyncio.run(main_async())

#!/usr/bin/env python3
"""
ROME Shell Executor v2.0
Directly executes bash commands, captures output, and reports progress.
"""
import sys
import os
import time
import subprocess
import json
import threading

# Silently import _log_event from rome_log if available.
try:
    # Attempt to find rome_log in its likely location: ../dictator/rome_log.py
    sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'dictator'))
    from rome_log import _log_event
except ImportError:
    _log_event = None

# Silently import ws_client from ws_client if available.
try:
    # Attempt to find ws_client in its likely location: ../dictator/ws_client.py
    sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'dictator'))
    from ws_client import send_event, flush
except ImportError:
    send_event = None
    flush = None

def shell_executor():
    # Priority: Env > Command Line > Default
    task_id = os.environ.get("ROME_TASK_ID")
    if not task_id:
        if len(sys.argv) > 1:
            task_id = sys.argv[1]
        else:
            task_id = f"shell_{int(time.time())}"

    # Priority: Env > Command Line > Current Time
    global_start_timestamp = None
    if os.environ.get("ROME_START_TIME"):
        try:
            global_start_timestamp = float(os.environ.get("ROME_START_TIME"))
        except: pass
    
    if global_start_timestamp is None:
        if len(sys.argv) > 2:
            try:
                global_start_timestamp = float(sys.argv[2])
            except: pass
    
    if global_start_timestamp is None:
        global_start_timestamp = time.time()
    
    # Priority: Last Argument > Env
    bash_command = None
    if len(sys.argv) >= 2:
        bash_command = sys.argv[-1]
    
    if not bash_command:
        bash_command = os.environ.get("ROME_PROMPT")

    if not bash_command:
        print("Usage: python3 shell_executor.py <task_id> <global_start_timestamp> <bash_command_string>")
        print("OR set ROME_TASK_ID and pass bash_command as last arg.")
        sys.exit(1)

    shell_timeout = float(os.environ.get('SHELL_TIMEOUT', 600))

    # task_dir = <rome-core>/legions/<task_id>/ — create if needed
    base_dir = os.path.dirname(os.path.abspath(__file__))
    task_dir = os.path.join(base_dir, task_id)
    os.makedirs(task_dir, exist_ok=True)

    start_time = time.time()
    full_output = []
    
    # Run: subprocess.Popen(['bash', '-c', bash_command], stdout=PIPE, stderr=STDOUT, text=True)
    process = subprocess.Popen(
        ['bash', '-c', bash_command],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        start_new_session=True,
    )

    def read_output(proc, output_list, tid, start_t):
        # Read stdout line by line (BLOCKING — no O_NONBLOCK)
        # Using iter(proc.stdout.readline, '') to ensure blocking reads.
        for line in iter(proc.stdout.readline, ''):
            output_list.append(line)
            last_line = line.strip()
            elapsed = time.time() - start_t
            # Print per-line progress to own stdout: PROGRESS:{task_id}:{elapsed:.1f}s:{last_line[:80]}
            print(f"PROGRESS:{tid}:{elapsed:.1f}s:{last_line[:80]}", flush=True)

            # Send real-time progress via WebSocket if available (throttled)
            if send_event and (len(output_list) % 5 == 0 or elapsed < 2):
                # We don't have a real total, so we use a rolling 'pseudo-progress'
                # that increments with line count, capped at 99%.
                percent = min(1 + (len(output_list) // 5), 99)
                send_event("progress", tid, {"percent": float(percent), "message": last_line[:80]})
        proc.stdout.close()

    reader_thread = threading.Thread(target=read_output, args=(process, full_output, task_id, start_time))
    reader_thread.daemon = True
    reader_thread.start()

    # Wait for process to finish or timeout
    is_timeout = False
    while process.poll() is None:
        if time.time() - start_time > shell_timeout:
            # Kill entire process group to avoid orphans
            import signal
            try:
                os.killpg(os.getpgid(process.pid), signal.SIGKILL)
            except OSError:
                process.kill()
            is_timeout = True
            break
        time.sleep(0.05)

    # Ensure reader thread finishes
    reader_thread.join(timeout=1.0)

    exit_code = process.returncode if not is_timeout else -1
    status = "SUCCESS" if exit_code == 0 and not is_timeout else "FAILED"
    elapsed_s = time.time() - start_time

    # Append timeout message if it happened
    if is_timeout:
        full_output.append(f"\n[TIMEOUT] Process killed after {shell_timeout}s\n")

    # Write full output to task_dir/report_{task_id}.txt
    report_path = os.path.join(task_dir, f"report_{task_id}.txt")
    try:
        with open(report_path, "w") as f:
            f.writelines(full_output)
    except Exception:
        pass

    # Write manifest.json: {rome_v:"2.0", task_id, status, usage:null, runtime:{elapsed_s, exit_code}}
    manifest = {
        "rome_v": "2.0",
        "task_id": task_id,
        "status": status,
        "usage": None,
        "runtime": {
            "elapsed_s": round(elapsed_s, 3),
            "exit_code": exit_code
        }
    }
    manifest_path = os.path.join(task_dir, "manifest.json")
    try:
        with open(manifest_path, "w") as f:
            json.dump(manifest, f, indent=2)
    except Exception:
        pass

    if send_event:
        send_event("complete", task_id, {"status": status, "report_path": report_path, "usage": None})
        if flush:
            flush()

    # Print last 3 lines as summary
    print("\n--- Summary ---")
    summary_lines = full_output[-3:]
    for l in summary_lines:
        print(l.strip())



if __name__ == "__main__":
    shell_executor()

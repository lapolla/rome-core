"""
ROME centralized JSON-line logger.
Writes to ROME_ROOT/logs/rome.jsonl, auto-rotates at 50 MB.
"""

import json
import os
import time
from pathlib import Path

ROME_ROOT = Path(os.environ.get("ROME_ROOT", "/home/paul-kane/projects/rome-core"))
LOG_DIR = ROME_ROOT / "logs"
LOG_FILE = LOG_DIR / "rome.jsonl"
MAX_SIZE = 50 * 1024 * 1024  # 50 MB
MAX_ROTATIONS = 5


def _rotate():
    """Rotate rome.jsonl → rome.jsonl.1, .1→.2, etc."""
    for i in range(MAX_ROTATIONS, 0, -1):
        src = LOG_DIR / f"rome.jsonl.{i}"
        dst = LOG_DIR / f"rome.jsonl.{i + 1}"
        if src.exists():
            if i == MAX_ROTATIONS:
                src.unlink()
            else:
                src.rename(dst)
    if LOG_FILE.exists():
        LOG_FILE.rename(LOG_DIR / "rome.jsonl.1")


def log_event(
    tool: str,
    task_id: str = "",
    status: str = "ok",
    duration_s: float = 0.0,
    message: str = "",
):
    """Append one JSON line to the ROME log."""
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)

        if LOG_FILE.exists() and LOG_FILE.stat().st_size >= MAX_SIZE:
            _rotate()

        entry = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "tool": tool,
            "task_id": task_id,
            "status": status,
            "duration_s": round(duration_s, 3),
            "message": message[:500],
        }
        with open(LOG_FILE, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        pass  # logging must never crash the server

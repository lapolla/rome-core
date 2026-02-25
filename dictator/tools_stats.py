"""Observability tools: rome_tail."""

import collections
import json
from pathlib import Path

from dictator.core import mcp, ROME_ROOT


@mcp.tool()
async def rome_tail(n: int = 20) -> str:
    """Show the last N entries from the ROME log, formatted for quick reading."""
    log_path = ROME_ROOT / "logs" / "rome.jsonl"

    if not log_path.exists():
        return json.dumps({"ok": False, "error": f"Log file not found at {log_path}"})

    lines = collections.deque(maxlen=n)
    try:
        with open(log_path, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    lines.append(line)
    except Exception as e:
        return json.dumps({"ok": False, "error": str(e)})

    entries = []
    for line in lines:
        try:
            d = json.loads(line)
            ts = d.get("timestamp", "?")
            tool = d.get("tool", "?")
            status = d.get("status", "?")
            dur = d.get("duration_s", 0.0)
            msg = d.get("message", "")

            entry = f"[{ts}] {tool} {status} {dur}s {msg}"

            usage = d.get("usage")
            if isinstance(usage, dict):
                cost = usage.get("cost_usd")
                if cost is not None:
                    entry += f" (${cost:.4f})"

            entries.append(entry)
        except (json.JSONDecodeError, TypeError, AttributeError):
            continue

    return json.dumps({"ok": True, "count": len(entries), "entries": entries})

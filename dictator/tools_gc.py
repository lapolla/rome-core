"""GC and stats tools: gc_legions, legion_stats, reset_tasks."""

import json
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path

from dictator.core import ROME_ROOT
from dictator.rome_log import log_event


def register(registry):
    """Register GC and stats tools with the given native ROME registry instance."""

    @registry.tool()
    async def gc_legions(max_age_days: int = 7) -> str:
        """Garbage collect old legion task directories."""
        legions_path = ROME_ROOT / "legions"
        if not legions_path.exists():
            return json.dumps({"ok": False, "error": "Legions directory not found"})

        dirs = []
        for p in legions_path.iterdir():
            if p.is_dir() and p.name != "archive":
                try:
                    dirs.append((p, p.stat().st_mtime))
                except OSError:
                    pass

        dirs.sort(key=lambda x: x[1], reverse=True)

        now = time.time()
        deleted = 0
        kept = 0
        freed_bytes = 0

        for i, (p, mtime) in enumerate(dirs):
            age_s = now - mtime
            if i < 50 or age_s < 86400:
                kept += 1
            elif age_s > max_age_days * 86400:
                try:
                    dir_size = sum(f.stat().st_size for f in p.rglob("*") if f.is_file())
                    shutil.rmtree(p)
                    deleted += 1
                    freed_bytes += dir_size
                except Exception:
                    kept += 1
            else:
                kept += 1

        log_event(tool="gc_legions", message=f"deleted={deleted} kept={kept} freed={freed_bytes}")
        return json.dumps({"ok": True, "deleted": deleted, "kept": kept, "freed_bytes": freed_bytes})

    @registry.tool()
    async def reset_tasks() -> str:
        """Clear all tasks from registry (including REGISTERED zombies). Resets dashboard."""
        from dictator.ws_client import send_command_async
        result = await send_command_async("reset", {})
        log_event(tool="reset_tasks", message=f"cleared={result.get('cleared', '?')}")
        return json.dumps(result)

    @registry.tool()
    async def legion_stats(period_hours: int = 24) -> str:
        """Aggregate legion performance and cost stats from the ROME log."""
        log_file = ROME_ROOT / "logs" / "rome.jsonl"
        if not log_file.exists():
            return json.dumps({"ok": False, "error": "Log file not found"})

        now = datetime.now(timezone.utc)
        total_events = 0
        success_count = 0
        error_count = 0
        total_cost_usd = 0.0
        durations = []
        breakdown = {}

        try:
            with open(log_file) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                    except (json.JSONDecodeError, TypeError):
                        continue

                    ts_str = entry.get("timestamp", "")
                    try:
                        ts = datetime.fromisoformat(ts_str)
                        if ts.tzinfo is None:
                            ts = ts.replace(tzinfo=timezone.utc)
                        age_h = (now - ts).total_seconds() / 3600
                        if age_h > period_hours:
                            continue
                    except (ValueError, TypeError):
                        continue

                    total_events += 1
                    tool = entry.get("tool", "unknown")
                    breakdown[tool] = breakdown.get(tool, 0) + 1

                    status = entry.get("status", "")
                    if status in ("ok", "success"):
                        success_count += 1
                    elif status in ("error", "exception", "timeout"):
                        error_count += 1

                    dur = entry.get("duration_s")
                    if dur is not None:
                        try:
                            durations.append(float(dur))
                        except (ValueError, TypeError):
                            pass

                    usage = entry.get("usage")
                    if isinstance(usage, dict):
                        cost = usage.get("cost_usd")
                        if cost is not None:
                            try:
                                total_cost_usd += float(cost)
                            except (ValueError, TypeError):
                                pass
        except Exception as e:
            return json.dumps({"ok": False, "error": str(e)})

        return json.dumps({
            "ok": True,
            "period_hours": period_hours,
            "total_events": total_events,
            "success_count": success_count,
            "error_count": error_count,
            "total_cost_usd": round(total_cost_usd, 4),
            "avg_duration_s": round(sum(durations) / len(durations), 2) if durations else 0.0,
            "breakdown": breakdown,
        })


def auto_gc(rome_root: Path = ROME_ROOT):
    """Startup GC: keep newest 50 + <24h, delete rest. Also resets zombie tasks. Called from entry point."""
    import sys
    # Skip automatic task reset on startup to preserve registry history
    # from dictator.ws_client import send_command_sync
    # try:
    #     send_command_sync("reset", {}, timeout=2.0)
    # except Exception:
    #     pass  # Daemon may not be up yet; safe to ignore

    legions_dir = rome_root / "legions"
    if not legions_dir.exists():
        return 0, 0

    dirs = []
    for d in legions_dir.iterdir():
        if d.is_dir() and d.name != "archive":
            try:
                dirs.append((d, d.stat().st_mtime))
            except OSError:
                pass

    dirs.sort(key=lambda x: x[1], reverse=True)
    now = time.time()
    deleted = 0
    kept = 0

    for i, (d, mtime) in enumerate(dirs):
        if i < 50 or (now - mtime) < 86400:
            kept += 1
        else:
            try:
                shutil.rmtree(d)
                deleted += 1
            except Exception:
                kept += 1

    if deleted:
        sys.stderr.write(f"ROME GC: deleted {deleted} dirs, kept {kept}\n")
    return deleted, kept

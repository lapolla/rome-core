"""Observability tools: rome_tail, rome_costs, rome_health, rome_find, senate_query."""

import collections
import json
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path

from dictator.core import mcp, ROME_ROOT, ARSENAL_PATH, run_cmd
from dictator.rome_log import log_event


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


@mcp.tool()
async def rome_costs(period_hours: int = 24) -> str:
    """Aggregates token usage and cost from rome.jsonl."""
    log_path = ROME_ROOT / "logs" / "rome.jsonl"
    if not log_path.exists():
        return json.dumps({"ok": False, "error": "Log file not found"}, indent=2)

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=period_hours)

    models = collections.defaultdict(
        lambda: {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "cost_usd": 0.0}
    )
    tool_calls = collections.Counter()
    totals = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "cost_usd": 0.0}

    try:
        with open(log_path, encoding="utf-8") as f:
            for line in f:
                try:
                    data = json.loads(line)
                    ts_str = data.get("timestamp")
                    if not ts_str:
                        continue

                    # Instructions specify ISO format like '2026-02-25T14:30:00+0000'
                    ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                    if ts < cutoff:
                        continue

                    tool_name = data.get("tool", "unknown")
                    tool_calls[tool_name] += 1

                    usage = data.get("usage")
                    if not usage or not isinstance(usage, dict):
                        continue

                    model = usage.get("model", "unknown")
                    in_t = usage.get("input_tokens", 0)
                    out_t = usage.get("output_tokens", 0)
                    tot_t = usage.get("total_tokens", 0)
                    cost = usage.get("cost_usd", 0.0)

                    models[model]["input_tokens"] += in_t
                    models[model]["output_tokens"] += out_t
                    models[model]["total_tokens"] += tot_t
                    models[model]["cost_usd"] += cost

                    totals["input_tokens"] += in_t
                    totals["output_tokens"] += out_t
                    totals["total_tokens"] += tot_t
                    totals["cost_usd"] += cost
                except (json.JSONDecodeError, ValueError):
                    continue
    except Exception as e:
        return json.dumps({"ok": False, "error": str(e)}, indent=2)

    return json.dumps(
        {
            "ok": True,
            "period_hours": period_hours,
            "models": dict(models),
            "tool_calls": dict(tool_calls),
            "totals": totals,
        },
        indent=2,
    )


@mcp.tool()
async def rome_health() -> str:
    """Check availability of all worker CLIs and core files."""
    capabilities = {}
    checks = {}

    # Check Arsenal
    try:
        with open(ARSENAL_PATH, encoding="utf-8") as f:
            arsenal = json.load(f)

        for name, info in arsenal.get("capabilities", {}).items():
            cli_args = info.get("args", [])
            if not cli_args:
                continue
            cli_name = cli_args[0]
            r = await run_cmd(f"which {cli_name}")
            available = r.get("ok", False)
            capabilities[name] = {
                "available": available,
                "path": r.get("stdout", "").strip() if available else "",
            }
        checks["arsenal_load"] = True
    except Exception as e:
        checks["arsenal_load"] = False
        checks["arsenal_error"] = str(e)

    # Check rome.jsonl
    log_path = ROME_ROOT / "logs" / "rome.jsonl"
    checks["log_exists"] = log_path.exists()
    checks["log_writable"] = os.access(log_path, os.W_OK) if log_path.exists() else False

    # Check config.json
    config_path = Path(__file__).parent / "config.json"
    checks["config_exists"] = config_path.exists()

    return json.dumps({"ok": True, "capabilities": capabilities, "checks": checks}, indent=2)


@mcp.tool()
async def rome_find(query: str, max_results: int = 10) -> str:
    """Search across all legion reports and manifests."""
    matches = []
    query_lower = query.lower()
    legions_dir = ROME_ROOT / "legions"

    if not legions_dir.exists():
        return json.dumps({"ok": False, "error": "Legions directory not found"}, indent=2)

    for task_dir in legions_dir.iterdir():
        if not task_dir.is_dir():
            continue

        task_id = task_dir.name
        timestamp = None

        # Check manifest.json
        manifest_path = task_dir / "manifest.json"
        if manifest_path.exists():
            try:
                with open(manifest_path, encoding="utf-8") as f:
                    manifest = json.load(f)
                    timestamp = manifest.get("timestamp")
                    manifest_content = json.dumps(manifest)
                    if query_lower in manifest_content.lower():
                        idx = manifest_content.lower().find(query_lower)
                        excerpt = manifest_content[max(0, idx - 50) : idx + 150]
                        matches.append(
                            {
                                "task_id": task_id,
                                "file": "manifest.json",
                                "excerpt": excerpt,
                                "timestamp": timestamp,
                            }
                        )
            except:
                pass

        if len(matches) >= max_results:
            break

        # Walk reports
        for report_file in task_dir.glob("report_*.txt"):
            try:
                content = report_file.read_text(encoding="utf-8")
                if query_lower in content.lower():
                    idx = content.lower().find(query_lower)
                    excerpt = content[max(0, idx - 50) : idx + 150].replace("\n", " ")
                    matches.append(
                        {
                            "task_id": task_id,
                            "file": report_file.name,
                            "excerpt": excerpt,
                            "timestamp": timestamp,
                        }
                    )
                    if len(matches) >= max_results:
                        break
            except:
                continue

        if len(matches) >= max_results:
            break

    return json.dumps({"ok": True, "query": query, "matches": matches[:max_results]}, indent=2)


@mcp.tool()
async def senate_query(question: str) -> str:
    """Ask the Senate which architect sector handles a concern."""
    architects_dir = ROME_ROOT / "senate" / "architects"
    if not architects_dir.exists():
        return json.dumps({"ok": False, "error": "Senate architects directory not found"}, indent=2)

    question_lower = question.lower()
    matches = []

    for md_file in sorted(architects_dir.glob("T*.md")):
        try:
            content = md_file.read_text(encoding="utf-8")
            if question_lower in content.lower():
                sector = md_file.stem  # e.g. "T0"
                matches.append({"sector": sector, "manifesto": content.strip()[:300]})
        except Exception:
            continue

    if not matches:
        # Fallback: list all sectors with their first line
        for md_file in sorted(architects_dir.glob("T*.md")):
            try:
                first_line = md_file.read_text(encoding="utf-8").split("\n")[0].strip()
                matches.append({"sector": md_file.stem, "manifesto": first_line})
            except Exception:
                continue

    return json.dumps({"ok": True, "question": question, "matches": matches}, indent=2)

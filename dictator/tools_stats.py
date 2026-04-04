"""Observability tools: rome_tail, rome_costs, rome_health, rome_find, senate_query."""

import collections
import json
import os
import time as _time
from datetime import datetime, timezone, timedelta
from pathlib import Path

from dictator.core import ROME_ROOT, ARSENAL_PATH, run_cmd
from dictator.rome_log import log_event


def register(registry):
    """Register stats and observability tools with the given native ROME registry instance."""

    @registry.tool()
    async def rome_tail(n: int = 20, task_id: str = None) -> str:
        """Show the last N entries from the ROME log, formatted for quick reading.
        Optionally filter by task_id."""
        log_path = ROME_ROOT / "logs" / "rome.jsonl"

        if not log_path.exists():
            return f"Error: Log file not found at {log_path}"

        import subprocess
        from shlex import quote
        
        try:
            if task_id:
                # Use grep to find tasks efficiently
                cmd = f"grep {quote(task_id)} {log_path} | tail -n {int(n)}"
                raw_lines = subprocess.check_output(cmd, shell=True, text=True).splitlines()
            else:
                # Simple tail for global logs
                cmd = f"tail -n {int(n)} {log_path}"
                raw_lines = subprocess.check_output(cmd, shell=True, text=True).splitlines()
        except subprocess.CalledProcessError:
            raw_lines = []
        except Exception as e:
            return f"Error executing tail/grep: {e}"

        entries = []
        for line in raw_lines:
            try:
                d = json.loads(line)
                # Handle both legacy rome_log format and new RomeEvent hydration format
                ts = d.get("timestamp") or d.get("ts", "?")
                tool = d.get("tool") or d.get("type", "?")
                status = d.get("status") or "ok"
                tid = d.get("task_id", "")
                dur = d.get("duration_s", 0.0)
                msg = d.get("message") or str(d.get("payload", ""))

                entry = f"[{ts}] {tool} {status} {dur}s {msg[:200]}"
                if tid and not task_id:
                    entry = f"[{ts}] [{tid}] {tool} {status} {dur}s {msg[:200]}"

                usage = d.get("usage")
                if isinstance(usage, dict):
                    cost = usage.get("cost_usd")
                    if cost is not None:
                        entry += f" (${cost:.4f})"

                entries.append(entry)
            except (json.JSONDecodeError, TypeError, AttributeError):
                continue

        if not entries:
            return "(no entries)"
        return f"Last {len(entries)} entries:\n" + "\n".join(entries)

    @registry.tool()
    async def rome_costs(period_hours: int = 24) -> str:
        """Aggregates token usage and cost from rome.jsonl."""
        log_path = ROME_ROOT / "logs" / "rome.jsonl"
        if not log_path.exists():
            return "Error: Log file not found"

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
            return f"Error: {e}"

        lines = [f"Period: {period_hours}h | Tasks: {sum(tool_calls.values())}"]
        lines.append(f"Tokens: {totals['input_tokens']} in / {totals['output_tokens']} out")
        if totals["cost_usd"] > 0:
            lines.append(f"Est. cost: ${totals['cost_usd']:.4f}")
        if models:
            for m, u in models.items():
                lines.append(f"  {m}: {u['input_tokens']}in/{u['output_tokens']}out ${u['cost_usd']:.4f}")
        return "\n".join(lines)

    @registry.tool()
    async def rome_health() -> str:
        """Check availability of all worker CLIs and core files."""
        import httpx
        capabilities = {}
        checks = {}

        # Check daemon HTTP health endpoint
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                resp = await client.get("http://127.0.0.1:8741/health")
                if resp.status_code == 200:
                    health = resp.json()
                    checks["daemon"] = "OK"
                    checks["daemon_uptime"] = f"{health.get('uptime_s', 0):.0f}s"
                    checks["daemon_active_tasks"] = health.get("active_tasks", 0)
                    checks["daemon_version"] = health.get("version", "?")
                else:
                    checks["daemon"] = f"HTTP {resp.status_code}"
        except Exception:
            checks["daemon"] = "OFFLINE"

        # Check Arsenal
        try:
            from dictator.tools_legion import _resolve_arsenal_paths
            with open(ARSENAL_PATH, encoding="utf-8") as f:
                arsenal = _resolve_arsenal_paths(json.load(f))

            for name, info in arsenal.get("capabilities", {}).items():
                exec_bin = info.get("exec", "")
                if exec_bin == "internal":
                    capabilities[name] = {"available": True, "path": "internal"}
                    continue
                
                cli_args = info.get("args", [])
                r = await run_cmd(f"which {exec_bin}")
                bin_ok = r.get("ok", False)
                bin_path = r.get("stdout", "").strip() if bin_ok else ""
                script = cli_args[0] if cli_args else ""
                script_ok = os.path.isfile(script) if script and script.startswith("/") else True
                available = bin_ok and script_ok
                capabilities[name] = {
                    "available": available,
                    "path": bin_path,
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

        # Build clean summary
        lines = []
        ok_caps = [n for n, c in capabilities.items() if c['available']]
        bad_caps = [n for n, c in capabilities.items() if not c['available']]
        lines.append(f"Capabilities: {len(ok_caps)}/{len(capabilities)} available")
        if bad_caps:
            lines.append(f"Unavailable: {', '.join(bad_caps)}")
        for k, v in checks.items():
            lines.append(f"{k}: {'OK' if v is True else v}")
        return '\n'.join(lines)

    @registry.tool()
    async def rome_find(query: str, max_results: int = 10) -> str:
        """Search across all legion reports and manifests."""
        matches = []
        query_lower = query.lower()
        legions_dir = ROME_ROOT / "legions"

        if not legions_dir.exists():
            return "Error: Legions directory not found"

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

        results = matches[:max_results]
        if not results:
            return f"No matches for '{query}'"
        lines = [f"Found {len(results)} matches for '{query}':"]
        for m in results:
            lines.append(f"  [{m.get('task_id','')}] {m.get('file','')}: {m.get('excerpt','')[:80]}")
        return "\n".join(lines)

    @registry.tool()
    async def senate_query(question: str) -> str:
        """Ask the Senate which architect sector handles a concern."""
        architects_dir = ROME_ROOT / "senate" / "architects"
        if not architects_dir.exists():
            return "Error: Senate architects directory not found"

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

        if not matches:
            return f"No sectors matched '{question}'"
        lines = [f"Sectors matching '{question}':"]
        for m in matches:
            lines.append(f"  {m['sector']}: {m['manifesto'][:100]}")
        return "\n".join(lines)

    @registry.tool()
    async def senate_brain(sector_id: int, mission: str) -> str:
        """Spawn a Senate brain — binds an LLM soul to a sector manifesto and executes a mission."""
        manifesto_path = ROME_ROOT / "senate" / "architects" / f"T{sector_id}.md"
        if not manifesto_path.exists():
            return f"Error: Sector T{sector_id} has no manifesto."

        manifesto = manifesto_path.read_text(encoding="utf-8")

        imperial_prompt = (
            f"YOU ARE THE ARCHITECT FOR ROME SECTOR {sector_id}.\n"
            f"YOUR MANIFESTO:\n{manifesto}\n\n"
            f"YOUR MISSION:\n{mission}\n\n"
            "Analyze the mission in the context of your sector's manifesto. "
            "Provide a concrete action plan or answer. Be specific and actionable."
        )

        from dictator.tools_legion import _execute_legion_impl
        task_id = f"senate_T{sector_id}_{int(_time.time())}"
        result = await _execute_legion_impl(
            task_id=task_id,
            capability="GEMINI",
            args=[imperial_prompt],
            ctx=None,
        )
        return json.dumps(result, indent=2)

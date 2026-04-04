"""Prefect tools: execute_prefect — autonomous domain-scoped agents."""

import json
import time
from pathlib import Path

from dictator.core import ROME_ROOT


def register(registry):
    """Register Prefect tools with the given native ROME registry instance."""

    @registry.tool()
    async def execute_prefect(domain: str, task: str, timeout_s: int = 600) -> str:
        """Execute an autonomous prefect agent with domain-scoped MCP tool access."""
        from dictator.tools_legion import _execute_legion_impl
        config_path = Path(__file__).parent / "prefect_domains.json"

        try:
            config = json.loads(config_path.read_text())
        except FileNotFoundError:
            return json.dumps({"ok": False, "error": f"Config not found: {config_path}"})

        domain_config = config.get(domain)
        if not domain_config:
            available = ", ".join(config.keys())
            return json.dumps({"ok": False, "error": f"Domain '{domain}' not found. Available: {available}"})

        tools = domain_config.get("tools", [])
        system = domain_config.get("system", "")
        prompt = system.replace("{tools}", ", ".join(tools))

        # Pre-flight: require tool declaration before execution
        if "*" not in tools:
            prompt += "\n\nPRE-FLIGHT: Before executing, declare which tools you will use: [TOOLS: tool1, tool2, ...]"

        full_prompt = f"{prompt}\n\nTask: {task}"

        task_id = f"prefect_{domain}_{int(time.time())}"

        result = await _execute_legion_impl(
            task_id=task_id,
            capability="GEMINI",
            args=[full_prompt],
            ctx=None,
        )
        result_json = json.dumps(result, indent=2)

        # Post-run audit (Phase 13) — check for tool usage outside whitelist
        if "*" not in tools:
            try:
                import re
                task_dir = ROME_ROOT / "legions" / task_id
                report_path = task_dir / f"report_{task_id}.txt"
                if report_path.exists():
                    report_text = report_path.read_text()
                    # Get all registered tool names
                    all_tools = list(registry.tools.keys())
                    allowed = set(tools)
                    violations = set()
                    for t in all_tools:
                        if t in allowed:
                            continue
                        # Check for actual tool call patterns, not just name mentions
                        patterns = [
                            rf'"name"\s*:\s*"{t}"',        # JSON tool call
                            rf'tool_use.*{t}',              # Claude tool_use
                            rf'function_call.*{t}',         # function_call style
                            rf'Calling {t}',                # progress log
                        ]
                        for pat in patterns:
                            if re.search(pat, report_text):
                                violations.add(t)
                                break
                    if violations:
                        result = json.loads(result_json)
                        result["ok"] = False
                        result["audit_violations"] = sorted(violations)
                        result["error"] = f"SECURITY VIOLATION: Prefect used unauthorized tools: {', '.join(sorted(violations))}"
                        if "summary" in result:
                            result["summary"] = result["summary"].replace("[OK]", "[FAIL]")
                        result_json = json.dumps(result, indent=2)
            except Exception:
                pass

        return result_json

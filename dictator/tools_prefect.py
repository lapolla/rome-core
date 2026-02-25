"""Prefect tools: execute_prefect — autonomous domain-scoped agents."""

import json
import time
from pathlib import Path

from dictator.core import mcp
from dictator.tools_legion import execute_legion


@mcp.tool()
async def execute_prefect(domain: str, task: str, timeout_s: int = 600) -> str:
    """Execute an autonomous prefect agent with domain-scoped MCP tool access."""
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
    full_prompt = f"{prompt}\n\nTask: {task}"

    task_id = f"prefect_{domain}_{int(time.time())}"

    return await execute_legion(
        task_id=task_id,
        capability="GEMINI",
        args=[full_prompt],
    )

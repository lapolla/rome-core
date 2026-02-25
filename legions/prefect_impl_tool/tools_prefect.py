import json
import time
from pathlib import Path
from dictator.core import mcp, ROME_ROOT
from dictator.tools_legion import execute_legion

@mcp.tool()
async def execute_prefect(domain: str, task: str, timeout_s: int = 600) -> str:
    """Execute an autonomous prefect agent with domain-scoped MCP tool access."""
    config_path = Path(__file__).parent / 'prefect_domains.json'
    
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
    except FileNotFoundError:
        return json.dumps({"error": f"Configuration file not found at {config_path}"})

    domain_config = config.get(domain)
    if not domain_config:
        return json.dumps({"error": f"Domain '{domain}' not found in configuration"})

    tools = domain_config.get("tools", [])
    system_prompt = domain_config.get("system_prompt", "")
    
    formatted_prompt = system_prompt.replace("{tools}", ", ".join(tools))
    full_prompt = f"{formatted_prompt}

Task: {task}"
    
    task_id = f"prefect_{domain}_{int(time.time())}"
    
    result = await execute_legion(
        task_id=task_id,
        capability='GEMINI',
        args=[full_prompt]
    )
    
    return result

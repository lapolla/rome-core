#!/usr/bin/env python3
"""
ROME Results MCP Server.
Allows agents to submit their final results directly to the ROME daemon via WebSocket.
This eliminates the 'empty report bug' caused by stdout/file redirection race conditions.
"""

import os
import sys
import asyncio
import json
from mcp.server.fastmcp import FastMCP

# Ensure project root is on path for dictator imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dictator.ws_client import submit_agent_result_async

mcp = FastMCP("rome-results")

@mcp.tool()
async def send_result(content: str, task_id: str | None = None, token: str | None = None) -> str:
    """
    Submits the final result/report for the current task to the ROME daemon.
    
    Args:
        content: The full text content of the result or report.
        task_id: Optional task ID. If omitted, uses ROME_TASK_ID from environment.
        token: Optional auth token. If omitted, uses ROME_TASK_TOKEN from environment.
    """
    # Fallback to environment variables injected by the daemon
    effective_task_id = task_id or os.environ.get("ROME_TASK_ID")
    effective_token = token or os.environ.get("ROME_TASK_TOKEN")
    
    if not effective_task_id:
        return "Error: No task_id provided and ROME_TASK_ID not found in environment."
    
    try:
        result = await submit_agent_result_async(
            task_id=effective_task_id,
            content=content,
            token=effective_token
        )
        return json.dumps(result, indent=2)
    except Exception as e:
        return f"Error submitting result via WebSocket: {str(e)}"

if __name__ == "__main__":
    mcp.run()

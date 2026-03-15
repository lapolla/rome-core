"""
WebSocket tools: ws_send.
Standardized interface for sending commands to the ROME Daemon.
"""

import json
from dictator.ws_client import send_command_async, submit_agent_result_async

def register(mcp):
    """Register WebSocket tools with the given FastMCP instance."""

    @mcp.tool()
    async def ws_send(command: str, payload: dict = {}, timeout: float = 5.0) -> str:
        """
        Sends a command to the ROME Daemon via WebSocket and waits for a response.
        Standard commands: list, status, dispatch, fire_and_forget.
        """
        result = await send_command_async(command, payload, timeout)
        return json.dumps(result)

    @mcp.tool()
    async def rome_submit_result(task_id: str, content: str) -> str:
        """
        Submits the agent's result for a given task.
        """
        result = await submit_agent_result_async(task_id, content)
        return json.dumps(result)

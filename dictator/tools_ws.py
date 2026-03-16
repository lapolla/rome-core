"""
WebSocket tools: ws_send, rome_await.
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
    async def rome_await(task_ids: list[str], timeout: float = 120.0, include_reports: bool = False) -> str:
        """
        Block until all specified tasks complete. Event-driven — no polling.
        Returns status + optional report content for each task.
        Uses the daemon's EventBus internally (subscribe → filter complete events → resolve).
        """
        result = await send_command_async("await", {
            "task_ids": task_ids,
            "include_reports": include_reports,
        }, timeout=timeout)
        return json.dumps(result)

    @mcp.tool()
    async def rome_submit_result(task_id: str, content: str) -> str:
        """
        Submits the agent's result for a given task.
        """
        result = await submit_agent_result_async(task_id, content)
        return json.dumps(result)

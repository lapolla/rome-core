"""Event emission helper — bridges stdio MCP tools to daemon event bus via WS."""
import asyncio
import os
from dictator.core import event_bus, task_registry
from dictator.events import emit_complete, emit_error, emit_cost_update


async def emit_events(ok, task_id, task_dir, result, usage):
    rp = result.get('report_path') or str(task_dir / f'report_{task_id}.txt')
    status = "SUCCESS" if ok else "FAILED"

    # Local path: running inside daemon process (shared memory)
    if os.environ.get("ROME_DAEMON"):
        try:
            if ok and usage:
                await emit_cost_update(event_bus, task_id, usage)
                task_registry.update_usage(task_id, usage)
            await emit_complete(event_bus, task_id, status, rp, usage)
            task_registry.complete(task_id, status, rp)
        except Exception:
            pass
        return

    # Remote path: running as stdio MCP — relay via WS
    from dictator.ws_client import send_event
    send_event("complete", task_id, {"status": status, "report_path": rp, "usage": usage or {}})


def emit_dispatch_start_ws(task_id: str, capability: str) -> None:
    from dictator.ws_client import send_event
    send_event("dispatch_start", task_id, {"capability": capability})


def emit_progress_ws(task_id: str, percent: int, message: str) -> None:
    from dictator.ws_client import send_event
    send_event("progress", task_id, {"percent": percent, "message": message})

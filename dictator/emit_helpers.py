"""Event emission helper — bridges stdio MCP tools to daemon event bus via HTTP."""
import asyncio
import json
import urllib.request
from dictator.core import event_bus, task_registry
from dictator.events import emit_complete, emit_error, emit_cost_update

DAEMON_URL = "http://127.0.0.1:8741"


def _post_event(event_type: str, task_id: str, payload: dict) -> None:
    """Fire-and-forget HTTP POST to daemon's event relay."""
    try:
        data = json.dumps({"type": event_type, "task_id": task_id, "payload": payload}).encode()
        req = urllib.request.Request(f"{DAEMON_URL}/api/event", data=data,
                                     headers={"Content-Type": "application/json"}, method="POST")
        urllib.request.urlopen(req, timeout=2)
    except Exception:
        pass


async def emit_events(ok, task_id, task_dir, result, usage):
    rp = result.get('report_path') or str(task_dir / f'report_{task_id}.txt')
    status = "SUCCESS" if ok else "FAILED"

    # Local event bus (works when running inside daemon)
    try:
        if ok and usage:
            await emit_cost_update(event_bus, task_id, usage)
            task_registry.update_usage(task_id, usage)
        await emit_complete(event_bus, task_id, status, rp, usage)
    except Exception:
        pass
    task_registry.complete(task_id, status, rp)

    # HTTP bridge to daemon (works when running as stdio MCP)
    _post_event("complete", task_id, {"status": status, "report_path": rp, "usage": usage or {}})


def emit_dispatch_start_http(task_id: str, capability: str) -> None:
    """Notify daemon of a new dispatch via HTTP."""
    _post_event("dispatch_start", task_id, {"capability": capability})

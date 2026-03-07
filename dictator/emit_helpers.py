"""Event emission helper for tools_legion — avoids inline bloat."""
import asyncio
from dictator.core import event_bus, task_registry
from dictator.events import emit_complete, emit_error, emit_cost_update


def emit_events(ok, task_id, task_dir, result, usage):
    rp = result.get('report_path') or str(task_dir / f'report_{task_id}.txt')
    if ok:
        if usage:
            asyncio.ensure_future(emit_cost_update(event_bus, task_id, usage))
            task_registry.update_usage(task_id, usage)
        asyncio.ensure_future(emit_complete(event_bus, task_id, "SUCCESS", rp, usage))
    else:
        asyncio.ensure_future(emit_error(event_bus, task_id, result.get("error", "")))
    task_registry.complete(task_id, "SUCCESS" if ok else "FAILED", rp)

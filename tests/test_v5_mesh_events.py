import asyncio
import time
import pytest
from pathlib import Path
from dictator.events import EventBus, TaskRegistry, RomeEvent, emit_dispatch_start, emit_complete
from aaak import AAAK

# ── 1. Event Bus: Sovereignty & Concurrency ───────────────────────────

@pytest.mark.asyncio
async def test_event_bus_publish_subscribe_flow():
    """Verify that events flow from publisher to multiple subscribers."""
    bus = EventBus()
    
    sub1_id, q1 = await bus.subscribe()
    sub2_id, q2 = await bus.subscribe()
    
    event = RomeEvent(
        type="test_event",
        task_id="task-123",
        ts=time.time(),
        sequence=0,
        source="test_source",
        payload={"data": "signal"}
    )
    
    published = await bus.publish(event)
    
    # Verify sequence was updated
    assert published.sequence == 1
    
    # Both subscribers should receive it
    ev1 = await q1.get()
    ev2 = await q2.get()
    
    assert ev1.type == "test_event"
    assert ev1.sequence == 1
    assert ev2.sequence == 1
    
    await bus.unsubscribe(sub1_id)
    await bus.unsubscribe(sub2_id)

@pytest.mark.asyncio
async def test_event_bus_bounded_queue_safety():
    """Verify that the bus doesn't block if a subscriber is slow (eviction)."""
    # Max size of 1
    bus = EventBus(max_queue_size=1)
    sub_id, q = await bus.subscribe()
    
    # Publish 3 events
    for i in range(3):
        await bus.publish(RomeEvent("type", "id", time.time(), 0, "src", {"i": i}))
        
    # Queue should only have the LAST event (or be full but not blocked)
    # The _enqueue logic drops the oldest if full.
    assert q.qsize() == 1
    last_ev = await q.get()
    assert last_ev.payload["i"] == 2


# ── 2. Task Registry: Hydration & Lifecycle ───────────────────────────

def test_task_registry_lifecycle():
    """Verify registration, progress, and terminal status."""
    reg = TaskRegistry()
    
    # 1. Register
    task = reg.register("job-1", "GEMINI")
    assert task["status"] == "registered"
    assert task["capability"] == "GEMINI"
    
    # 2. Update Progress
    reg.update_progress("job-1", 50, "thinking")
    task = reg.get("job-1")
    assert task["status"] == "running"
    assert task["progress_percent"] == 50
    
    # 3. Complete
    reg.complete("job-1", "completed", "/tmp/report.txt")
    task = reg.get("job-1")
    assert task["status"] == "completed"
    assert task["progress_percent"] == 100

def test_task_registry_waste_tracking():
    """Verify token waste accumulation."""
    reg = TaskRegistry()
    reg.add_waste(100)
    reg.add_waste(250)
    assert reg.get_waste() == 350


# ── 3. Fact Broadcast: The V5 Mesh Pulse ──────────────────────────────

@pytest.mark.asyncio
async def test_fact_broadcast_integration(tmp_path):
    """Verify that AAAK post_result triggers a facts_broadcast event."""
    bus = EventBus()
    a = AAAK(store_dir=tmp_path, prefix="broadcast_test")
    
    sub_id, q = await bus.subscribe()
    
    # Mock the broadcast_fn that the daemon would provide
    async def mock_daemon_broadcast(event_dict):
        # Convert dict back to RomeEvent for the bus
        ev = RomeEvent(
            type=event_dict["type"],
            task_id=None,
            ts=time.time(),
            sequence=0,
            source="aaak",
            payload=event_dict["payload"]
        )
        await bus.publish(ev)

    # Simulate a successful task result
    manifest = {
        "status": "SUCCESS",
        "task_id": "task-abc",
        "usage": {"total_tokens": 50},
        "artifacts": []
    }
    
    # The hook call
    a.post_result(manifest, task_description="Fixed the bug", broadcast_fn=mock_daemon_broadcast)
    
    # Wait for the broadcast event on the bus
    # Note: post_result is synchronous in the current implementation, but 
    # mock_daemon_broadcast is async. In real life, the daemon's handle_submit_result
    # would await this.
    
    # Give it a tiny bit of time if needed, but here it's concurrent
    ev = await asyncio.wait_for(q.get(), timeout=1.0)
    
    assert ev.type == "facts_broadcast"
    assert ev.payload["fact"]["task"] == "Fixed the bug"
    assert ev.payload["fact"]["status"] == "SUCCESS"

# ── 4. Mesh Hydration (Log Replay) ────────────────────────────────────

def test_task_registry_hydration(tmp_path):
    """Verify that the registry can rebuild state from a JSONL log."""
    log_file = tmp_path / "rome.jsonl"
    
    # Create fake log entries
    events = [
        {"type": "dispatch_start", "task_id": "t1", "ts": time.time(), "payload": {"capability": "GEMINI"}},
        {"type": "progress", "task_id": "t1", "ts": time.time(), "payload": {"percent": 50, "message": "working"}},
        {"type": "complete", "task_id": "t1", "ts": time.time(), "payload": {"status": "SUCCESS", "report_path": "/tmp/r.txt"}}
    ]
    
    with open(log_file, "w") as f:
        for ev in events:
            f.write(json.dumps(ev) + "\n")
            
    reg = TaskRegistry()
    count = reg.hydrate_from_log(log_file)
    
    assert count == 3
    task = reg.get("t1")
    assert task is not None
    assert task["status"] == "SUCCESS"
    assert task["progress_percent"] == 100

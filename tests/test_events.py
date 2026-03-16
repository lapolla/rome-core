"""Tests for EventBus and TaskRegistry — the stateful core of ROME."""

import asyncio
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from dictator.events import EventBus, TaskRegistry, RomeEvent


# ── EventBus ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_eventbus_publish_subscribe():
    """Subscriber receives published events."""
    bus = EventBus(max_queue_size=100)
    sid, queue = await bus.subscribe()

    event = RomeEvent(type="test", task_id="t1", ts=time.time(), sequence=0, source="test", payload={"k": "v"})
    published = await bus.publish(event)

    assert published.sequence > 0
    received = queue.get_nowait()
    assert received.type == "test"
    assert received.task_id == "t1"
    assert received.payload == {"k": "v"}

    await bus.unsubscribe(sid)


@pytest.mark.asyncio
async def test_eventbus_multiple_subscribers():
    """All subscribers receive the same event."""
    bus = EventBus(max_queue_size=100)
    sid1, q1 = await bus.subscribe()
    sid2, q2 = await bus.subscribe()

    event = RomeEvent(type="broadcast", task_id="t2", ts=time.time(), sequence=0, source="test", payload={})
    await bus.publish(event)

    assert q1.get_nowait().type == "broadcast"
    assert q2.get_nowait().type == "broadcast"

    await bus.unsubscribe(sid1)
    await bus.unsubscribe(sid2)


@pytest.mark.asyncio
async def test_eventbus_unsubscribe_stops_delivery():
    """After unsubscribe, no more events are received."""
    bus = EventBus(max_queue_size=100)
    sid, queue = await bus.subscribe()
    await bus.unsubscribe(sid)

    event = RomeEvent(type="ghost", task_id="t3", ts=time.time(), sequence=0, source="test", payload={})
    await bus.publish(event)

    assert queue.empty()


@pytest.mark.asyncio
async def test_eventbus_bounded_queue_eviction():
    """When queue is full, oldest events are evicted (not deadlock)."""
    bus = EventBus(max_queue_size=3)
    sid, queue = await bus.subscribe()

    for i in range(5):
        await bus.publish(RomeEvent(type="flood", task_id=f"t{i}", ts=time.time(), sequence=0, source="test", payload={"i": i}))

    # Queue should have at most 3 items, not deadlocked
    items = []
    while not queue.empty():
        items.append(queue.get_nowait())
    assert len(items) <= 3

    await bus.unsubscribe(sid)


@pytest.mark.asyncio
async def test_eventbus_sequence_monotonic():
    """Sequence numbers are monotonically increasing."""
    bus = EventBus(max_queue_size=100)
    sid, queue = await bus.subscribe()

    seqs = []
    for _ in range(5):
        e = await bus.publish(RomeEvent(type="seq", task_id="s", ts=0, sequence=0, source="t", payload={}))
        seqs.append(e.sequence)

    assert seqs == sorted(seqs)
    assert len(set(seqs)) == 5  # all unique

    await bus.unsubscribe(sid)


# ── TaskRegistry ──────────────────────────────────────────────────────

def test_registry_register_and_get():
    reg = TaskRegistry(ttl_seconds=3600)
    task = reg.register("task-1", "GEMINI")
    assert task["task_id"] == "task-1"
    assert task["capability"] == "GEMINI"
    assert task["status"] == "registered"

    got = reg.get("task-1")
    assert got is not None
    assert got["task_id"] == "task-1"


def test_registry_update_progress():
    reg = TaskRegistry(ttl_seconds=3600)
    reg.register("task-2", "SAFE_SHELL")
    updated = reg.update_progress("task-2", 50.0, "halfway")
    assert updated["progress_percent"] == 50.0
    assert updated["progress_message"] == "halfway"
    assert updated["status"] == "running"


def test_registry_complete():
    reg = TaskRegistry(ttl_seconds=3600)
    reg.register("task-3", "CODEX")
    completed = reg.complete("task-3", "completed", "/tmp/report.txt")
    assert completed["status"] == "completed"
    assert completed["progress_percent"] == 100.0
    assert completed["report_path"] == "/tmp/report.txt"


def test_registry_get_nonexistent():
    reg = TaskRegistry(ttl_seconds=3600)
    assert reg.get("nonexistent") is None


def test_registry_update_nonexistent():
    reg = TaskRegistry(ttl_seconds=3600)
    assert reg.update_progress("ghost", 50, "nope") is None
    assert reg.complete("ghost", "failed", None) is None


def test_registry_get_all():
    reg = TaskRegistry(ttl_seconds=3600)
    reg.register("a", "GEMINI")
    reg.register("b", "CODEX")
    all_tasks = reg.get_all()
    assert "a" in all_tasks
    assert "b" in all_tasks
    assert len(all_tasks) == 2


def test_registry_clear_finished():
    reg = TaskRegistry(ttl_seconds=3600)
    reg.register("running-1", "GEMINI")
    reg.update_progress("running-1", 50, "busy")
    reg.register("done-1", "CODEX")
    reg.complete("done-1", "completed", None)

    cleared = reg.clear_finished()
    assert cleared == 1
    assert reg.get("running-1") is not None
    assert reg.get("done-1") is None


def test_registry_clear_all():
    reg = TaskRegistry(ttl_seconds=3600)
    reg.register("x", "GEMINI")
    reg.register("y", "CODEX")
    cleared = reg.clear_all()
    assert cleared == 2
    assert reg.get_all() == {}


def test_registry_sweep_orphans():
    reg = TaskRegistry(ttl_seconds=3600)
    reg.register("orphan-1", "GEMINI")
    reg.update_progress("orphan-1", 30, "running")
    reg.register("orphan-2", "CODEX")  # still registered

    swept = reg.sweep_orphans()
    assert swept == 2
    assert reg.get("orphan-1")["status"] == "failed"
    assert reg.get("orphan-2")["status"] == "failed"


def test_registry_waste_tracking():
    reg = TaskRegistry(ttl_seconds=3600)
    assert reg.get_waste() == 0
    reg.add_waste(1000)
    reg.add_waste(500)
    assert reg.get_waste() == 1500


def test_registry_snapshot_isolation():
    """get() returns a copy, not a reference — mutations don't leak."""
    reg = TaskRegistry(ttl_seconds=3600)
    reg.register("iso", "GEMINI")
    snap = reg.get("iso")
    snap["status"] = "HACKED"
    assert reg.get("iso")["status"] == "registered"

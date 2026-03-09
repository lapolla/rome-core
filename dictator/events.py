from __future__ import annotations

import asyncio
import threading
import time
import uuid
from dataclasses import dataclass, replace
from typing import Any


QUEUE_MAXSIZE = 1000
TASK_TTL_SECONDS = 3600


@dataclass(slots=True)
class RomeEvent:
    type: str
    task_id: str | None
    ts: float
    sequence: int
    source: str
    payload: dict[str, Any]


class EventBus:
    def __init__(self, max_queue_size: int = QUEUE_MAXSIZE, source: str = "rome") -> None:
        self._max_queue_size = max_queue_size
        self._source = source
        self._subscribers: dict[str, asyncio.Queue[RomeEvent]] = {}
        self._subscribers_lock = asyncio.Lock()
        self._sequence_lock = threading.Lock()
        self._sequence = 0

    async def publish(self, event: RomeEvent) -> RomeEvent:
        published = replace(event, sequence=self._next_sequence())
        async with self._subscribers_lock:
            queues = list(self._subscribers.values())
        for queue in queues:
            self._enqueue(queue, published)
        return published

    async def subscribe(self) -> tuple[str, asyncio.Queue[RomeEvent]]:
        queue: asyncio.Queue[RomeEvent] = asyncio.Queue(maxsize=self._max_queue_size)
        subscriber_id = uuid.uuid4().hex
        async with self._subscribers_lock:
            self._subscribers[subscriber_id] = queue
        return subscriber_id, queue

    async def unsubscribe(self, subscriber_id: str) -> None:
        async with self._subscribers_lock:
            self._subscribers.pop(subscriber_id, None)

    def _next_sequence(self) -> int:
        with self._sequence_lock:
            self._sequence += 1
            return self._sequence

    @staticmethod
    def _enqueue(queue: asyncio.Queue[RomeEvent], event: RomeEvent) -> None:
        while queue.full():
            try:
                queue.get_nowait()
            except asyncio.QueueEmpty:
                break
        try:
            queue.put_nowait(event)
        except asyncio.QueueFull:
            # Another producer may have refilled the queue after eviction.
            EventBus._enqueue(queue, event)


async def emit_dispatch_start(bus: EventBus, task_id: str, capability: str) -> RomeEvent:
    return await bus.publish(
        RomeEvent(
            type="dispatch_start",
            task_id=task_id,
            ts=time.time(),
            sequence=0,
            source=bus._source,
            payload={"capability": capability},
        )
    )


async def emit_progress(bus: EventBus, task_id: str, percent: float, message: str) -> RomeEvent:
    return await bus.publish(
        RomeEvent(
            type="progress",
            task_id=task_id,
            ts=time.time(),
            sequence=0,
            source=bus._source,
            payload={"percent": percent, "message": message},
        )
    )


async def emit_complete(
    bus: EventBus,
    task_id: str,
    status: str,
    report_path: str | None,
    usage: dict[str, Any] | None,
) -> RomeEvent:
    return await bus.publish(
        RomeEvent(
            type="complete",
            task_id=task_id,
            ts=time.time(),
            sequence=0,
            source=bus._source,
            payload={
                "status": status,
                "report_path": report_path,
                "usage": dict(usage or {}),
            },
        )
    )


async def emit_error(bus: EventBus, task_id: str, message: str) -> RomeEvent:
    return await bus.publish(
        RomeEvent(
            type="error",
            task_id=task_id,
            ts=time.time(),
            sequence=0,
            source=bus._source,
            payload={"message": message},
        )
    )


async def emit_cost_update(bus: EventBus, task_id: str, usage: dict[str, Any] | None) -> RomeEvent:
    return await bus.publish(
        RomeEvent(
            type="cost_update",
            task_id=task_id,
            ts=time.time(),
            sequence=0,
            source=bus._source,
            payload={"usage": dict(usage or {})},
        )
    )


class TaskRegistry:
    def __init__(self, ttl_seconds: int = TASK_TTL_SECONDS) -> None:
        self._ttl_seconds = ttl_seconds
        self._tasks: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()

    def register(self, task_id: str, capability: str) -> dict[str, Any]:
        now = time.time()
        with self._lock:
            self._cleanup_locked(now)
            task = {
                "task_id": task_id,
                "capability": capability,
                "status": "registered",
                "progress_percent": 0.0,
                "progress_message": "",
                "usage": {},
                "report_path": None,
                "created_at": now,
                "updated_at": now,
            }
            self._tasks[task_id] = task
            return self._snapshot(task)

    def update_progress(self, task_id: str, percent: float, message: str) -> dict[str, Any] | None:
        with self._lock:
            self._cleanup_locked()
            task = self._tasks.get(task_id)
            if task is None:
                return None
            task["progress_percent"] = percent
            task["progress_message"] = message
            task["status"] = "running"
            task["updated_at"] = time.time()
            return self._snapshot(task)

    def update_usage(self, task_id: str, usage: dict[str, Any] | None) -> dict[str, Any] | None:
        with self._lock:
            self._cleanup_locked()
            task = self._tasks.get(task_id)
            if task is None:
                return None
            task["usage"] = dict(usage or {})
            task["updated_at"] = time.time()
            return self._snapshot(task)

    def complete(self, task_id: str, status: str, report_path: str | None) -> dict[str, Any] | None:
        with self._lock:
            self._cleanup_locked()
            task = self._tasks.get(task_id)
            if task is None:
                return None
            task["status"] = status
            task["progress_percent"] = 100.0
            task["report_path"] = report_path
            task["updated_at"] = time.time()
            return self._snapshot(task)

    def get(self, task_id: str) -> dict[str, Any] | None:
        with self._lock:
            self._cleanup_locked()
            task = self._tasks.get(task_id)
            return self._snapshot(task) if task is not None else None

    def clear_finished(self) -> int:
        """Remove all non-active tasks. Returns count removed."""
        with self._lock:
            to_remove = [
                tid for tid, t in self._tasks.items()
                if t.get("status") not in ("registered", "running")
            ]
            for tid in to_remove:
                self._tasks.pop(tid, None)
            return len(to_remove)

    def clear_all(self) -> int:
        """Remove all tasks regardless of status. Returns count removed."""
        with self._lock:
            count = len(self._tasks)
            self._tasks.clear()
            return count

    def get_all(self) -> dict[str, dict[str, Any]]:
        with self._lock:
            self._cleanup_locked()
            return {task_id: self._snapshot(task) for task_id, task in self._tasks.items()}

    def _cleanup_locked(self, now: float | None = None) -> None:
        cutoff = time.time() if now is None else now
        expired = []
        for task_id, task in self._tasks.items():
            status = str(task.get("status", "")).upper()
            
            if status in ("SUCCESS", "OK"):
                ttl = 30  # Remove successful tasks quickly (30 seconds)
            elif status in ("FAILED", "ERROR", "TIMEOUT", "ERR"):
                ttl = 86400  # Keep failed tasks for 24 hours
            else:
                ttl = self._ttl_seconds  # Default 1 hour for active/pending tasks
                
            age = cutoff - float(task.get("updated_at", task.get("created_at", cutoff)))
            if age > ttl:
                expired.append(task_id)

        for task_id in expired:
            self._tasks.pop(task_id, None)

    @staticmethod
    def _snapshot(task: dict[str, Any]) -> dict[str, Any]:
        snapshot = dict(task)
        snapshot["usage"] = dict(task.get("usage", {}))
        return snapshot


__all__ = [
    "EventBus",
    "QUEUE_MAXSIZE",
    "RomeEvent",
    "TASK_TTL_SECONDS",
    "TaskRegistry",
    "emit_complete",
    "emit_cost_update",
    "emit_dispatch_start",
    "emit_error",
    "emit_progress",
]

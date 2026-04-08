from __future__ import annotations

import asyncio
import threading
import time
import uuid
import logging
import json
from pathlib import Path
from dataclasses import dataclass, replace
from typing import Any

from dictator.rome_log import log_event


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

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "task_id": self.task_id,
            "ts": self.ts,
            "sequence": self.sequence,
            "source": self.source,
            "payload": self.payload,
        }


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
        log_event(
            tool=published.type,
            task_id=published.task_id,
            status=published.payload.get("status", ""),
            message=published.payload.get("message", ""),
            usage=published.payload.get("usage"),
            sequence=published.sequence
        )
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
        for _ in range(3):  # bounded retry, no recursion
            while queue.full():
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    break
            try:
                queue.put_nowait(event)
                return
            except asyncio.QueueFull:
                continue
        # Drop event after 3 failed attempts rather than infinite loop


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
    report: str | None = None,
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
                "report": report or "",
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


async def emit_capability_status(bus: EventBus, capability: str, available: bool, reason: str = '') -> RomeEvent:
    return await bus.publish(
        RomeEvent(
            type="capability_status",
            task_id=None,
            ts=time.time(),
            sequence=0,
            source=bus._source,
            payload={"capability": capability, "available": available, "reason": reason},
        )
    )


async def emit_system_status(bus: EventBus, active_tasks: int, uptime_s: float) -> RomeEvent:
    return await bus.publish(
        RomeEvent(
            type="system_status",
            task_id=None,
            ts=time.time(),
            sequence=0,
            source=bus._source,
            payload={"active_tasks": active_tasks, "uptime_s": uptime_s},
        )
    )


async def emit_facts_broadcast(bus: EventBus, task_id: str | None, fact: dict[str, Any]) -> RomeEvent:
    return await bus.publish(
        RomeEvent(
            type="facts_broadcast",
            task_id=task_id,
            ts=time.time(),
            sequence=0,
            source=bus._source,
            payload={"fact": fact},
        )
    )


class TaskRegistry:
    def __init__(self, ttl_seconds: int = TASK_TTL_SECONDS) -> None:
        self._ttl_seconds = ttl_seconds
        self._tasks: dict[str, dict[str, Any]] = {}
        self._session_waste_tokens = 0
        self._replay_event_count = 0
        self._lock = threading.Lock()

    def add_waste(self, tokens: int) -> int:
        with self._lock:
            self._session_waste_tokens += tokens
            return self._session_waste_tokens

    def get_waste(self) -> int:
        with self._lock:
            return self._session_waste_tokens

    def increment_replay_event_count(self) -> None:
        with self._lock:
            self._replay_event_count += 1

    def get_replay_event_count(self) -> int:
        with self._lock:
            return self._replay_event_count

    def register(self, task_id: str, capability: str, timestamp: float | None = None, parent_task_id: str | None = None, token: str | None = None) -> dict[str, Any]:
        now = time.time() if timestamp is None else timestamp
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
                "parent_task_id": parent_task_id,
                "token": token or str(uuid.uuid4()),
            }
            self._tasks[task_id] = task
            return self._snapshot(task)

    _TERMINAL_STATUSES = {"completed", "SUCCESS", "FAILED", "failed", "cancelled", "error"}

    def update_progress(self, task_id: str, percent: float, message: str) -> dict[str, Any] | None:
        with self._lock:
            self._cleanup_locked()
            task = self._tasks.get(task_id)
            if task is None:
                return None
            if task.get("status") in self._TERMINAL_STATUSES:
                return None  # signal caller: progress dropped, task already terminal
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

    def update_task(self, task_id: str, updates: dict[str, Any]) -> dict[str, Any] | None:
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                return None
            task.update(updates)
            task["updated_at"] = time.time()
            return self._snapshot(task)

    def complete(self, task_id: str, status: str, report_path: str | None, report: str | None = None) -> dict[str, Any] | None:
        with self._lock:
            self._cleanup_locked()
            task = self._tasks.get(task_id)
            if task is None:
                return None
            task["status"] = status
            task["progress_percent"] = 100.0
            task["report_path"] = report_path
            if report is not None:
                task["report"] = report
            task["updated_at"] = time.time()
            task["completed_at"] = time.time()
            return self._snapshot(task)

    def get(self, task_id: str) -> dict[str, Any] | None:
        with self._lock:
            self._cleanup_locked()
            task = self._tasks.get(task_id)
            return self._snapshot(task) if task is not None else None

    def sweep_orphans(self) -> int:
        """Mark any registered/running tasks as failed (called on daemon startup)."""
        swept = 0
        with self._lock:
            for task in self._tasks.values():
                if task.get("status") in {"registered", "running"}:
                    task["status"] = "failed"
                    task["progress_message"] = "Daemon restarted"
                    task["updated_at"] = time.time()
                    swept += 1
        return swept

    def remove(self, task_id: str) -> bool:
        """Remove a single task by ID. Returns True if it existed."""
        with self._lock:
            return self._tasks.pop(task_id, None) is not None

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

    def hydrate_from_log(self, log_path: Path, bus: EventBus | None = None) -> int:
        """Hydrate registry state from a ROME JSONL log file."""
        if not log_path.exists():
            return 0

        count = 0
        with open(log_path, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                    # Support both legacy rome_log format and new RomeEvent hydration format
                    ev_type = data.get("type") or data.get("tool")
                    tid = data.get("task_id")
                    ts_raw = data.get("ts") or data.get("timestamp")
                    payload = data.get("payload", data) # for legacy, use whole dict as payload

                    # Convert ISO timestamp to float if needed
                    if isinstance(ts_raw, str):
                        try:
                            from datetime import datetime
                            ts = datetime.fromisoformat(ts_raw.replace("Z", "+00:00")).timestamp()
                        except:
                            ts = time.time()
                    else:
                        ts = float(ts_raw or time.time())

                    if bus and data.get("type"): # Only replay structured RomeEvents to the bus
                        # We don't have a replay method, but we can update sequence
                        with bus._sequence_lock:
                            bus._sequence = max(bus._sequence, data.get("sequence", 0))

                    if not tid:
                        continue

                    count += 1
                    if ev_type in ("dispatch_start", "execute_legion"):
                        self.register(
                            tid, 
                            payload.get("capability", "unknown"),
                            timestamp=ts,
                            parent_task_id=payload.get("parent_task_id"),
                            token=payload.get("token")
                        )
                    elif ev_type == "progress":
                        self.update_progress(tid, payload.get("percent", 0), payload.get("message", ""))
                    elif ev_type in ("complete", "legion_wrapper"):
                        status = payload.get("status", "completed")
                        if status == "success": status = "completed"
                        self.complete(tid, status, payload.get("report_path"))
                    elif ev_type == "error":
                        self.complete(tid, "failed", None)
                        self.update_task(tid, {"progress_message": payload.get("message", "error")})
                    elif ev_type == "cost_update":
                        self.update_usage(tid, payload.get("usage"))

                except Exception:
                    continue
        
        with self._lock:
            self._replay_event_count = count
        return count

    def _cleanup_locked(self, now: float | None = None) -> None:
        cutoff = time.time() if now is None else now
        expired = []
        for task_id, task in self._tasks.items():
            status = str(task.get("status", "")).upper()
            
            age = cutoff - float(task.get("updated_at", task.get("created_at", cutoff)))

            if status == "REGISTERED" and age > 300:
                task["status"] = "expired"
                status = "EXPIRED"

            if status in ("SUCCESS", "OK", "COMPLETED"):
                ttl = 60  # High-speed success rotation (1 minute)
            elif status in ("FAILED", "ERROR", "TIMEOUT", "ERR", "CANCELLED"):
                ttl = 300  # Prune failures quickly (5 minutes)
            else:
                ttl = self._ttl_seconds  # Default for active tasks
                
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
    "emit_capability_status",
    "emit_complete",
    "emit_cost_update",
    "emit_dispatch_start",
    "emit_error",
    "emit_facts_broadcast",
    "emit_progress",
    "emit_system_status",
]


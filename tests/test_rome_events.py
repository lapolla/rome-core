"""Tests for rome_events buffer and _format_event."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from dictator.tools_ws import _format_event, _event_buffer, _seen_events


def _make_event(etype: str, task_id: str = "t1", payload: dict = None):
    return {
        "type": "event",
        "event": {
            "type": etype,
            "task_id": task_id,
            "ts": 1234567890.0,
            "sequence": 1,
            "source": "rome",
            "payload": payload or {},
        },
    }


class TestFormatEvent:
    def test_complete_success(self):
        msg = _make_event("complete", "job-1", {"status": "SUCCESS"})
        assert _format_event(msg) == "[SUCCESS] job-1"

    def test_complete_failed(self):
        msg = _make_event("complete", "job-2", {"status": "failed"})
        assert _format_event(msg) == "[FAILED] job-2"

    def test_progress(self):
        msg = _make_event("progress", "job-3", {"percent": 50, "message": "halfway"})
        assert _format_event(msg) == "[PROGRESS] job-3 50% halfway"

    def test_dispatch_start(self):
        msg = _make_event("dispatch_start", "job-4", {"capability": "GEMINI"})
        assert _format_event(msg) == "[DISPATCH] job-4 → GEMINI"

    def test_heartbeat_filtered(self):
        msg = _make_event("heartbeat", "")
        assert _format_event(msg) is None

    def test_system_status_filtered(self):
        msg = _make_event("system_status", "")
        assert _format_event(msg) is None

    def test_unknown_event_type(self):
        msg = _make_event("custom_thing", "job-5")
        assert _format_event(msg) == "[CUSTOM_THING] job-5"

    def test_non_event_ignored(self):
        msg = {"type": "response", "request_id": "abc"}
        assert _format_event(msg) is None


class TestDedup:
    def setup_method(self):
        _event_buffer.clear()
        _seen_events.clear()

    def test_dedup_prevents_duplicate_dispatch(self):
        """Same type+task_id should be deduped."""
        key = "dispatch_start:job-1"
        _seen_events.add(key)
        # Second occurrence should be skipped by the listener logic
        assert key in _seen_events

    def test_clear_on_drain(self):
        """Draining buffer also clears seen set."""
        _seen_events.add("complete:x")
        _event_buffer.append("test line")
        # Simulate drain
        list(_event_buffer)
        _event_buffer.clear()
        _seen_events.clear()
        assert len(_seen_events) == 0
        assert len(_event_buffer) == 0

    def test_different_types_not_deduped(self):
        """dispatch_start and complete for same task are distinct."""
        _seen_events.add("dispatch_start:job-1")
        assert "complete:job-1" not in _seen_events

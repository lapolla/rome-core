import pytest
import time
from dictator.events import TaskRegistry

def test_loose_transitions():
    reg = TaskRegistry(ttl_seconds=3600)
    task_id = "test-task"
    
    # 1. Normal flow
    reg.register(task_id, "GENERIC")
    task = reg.get(task_id)
    assert task["status"] == "registered"
    
    reg.update_progress(task_id, 10, "Working")
    task = reg.get(task_id)
    assert task["status"] == "running"
    
    reg.complete(task_id, "completed", "/tmp/report.txt")
    task = reg.get(task_id)
    assert task["status"] == "completed"
    
    # 2. LOOSE TRANSITION: completed -> running (Currently ALLOWED)
    # This should be REJECTED in the new state machine.
    reg.update_progress(task_id, 50, "Still working?")
    task = reg.get(task_id)
    # In current loose implementation, this passes and status becomes "running"
    # assert task["status"] == "completed" # This would fail now
    
    # 3. LOOSE TRANSITION: failed -> completed (Currently ALLOWED)
    task_id_2 = "test-task-2"
    reg.register(task_id_2, "GENERIC")
    reg.complete(task_id_2, "failed", None)
    assert reg.get(task_id_2)["status"] == "failed"
    
    reg.complete(task_id_2, "completed", "/tmp/report.txt")
    assert reg.get(task_id_2)["status"] == "completed" # Should be rejected

if __name__ == "__main__":
    test_loose_transitions()

import os
import json
import time
import threading
from pathlib import Path

import pytest

from aaak.compress import compress
from aaak.store import FactStore, _tokenize
from aaak.distill import distill, needs_distill
from aaak import get_aaak, AAAK

# ── aaak/compress.py ──────────────────────────────────────────────────

def test_compress_success_null_fields():
    """Fix 1: Should not crash if usage/runtime are None (JSON null)."""
    m = {'status': 'SUCCESS', 'usage': None, 'runtime': None, 'metadata': None, 'artifacts': []}
    f = compress(m, 'test nulls')
    assert f['status'] == 'SUCCESS'
    assert f['task'] == 'test nulls'
    assert f['confidence'] == 0.3  # no output, low confidence
    assert f['tokens_used'] == 0
    assert f['elapsed_s'] == 0

def test_compress_failure_metadata():
    """Extract error reason from metadata if available."""
    m = {'status': 'FAILED', 'usage': {'total_tokens': 150}, 'metadata': {'failure_reason': 'OOM'}}
    f = compress(m, 'fail task')
    assert f['status'] == 'FAILED'
    assert f['error'] == 'OOM'
    assert f['confidence'] == 0.1

def test_compress_short_error_extraction(tmp_path):
    """Fix 2: Should extract short errors (e.g., 'Error: 403')."""
    report = tmp_path / "report.txt"
    report.write_text("Error: 403\nConnection reset", encoding="utf-8")
    
    m = {'status': 'FAILED', 'artifacts': [{'path': str(report)}]}
    f = compress(m, 'short err')
    assert f['error'] == '403'

def test_compress_extract_changes(tmp_path):
    """Extract key changes from bullet points and modified files."""
    report = tmp_path / "report.txt"
    report.write_text("modified src/app.py\n- fixed the auth logic", encoding="utf-8")
    
    m = {'status': 'SUCCESS', 'artifacts': [{'path': str(report)}]}
    f = compress(m, 'changes')
    assert "modified src/app.py" in f['key_changes']
    assert "fixed the auth logic" in f['key_changes']


# ── aaak/store.py ─────────────────────────────────────────────────────

def test_store_save_load(tmp_path):
    """Save and retrieve a fact."""
    store = FactStore(store_dir=tmp_path, prefix="test")
    store.save({"status": "SUCCESS", "task": "fix auth"})
    
    active = store.load_active()
    assert len(active) == 1
    assert active[0]["task"] == "fix auth"
    assert "ts" in active[0]

def test_store_compact_expiry(tmp_path):
    """Fix 5/6: Expired facts should be dropped on compact()."""
    # Create store with -1 TTL so everything expires immediately
    store = FactStore(store_dir=tmp_path, prefix="test", ttl_seconds=-1)
    store.save({"status": "SUCCESS", "task": "expired"})
    
    assert len(store.load_active()) == 0
    kept = store.compact()
    assert kept == 0
    
    # Check underlying file is empty
    with open(store._path, "r") as f:
        assert len(f.read().strip()) == 0

def test_store_tokenize_short_words():
    """Fix 7: Tokenizer must retain short critical terms (DB, WS, v5)."""
    tokens = _tokenize("Fix DB auth in WS for v5")
    assert "db" in tokens
    assert "ws" in tokens
    assert "v5" in tokens
    assert "fix" in tokens

def test_store_query(tmp_path):
    """Recall querying by Jaccard similarity."""
    store = FactStore(store_dir=tmp_path, prefix="test")
    store.save({"task": "add login page", "result": "JWT implemented"})
    store.save({"task": "fix css", "result": "margin updated"})
    
    results = store.query("jwt auth login")
    assert len(results) > 0
    assert "login page" in results[0]["task"]


# ── aaak/distill.py ───────────────────────────────────────────────────

def test_distill_budget_truncation():
    """Fix 8: Truncate large prompts safely without negative budgets."""
    prompt = "x" * 8000
    raw = {"prompt": prompt}
    
    res = distill(raw, "long task")
    assert len(res) < 5000
    assert "[...truncated...]" in res
    assert "GOAL: long task" in res
    assert "INTENT:" in res
    assert "CAUSE:" in res
    assert "TASK:" in res

def test_needs_distill():
    """Estimate tokens and check for causal structure."""
    assert needs_distill("short prompt", threshold=800)  # Lacks structure
    assert needs_distill("x" * 4000, threshold=800)  # Exceeds threshold
    assert not needs_distill("GOAL: a\nINTENT: b\nCAUSE: c", threshold=800)  # Structured and short


# ── aaak/__init__.py ──────────────────────────────────────────────────

def test_aaak_post_result_poison_prevention(tmp_path):
    """Failed tasks ARE stored in V5 so they can act as causal constraints."""
    a = AAAK(store_dir=tmp_path, prefix="test")
    
    res = a.post_result({"status": "FAILED", "task_id": "bad"})
    assert res["status"] == "FAILED"
    assert res["cause"] == "Execution failed"
    assert len(a.store.load_active()) == 1
    
    res2 = a.post_result({"status": "SUCCESS", "task_id": "good"})
    assert res2["status"] == "SUCCESS"
    assert len(a.store.load_active()) == 2

def test_aaak_factory_isolation():
    """Fix 9: get_aaak() should yield isolated instances per prefix."""
    a1 = get_aaak("camp1")
    a2 = get_aaak("camp2")
    assert a1 is not a2
    assert a1.store._path.stem == "camp1"
    assert a2.store._path.stem == "camp2"

def test_aaak_broadcast_fn_called(tmp_path):
    """Fix 10: ensure broadcast_fn is called with the facts_broadcast event."""
    a = AAAK(store_dir=tmp_path, prefix="test")
    
    broadcasts = []
    def mock_broadcast(event):
        broadcasts.append(event)
        
    a.post_result({"status": "SUCCESS", "task_id": "abc"}, broadcast_fn=mock_broadcast)
    
    assert len(broadcasts) == 1
    assert broadcasts[0]["type"] == "facts_broadcast"
    assert "fact" in broadcasts[0]["payload"]
    assert broadcasts[0]["payload"]["fact"]["status"] == "SUCCESS"

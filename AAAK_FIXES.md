# AAAK + ROME v4 — Fixes for Gemini

> **Status: All 11 fixes implemented.** Committed in 63911e7 + post-audit corrections.
> Fix 9 uses per-prefix cache (not pure factory) — correct for ws_server shared-campaign usage.

Audit findings translated to concrete tasks. Each fix is self-contained.
Scope: `aaak/` + targeted hooks in `legions/`. Do NOT refactor outside these files.

---

## FIX 1 — compress.py: crash on `usage: null` manifest
**File:** `aaak/compress.py`  
**Line:** ~21  
**Bug:** `manifest.get("usage", {})` returns `None` (not missing — explicitly `null` in JSON).  
Downstream `.get("total_tokens", 0)` throws `AttributeError: 'NoneType'`.  
Same for `runtime`.

**Fix:**
```python
usage = manifest.get("usage") or {}
runtime = manifest.get("runtime") or {}
metadata = manifest.get("metadata") or {}
```

---

## FIX 2 — compress.py: short errors ignored
**File:** `aaak/compress.py`  
**Line:** `_extract_error()` function  
**Bug:** Regex requires error message ≥ 10 chars. "Error: EOF", "Error: 403" are silently dropped.

**Fix:** Change `{10,200}` to `{3,200}` in both patterns in `_extract_error()`.

---

## FIX 3 — compress.py: only store SUCCESS facts
**File:** `aaak/compress.py` + `aaak/__init__.py`  
**Bug:** `post_result()` compresses and stores facts from FAILED tasks. Poisons recall context for subsequent subtasks with error noise.

**Fix in `aaak/__init__.py` → `post_result()`:** Add guard before `compress()`:
```python
def post_result(self, manifest: dict[str, Any], task_description: str = "") -> dict[str, Any]:
    status = manifest.get("status", "UNKNOWN")
    if status not in ("SUCCESS", "completed"):
        return {}  # do not poison fact store with failed results
    fact = compress(manifest, task_description)
    self.store.save(fact)
    return fact
```

---

## FIX 4 — store.py: crash safety on write
**File:** `aaak/store.py`  
**Line:** `save()` method, ~line 44  
**Bug:** File write not flushed. Process crash after `write()` but before OS flush loses the fact.

**Fix:** Add `f.flush()` after the write line:
```python
f.write(line + "\n")
f.flush()
```

---

## FIX 5 — store.py: compact() race condition
**File:** `aaak/store.py`  
**Line:** `compact()` method, ~line 65  
**Bug:** Reads `load_active()` outside the lock, then acquires lock to rewrite. A concurrent `save()` between read and rewrite is silently deleted.

**Fix:** Read and write inside the same lock acquisition:
```python
def compact(self) -> int:
    cutoff = time.time() - self._ttl
    with self._lock:
        if not self._path.exists():
            return 0
        lines = self._path.read_text(encoding="utf-8").splitlines()
        active = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                fact = json.loads(line)
                if fact.get("ts", 0) >= cutoff:
                    active.append(line)
            except json.JSONDecodeError:
                continue
        with open(self._path, "w", encoding="utf-8") as f:
            for line in active:
                f.write(line + "\n")
            f.flush()
        return len(active)
```

---

## FIX 6 — store.py: auto-compact to prevent unbounded growth
**File:** `aaak/store.py`  
**Bug:** `compact()` is never called. Expired facts accumulate forever. `load_active()` scans the whole file on every `query()` call.

**Fix:** Add a counter to `save()` and auto-compact every 50 saves:
```python
def __init__(self, ...):
    ...
    self._save_count = 0

def save(self, fact):
    ...
    self._save_count += 1
    if self._save_count % 50 == 0:
        self.compact()
```

---

## FIX 7 — store.py: tokenizer drops useful short tokens
**File:** `aaak/store.py`  
**Line:** `_tokenize()` function  
**Bug:** Drops words `len(w) > 2`, silently discarding "DB", "UI", "S3", "PR", "Go", "v4", "v5", "WS", "JWT".

**Fix:** Change to `len(w) >= 2`:
```python
def _tokenize(text: str) -> set[str]:
    return {w for w in text.lower().split() if len(w) >= 2}
```

---

## FIX 8 — distill.py: negative task_budget produces garbage
**File:** `aaak/distill.py`  
**Line:** ~48  
**Bug:** If facts + files sections already exceed the token budget, `task_budget` goes negative. `max(100, task_budget // 2)` then extracts 200 chars of prompt regardless, violating the limit and potentially slicing mid-token.

**Fix:** Clamp budget and guard the append:
```python
task_budget = (DEFAULT_THRESHOLD * CHARS_PER_TOKEN) - len("\n".join(sections))
task_budget = max(200, task_budget)  # always give task at least 200 chars

if len(prompt) <= task_budget:
    sections.append(prompt)
else:
    half = task_budget // 2
    sections.append(prompt[:half])
    if len(prompt) > half * 2:
        sections.append("[...truncated...]")
        sections.append(prompt[-half:])
```

---

## FIX 9 — __init__.py: singleton prefix comparison bug
**File:** `aaak/__init__.py`  
**Line:** ~79  
**Bug:** `_default.store._path.stem` returns filename without extension. If prefix is `campaign.v2.1`, `.stem` returns `campaign.v2` — mismatch causes constant re-instantiation. Also: concurrent campaigns sharing one global `_default` overwrite each other's store.

**Fix:** Drop the singleton entirely — it's only used in Hook 2 (legion_wrapper) where campaigns don't overlap. Replace with a simple factory:
```python
def get_aaak(prefix: str = "default") -> AAAK:
    """Create a fresh AAAK instance for the given prefix."""
    return AAAK(prefix=prefix)
```
The AAAK instances in tools_legion.py and ws_server.py already use `parent_task_id or task_id` as prefix — each campaign gets its own store naturally.

---

## FIX 10 — __init__.py: add broadcast_fn stub to post_result
**File:** `aaak/__init__.py`  
**Reason:** V5 `facts_broadcast` event requires `post_result` to accept an optional callable. Adding it now (as no-op) means the signature is stable when the daemon wires it up.

**Fix:** Update `post_result` signature (incorporate Fix 3 as well):
```python
def post_result(
    self,
    manifest: dict[str, Any],
    task_description: str = "",
    broadcast_fn=None,
) -> dict[str, Any]:
    status = manifest.get("status", "UNKNOWN")
    if status not in ("SUCCESS", "completed"):
        return {}
    fact = compress(manifest, task_description)
    self.store.save(fact)
    if broadcast_fn is not None:
        try:
            broadcast_fn({"type": "facts_broadcast", "payload": {"fact": fact}})
        except Exception:
            pass
    return fact
```

---

## FIX 11 — legion_wrapper.py: Hook 2 dead for persistent workers
**File:** `legions/legion_wrapper.py`  
**Line:** ~269 (AAAK Hook 2 block)  
**Bug:** Persistent workers receive prompts via WS JSON — they never read `task.md` before execution. Writing distilled content to `task.md` has zero effect in worker mode.

**Fix:** Add a worker-mode guard so the hook only fires for subprocess mode:
```python
# AAAK Hook 2: Safety net — only applies to subprocess mode
# Persistent workers receive prompts via WS, not task.md
worker_mode = os.environ.get("ROME_WORKER_MODE") == "worker"
if AAAK_ENABLED and not worker_mode and initial_task_content and needs_distill(initial_task_content):
    ...
```

---

## NOT for Gemini (architectural / v5 scope)

- Centurion `subprocess.run` → WS dispatch rewrite (v5 prerequisite, separate effort)
- `_execute_legion_native` deduplication with `_execute_legion_impl` (risky refactor)
- `WorkerRegistry` distributed state (v5)
- `facts_broadcast` daemon wiring (needs `broadcast_fn` passed through dispatch chain)
- Pre-existing test failures (`ctx=None` kwarg, truncation assertion)

---

## Verification

After all fixes:
```bash
cd ~/projects/rome-core
python3 -c "
from aaak import AAAK
from aaak.compress import compress

# Fix 1: null usage should not crash
m = {'status': 'SUCCESS', 'usage': None, 'runtime': None, 'metadata': None, 'artifacts': []}
f = compress(m, 'test')
print('Fix 1 OK:', f['status'])

# Fix 3: failed manifest should not be stored
a = AAAK(prefix='verify')
result = a.post_result({'status': 'FAILED', 'usage': None}, 'bad task')
assert result == {}, f'Fix 3 FAILED: {result}'
print('Fix 3 OK')

# Fix 7: short tokens retained
from aaak.store import _tokenize
assert 'db' in _tokenize('fix DB auth'), 'Fix 7 FAILED'
print('Fix 7 OK')

# Fix 9: no singleton, each call fresh
from aaak import get_aaak
a1 = get_aaak('camp1')
a2 = get_aaak('camp2')
assert a1 is not a2, 'Fix 9 FAILED'
print('Fix 9 OK')

a.store.clear()
print('ALL FIXES VERIFIED')
"
python3 -m pytest tests/ -q 2>&1 | tail -5
```

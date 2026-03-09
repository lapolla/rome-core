# ROME Redesign Plan — Dashboard + Shell Executor

## Problem Statement

Current ROME has two critical failures:
1. **SAFE_SHELL is broken** — legion_wrapper was built for LLMs. Bash exits in 10ms,
   O_NONBLOCK read loop misses output, `parse_usage` expects JSON, task.md instruction
   is passed as a literal bash command → exit_code=127.
2. **Dashboard regressed** — `launch_centurion` moved to `/dev/tty` (separate terminal).
   Old version rendered inline with live row updates. User wants it back.

Plus: failed tasks just die. No retry, no resilience.

---

## Design Principles

- **Inline rendering** — dashboard lives in Claude Code output, no new terminals
- **Live rows** — ANSI cursor control rewrites rows in-place (not append-only)
- **Self-healing** — task fails → wake another legion → retry until success or max retries
- **Summary only** — orchestrator sees status rows + 2-line results, never walls of text
- **Shell is not an LLM** — separate executor, no JSON, no task.md dance

---

## New Files

### `legions/shell_executor.py`

Standalone executor for shell commands. Called directly by dictator, not through legion_wrapper.

**Responsibilities:**
- Accept: task_id, command string, timeout (default 60s)
- Run: `subprocess.Popen(["bash", "-c", cmd], stdout=PIPE, stderr=STDOUT)`
- Read: blocking reads in a thread, last stdout line sent as live progress message
- Write: full stdout to `report_{task_id}.txt`
- Write: manifest.json (same structure as legion_wrapper, `usage: null`)
- Return: summary dict — `{status, exit_code, duration_s, last_lines: [3 lines]}`

**Progress reporting:**
- Every 0.5s: emit `{type: "progress", task_id, elapsed, message: last_stdout_line}`
- Dashboard consumes these to rewrite the row in-place

**No JSON parsing. No parse_usage. No parse_rome_signals. No task.md.**

---

### `legions/dashboard.py`

Inline ANSI TUI. Renders directly to stdout (Claude Code interface). No `/dev/tty`.

**Row format:**
```
[ROME:task-name     ] [████████░░] [RUNNING ] [  1.2s] >> last message here
[ROME:other-task    ] [██████████] [SUCCESS ] [  0.3s] >> Plugin.cpp found
[ROME:failed-task   ] [████░░░░░░] [RETRY2/3] [  3.1s] >> retrying with Pro...
```

**Implementation:**
- On start: print N blank rows (one per task), save cursor position
- On update: move cursor up to row index, rewrite the row, move cursor back down
- Colors:
  - Yellow: RUNNING
  - Green: SUCCESS
  - Red: FAILED (terminal failure after all retries)
  - Orange/yellow: RETRYING
- Progress bar: filled blocks based on elapsed time (capped at 90% until done)
- On finish: print summary block, leave cursor at bottom

**Summary block (Caesar's Consolidated Intelligence):**
```
=== CAESAR'S CONSOLIDATED INTELLIGENCE ===
Campaign: campaign-id
Tasks:    8 succeeded, 1 failed, 1 retried
Total:    12.4s
---
[task-name] >> 2-line result summary
[task-name] >> 2-line result summary
```

**API:**
```python
db = Dashboard(task_ids)      # initializes rows
db.update(task_id, status, elapsed, message)  # rewrites row
db.finish(results)            # prints summary block
```

---

## Modified Files

### `legions/centurion_wrapper.py`

Replace `/dev/tty` rendering with `dashboard.py`.

Add self-healing retry loop:

```
for each task:
  attempt = 1
  while attempt <= MAX_RETRIES:
    result = run_task(capability, prompt)
    if result.status == SUCCESS:
      break
    attempt += 1
    capability = FALLBACK_CHAIN[capability][attempt]
    dashboard.update(task_id, RETRYING, ...)

  if attempt > MAX_RETRIES:
    dashboard.update(task_id, FAILED, ...)
```

**Fallback chains:**
```python
FALLBACK_CHAIN = {
    "GEMINI":      ["GEMINI", "GEMINI_PRO", "CODEX"],
    "SAFE_SHELL":  ["SAFE_SHELL", "SAFE_SHELL"],   # retry same, once
    "CODEX":       ["CODEX", "GEMINI"],
}
```

MAX_RETRIES = 3 per task.

Dashboard row shows `[RETRY 2/3]` during retry attempts.

---

### `dictator/tools_legion.py`

**SAFE_SHELL routing:**
```python
if capability == "SAFE_SHELL":
    result = await run_shell_executor(task_id, prompt, timeout=60)
else:
    result = await run_legion_wrapper(task_id, capability, args, ...)
```

`run_shell_executor` calls `shell_executor.py` directly via subprocess.

**Campaign changes:**
- `execute_campaign` always initializes `Dashboard` before dispatching tasks
- Task progress updates fed to dashboard during execution
- Returns consolidated summary only (no report file contents)

**`rome_dispatch` return value:**
- Currently returns full report path + status
- New: returns `{status, duration, summary: "2 lines max"}`
- Never returns raw file content

---

### `arsenal/core_arsenal.json`

```json
"SAFE_SHELL": {
  "exec": "/home/paul-kane/projects/rome-core/legions/shell_executor.py",
  "timeout": 60,
  "_note": "Dedicated bash executor — no LLM wrapper, no JSON"
}
```

Remove `args` field — shell_executor handles command passing directly.

---

## Implementation Order

1. **`dashboard.py`** — standalone, no deps, testable immediately
2. **`shell_executor.py`** — standalone, fixes SAFE_SHELL now
3. **`tools_legion.py`** — wire SAFE_SHELL to shell_executor
4. **`centurion_wrapper.py`** — add retry loop + swap to dashboard.py
5. **`execute_campaign`** — auto-init dashboard, feed updates
6. **`arsenal/core_arsenal.json`** — update SAFE_SHELL entry

---

## What Does NOT Change

- `legion_wrapper.py` — stays as-is for LLM capabilities (GEMINI, CLAUDE, CODEX)
- `parse_usage` — stays for token tracking of LLM tasks
- `parse_rome_signals` — stays for LLM ROME signal parsing
- `execute_legion` single-task flow — no dashboard (inline progress already works)
- Manifest structure — same schema, shell tasks just have `usage: null`

---

## Success Criteria

- [ ] SAFE_SHELL dispatches run bash commands and capture output correctly
- [ ] Campaign dashboard renders inline (no new terminal)
- [ ] Rows update in-place via ANSI cursor control
- [ ] Failed tasks retry up to 3x with fallback capability
- [ ] Orchestrator receives summary only (no text walls)
- [ ] Shell tasks show live last-line progress during execution
- [ ] Caesar's summary block appears after all tasks complete

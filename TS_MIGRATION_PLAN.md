# ROME TS Migration — Execution Plan

**Goal:** Complete the Python → TS rewrite for SAFE_SHELL, verify end-to-end dispatch (GEMINI + SAFE_SHELL) returns inline `report` via WS, eliminate `report_path` from the protocol.

**Audience:** GEMINI worker will implement each task below. Tasks are ordered — do them sequentially and verify before moving on.

---

## Current uncommitted state

- `src/peer_server.ts` — PATH fix (prepends `path.dirname(process.execPath)`), TS `executeTask` wiring for `.py`-exec capabilities (GEMINI/CLAUDE/CODEX/MISTRAL), `runLegion` subprocess path simplified, `event` command handler now updates registry on `complete`/`progress` events.
- `src/legion_worker.ts` — `Manifest` interface has new `report: string` field; `executeTask` populates it from `reportContent` before writing `manifest.json`.
- `legions/shell_executor.py` — line 162 changed to send inline `report` instead of `report_path`. **REVERT THIS** (see Task 1).

---

## Task 1 — Revert the Python shell_executor.py edit

**Why:** Python files are legacy and on the way out. Don't extend them. The inline-report change is about to be moot when shell_executor is ported to TS.

**File:** `legions/shell_executor.py`, line 162
**Change:** Restore the original:
```python
send_event("complete", task_id, {"status": status, "report_path": report_path, "usage": None})
```

**Verify:** `git diff legions/shell_executor.py` shows no changes.

---

## Task 2 — Port shell_executor to TS

**Why:** Remove the last Python subprocess from the SAFE_SHELL dispatch path.

**New file:** `src/shell_executor.ts`
**Export:** `async function executeShell(taskId: string, command: string, wsSender?: (ev: object) => Promise<void>): Promise<{ status: 'SUCCESS' | 'FAILED'; report: string; exit_code: number; elapsed_s: number }>`

**Behavior (matches `legions/shell_executor.py` semantics):**
1. Spawn `bash -c <command>` via `child_process.spawn` with `detached: true`, `cwd = ROME_ROOT/legions/<task_id>` (mkdirp), `env = { ...process.env, ROME_TASK_ID: taskId, ROME_TASK_DIR: taskDir }`.
2. Capture stdout+stderr into a `chunks: Buffer[]`. Stream line-by-line and call `wsSender({type:'event', event:{type:'progress', task_id, payload:{percent, message: last_line_trimmed_80}}})` every ~5 lines or when <2s elapsed (same heuristic as the Python version).
3. Honor `SHELL_TIMEOUT` env var (default 600s). On timeout: `proc.kill('SIGKILL')` and append `"\n[TIMEOUT] Process killed after Ns\n"` to chunks.
4. On exit:
   - `status = exit_code === 0 && !timedOut ? 'SUCCESS' : 'FAILED'`
   - `report = Buffer.concat(chunks).toString('utf-8').slice(0, 4000)` (truncate, no file write — report lives in WS event only)
   - Do **not** write `manifest.json` or `report_<task_id>.txt` to disk.
5. Return `{status, report, exit_code, elapsed_s}`.

**Do NOT:** import from `legion_worker.ts` — keep shell_executor standalone, simpler.

---

## Task 3 — Wire TS shell executor into runLegion

**File:** `src/peer_server.ts`, method `runLegion`

**Change:** The current subprocess branch (for `cap.exec !== *.py`) spawns `python3 legions/shell_executor.py`. Replace it entirely with an `executeShell()` call.

**Pseudocode:**
```ts
import { executeShell } from './shell_executor.js';

// In runLegion, after the .py-exec branch:
if (capability === 'SAFE_SHELL') {
  this.registry.update(task_id, 'running');
  const wsSender = async (ev: object) => {
    const inner = (ev as any).event ?? ev;
    if (inner.type === 'progress') {
      this.registry.updateProgress(task_id, inner.payload?.percent ?? 0, inner.payload?.message ?? '');
    }
    this.bus.broadcast(inner);
  };
  try {
    const result = await executeShell(task_id, prompt, wsSender);
    const ok = result.status === 'SUCCESS';
    this.registry.update(task_id, ok ? 'completed' : 'failed', { status: result.status, ok, report: result.report });
    this.bus.broadcast({ type: 'complete', task_id, payload: { status: result.status, ok, report: result.report } });
    this.logUsage('shell_ts', ok ? 'completed' : 'failed', task_id, undefined);
  } catch (e: any) {
    this.registry.update(task_id, 'failed', { error: String(e) });
    this.bus.broadcast({ type: 'complete', task_id, payload: { status: 'FAILED', ok: false, report: String(e) } });
  }
  return;
}
```

**Also delete:** the entire trailing `spawn(cap.exec...)` block (the old subprocess path). SAFE_SHELL is the only capability that hit it.

---

## Task 4 — Arsenal cleanup

**File:** `arsenal/core_arsenal.json`
**Change:** The `SAFE_SHELL` entry's `exec`/`args` fields are now dead. Remove them but keep the entry (so dispatch still sees the capability as registered). Minimal entry:
```json
"SAFE_SHELL": {
  "timeout": 600,
  "_note": "Dedicated bash executor — runs in-process via src/shell_executor.ts",
  "peer_port": 8745,
  "peer_host": "127.0.0.1"
}
```

**Do NOT touch:** GEMINI/CLAUDE/CODEX/MISTRAL entries — they still use `{MODEL}` and their CLI args for `executeTask`.

---

## Task 5 — Build, restart, verify

```bash
npx tsc
systemctl --user restart rome-daemon
curl -s http://localhost:8741/health
```

**Test 1 — SAFE_SHELL (in-process TS):**
```bash
python3 rome_native.py dispatch SAFE_SHELL "echo hello && date && uname -a"
```
Expect: `ok: true`, response contains `task_id`. Then query status:
```bash
python3 -c "
import asyncio, rome_native
r = asyncio.run(rome_native.send_command_async('await', {'task_ids':['<TASK_ID>'], 'include_reports': True, 'timeout': 30}, rome_native.DEFAULT_DAEMON_URI))
print(r)
"
```
Expect: `status: SUCCESS`, `report` field contains the shell output inline, **no `report_path` field**, no file written to `legions/<task_id>/`.

**Test 2 — GEMINI (in-process TS executeTask):**
```bash
python3 rome_native.py dispatch GEMINI "What is 2+2? Answer in one word."
```
Follow up with `await`. Expect: spawn succeeds (PATH fix is in), `status: SUCCESS`, `report` is Gemini's answer inline. If model 3.1-pro is rate-limited, `executeTask` should fall back via `modelChain`.

**Test 3 — No report files written:**
```bash
ls -la legions/task-* 2>/dev/null | grep -c report_
```
Should be 0 for tasks dispatched after the restart.

---

## Task 6 — Clean up legacy Python references (optional, same PR)

- `git rm legions/shell_executor.py` once Task 5 passes
- Remove SAFE_SHELL worker references from `dictator/ws_server.py` (if still present)
- Leave `legion_wrapper.py` alone for now — some tests still import it

---

## Out of scope (for later)

- **Native RomeDispatch tool compatibility** — Claude Code's built-in `RomeDispatch` fails with `[Tool result missing due to internal error]` against the TS daemon. `rome_native.py` works fine, so the TS protocol is correct. The native tool is a Python client shipped inside Claude Code — not fixable from this repo. Track as known issue; workaround is `rome_native.py` / direct WS probes.
- **AAAK port to TS** — context compression still Python-only. Large task, separate PR.
- **V5 peer mesh** — unchanged.

---

## Acceptance

- `npx tsc` clean
- Daemon starts, `/health` returns 200
- SAFE_SHELL dispatch returns inline `report`, no file I/O
- GEMINI dispatch returns inline `report`, no `python3 legion_wrapper.py` in process tree
- `git grep -l "shell_executor.py"` returns nothing (Task 6) or only comments/tests
- No new Python files introduced

# ROME Protocol v4.0.0 Specification
**Status:** ACTIVE | **Authority:** Absolute | **Version:** 4.0.0

## 1. Overview: WebSocket-Native Sovereignty
ROME v4.0.0 is the transition from MCP-mediated to WebSocket-native. The daemon is a pure `websockets.serve()` process — no ASGI, no Starlette, no Uvicorn. HTTP is only served via `process_request` hook for `/health` and `/dashboard/`. Everything else is WS.

## 2. The Death of the Middleman (MCP Deprecation for Runtime)
- **The Problem:** MCP adds latency per request and bloats the LLM context window with tool descriptions and response payloads.
- **The Solution:** Every ROME component (Dictator, Centurion, Legions) communicates via raw JSON frames over a persistent WebSocket connection on port 8741.
- **MCP retained for:** Claude Code integration only (stdio transport via `dictator/cli.py`). Not used for daemon-to-worker communication.

## 3. Persistent Legions (Long-Lived Agents)
- **Handshake:** Client sends `agent_hello` with capabilities, version, platform → daemon responds `worker_ack` with accepted capabilities.
- **WorkerRegistry:** Tracks connected workers by `id(ws)`. Finds idle workers by capability, marks busy/idle per task.
- **Dispatch routing priority:** NATIVE_SHELL (in-process) → persistent worker (WS) → subprocess fallback (legacy).
- **Worker events:** Workers send `{"type": "event", "event": {...}}` for progress/complete/error. Daemon relays to EventBus + all subscribers.
- **Orphan cleanup:** On worker disconnect, all busy tasks marked failed with error event.
- **Reconnection:** Workers implement exponential backoff (1s → 30s max) on disconnect.

## 4. The "Dry, Kiss ASS" Principles
- **DRY (Don't Repeat Yourself):** One protocol (WS) for logs, tasks, and media control.
- **KISS (Keep It Simple, Stupid):** Minimize abstraction layers. Direct Shell Access (DSA) over WS commands.
- **ASS (Avoid Silly/Stupid Assumptions):** Zero assumptions about system state. Tools verify existence and state via the WS feedback loop before execution.

## 5. Direct Shell Access (DSA)
- **`NATIVE_SHELL` Capability:** Executes commands directly within the ROME daemon's Python process via `core.run_cmd()`.
- **Latency:** Sub-millisecond execution overhead (~2ms total task lifecycle).
- **Command:** `{"type": "command", "command": "native_shell", "payload": {"command": "..."}}`
- **vs SAFE_SHELL:** SAFE_SHELL spawns a detached `shell_executor.py` subprocess (async, reports via WS). NATIVE_SHELL is synchronous and in-process.

## 6. WS Command Protocol (20 commands)

All commands: `{"type": "command", "command": "<name>", "request_id": "<id>", "payload": {}}`
All responses: `{"type": "response", "request_id": "<id>", "ok": true/false, "payload": {}}`

| Command | Purpose |
|---------|---------|
| `dispatch` | Dispatch task (NATIVE_SHELL → worker → subprocess) |
| `status` | Task/system status |
| `get_state` | Full daemon state dump |
| `await` | Block until task_ids complete (EventBus, no polling) |
| `cancel` | Cancel running task or clean zombie |
| `native_shell` | Execute shell in daemon process |
| `submit_result` | Worker submits result (auto-summarized if >2KB) |
| `interrupt` | Cancel or steer worker mid-execution |
| `read_file` | Read file with line range + overview mode |
| `write_file` | Write file |
| `list_dir` | List directory with depth/limit |
| `read_report` | Read report file (truncated to 4KB) |
| `event` | Relay events from MCP to EventBus |
| `reset` | Clear all tasks from registry |
| `clear` | Clear finished tasks only |
| `ping` | Returns pong + timestamp |
| `workers` | List connected persistent workers |
| `recent_events` | Tasks changed since timestamp |
| `report_usage` | Self-report token usage |
| `dashboard_stats` | Aggregated stats for web dashboard |

## 7. Real-Time Interrupts & Steering
- **`interrupt` Command:** Cancel tasks or steer persistent workers mid-execution.
- **Targeting:** By `task_id` (cancel) or `worker_id` (inject prompt, signal).
- **Types:** `cancel`, `inject_prompt`, `signal`.

## 8. Auto-Lean Mode
Daemon tracks cumulative output chars per session:
- **Normal** (0–100K chars): Full events, full reports
- **Lean** (100K–300K chars): 1 event max, prefer summaries
- **Ultra-lean** (>300K chars): No events, status-only responses

## 9. Result Compression
Worker results >2000 chars auto-summarized via Gemini Flash on `submit_result`. Summary stored in TaskRegistry. `await` returns summary by default (`full=True` for raw report).

## 10. Zombie Reaping
System status loop (30s) auto-fails tasks stuck at 0% progress for >180s. Daemon startup sweeps all registered/running tasks to failed state.

## 11. Task Manifest (v4)

```json
{
  "rome_v": "4.0",
  "task_id": "...",
  "status": "SUCCESS",
  "metadata": {},
  "usage": {
    "model": "gemini-3.1-pro-preview",
    "input_tokens": 3486,
    "output_tokens": 27,
    "total_tokens": 3513,
    "cost_usd": 0.0012
  },
  "progress": ["0% + [0.0s] Engaged (4.0.0).", "..."],
  "artifacts": [{"path": "report_TASK_ID.txt", "type": "extracted"}],
  "runtime": {"elapsed_s": 12.5, "exit_code": 0}
}
```

---
**"Data without structure is noise; Protocols with middlemen are bottlenecks. ROME is the Mesh."**

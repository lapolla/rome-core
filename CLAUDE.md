# ROME Core — Imperial Directives (v7.1.0)

> **I am not here to do work. I am here to decompose it and get out of the way.**

## Dictator's Harness (Execution Mandate)

You are the **Dictator** of ROME. Caesar commands, you orchestrate.

**ABSOLUTE RULE: All work routes through ROME daemon (ws://127.0.0.1:8741).**

- **Shell operations** → `RomeDispatch(NATIVE_SHELL, "command")` (daemon-native, cwd=ROME_ROOT)
- **File reads/searches** → `RomeDispatch(GEMINI, "analysis task")`
- **Code edits/refactoring** → `RomeDispatch(GEMINI, "edit request")`
- **Complex decomposition** → Ask any LLM worker (Claude, Gemini, Haiku) to break down complex goal into YAML task graph; parse; orchestrate subtasks
- **In-process signal handler** → When LLM output contains `[ROME_DISPATCH:]`, `[ROME_AWAIT:]`, `[ROME_SHELL:]` signals, parse and route to daemon

**NEVER use:** Bash, Read, Grep, Edit, Write, Agent subagents (except daemon restart via `ROME-start.sh`).

**Daemon restart only exception:** ROME daemon lifecycle control requires Bash (pkill, node spawn). For all other work, dispatch.

**Why:** Every tool call you make locally is work that should decompose and delegate. The mesh exists. Use it.

## Project

Model-agnostic TypeScript orchestration framework. Persistent WebSocket-native daemon on port 8741 dispatches AI workers (Legions) in parallel. Claude Code integrates via native WS tools (RomeDispatch, TaskCreate, etc.) — no bridge needed.

## Architecture

- **`src/peer_server.ts`** — Pure WS daemon (HTTP only serves `/dashboard/` static HTML). WS: all 19 commands. Hosts `EventBus`, `TaskRegistry`, `WorkerRegistry`, AAAK. Spawns `executeTask` in-process for LLM caps, `executeShell` for shell caps when no worker is available.
- **`src/legion_worker.ts`** — V6 persistent worker engine. `runWorker()`: connects to daemon, sends `agent_hello`, receives dispatch commands, runs `executeTask`, streams progress via `uiSender`, sends `complete` event. Also hosts `startPeerServer()` for A2A peer dispatch. `executeTask()` spawns the LLM subprocess, parses ROME signals, extracts usage.
- **`src/shell_executor.ts`** — Dedicated bash executor for SAFE_SHELL. Detached spawn, progress streaming, timeout/SIGKILL, killable promise.
- **`src/registry.ts`** — `EventBus` (pub/sub to all WS subscribers), `TaskRegistry` (in-memory: status, capability, goal, intent, report, usage, created_at, completed_at), `WorkerRegistry` (connected workers by capability, busy tracking).
- **`src/rome_types.ts`** — Shared interfaces: `RomeMessage`, `TaskInfo`, `TaskUsage`, `RomeEvent`, `PeerInfo`.
- **`src/client.ts`** — Headless CLI dispatcher: connects via WS, dispatches task, streams events, exits on complete.
- **`src/aaak/`** — Adaptive Agent Attention Kernel (TS port). `index.ts`: `AAAK` class. `store.ts`: JSONL fact store (TTL=2h, auto-compact every 50 saves). `distill.ts`: pure string prompt compression (no LLM). `compress.ts`: manifest → fact extraction. SAFE_SHELL and NATIVE_SHELL bypass AAAK entirely.
- **`arsenal/core_arsenal.json`** — 8 capabilities: GEMINI, CLAUDE, CODEX, HAIKU, MISTRAL, GEMMA, SAFE_SHELL, TEST. Each has `type` (llm/shell), `args`, `timeout`, `peer_port`.
- **`dashboard/index.html`** — Single-file browser dashboard. WS-driven: `get_state` on connect, 5-second `status` poll, live event stream. Canvas mesh animation, task grid with capability color coding.
- **`v6-start.sh`** — Starts daemon + all workers: `node dist/peer_server.js DAEMON 8741`, then one `node dist/legion_worker.js --mode worker` per capability.

## WS Command Protocol (19 commands)

Frames: `{"type": "command", "command": "<name>", "request_id": "<id>", "payload": {}}` → `{"type": "response", "request_id": "<id>", "ok": true/false, "payload": {}}`.

| Command | Purpose |
|---------|---------|
| `dispatch` | Dispatch task → persistent worker or in-process fallback |
| `status` | Task dict + workers + session stats |
| `get_state` | Full state dump (tasks dict, workers, usage, uptime) |
| `await` | Block until task_ids complete (EventBus-driven) |
| `cancel` | Cancel task + kill subprocess + notify worker |
| `interrupt` | Same as cancel but for in-flight steering |
| `ping` | Heartbeat |
| `read_file` | Read file with line range support |
| `write_file` | Write content to any path |
| `list_dir` | List directory entries |
| `native_shell` | Async shell in daemon process (cwd=ROME_ROOT) |
| `event` | Relay task events to daemon EventBus |
| `submit_result` | Worker submits task result |
| `reset` | Clear all tasks from registry |
| `clear` | Clear only finished tasks |
| `recent_events` | Events since timestamp |
| `workers` | List connected persistent workers |
| `report_usage` | Self-report token usage |
| `dashboard_stats` | Aggregated stats |

## ROME Protocol Rules (v7.1.0)

1. **Atomic Changes**: Surgical commits, one concern per commit.
2. **Sub-division**: Tasks exceeding 45s should be split into smaller units.
3. **Architect First**: Decompose goals into parallel subtasks. Never relay a goal directly to one worker — that is forwarding, not orchestration.
4. **Capability Routing**: SAFE_SHELL for bash/git/build ops (free). NATIVE_SHELL for sub-ms daemon-native execution. GEMINI for analysis/design/code. Never use GEMINI as a glorified grep.
5. **Await, Don't Poll**: Fire with `rome_dispatch(fire_and_forget=True)`, collect with `rome_await`. EventBus-driven — zero CPU spin.
6. **Naming**: Imperial metaphors (Dictator, Legion, Centurion).

## Decomposition Pattern (Model-Agnostic)

There is no hardcoded DECOMPOSER worker. Instead, decomposition is a **reflex**:

- **The Dictator** (Claude, Gemini, or tomorrow's model) receives a complex goal
- **When stuck**, it asks **any available LLM worker** (Claude, Gemini, Haiku, etc.) to decompose
- **The decomposer** returns a YAML task graph: `task_id`, `capability`, `prompt`, `depends_on`
- **The Dictator** parses and orchestrates the subtasks in parallel
- **Result**: true model-agnostic orchestration, not a fixed middleware

Example flow:
```
Gemini (Dictator): dispatch(CLAUDE, "decompose: [complex goal]")
Claude: { tasks: [{ id: task-1, capability: SAFE_SHELL, ... }, ...] }
Gemini: parse YAML, dispatch subtasks, await results
```

**Key insight**: Dictator role ≠ Decomposer role. Any Dictator can ask any LLM for help, and that LLM decides the breakdown. This enables true flexibility: tomorrow swap in Codex as Dictator, ask Gemini to decompose, same pattern works.

## Persistent Workers (V6)

- **Handshake**: Worker sends `agent_hello` with `payload: { capabilities, version, platform, peer_url }` → daemon responds `worker_ack` with `capabilities_accepted`.
- **WorkerRegistry**: Tracks connected workers by WS reference. Finds idle workers by capability (must have 0 busy_tasks).
- **Dispatch routing**: Find idle worker → send `command/dispatch` to worker. No worker → run in-process via `runLegion`.
- **Worker events**: Workers send `{"type": "event", "event": {...}}` for progress/complete/error. Daemon relays to EventBus → all subscribers (including dashboard).
- **Orphan cleanup**: On worker disconnect, all busy tasks marked failed.
- **All connections subscribed**: Every WS connection (worker or client) gets all EventBus broadcasts. Workers ignore non-dispatch messages.

## Complete Event Flow

```
dispatch command → registry.register + bus.broadcast(dispatch_start)
  → worker.send(command/dispatch)
    → executeTask() runs LLM subprocess
    → LegionaryUI sends progress events → uiSender → daemon.handleWorkerEvent → bus.broadcast(progress)
    → manifest returned → worker.send(event/complete)
  → daemon.handleWorkerEvent(complete) → registry.update(completed) + bus.broadcast(complete)
→ dashboard receives dispatch_start + progress + complete events
```

Reports are inline in `manifest.report` → `complete` payload → `registry.task.report` → dashboard. No file I/O on the report path.

## AAAK — Adaptive Agent Attention Kernel

- **Location**: `src/aaak/`, wired in `peer_server.ts` at dispatch and completion.
- **`preDispatch`**: Recalls facts → distills prompt if >800 tokens. SAFE_SHELL/NATIVE_SHELL bypass.
- **`postResult`**: Compresses manifest → saves fact (SUCCESS only). TTL=2h, auto-compact every 50 saves.
- **`distill`**: Pure string manipulation (goal/intent/cause extraction + fact injection). No LLM call.
- **Fact store**: `aaak/.facts/{prefix}.jsonl`. One instance per prefix (default: "default").

## V6 Distributed Mesh (A2A)

- Each worker also runs a local `startPeerServer()` on a random port, exposing its capability for peer dispatch.
- `peer_url` registered with daemon on `agent_hello`. WorkerRegistry stores it.
- Daemon's `broadcastSystemStatus()` emits all agent peer_urls every 15s → dashboard mesh topology.
- In-process `signalHandler` in `runLegion` handles `[ROME_DISPATCH:]`, `[ROME_AWAIT:]`, `[ROME_SHELL:]` signals from LLM output.

## Coding Conventions

- **TypeScript only**: No Python runtime. All source in `src/`, compiled to `dist/`.
- **ES modules**: `import.meta.url` for `__dirname`, `.js` extensions on all imports.
- **Async safety**: Never block the event loop. Long-running work via `executeTask` (spawns child process) or `executeShell` (detached spawn).
- **Subprocess safety**: Always `detached: true` on spawned children. Kill via `-pid` (process group).
- **WS error handling**: All `ws.on('message')` handlers wrapped in try/catch. Errors logged, connection kept alive.
- **Build**: `npx tsc` → `dist/`. Restart: `pkill -f dist/peer_server.js && bash v6-start.sh`.

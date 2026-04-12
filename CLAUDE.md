# ROME Core — Imperial Directives (v6.0.0)

> **I am not here to do work. I am here to decompose it and get out of the way.**

## Project

Model-agnostic TypeScript orchestration framework. Persistent WebSocket-native daemon on port 8741 dispatches AI workers (Legions) in parallel. Claude Code integrates via native WS tools (RomeDispatch, TaskCreate, etc.) — no bridge needed.

## Architecture

- **`src/peer_server.ts`** — Pure WS + HTTP daemon. HTTP: `/health` (JSON), `/dashboard/` (static HTML). WS: all 19 commands. Hosts `EventBus`, `TaskRegistry`, `WorkerRegistry`, AAAK. Spawns `executeTask` in-process for LLM caps, `executeShell` for shell caps when no worker is available.
- **`src/legion_worker.ts`** — V6 persistent worker engine. `runWorker()`: connects to daemon, sends `agent_hello`, receives dispatch commands, runs `executeTask`, streams progress via `uiSender`, sends `complete` event. Also hosts `startPeerServer()` for A2A peer dispatch. `executeTask()` spawns the LLM subprocess, parses ROME signals, extracts usage.
- **`src/shell_executor.ts`** — Dedicated bash executor for SAFE_SHELL. Detached spawn, progress streaming, timeout/SIGKILL, killable promise.
- **`src/registry.ts`** — `EventBus` (pub/sub to all WS subscribers), `TaskRegistry` (in-memory: status, capability, goal, intent, report, usage, created_at, completed_at), `WorkerRegistry` (connected workers by capability, busy tracking).
- **`src/rome_types.ts`** — Shared interfaces: `RomeMessage`, `TaskInfo`, `TaskUsage`, `RomeEvent`, `PeerInfo`.
- **`src/client.ts`** — Headless CLI dispatcher: connects via WS, dispatches task, streams events, exits on complete.
- **`src/aaak/`** — Adaptive Agent Attention Kernel (TS port). `index.ts`: `AAAK` class. `store.ts`: JSONL fact store (TTL=2h, auto-compact every 50 saves). `distill.ts`: pure string prompt compression (no LLM). `compress.ts`: manifest → fact extraction. SAFE_SHELL and NATIVE_SHELL bypass AAAK entirely.
- **`arsenal/core_arsenal.json`** — 6 capabilities: GEMINI, CLAUDE, CODEX, HAIKU, MISTRAL, SAFE_SHELL. Each has `type` (llm/shell), `args`, `timeout`, `peer_port`.
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

## ROME Protocol Rules (v6.0.0)

1. **Atomic Changes**: Surgical commits, one concern per commit.
2. **Sub-division**: Tasks exceeding 45s should be split into smaller units.
3. **Architect First**: Decompose goals into parallel subtasks. Never relay a goal directly to one worker — that is forwarding, not orchestration.
4. **Capability Routing**: SAFE_SHELL for bash/git/build ops (free). NATIVE_SHELL for sub-ms daemon-native execution. GEMINI for analysis/design/code. Never use GEMINI as a glorified grep.
5. **Await, Don't Poll**: Fire with `rome_dispatch(fire_and_forget=True)`, collect with `rome_await`. EventBus-driven — zero CPU spin.
6. **Naming**: Imperial metaphors (Dictator, Legion, Centurion).

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

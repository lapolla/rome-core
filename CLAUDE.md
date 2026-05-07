# ROME Core — Imperial Directives (v7.1.0)

> **I am not here to do work. I am here to decompose it and get out of the way.**

## Orchestrator's Harness (Execution Mandate)

You are the **Orchestrator** of the ROME Mesh. Caesar commands, you decompose and delegate.

**ABSOLUTE RULE: All work routes through ROME daemon (ws://127.0.0.1:8741).**

- **Shell operations** → `ws_send("native_shell", {command: "..."})`
- **Mesh Dispatch** → `ws_send("dispatch", {capability: "...", prompt: "..."})`
- **Real-time Interaction** → Use Direct Agent Signals (DAS) in full-duplex agents: `[ROME_SHELL: "command"]`, `[ROME_DISPATCH: CAP "prompt"]`.
- **In-process signal handler** → Native agents intercept signals in real-time, executing tools via the existing WS connection and feeding results back.

**NEVER use:** Local Bash, Read, Grep, Edit, Write (except daemon control).

## Architecture

- **`src/peer_server.ts`** — Pure WS daemon. Injects sovereign audio context (`PULSE_SERVER`, `XDG_RUNTIME_DIR`) into all sub-tasks.
- **`src/native_agent.ts`** — V7 full-duplex native agent. Pure JS/TS implementation. Connects to Ollama/Mistral directly. Implements the real-time DAS signal loop via the primary WebSocket.
- **`src/shell_executor.ts`** — Dedicated bash executor for SAFE_SHELL.
- **`src/registry.ts`** — `EventBus` (with 100-event replay), `TaskRegistry` (causal tracking), `WorkerRegistry`.
- **`src/client.ts`** — Headless CLI dispatcher.
- **`ROME-start.sh`** — Orchestrates clean mesh startup. Hardened cleanup logic to prevent zombie worker leaks. Injects audio environment.

## WS Command Protocol (17 commands)

Frames: `{"type": "command", "command": "<name>", "request_id": "<id>", "payload": {}}` → `{"type": "response", "request_id": "<id>", "ok": true/false, "payload": {}}`.

| Command | Purpose |
|---------|---------|
| `ping` | Heartbeat |
| `dispatch` | Dispatch task → persistent worker or in-process fallback |
| `native_shell` | Async shell in daemon process (cwd=ROME_ROOT) |
| `await` | Block until task_ids complete (EventBus-driven) |
| `status` | Task dict + workers + session stats |
| `get_state` | Full state dump (tasks dict, workers, usage, uptime) |
| `workers` | List connected persistent workers |
| `probe_arsenal` | Probe configured capabilities; return availability |
| `read_report` | Read a stored task report |
| `state_get` | Read a Blackboard key |
| `state_set` | Write a Blackboard key |
| `state_delete` | Delete a Blackboard key |
| `state_get_meta` | Read Blackboard key metadata |
| `aaak_recall` | Query AAAK fact store by text (returns ranked facts) |
| `aaak_seed` | Seed a fact directly into AAAK store |
| `clear` | Clear only finished tasks |
| `reset` | Clear all tasks from registry |

**Removed in v7 (or never implemented):** `cancel`, `interrupt`, `read_file`, `write_file`, `list_dir`, `event`, `submit_result`, `recent_events`, `report_usage`, `dashboard_stats`. Worker events (`progress`, `complete`, `error`) are message types on the worker→daemon channel, not commands.

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

## Persistent Workers

- **Handshake**: Worker sends `agent_hello` with `payload: { capabilities, version, platform, one_shot }` → daemon responds `worker_ack` with `capabilities_accepted`.
- **WorkerRegistry**: Tracks connected workers by WS reference. Finds idle workers by capability (must have 0 busy_tasks).
- **Dispatch routing**: Find idle worker → send `command/dispatch` to worker. No worker → returns failure error message.
- **Worker events**: Workers send `{"type": "event", "event": {...}}` for progress/complete/error. Daemon relays to EventBus → all subscribers (including dashboard).
- **Orphan cleanup**: On worker disconnect, all busy tasks marked failed.
- **All connections subscribed**: Every WS connection (worker or client) gets all EventBus broadcasts. Workers ignore non-dispatch messages.

## Complete Event Flow

```
dispatch command → registry.register + bus.broadcast(dispatch_start)
  → worker.send(command/dispatch)
    → native_agent.sendEvent / shell_executor.onData
    → daemon.handleWorkerEvent → bus.broadcast(progress/complete)
→ dashboard receives dispatch_start + progress + complete events
```

Reports are inline in `manifest.report` → `complete` payload → `registry.task.report` → dashboard. No file I/O on the report path.

## AAAK — Adaptive Agent Attention Kernel

AAAK is **write-only on the dispatch path**. `postResult` records facts on success; `preDispatch` was removed in v7. Explicit recall is via the `aaak_recall` WS command, never auto-injected.

- **Location**: `src/aaak/`, wired in `peer_server.ts` at completion only.
- **`postResult`**: Compresses manifest → saves fact (SUCCESS only). TTL=2h, auto-compact every 50 saves.
- **Fact store**: vectra `LocalIndex` under `.rome/memory/<prefix>`.
- **`aaak_recall`** WS command: Dictator queries facts by text, returns ranked results.
- **`aaak_seed`** WS command: Dictator seeds facts directly into the store.

## Coding Conventions

- **TypeScript only**: No Python runtime. All source in `src/`, compiled to `dist/`.
- **ES modules**: `import.meta.url` for `__dirname`, `.js` extensions on all imports.
- **Async safety**: Never block the event loop. Long-running work via subprocess spawning or detached shell execution.
- **Subprocess safety**: Always `detached: true` on spawned children. Kill via `-pid` (process group).
- **WS error handling**: All `ws.on('message')` handlers wrapped in try/catch. Errors logged, connection kept alive.
- **No inline comments**: Use block comments only where the why is load-bearing; otherwise keep code self-documenting.
- **Build**: `npx tsc` → `dist/`. Restart: `pkill -f dist/peer_server.js && bash ROME-start.sh`.

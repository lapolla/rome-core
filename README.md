# ROME: Remote Orchestrated Model Execution

A Python orchestration framework. Provides a persistent WebSocket-native daemon that dispatches AI workers (Legions) in parallel, supports persistent worker connections, streams live progress, and serves a browser dashboard.

## Imperial Hierarchy

```
Emperor (You)
  └── Dictator (any LLM — Claude, GPT, Gemini)
        └── Centurion (optional nested orchestrator)
              └── Legions (GEMINI | CLAUDE | CODEX | MISTRAL | SAFE_SHELL)
```

## Architecture

```
dictator/
  daemon.py          Pure WS daemon (websockets.serve(), port 8741)
  core.py            Config, run_cmd/run_cmd_stream, EventBus, TaskRegistry
  ws_server.py       WS protocol handler (20 commands), WorkerRegistry, auto-lean
  ws_client.py       Thread-safe WS client (fire-and-forget + sync/async)
  events.py          RomeEvent dataclass + pub/sub EventBus + TaskRegistry
  config.json        Path constants (17 keys)
  legion_patches.json  Capability-specific prompt injections
legions/
  legion_wrapper.py  V4 persistent worker engine (once + worker modes)
  shell_executor.py  Dedicated bash executor for SAFE_SHELL (no LLM)
  centurion_wrapper.py  Campaign orchestrator with retry loop + dashboard
  dashboard.py       Inline ANSI TUI for campaign progress
  .cache/            1-hour TTL result cache
arsenal/
  core_arsenal.json  6 capabilities (GEMINI, CLAUDE, CODEX, MISTRAL, SAFE_SHELL, CENTURION)
senate/
  brain.py           Sector manifesto dispatcher
  architects/        64 sector manifestos (T0.md–T63.md)
client/
  orchestrator.py    Headless CLI orchestrator (Haiku/Flash → WS dispatch)
campaigns/
  *.yaml             Task pipeline templates
  loader.py          YAML campaign loader + WS dispatcher
```

## Quick Start

### Start the daemon

```bash
python3 -m dictator.daemon --port 8741
# WebSocket:     ws://localhost:8741/ws
# Dashboard:     http://localhost:8741/dashboard/
# Health:        http://localhost:8741/health
```

### Start a persistent Gemini worker

```bash
python3 legions/legion_wrapper.py \
  --mode worker \
  --capabilities GEMINI \
  --ws-url ws://127.0.0.1:8741/ws \
  --ws-token ROME_V4_SECURE_TOKEN \
  -- gemini --sandbox false --yolo --output-format json -m gemini-3.1-pro-preview -p
```

### Claude Code (native WS)

Claude Code integrates via native RomeDispatch tool — no MCP bridge needed. Daemon handles all routing.

### Headless orchestrator

```bash
echo "Fix the bug in main.py and run tests" | python3 client/orchestrator.py -
```

## Capabilities & Failover

| Capability | Role | Fallback |
|------------|------|---------|
| GEMINI | High-speed generalist coding/analysis | → CODEX → MISTRAL |
| CLAUDE | Architectural decisions, security review | — |
| CODEX | Code manipulation, repo insight | → MISTRAL |
| MISTRAL | Mistral Vibe CLI — analysis/research | — |
| SAFE_SHELL | Detached bash subprocess (no LLM) | retry once |

## WebSocket Protocol (v4)

Server listens at `ws://localhost:8741/ws`. Auth via `Authorization: Bearer <token>` header or `?token=` query param.

### Commands (client → server)

All commands are JSON frames: `{"type": "command", "command": "<name>", "request_id": "<id>", "payload": {}}`

| Command | Purpose |
|---------|---------|
| `dispatch` | Dispatch task (routes: NATIVE_SHELL → persistent worker → subprocess) |
| `status` | Task/system status. `summary` flag for session stats |
| `get_state` | Full daemon state dump |
| `await` | Block until task_ids complete (EventBus-driven) |
| `cancel` | Cancel running task |
| `native_shell` | Execute shell in daemon process (sub-ms) |
| `submit_result` | Worker submits task result |
| `interrupt` | Cancel or steer a worker mid-execution |
| `read_file` | Read file with line ranges |
| `write_file` | Write file |
| `list_dir` | List directory |
| `read_report` | Read report file |
| `event` | Relay task events to EventBus |
| `reset` | Clear all tasks |
| `clear` | Clear finished tasks |
| `ping` | Heartbeat |
| `workers` | List persistent workers |
| `recent_events` | Tasks changed since timestamp |
| `report_usage` | Self-report token usage |
| `dashboard_stats` | Aggregated stats for web dashboard |

### Events (server → client)

```json
{"type": "event", "event": {"type": "complete", "task_id": "...", "payload": {...}}}
{"type": "event", "event": {"type": "progress", "task_id": "...", "payload": {...}}}
{"type": "event", "event": {"type": "dispatch_start", "task_id": "...", "payload": {...}}}
{"type": "event", "event": {"type": "error", "task_id": "...", "payload": {...}}}
{"type": "event", "event": {"type": "heartbeat", ...}}
```

### Persistent Workers

Workers connect via WS and send `agent_hello` to register capabilities. The daemon routes matching dispatches to idle workers instead of spawning subprocesses.

```
Client: {"type": "agent_hello", "capabilities": ["GEMINI"], "version": "4.0.0"}
Server: {"type": "worker_ack", "ok": true, "capabilities_accepted": ["GEMINI"]}
```

## ROME Signal Protocol

LLM workers use these tags to communicate with `legion_wrapper.py`:

```
[ROME_START] ... [ROME_END]     Primary artifact
[ROME_META: key=value]          Inject into manifest.json
[ROME_STATUS: SUCCESS|FAILED|RETRY]   Explicit outcome
```

Every task produces a `manifest.json`:
```json
{
  "rome_v": "4.0",
  "task_id": "...",
  "status": "SUCCESS",
  "usage": {"model": "...", "input_tokens": 3486, "output_tokens": 27, "cost_usd": 0.0012},
  "progress": ["0% ...", "50% ...", "100% ..."],
  "artifacts": [{"path": "report_TASK_ID.txt", "type": "extracted"}],
  "runtime": {"elapsed_s": 12.5, "exit_code": 0}
}
```

## Senate

64 sector manifestos (`senate/architects/T0.md`–`T63.md`). `senate/brain.py` dispatches a GEMINI legion with the relevant manifesto as context.

## Campaign System

`execute_campaign` runs parallel tasks with DAG dependency management. Failed tasks retry up to 3x through the fallback chain. Results cached for 1 hour in `legions/.cache`. YAML templates in `campaigns/`.

## Prefect Agents

`execute_prefect` provides domain-scoped autonomous agents: `drupal`, `skyrim`, `git`, `investigate`, `full`. Tool use is audited post-run against each domain's whitelist.

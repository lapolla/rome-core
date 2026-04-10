# ROME Core — Imperial Directives (v5.0.0)

> **I am not here to do work. I am here to decompose it and get out of the way.**

## Project

Model-agnostic Python orchestration framework. Persistent WebSocket-native daemon on port 8741 dispatches AI workers (Legions) in parallel. Claude Code integrates via native WS tools (RomeDispatch, TaskCreate, etc.) — no bridge needed.

## Architecture

- **`dictator/daemon.py`** — Pure WS daemon (`websockets.serve()`). HTTP via `process_request` hook: `/health`, `/dashboard/`. No ASGI/Starlette/Uvicorn.
- **`dictator/core.py`** — Central registry: config, `run_cmd`, `run_cmd_stream`, EventBus, TaskRegistry, DictatorResponse, `dictator_tool` decorator. All subprocesses use `start_new_session=True`.
- **`dictator/config.json`** — Externalized path constants (17 keys: root_dir, git_root, rome_root, ws_token, daemon_port, etc.).
- **`dictator/ws_server.py`** — WS connection manager, WorkerRegistry (persistent workers), WSAdapter (wraps raw websockets to Starlette-like API), 20 WS commands, heartbeat, zombie reaping, auto-lean mode.
- **`dictator/ws_client.py`** — Thread-safe WS client. Two modes: fire-and-forget sender (persistent background connection) + sync/async command client (short-lived connections). All `websockets.connect()` use `open_timeout=30`.
- **`dictator/rome_log.py`** — JSON-line logger with 50MB auto-rotation (`logs/rome.jsonl`).
- **`dictator/events.py`** — `RomeEvent` dataclass + `EventBus` pub/sub (bounded asyncio queues per subscriber) + `TaskRegistry` in-memory task state store (status, capability, progress, usage, report path, summary, token). 8 event emitters (includes `emit_facts_broadcast`).
- **`legions/legion_wrapper.py`** — V4 persistent worker engine. Two modes: `--mode once` (legacy subprocess) and `--mode worker` (persistent WS connection with `agent_hello` handshake). LegionaryUI with WS progress streaming, usage parsing (Claude + Gemini JSON), ROME signal extraction.
- **`legions/shell_executor.py`** — Dedicated bash executor for SAFE_SHELL. WS progress reporting, timeout/SIGKILL, manifest.json output.
- **`legions/centurion_wrapper.py`** — Campaign orchestrator: inline ANSI dashboard + retry loop (max 3 per task through fallback chain).
- **`legions/dashboard.py`** — Inline ANSI TUI. Cursor-control row rewrites.
- **`arsenal/core_arsenal.json`** — 6 capabilities: GEMINI, CLAUDE, CODEX, MISTRAL, SAFE_SHELL, CENTURION.
- **`aaak/`** — Adaptive Agent Attention Kernel. Purely programmatic (no LLM) context compression middleware. 3 hooks: `pre_dispatch` (recall facts + distill prompt), `post_result` (compress output → fact, store, broadcast), `guard_prompt` (subprocess safety net). Fact store: thread-safe JSONL with TTL=2h, Jaccard recall, auto-compaction every 50 saves. Only SUCCESS facts stored — failures never enter recall context.
- **`senate/brain.py`** — Soul spawner: loads sector manifesto + dispatches GEMINI legion.
- **`senate/architects/`** — 64 sector manifestos (T0.md–T63.md).
- **`client/orchestrator.py`** — Headless CLI: Haiku/Flash → subtask JSON → WS dispatch → JSONL stdout.
- **`campaigns/`** — YAML-defined task pipelines with `loader.py`.
- **`rome_native.py`** — WS CLI client for direct daemon commands + `PeerServer` stub (V5 mesh, port 8742). PeerServer dispatch not yet implemented — returns `ok: False` until wired to legion_wrapper.
- **`tests/`** — pytest suite: tools, signals, usage parsing, WS protocol, EventBus, v4 WS, AAAK pipeline, V5 mesh events.

## WS Command Protocol (20 commands)

The daemon accepts JSON frames of shape `{"type": "command", "command": "<name>", "request_id": "<id>", "payload": {}}` and responds with `{"type": "response", "request_id": "<id>", "ok": true/false, "payload": {}}`.

| Command | Purpose |
|---------|---------|
| `dispatch` | Dispatch a task (routes to persistent worker, NATIVE_SHELL, or subprocess) |
| `status` | Get task status, capabilities, workers. Supports `summary` flag for session stats |
| `get_state` | Full daemon state dump (tasks, waste, workers, capabilities) |
| `await` | Block until specified task_ids complete (EventBus-driven, no polling) |
| `cancel` | Cancel a running task or clean zombie registry entry |
| `ping` | Heartbeat check |
| `read_report` | Read report file content (truncated to 4KB) |
| `read_file` | Read any file with line range support + overview mode (start_line=0) |
| `write_file` | Write content to any path |
| `list_dir` | List directory with depth/limit |
| `native_shell` | Execute shell command in daemon process (NATIVE_SHELL DSA, sub-ms overhead) |
| `event` | Relay task events to daemon EventBus |
| `submit_result` | Worker submits task result (auto-summarized if >2KB) |
| `reset` | Clear all tasks from registry |
| `clear` | Clear only finished tasks |
| `recent_events` | Tasks changed since timestamp (for hook-based event injection) |
| `interrupt` | Cancel task or steer persistent worker mid-execution |
| `workers` | List connected persistent workers |
| `report_usage` | Dictator self-reports token usage |
| `dashboard_stats` | Aggregated stats for web dashboard |

## ROME Protocol Rules (v5.0.0)

1. **Atomic Changes**: Surgical commits, one concern per commit.
2. **Sub-division**: Tasks exceeding 45s should be split into smaller units.
3. **Manifesto Compliance**: Legion tasks governed by manifestos in `legions/TASK_*/`.
4. **Naming**: Adhere to Imperial metaphors (Dictator, Legion, Senate, Centurion).
5. **Observability**: Use `rome_tail` to monitor progress, `rome_costs` for budget tracking.
6. **Architect First**: When given a goal, decompose it into parallel subtasks and fire `execute_campaign` immediately. Never relay a goal directly to one GEMINI task — that is forwarding, not orchestration. Ask: what are all the independent workstreams? Assign the right capability to each. Only use `rome_dispatch` for single atomic tasks.
7. **Capability Routing**: SAFE_SHELL for bash/git/build ops (free). NATIVE_SHELL for sub-ms daemon-native execution. GEMINI for analysis/design/code when it needs file access. Never use GEMINI as a glorified cat/grep — SAFE_SHELL gathers execution output, GEMINI reasons about code it reads directly.
8. **Await, Don't Poll**: Fire tasks with `rome_dispatch(fire_and_forget=True)`, then collect results with `rome_await(task_ids, include_reports=True)`. One call in, all results back — no sleep loops, no rome_tail polling. The daemon uses EventBus internally (zero CPU spin).

## V5 Distributed Mesh (in progress)

- **Status**: Phase 1 complete. Phases 2-3 partial.
- **Phase 1** ✅ — `facts_broadcast` event wired: `emit_facts_broadcast` in `events.py`, `post_result(broadcast_fn=...)` in AAAK, `asyncio.create_task(emit_facts_broadcast(...))` in `ws_server._execute_legion_native`.
- **Phase 2** 🚧 — `PeerServer` stub in `rome_native.py` (port 8742). Auth check implemented. Dispatch handler returns `ok: False` — not yet connected to `legion_wrapper`.
- **Phase 3** ⬜ — Direct agent-to-agent dispatch (`peer_url` field in WorkerRegistry exists, routing logic present in `handle_dispatch`, but peer must implement dispatch to be usable).
- **Next**: Wire `PeerServer.handle_connection` dispatch to actually spawn a legion_wrapper subprocess.

## AAAK — Adaptive Agent Attention Kernel

- **Location**: `aaak/` module, wired in `dictator/ws_server.py` and `legions/legion_wrapper.py`.
- **Config**: `aaak_enabled` (bool), `aaak_distill_threshold` (tokens, default 800), `aaak_fact_ttl_seconds` (default 7200), `aaak_max_recall` (default 7) — all in `dictator/config.json`.
- **`get_aaak(prefix)`**: Returns cached AAAK instance per prefix (one per campaign/task chain). Store file: `aaak/{prefix}.jsonl`.
- **Dispatch flow**: `pre_dispatch` → recalls facts from store → distills prompt if >800 tokens → returns compressed prompt. SAFE_SHELL and NATIVE_SHELL bypass AAAK entirely.
- **Post-result flow**: `post_result` → compress manifest → if status != SUCCESS, return `{}` (failures not stored) → save fact → call `broadcast_fn` if provided.
- **Guard**: `guard_prompt` in `legion_wrapper` — only fires in subprocess mode (`ROME_WORKER_MODE != worker`), no store access.
- **Distill**: Only fires when `token_estimate(prompt) > threshold`. Does NOT force distillation on short natural-language prompts.

## Persistent Workers (v4)

- **Handshake**: Client sends `agent_hello` with capabilities/version/platform → daemon responds `worker_ack`.
- **WorkerRegistry**: Tracks connected workers by `id(ws)`. Finds idle workers by capability, marks busy/idle per task.
- **Dispatch routing priority**: NATIVE_SHELL → persistent worker → subprocess fallback.
- **Worker events**: Workers send `{"type": "event", "event": {...}}` for progress/complete/error. Daemon relays to EventBus.
- **Orphan cleanup**: On worker disconnect, all busy tasks marked failed.
- **Live workers**: GEMINI and SAFE_SHELL are resident in memory.

## Legion & Campaign Features

- **Failover Chain**: GEMINI → CODEX → MISTRAL on rate limits / failures. SAFE_SHELL retries once.
- **Result Caching**: 1-hour TTL in `legions/.cache`. `rome_dispatch(no_cache=True)` bypasses.
- **Prompt Patches**: Capability-specific rules injected from `dictator/legion_patches.json`.
- **Token Discipline**: MAX_OUTPUT_CHARS=2000 truncation in `_execute_legion_impl`; full output in report file.
- **Progress Trimming**: `manifest.json` progress field is a compact dict `{count, final, log_path}` — full log in `progress.log` in task dir.
- **Campaign Error Isolation**: `execute_campaign` uses `return_exceptions=True`.
- **Campaign Concurrency Cap**: `execute_campaign` uses `asyncio.Semaphore(20)` — max 20 parallel dispatches per campaign.
- **Usage Aggregation**: Claude/Gemini JSON usage extracted by `legion_wrapper`, written to manifest. Gemini pricing table covers models from 1.5 through 3.1.
- **Fire-and-Forget**: `rome_dispatch(fire_and_forget=True)` → delegates to daemon via WS, returns `DISPATCHED:{task_id}` immediately. Auto-triggers for capabilities with timeout > 120s.
- **Output Path Fallback**: `rome_dispatch(output_path=...)` copies report to output_path after completion.
- **SAFE_SHELL Routing**: Routes via persistent legion_wrapper worker (spawns `shell_executor.py` per task). `handle_event` complete path reads report file and passes inline — output is no longer silently dropped.
- **Auto GC**: `auto_gc()` available on startup — runs `gc_legions` (keep newest 50 + <24h).
- **Centurion Hierarchy**: CENTURION capability dispatches CODEX/MISTRAL as sub-legionnaires.
- **Auto-Retry**: Empty report on success triggers one retry with `no_cache=True`.
- **Auto-Routing**: `capability="AUTO"` runs `_recommend_capability_impl` heuristics to select best worker.

## Result Compression & Auto-Lean

- **Result compression**: Worker results >2000 chars auto-summarized via Gemini Flash (`gemini-3.1-pro-preview`) on submit. Summary stored in task registry; `rome_await` returns summary by default (`full=True` for raw).
- **Auto-lean mode**: Daemon tracks cumulative output chars per session. At 100K chars → lean (1 event max, prefer summaries). At 300K chars → ultra-lean (no events, status-only responses).
- **`prompt_file`**: `rome_dispatch` and daemon `dispatch` command accept `prompt_file` param — prompt stays on disk, never enters context.
- **Campaign templates**: `campaign_run(template="edit-function", overrides={...})` loads YAML from `campaigns/`, substitutes params, dispatches.

## Context Diet

- **Principle**: Full data stays on disk. Only summaries and targeted excerpts enter the context window.
- **`prompt_file`**: Long prompts stay on disk, passed by path to daemon dispatch.
- **Auto-lean**: Daemon tracks session output volume and progressively reduces response verbosity.

## WS Protocol Notes

- All daemon communication is pure WebSocket. No HTTP API routes (`/api/*` returns 404).
- HTTP served only via `process_request` hook: `/health` (JSON status) and `/dashboard/*` (static files).
- `ws_client.py` uses `open_timeout=30` on all `websockets.connect()` calls.
- **Push-based await**: `handle_await` returns immediately with completed + pending lists. Client holds WS open and receives `complete` events via `relay_events`. No polling.
- **Zombie reaping**: System status loop (30s) auto-fails tasks stuck at 0% for >180s.
- **Auth**: Token via `Authorization: Bearer <token>` header or `?token=` query param. Dashboard connections (same-origin) bypass auth.
- **Heartbeat**: Every 15s per connection.
- **Daemon managed by systemd**: `rome-daemon.service` (user unit). Restart via `systemctl --user restart rome-daemon`. Has `ExecStartPre=fuser -k 8741/tcp` guard.

## Gemini Dictator Mode

Gemini CLI can run as the primary interactive agent ("Dictator") with Claude as "Architect":
- **`consult_architect`** tool — dispatches CLAUDE capability via WS, awaits with polling fallback
- **`GEMINI.md`** at project root — dictator-mode instructions for Gemini
- **`legion_patches.json`** — CLAUDE capability includes architect role guidance
- Claude receives questions via `rome_dispatch(CLAUDE)`, responds with design decisions

## Campaign Templates

- **`campaigns/`** — YAML-defined task pipelines. `loader.py` reads any YAML, dispatches via WS, awaits results.
- **Format**: `name`, `tasks[]` with `id`, `capability`, `prompt`, `input_files`, `depends_on`.
- **Usage**: `python3 campaigns/loader.py campaigns/example.yaml` from CLI.
- **Dependency graph**: `execute_campaign` supports `depends_on` — waits for upstream tasks, fails dependents on upstream failure.

## Prefect Agents

- **Autonomous Agents**: `execute_prefect` dispatches domain-scoped agents: `drupal`, `skyrim`, `git`, `investigate`, `full`.
- **Tool Audit**: Post-run log analysis enforces tool whitelist with regex-based detection; violations mark task FAILED.
- **Pre-flight Declaration**: Agents must declare tool intent before use.

## Coding Conventions

- **Type hints**: Use `Callable` from `collections.abc`. Never use lowercase `callable` with `|` union syntax — it's a builtin function, causes `TypeError` at import time.
- **Subprocess safety**: Always `start_new_session=True`. Never let child processes propagate signals to the daemon.
- **WS dispatch**: Long-running tasks must use `asyncio.to_thread()` or `asyncio.create_task()` — never block the event loop inline.

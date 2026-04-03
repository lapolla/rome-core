# ROME Core — Imperial Directives (v4.0.0)

> **I am not here to do work. I am here to decompose it and get out of the way.**

## Project

Model-agnostic Python orchestration framework. Persistent WebSocket-native daemon on port 8741 dispatches AI workers (Legions) in parallel. MCP-over-stdio retained for Claude Code integration; all runtime communication is pure WebSocket.

## Architecture

- **`dictator/daemon.py`** — Pure WS daemon (`websockets.serve()`). HTTP via `process_request` hook: `/health`, `/dashboard/`. No ASGI/Starlette/Uvicorn.
- **`dictator/cli.py`** — MCP stdio entry point. Loads tools via orchestrator, serves as `asshole` MCP server for Claude Code.
- **`dictator/core.py`** — Central registry: config, `run_cmd`, `run_cmd_stream`, EventBus, TaskRegistry, DictatorResponse, `dictator_tool` decorator. All subprocesses use `start_new_session=True`.
- **`dictator/config.json`** — Externalized path constants (17 keys: root_dir, git_root, rome_root, ws_token, daemon_port, etc.).
- **`dictator/ws_server.py`** — WS connection manager, WorkerRegistry (persistent workers), WSAdapter (wraps raw websockets to Starlette-like API), 20 WS commands, heartbeat, zombie reaping, auto-lean mode.
- **`dictator/ws_client.py`** — Thread-safe WS client. Two modes: fire-and-forget sender (persistent background connection) + sync/async command client (short-lived connections). All `websockets.connect()` use `open_timeout=30`.
- **`dictator/rome_log.py`** — JSON-line logger with 50MB auto-rotation (`logs/rome.jsonl`).
- **`dictator/events.py`** — `RomeEvent` dataclass + `EventBus` pub/sub (bounded asyncio queues per subscriber) + `TaskRegistry` in-memory task state store (status, capability, progress, usage, report path, summary, token). 7 event emitters.
- **`dictator/emit_helpers.py`** — Bridges stdio MCP tools to daemon EventBus via WS. Detects IS_DAEMON for in-process vs remote path.
- **`dictator/orchestrator.py`** — Dynamic tool discovery: scans `tools_*.py`, registers with FastMCP, applies profile-based module filtering and tool excludes.
- **`dictator/profiles.py`** — 6 profiles with per-profile tool excludes.
- **`legions/legion_wrapper.py`** — V4 persistent worker engine. Two modes: `--mode once` (legacy subprocess) and `--mode worker` (persistent WS connection with `agent_hello` handshake). LegionaryUI with WS progress streaming, usage parsing (Claude + Gemini JSON), ROME signal extraction.
- **`legions/shell_executor.py`** — Dedicated bash executor for SAFE_SHELL. WS progress reporting, timeout/SIGKILL, manifest.json output.
- **`legions/centurion_wrapper.py`** — Campaign orchestrator: inline ANSI dashboard + retry loop (max 3 per task through fallback chain).
- **`legions/dashboard.py`** — Inline ANSI TUI. Cursor-control row rewrites.
- **`arsenal/core_arsenal.json`** — 7 capabilities: GEMINI, CLAUDE, CODEX, OPENCODE, MCP_TOOL_CLIENT, SAFE_SHELL, NATIVE_SHELL.
- **`senate/brain.py`** — Soul spawner: loads sector manifesto + dispatches GEMINI legion.
- **`senate/architects/`** — 64 sector manifestos (T0.md–T63.md).
- **`client/orchestrator.py`** — Headless CLI: Haiku/Flash → subtask JSON → WS dispatch → JSONL stdout.
- **`campaigns/`** — YAML-defined task pipelines with `loader.py`.
- **`rome_native.py`** — Minimal WS CLI client for direct daemon commands.
- **`tests/`** — pytest suite: tools, signals, usage parsing, WS protocol, EventBus, v4 WS.

## MCP Server (56 tools, 12 modules)

- **`tools_fs`**: fs_read, fs_write, read_anywhere, write_anywhere, list_directory
- **`tools_git`**: git_status, git_diff, git_commit, git_push *(all accept `repo_path` param)*
- **`tools_drupal`**: rsync_ftk_modules, drush_run, drupal_fj_run
- **`tools_legion`**: execute_legion, execute_campaign, rome_dispatch, recommend_capability, consult_architect, launch_centurion, clear_cache, campaign_run
- **`tools_desktop`**: desktop_screenshot, desktop_click, desktop_type_text, desktop_press_key, desktop_find_window, desktop_focus_window, desktop_get_mouse_location, desktop_notify
- **`tools_gc`**: gc_legions, reset_tasks, legion_stats
- **`tools_stats`**: rome_tail, rome_costs, rome_health, rome_find, senate_query, senate_brain
- **`tools_prefect`**: execute_prefect
- **`tools_docs`**: update_project_docs
- **`tools_ws`**: ws_send, rome_submit_result, rome_events

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
| `event` | Relay task events from MCP stdio tools to daemon EventBus |
| `submit_result` | Worker submits task result (auto-summarized if >2KB) |
| `reset` | Clear all tasks from registry |
| `clear` | Clear only finished tasks |
| `recent_events` | Tasks changed since timestamp (for hook-based event injection) |
| `interrupt` | Cancel task or steer persistent worker mid-execution |
| `workers` | List connected persistent workers |
| `report_usage` | Dictator self-reports token usage |
| `dashboard_stats` | Aggregated stats for web dashboard |

## ROME Protocol Rules (v4.0.0)

1. **Atomic Changes**: Surgical commits, one concern per commit.
2. **Sub-division**: Tasks exceeding 45s should be split into smaller units.
3. **Manifesto Compliance**: Legion tasks governed by manifestos in `legions/TASK_*/`.
4. **Naming**: Adhere to Imperial metaphors (Dictator, Legion, Senate, Centurion).
5. **Observability**: Use `rome_tail` to monitor progress, `rome_costs` for budget tracking.
6. **Architect First**: When given a goal, decompose it into parallel subtasks and fire `execute_campaign` immediately. Never relay a goal directly to one GEMINI task — that is forwarding, not orchestration. Ask: what are all the independent workstreams? Assign the right capability to each. Only use `rome_dispatch` for single atomic tasks.
7. **Capability Routing**: SAFE_SHELL for bash/git/build ops (free). NATIVE_SHELL for sub-ms daemon-native execution. GEMINI for analysis/design/code when it needs file access. Never use GEMINI as a glorified cat/grep — SAFE_SHELL gathers execution output, GEMINI reasons about code it reads directly.
8. **Await, Don't Poll**: Fire tasks with `rome_dispatch(fire_and_forget=True)`, then collect results with `rome_await(task_ids, include_reports=True)`. One call in, all results back — no sleep loops, no rome_tail polling. The daemon uses EventBus internally (zero CPU spin).

## Persistent Workers (v4)

- **Handshake**: Client sends `agent_hello` with capabilities/version/platform → daemon responds `worker_ack`.
- **WorkerRegistry**: Tracks connected workers by `id(ws)`. Finds idle workers by capability, marks busy/idle per task.
- **Dispatch routing priority**: NATIVE_SHELL → persistent worker → subprocess fallback.
- **Worker events**: Workers send `{"type": "event", "event": {...}}` for progress/complete/error. Daemon relays to EventBus.
- **Orphan cleanup**: On worker disconnect, all busy tasks marked failed.
- **Live workers**: GEMINI and SAFE_SHELL are resident in memory.

## Legion & Campaign Features

- **Failover Chain**: GEMINI → CODEX → OPENCODE on rate limits / failures. SAFE_SHELL retries once.
- **Result Caching**: 1-hour TTL in `legions/.cache`. `rome_dispatch(no_cache=True)` bypasses.
- **Prompt Patches**: Capability-specific rules injected from `dictator/legion_patches.json`.
- **Token Discipline**: MAX_OUTPUT_CHARS=2000 truncation in `_execute_legion_impl`; full output in report file.
- **Progress Trimming**: Progress arrays trimmed to first 3 + last 3 entries in MCP responses.
- **Campaign Error Isolation**: `execute_campaign` uses `return_exceptions=True`.
- **Usage Aggregation**: Claude/Gemini JSON usage extracted by `legion_wrapper`, written to manifest. Gemini pricing table covers models from 1.5 through 3.1.
- **Fire-and-Forget**: `rome_dispatch(fire_and_forget=True)` → delegates to daemon via WS, returns `DISPATCHED:{task_id}` immediately. Auto-triggers for capabilities with timeout > 120s.
- **Output Path Fallback**: `rome_dispatch(output_path=...)` copies report to output_path after completion.
- **SAFE_SHELL Routing**: Bypasses legion_wrapper entirely; spawns `shell_executor.py` as detached subprocess. Completion lifecycle owned by shell_executor (sends WS `complete` event).
- **Auto GC**: `auto_gc()` available on startup — runs `gc_legions` (keep newest 50 + <24h).
- **Centurion Hierarchy**: CENTURION capability dispatches CODEX/OPENCODE as sub-legionnaires.
- **Auto-Retry**: Empty report on success triggers one retry with `no_cache=True`.
- **Auto-Routing**: `capability="AUTO"` runs `_recommend_capability_impl` heuristics to select best worker.

## Result Compression & Auto-Lean

- **Result compression**: Worker results >2000 chars auto-summarized via Gemini Flash (`gemini-3.1-pro-preview`) on submit. Summary stored in task registry; `rome_await` returns summary by default (`full=True` for raw).
- **Auto-lean mode**: Daemon tracks cumulative output chars per session. At 100K chars → lean (1 event max, prefer summaries). At 300K chars → ultra-lean (no events, status-only responses).
- **`prompt_file`**: `rome_dispatch` and daemon `dispatch` command accept `prompt_file` param — prompt stays on disk, never enters context.
- **Campaign templates**: `campaign_run(template="edit-function", overrides={...})` loads YAML from `campaigns/`, substitutes params, dispatches. Keeps MCP tool calls terse.

## Context Diet (MCP Tool Output Compaction)

- **`read_anywhere`**: Returns `[ROME: lines X-Y of N]` header + requested range only. Supports `start_line`/`end_line` params (1-indexed, inclusive).
- **`DictatorResponse`**: Standardized response wrapper for all tools. `dictator_tool` decorator handles exceptions uniformly.
- **Claude Code hook**: PreToolUse hook (`~/.claude/hooks/block_builtin_io.sh`) blocks built-in Read/Bash/Grep/Glob — forces all I/O through MCP compact tools.
- **`rome_events`**: Drains buffered daemon events as compact one-liners (`HH:MM:SS [STATUS] task_id`). Background WS listener starts on first call.
- **Principle**: Full data stays on disk. Only summaries and targeted excerpts enter the context window.

## WS Protocol Notes

- All daemon communication is pure WebSocket. No HTTP API routes (`/api/*` returns 404).
- HTTP served only via `process_request` hook: `/health` (JSON status) and `/dashboard/*` (static files).
- `ws_client.py` uses `open_timeout=30` on all `websockets.connect()` calls.
- **Push-based await**: `handle_await` returns immediately with completed + pending lists. Client holds WS open and receives `complete` events via `relay_events`. No polling.
- **Zombie reaping**: System status loop (30s) auto-fails tasks stuck at 0% for >180s.
- **Auth**: Token via `Authorization: Bearer <token>` header or `?token=` query param. Dashboard connections (same-origin) bypass auth.
- **Heartbeat**: Every 15s per connection.
- **Daemon managed by systemd**: `rome-dictator.service` (system unit). Restart via `sudo systemctl restart rome-dictator`. MCP server entry point: `dictator/cli.py` (stdio) — needs `/mcp` reconnect after code changes.

## Profiles (ROME_PROFILE)

Set `ROME_PROFILE` env var to load only needed tools per session:
- **`core`** (12 tools) — fs, ws, legion basics. Minimal context footprint.
- **`drupal`** (21 tools) — core + git, drupal tools.
- **`desktop`** — core + desktop tools.
- **`orchestrate`** (26 tools) — core + gc, stats tools.
- **`gemini`** (21 tools) — core + git, gc. Gemini-as-dictator mode with `consult_architect`.
- **`full`** (55 tools) — all modules. Default when unset.

Profiles defined in `dictator/profiles.py`. Per-profile tool excludes strip rarely-needed tools from loaded modules.

## Gemini Dictator Mode

Gemini CLI can run as the primary interactive agent ("Dictator") with Claude as "Architect":
- **`ROME_PROFILE=gemini`** in `~/.gemini/settings.json` MCP env
- **`consult_architect`** tool — dispatches CLAUDE capability via WS, awaits with polling fallback
- **`GEMINI.md`** at project root — dictator-mode instructions for Gemini
- **`legion_patches.json`** — CLAUDE capability includes architect role guidance
- Claude receives questions via `rome_dispatch(CLAUDE)`, responds with design decisions

## Campaign Templates

- **`campaigns/`** — YAML-defined task pipelines. `loader.py` reads any YAML, dispatches via WS, awaits results.
- **Format**: `name`, `tasks[]` with `id`, `capability`, `prompt`, `input_files`, `depends_on`.
- **Usage**: `campaign_run(template="name", overrides={...})` from MCP, or `python3 campaigns/loader.py campaigns/example.yaml` from CLI.
- **Dependency graph**: `execute_campaign` supports `depends_on` — waits for upstream tasks, fails dependents on upstream failure.

## Prefect Agents

- **Autonomous Agents**: `execute_prefect` dispatches domain-scoped agents: `drupal`, `skyrim`, `git`, `investigate`, `full`.
- **Tool Audit**: Post-run log analysis enforces tool whitelist with regex-based detection; violations mark task FAILED.
- **Pre-flight Declaration**: Agents must declare tool intent before use.

## Coding Conventions

- **Type hints**: Use `Callable` from `collections.abc`. Never use lowercase `callable` with `|` union syntax — it's a builtin function, causes `TypeError` at import time.
- **Subprocess safety**: Always `start_new_session=True`. Never let child processes propagate signals to the MCP server.
- **WS dispatch**: Long-running tasks must use `asyncio.to_thread()` or `asyncio.create_task()` — never block the event loop inline.
- **Stderr**: Do not write to `sys.stderr.buffer` in `run_cmd_stream` — blocks the MCP stdio pipe.
- **DictatorResponse**: All new tools should use `@dictator_tool` decorator and return `DictatorResponse` for consistent error handling.

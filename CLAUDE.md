# ROME Core — Imperial Directives (v2.5)

> **I am not here to do work. I am here to decompose it and get out of the way.**

## Project

Model-agnostic Python MCP orchestration framework. Persistent ASGI daemon exposes MCP-over-SSE for Claude Code, WebSocket for external clients/dashboard, and dispatches AI workers (Legions) in parallel.

## Architecture

- **`dictator/daemon.py`** — ASGI app (Starlette + Uvicorn); mounts FastMCP SSE at `/mcp`, WS at `/ws`, dashboard at `/dashboard/`. Port 8741.
- **`dictator/dictator.py`** — Legacy stdio entry point (kept for fallback).
- **`dictator/core.py`** — Central registry: config, `run_cmd`, `run_cmd_stream`, EventBus, mcp instance. All subprocesses use `start_new_session=True` (process group isolation).
- **`dictator/config.json`** — Externalized path constants (17 keys: root_dir, git_root, rome_root, ws_token, daemon_port, etc.).
- **`dictator/ws_server.py`** — WS connection manager + command dispatcher (dispatch, status, get_state, cancel, ping, read_report, await, reset, clear, event, submit_result).
- **`dictator/ws_client.py`** — Internal WS sender. Two modes: fire-and-forget sender + sync command client. All `websockets.connect()` calls use `open_timeout=30`.
- **`dictator/rome_log.py`** — JSON-line logger with 50MB auto-rotation (`logs/rome.jsonl`).
- **`dictator/events.py`** — `RomeEvent` dataclass + `EventBus` pub/sub (bounded asyncio queues per subscriber) + `TaskRegistry` in-memory task state store (status, capability, progress, usage, report path).
- **`legions/legion_wrapper.py`** — Subprocess harness for LLM workers; parses ROME signals, usage (Claude/Gemini JSON), manifests, progress bars.
- **`legions/shell_executor.py`** — Dedicated bash executor for SAFE_SHELL. No JSON, no parse_usage, no task.md.
- **`legions/centurion_wrapper.py`** — Campaign orchestrator: inline ANSI dashboard + retry loop (max 3 per task through fallback chain).
- **`legions/dashboard.py`** — Inline ANSI TUI. Cursor-control row rewrites. No `/dev/tty`.
- **`arsenal/core_arsenal.json`** — Capability registry (CLIs, args, timeouts).
- **`senate/brain.py`** — Soul spawner: loads sector manifesto + dispatches GEMINI legion.
- **`senate/architects/`** — 64 sector manifestos (T0.md–T63.md).
- **`client/orchestrator.py`** — Headless CLI: Haiku/Flash → subtask JSON → WS dispatch → JSONL stdout.
- **`tests/`** — pytest suite: tools, signals, usage parsing, WS protocol, EventBus.

## MCP Server (50 tools, 12 modules)

- **`tools_fs`**: shell_exec, fs_read, fs_write, read_anywhere, write_anywhere, list_directory
- **`tools_git`**: git_status, git_diff, git_commit, git_push *(all accept `repo_path` param)*
- **`tools_drupal`**: rsync_ftk_modules, drush_run, drupal_fj_run
- **`tools_legion`**: execute_legion, execute_campaign, rome_dispatch, recommend_capability, launch_centurion, clear_cache
- **`tools_skyrim`**: skyrim_console, skyrim_read_state, skyrim_face_actor, skyrim_follow_actor, skyrim_pivot, skyrim_compound_move, compile_papyrus
- **`tools_desktop`**: desktop_screenshot, desktop_click, desktop_type_text, desktop_press_key, desktop_find_window, desktop_focus_window, desktop_get_mouse_location, desktop_notify
- **`tools_media`**: http_fetch, fetch_mo2_mod
- **`tools_gc`**: gc_legions, reset_tasks, legion_stats
- **`tools_stats`**: rome_tail (optionally filters by task_id), rome_costs, rome_health, rome_find, senate_query, senate_brain
- **`tools_prefect`**: execute_prefect
- **`tools_docs`**: update_project_docs
- **`tools_ws`**: ws_send, rome_await, rome_submit_result

## ROME Protocol Rules (v2.5)

1. **Atomic Changes**: Surgical commits, one concern per commit.
2. **Sub-division**: Tasks exceeding 45s should be split into smaller units.
3. **Manifesto Compliance**: Legion tasks governed by manifestos in `legions/TASK_*/`.
4. **Naming**: Adhere to Imperial metaphors (Dictator, Legion, Senate, Centurion).
5. **Observability**: Use `rome_tail` to monitor progress, `rome_costs` for budget tracking.
6. **Architect First**: When given a goal, decompose it into parallel subtasks and fire `execute_campaign` immediately. Never relay a goal directly to one GEMINI task — that is forwarding, not orchestration. Ask: what are all the independent workstreams? Assign the right capability to each. Only use `rome_dispatch` for single atomic tasks.
7. **Capability Routing**: SAFE_SHELL for bash/git/build ops (free). GEMINI for analysis/design/code when it needs MCP file access. Never use GEMINI as a glorified cat/grep — SAFE_SHELL gathers execution output, GEMINI reasons about code it reads directly.
8. **Await, Don't Poll**: Fire tasks with `rome_dispatch(fire_and_forget=True)`, then collect results with `rome_await(task_ids, include_reports=True)`. One call in, all results back — no sleep loops, no rome_tail polling. The daemon uses EventBus internally (zero CPU spin).

## Legion & Campaign Features

- **Failover Chain**: GEMINI → CODEX → OPENCODE on rate limits / failures. SAFE_SHELL retries once.
- **Result Caching**: 1-hour TTL in `legions/.cache`. `rome_dispatch(no_cache=True)` bypasses.
- **Prompt Patches**: Capability-specific rules injected from `dictator/legion_patches.json`.
- **Token Discipline**: MAX_OUTPUT_CHARS=2000 truncation in `_execute_legion_impl`; full output in report file.
- **Progress Trimming**: Progress arrays trimmed to first 3 + last 3 entries in MCP responses.
- **Campaign Error Isolation**: `execute_campaign` uses `return_exceptions=True`.
- **Usage Aggregation**: Claude/Gemini JSON usage extracted by `legion_wrapper`, written to manifest.
- **Fire-and-Forget**: `rome_dispatch(fire_and_forget=True)` → returns `DISPATCHED:{task_id}` immediately; task runs in background asyncio.Task.
- **Output Path Fallback**: `rome_dispatch(output_path=...)` copies report to output_path after completion (required for GEMINI CLI which cannot write directly).
- **SAFE_SHELL Routing**: `capability == "SAFE_SHELL"` bypasses legion_wrapper entirely; calls shell_executor.py via `asyncio.to_thread()` (prevents blocking the event loop).
- **Auto GC**: `auto_gc()` fires on every MCP server startup — runs `gc_legions` + `reset_tasks` to clear zombie tasks.
- **Centurion Hierarchy**: CENTURION capability dispatches CODEX/OPENCODE as sub-legionnaires within its session.

## WS Protocol Notes

- All daemon communication is pure WebSocket. No HTTP API routes (`/api/*` returns 404).
- `ws_client.py` uses `open_timeout=30` on all `websockets.connect()` calls (prevents handshake timeout under load).
- `reset` command clears all tasks in the registry including REGISTERED zombies.
- RUNNING dashboard counter excludes REGISTERED state (only counts truly running tasks).
- Heartbeat every 10–15s.

## Prefect Agents

- **Autonomous Agents**: `execute_prefect` dispatches domain-scoped agents: `drupal`, `skyrim`, `git`, `investigate`, `full`.
- **Tool Audit**: Post-run log analysis enforces tool whitelist with regex-based detection; violations mark task FAILED.
- **Pre-flight Declaration**: Agents must declare tool intent before use.

## Coding Conventions

- **Type hints**: Use `Callable` from `collections.abc`. Never use lowercase `callable` with `|` union syntax — it's a builtin function, causes `TypeError` at import time.
- **Subprocess safety**: Always `start_new_session=True`. Never let child processes propagate signals to the MCP server.
- **WS dispatch**: Long-running tasks must use `asyncio.to_thread()` or `asyncio.create_task()` — never block the event loop inline.
- **Stderr**: Do not write to `sys.stderr.buffer` in `run_cmd_stream` — blocks the MCP stdio pipe.

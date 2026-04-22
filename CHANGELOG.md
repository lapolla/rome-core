## v7.1.0 — 2026-04-23
- **JS Sovereignty Migration**: Initiated the decommissioning of legacy Python/CLI wrappers in favor of pure JS/TS native agents.
- **Full-Duplex Native Agent**: Implemented `src/native_agent.ts` with direct WebSocket integration and real-time multi-turn tool interaction.
- **Gemma V7 Native**: Switched GEMMA to the new native agent, enabling high-performance local mesh participation via Ollama.
- **Kernel Fixes**: 
    - Fixed `native_shell` task-id reporting and execution robustness.
    - Injected sovereign audio context (PipeWire/Pulse) into the daemon environment.
- **Dashboard Optimization**: Expanded Mesh Topology canvas to full header width and removed legacy stat cards.
- **Process Management**: Hardened `ROME-start.sh` cleanup logic to prevent worker leaks.

## v7.1.0 — 2026-04-13

### Security & Configuration
- **File-based Config**: Documented `dictator/config.json` for daemon settings and `.rome_SOVEREIGN_TOKEN` for secure WebSocket authentication.
- **Secrets Cleanup**: Removed hardcoded ports and environment variable secrets (e.g., `ROME_V4_SECURE_TOKEN`) from setup documentation.

### Cleanup & Maintenance
- **Legacy References**: Removed v6 architectural and quick-start references from `README.md`.
- **Migration Files**: Removed completed v7 migration plans (`V7_MIGRATION_PLAN.md`, `TS_MIGRATION_PLAN.md`) and draft specifications (`ROME_PROTOCOL_V7_DRAFT.md`).

---

## v4.0.0 — 2026-04-03

### Breaking Changes
- **Pure WS daemon**: Replaced ASGI/Starlette/Uvicorn with raw `websockets.serve()`. No HTTP API routes — only `/health` and `/dashboard/` served via `process_request` hook.
- **Daemon version**: `_VERSION` bumped from `"3.0"` to `"4.0"`.
- **Manifest version**: `rome_v` in manifests now `"4.0"`.

### Features
- **Persistent workers**: `legion_wrapper.py --mode worker` connects via WS, sends `agent_hello`, receives dispatches. WorkerRegistry tracks idle/busy state. Dispatch routing: NATIVE_SHELL → persistent worker → subprocess fallback.
- **NATIVE_SHELL DSA**: `native_shell` WS command executes shell in daemon process via `core.run_cmd()`. Sub-millisecond overhead.
- **20 WS commands**: dispatch, status, get_state, await, cancel, native_shell, submit_result, interrupt, read_file, write_file, list_dir, read_report, event, reset, clear, ping, workers, recent_events, report_usage, dashboard_stats.
- **Interrupt/steering**: `interrupt` command cancels tasks or injects prompts into persistent workers mid-execution.
- **Auto-lean mode**: Tracks cumulative output chars. 100K → lean, 300K → ultra-lean.
- **Result compression**: Reports >2KB auto-summarized via Gemini Flash on `submit_result`.
- **Zombie reaping**: 30s status loop auto-fails tasks stuck at 0% for >180s. Daemon startup sweeps orphans.
- **Capability detection fix**: LLM capabilities (CLAUDE, CODEX) now check binary on PATH as fallback when no persistent worker connected. Previously showed red on dashboard unless a worker was registered.
- **Gemini worker systemd service**: `rome-gemini-worker.service` user unit auto-starts persistent Gemini worker.
- **DictatorResponse**: Standardized response wrapper + `@dictator_tool` decorator for consistent error handling.
- **Auto-routing**: `capability="AUTO"` runs heuristics to select best worker.
- **Campaign dependency graph**: `execute_campaign` supports `depends_on` — fails dependents on upstream failure.

### Docs
- CLAUDE.md: Updated to v4.0.0 with full WS command table, persistent workers section, 20 commands
- README.md: Updated architecture, tool list, WS protocol, persistent workers
- SETUP.md: Removed uvicorn dependency, added worker setup instructions
- ROME_PROTOCOL_V4_SPEC.md: Full v4 specification
- ROME_PROTOCOL_V3_SPEC.md: Marked as SUPERSEDED

---

## Update: 2026-03-09

### Fixes
- **rome_dispatch output_path fallback**: Copies report file to output_path when agent CLI cannot write directly (GEMINI). Previously returned ERR even on successful tasks.
- **rome_dispatch fire_and_forget**: New `fire_and_forget=True` param starts task in background asyncio.Task, returns `DISPATCHED:{task_id}` immediately. Prevents MCP connection drops caused by long-running legion tasks blocking the stdio pipe.

### Docs
- DASHBOARD_TODO.md: Feature roadmap for ROME Dashboard (9 items, prioritized HIGH/MEDIUM/LOW)
- TODO.md: Marked WebSocket transport as complete
- CLAUDE.md: Documented fire_and_forget and output_path fallback


## Update: 2026-02-28 19:08:31

### Features Updated
- **Token Discipline Guard** (complete): MAX_OUTPUT_CHARS=2000 truncation in _execute_legion_impl, writes full output to report file, returns path reference
- **Progress Trimming** (complete): Progress arrays trimmed to first 3 + last 3 entries, 95%+ reduction in MCP response bloat
- **Cache Fixes** (complete): rome_dispatch now passes no_cache param, new clear_cache MCP tool
- **Token Accounting** (complete): Estimated outbound tokens logged at all 3 MCP return points (execute_legion, execute_campaign, rome_dispatch)
- **MEMORY.md Routing Table** (complete): Mandatory slave routing decision table added at top of MEMORY.md

### Verification
- [x] Progress trimming verified: 365 lines -> 7 lines in MCP response
- [x] clear_cache tool: wiped 28 stale entries
- [x] no_cache on rome_dispatch: fresh execution confirmed
- [x] Token accounting: token_guard entries in rome.jsonl
- [x] Syntax check passed on tools_legion.py

## Update: 2026-02-28 22:37:05

### Features Updated
- **ROME Silent Protocol** (complete): Added ROME_SILENT env var support to suppress progress bars in the prompt.
- **Real-time UI Alignment** (complete): Redirected progress bars to stderr and optimized streaming for carriage returns.
- **Chunk-based Command Streaming** (complete): Replaced line-buffering with granular reads to support in-place UI updates.
- **High-Fidelity Visuals** (complete): Restored solid Unicode blocks (█) and ANSI colors to the Legionnaire UI.

### Verification
- [x] Verified live progress rendering in shell_exec results
- [x] Confirmed ROME_SILENT effectively disables visual overrides
- [x] Validated chunk-based streaming with high-concurrency campaigns

## Update: 2026-03-09 20:21:07

### Features Updated
- **Pure WebSocket control plane** (completed): Eliminated all HTTP API routes (/api/event, /api/reset, /api/clear, /api/status). All daemon communication now goes through WS. New ws_client.py provides persistent fire-and-forget sender + sync command client for MCP tools.
- **Process group isolation** (completed): Added start_new_session=True to all subprocess spawns in core.py (run_cmd, run_cmd_stream) and legion_wrapper.py. Gemini/Node.js no longer kills the Python MCP server via signal propagation.
- **Stderr pipe deadlock fix** (completed): Removed sys.stderr.buffer.write() from run_cmd_stream. Progress lines no longer block the MCP server's stdio pipe during long Gemini runs.
- **reset_tasks MCP tool** (completed): New tool that clears all tasks (including REGISTERED zombies) from the daemon registry via WS reset command. Hooked into auto_gc() so it fires on every MCP server startup.
- **Dashboard RUNNING counter fix** (completed): Fixed REGISTERED tasks being counted as RUNNING in dashboard stats. RUNNING now only counts tasks in actual running state.
- **Dashboard pure WS** (completed): Replaced HTTP fetch polling of /api/status with WS status summary command. DAEMON chip shows live status. Uptime now sourced from WS response.
- **Headless orchestrator upgraded** (completed): Upgraded from claude-3-haiku-20240307 to claude-sonnet-4-6 for better routing quality.
- **TaskRegistry.clear_all()** (completed): Added clear_all() method to TaskRegistry to complement clear_finished(). Removes all tasks regardless of status.
- **WS protocol expanded** (completed): Added reset, clear, event, and status(summary) commands to ws_server.py _handle_command dispatcher.

### Verification
- [x] Daemon starts clean with no HTTP routes — /api/* returns 404
- [x] Dashboard DAEMON chip shows OK via WS, no fetch() calls
- [x] MCP reconnect triggers auto_gc which resets zombie tasks via WS
- [x] Gemini runs no longer kill MCP server (start_new_session=True)
- [x] reset_tasks MCP tool clears all tasks including REGISTERED
- [x] RUNNING counter in dashboard excludes REGISTERED tasks
- [x] Headless orchestrator uses claude-sonnet-4-6
